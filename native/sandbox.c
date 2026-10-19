#define _GNU_SOURCE
#include <dirent.h>
#include <errno.h>
#include <fcntl.h>
#include <linux/landlock.h>
#include <linux/sched.h>
#include <limits.h>
#include <seccomp.h>
#include <sched.h>
#include <signal.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/prctl.h>
#include <sys/resource.h>
#include <sys/stat.h>
#include <sys/syscall.h>
#include <sys/types.h>
#include <sys/wait.h>
#include <time.h>
#include <unistd.h>

static void fail(const char *message) { perror(message); exit(125); }
static unsigned long long handled;
static void terminate_group(int signal_number) {
    (void)signal_number;
    kill(-getpgrp(),SIGKILL);
    _Exit(125);
}

static void grant(int ruleset, const char *path, int writable) {
    int fd = open(path, O_PATH | O_CLOEXEC);
    if (fd < 0) fail(path);
    struct stat st;
    if (fstat(fd, &st)) fail("stat grant");
    uint64_t access = LANDLOCK_ACCESS_FS_READ_FILE | LANDLOCK_ACCESS_FS_EXECUTE;
    if (S_ISDIR(st.st_mode)) access |= LANDLOCK_ACCESS_FS_READ_DIR;
    if (writable) {
        access |= LANDLOCK_ACCESS_FS_WRITE_FILE | LANDLOCK_ACCESS_FS_TRUNCATE;
        if (S_ISDIR(st.st_mode)) access |= LANDLOCK_ACCESS_FS_REMOVE_DIR |
            LANDLOCK_ACCESS_FS_REMOVE_FILE | LANDLOCK_ACCESS_FS_MAKE_DIR |
            LANDLOCK_ACCESS_FS_MAKE_REG | LANDLOCK_ACCESS_FS_MAKE_SOCK |
            LANDLOCK_ACCESS_FS_REFER;
    }
    struct landlock_path_beneath_attr rule = {.allowed_access=access & handled, .parent_fd=fd};
    if (syscall(SYS_landlock_add_rule, ruleset, LANDLOCK_RULE_PATH_BENEATH, &rule, 0)) fail("landlock rule");
    close(fd);
}

static void filter(void) {
    scmp_filter_ctx ctx = seccomp_init(SCMP_ACT_ALLOW);
    if (!ctx) fail("seccomp_init");
    const char *deny[] = {"setsid", "setpgid", "ptrace", "process_vm_readv", "process_vm_writev",
        "mount", "umount2", "pivot_root", "unshare", "setns", "bpf", "keyctl", "add_key",
        "request_key", "kexec_load", "open_by_handle_at", "name_to_handle_at", "connect",
        "kill", "tkill", "tgkill", "pidfd_send_signal", "pidfd_getfd", "pidfd_open", "reboot", "swapon", "swapoff", "sched_setaffinity",
        "io_uring_setup", "perf_event_open", "userfaultfd", NULL};
    for (int i=0; deny[i]; i++) {
        int number = seccomp_syscall_resolve_name(deny[i]);
        if (number != __NR_SCMP_ERROR && seccomp_rule_add(ctx, SCMP_ACT_ERRNO(EPERM), number, 0)) fail("seccomp rule");
    }
    if (seccomp_rule_add(ctx, SCMP_ACT_ERRNO(EPERM), SCMP_SYS(socket), 1,
            SCMP_A0(SCMP_CMP_NE, 1))) fail("socket rule");
    if (seccomp_rule_add(ctx, SCMP_ACT_ERRNO(ENOSYS), SCMP_SYS(clone3), 0)) fail("clone3 rule");
    const unsigned long namespace_flags[] = {CLONE_NEWUSER,CLONE_NEWNS,CLONE_NEWPID,CLONE_NEWNET,CLONE_NEWIPC,CLONE_NEWUTS,CLONE_NEWCGROUP};
    for (size_t i=0;i<sizeof(namespace_flags)/sizeof(namespace_flags[0]);i++)
        if (seccomp_rule_add(ctx,SCMP_ACT_ERRNO(EPERM),SCMP_SYS(clone),1,
                SCMP_A0(SCMP_CMP_MASKED_EQ,namespace_flags[i],namespace_flags[i]))) fail("clone namespace rule");
    if (seccomp_load(ctx)) fail("seccomp_load");
    seccomp_release(ctx);
}

static unsigned long long tree_bytes(const char *path, int depth) {
    if (depth > 32) return ULLONG_MAX;
    DIR *dir = opendir(path);
    if (!dir) return 0;
    unsigned long long total = 0;
    struct dirent *entry;
    while ((entry=readdir(dir))) {
        if (!strcmp(entry->d_name,".") || !strcmp(entry->d_name,"..")) continue;
        struct stat st;
        if (fstatat(dirfd(dir),entry->d_name,&st,AT_SYMLINK_NOFOLLOW)) continue;
        if (S_ISREG(st.st_mode)) total += (unsigned long long)st.st_size;
        else if (S_ISDIR(st.st_mode)) {
            char child[4096];
            if (snprintf(child,sizeof(child),"%s/%s",path,entry->d_name)>=(int)sizeof(child)) { total=ULLONG_MAX; break; }
            unsigned long long size=tree_bytes(child,depth+1);
            if (size==ULLONG_MAX || total>ULLONG_MAX-size) { total=ULLONG_MAX; break; }
            total+=size;
        }
    }
    closedir(dir);
    return total;
}

static int resources_exceeded(pid_t group, unsigned long long memory) {
    DIR *proc=opendir("/proc");
    if (!proc) return 1;
    struct dirent *entry;
    unsigned long long rss=0;
    int processes=0,threads=0;
    while ((entry=readdir(proc))) {
        if (entry->d_name[0]<'0' || entry->d_name[0]>'9') continue;
        char filename[128],line[4096];
        snprintf(filename,sizeof(filename),"/proc/%s/stat",entry->d_name);
        FILE *file=fopen(filename,"r");
        if (!file) continue;
        char *ok=fgets(line,sizeof(line),file); fclose(file);
        if (!ok) continue;
        char *p=strrchr(line,')');
        if (!p) continue;
        char state; long parent,pgid;
        if (sscanf(p+2,"%c %ld %ld",&state,&parent,&pgid)!=3 || pgid!=group) continue;
        processes++;
        snprintf(filename,sizeof(filename),"/proc/%s/status",entry->d_name);
        file=fopen(filename,"r");
        if (file) {
            while (fgets(line,sizeof(line),file)) {
                int count;
                if (sscanf(line,"Threads: %d",&count)==1) threads+=count;
            }
            fclose(file);
        }
        snprintf(filename,sizeof(filename),"/proc/%s/statm",entry->d_name);
        file=fopen(filename,"r");
        unsigned long pages=0,dummy=0;
        if (file) { if (fscanf(file,"%lu %lu",&dummy,&pages)==2) rss+=(unsigned long long)pages*(unsigned long)getpagesize(); fclose(file); }
    }
    closedir(proc);
    return rss>memory || processes>48 || threads>128;
}

int main(int argc,char **argv) {
    int abi=(int)syscall(SYS_landlock_create_ruleset,NULL,0,LANDLOCK_CREATE_RULESET_VERSION);
    if (argc==2 && !strcmp(argv[1],"--check")) {
        printf("{\"landlock_abi\":%d,\"seccomp\":true,\"available\":%s}\n",abi,abi>=3?"true":"false");
        return abi>=3?0:125;
    }
    if (abi<3) { fprintf(stderr,"Landlock ABI 3 or later is required; refusing unconfined execution.\n"); return 125; }
    handled=(1ULL<<15)-1;
    struct landlock_ruleset_attr attr={.handled_access_fs=handled};
    int ruleset=(int)syscall(SYS_landlock_create_ruleset,&attr,sizeof(attr),0);
    if (ruleset<0) fail("landlock_create_ruleset");
    const char *workspace=NULL;
    int command=0,timeout=900;
    unsigned long long memory=2048ULL*1024*1024;
    for (int i=1;i<argc;i++) {
        if (!strcmp(argv[i],"--")) { command=i+1; break; }
        if (i+1>=argc) fail("missing argument");
        if (!strcmp(argv[i],"--read")) grant(ruleset,argv[++i],0);
        else if (!strcmp(argv[i],"--readwrite")) grant(ruleset,argv[++i],1);
        else if (!strcmp(argv[i],"--write")) { workspace=argv[++i]; grant(ruleset,workspace,1); }
        else if (!strcmp(argv[i],"--timeout")) timeout=atoi(argv[++i]);
        else if (!strcmp(argv[i],"--memory-mb")) memory=strtoull(argv[++i],NULL,10)*1024*1024;
        else { fprintf(stderr,"Unknown sandbox option\n"); return 125; }
    }
    if (!command || command>=argc || !workspace || timeout<1 || timeout>86400) return 125;
    if (getpgrp()!=getpid() && setsid()<0) fail("setsid");
    pid_t parent=getppid();
    struct sigaction action={0}; action.sa_handler=terminate_group; sigemptyset(&action.sa_mask);
    if (sigaction(SIGTERM,&action,NULL) || sigaction(SIGINT,&action,NULL)) fail("supervisor signal handler");
    if (prctl(PR_SET_PDEATHSIG,SIGTERM,0,0,0)) fail("supervisor parent death");
    if (getppid()!=parent) terminate_group(SIGTERM);
    if (prctl(PR_SET_CHILD_SUBREAPER,1,0,0,0)) fail("subreaper");
    pid_t child=fork();
    if (child<0) fail("fork");
    if (!child) {
        if (prctl(PR_SET_PDEATHSIG,SIGKILL)) fail("parent death");
        struct rlimit lim={memory,memory}; setrlimit(RLIMIT_AS,&lim);
        cpu_set_t available,bounded;
        CPU_ZERO(&bounded);
        if (sched_getaffinity(0,sizeof(available),&available)) fail("get CPU affinity");
        int cores=0;
        for (int cpu=0;cpu<CPU_SETSIZE && cores<2;cpu++) if (CPU_ISSET(cpu,&available)) { CPU_SET(cpu,&bounded); cores++; }
        if (!cores || sched_setaffinity(0,sizeof(bounded),&bounded)) fail("set CPU affinity");
        lim=(struct rlimit){512,512}; setrlimit(RLIMIT_NOFILE,&lim);
        lim=(struct rlimit){0,0}; setrlimit(RLIMIT_CORE,&lim);
        lim=(struct rlimit){4ULL*1024*1024*1024,4ULL*1024*1024*1024}; setrlimit(RLIMIT_FSIZE,&lim);
        if (prctl(PR_SET_NO_NEW_PRIVS,1,0,0,0)) fail("no_new_privs");
        if (syscall(SYS_landlock_restrict_self,ruleset,0)) fail("landlock_restrict_self");
        close(ruleset); filter();
        if (chdir(workspace)) fail("workspace");
        umask(077); execv(argv[command],&argv[command]); fail("exec");
    }
    close(ruleset);
    time_t started=time(NULL);
    int status=0;
    while (waitpid(child,&status,WNOHANG)==0) {
        if (time(NULL)-started>timeout || resources_exceeded(getpid(),memory) ||
                tree_bytes(workspace,0)>4ULL*1024*1024*1024) {
            fprintf(stderr,"Job exceeded its aggregate time/memory/process/output budget.\n");
            kill(-getpid(),SIGKILL); return 124;
        }
        usleep(100000);
    }
    int orphan_status;
    for (int attempt=0;attempt<20;attempt++) {
        pid_t remaining;
        do { remaining=waitpid(-1,&orphan_status,WNOHANG); } while (remaining>0);
        if (remaining<0 && errno==ECHILD) return WIFEXITED(status)?WEXITSTATUS(status):128+WTERMSIG(status);
        usleep(50000);
    }
    fprintf(stderr,"Producer descendants remained after completion; output rejected.\n");
    kill(-getpid(),SIGKILL); return 125;
}
