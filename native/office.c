#define _GNU_SOURCE
#include <stdbool.h>
#include <stddef.h>
#include <stdio.h>
#include <stdlib.h>
#include <dlfcn.h>
#include <LibreOfficeKit/LibreOfficeKit.h>

int main(int argc,char **argv) {
    if (argc!=6) { fprintf(stderr,"office: program-directory input-URI output-URI format profile-URI\n"); return 2; }
    char library[4096];
    if (snprintf(library,sizeof(library),"%s/libmergedlo.so",argv[1])>=(int)sizeof(library)) return 2;
    void *handle=dlopen(library,RTLD_NOW|RTLD_GLOBAL);
    if (!handle) { fprintf(stderr,"%s\n",dlerror()); return 2; }
    LibreOfficeKit *(*initialize)(const char *,const char *)=dlsym(handle,"libreofficekit_hook_2");
    if (!initialize) { fprintf(stderr,"LibreOfficeKit is unavailable\n"); return 2; }
    LibreOfficeKit *office=initialize(argv[1],argv[5]);
    if (!office) { fprintf(stderr,"LibreOfficeKit could not initialize its private profile\n"); return 2; }
    LibreOfficeKitDocument *document=office->pClass->documentLoadWithOptions(office,argv[2],"EnableMacrosExecution=false,MacroSecurityLevel=3");
    int ok=0;
    if (document) {
        ok=document->pClass->saveAs(document,argv[3],argv[4],NULL);
        document->pClass->destroy(document);
    }
    if (!ok) {
        char *error=office->pClass->getError(office);
        fprintf(stderr,"%s\n",error?error:"The document could not be converted");
        if (error) office->pClass->freeError(error);
    }
    office->pClass->destroy(office);
    /* This is a disposable LibreOfficeKit process. Do not re-enter the dynamic
       library's process-global C++ destructors after its explicit destroy. */
    fflush(NULL);
    _Exit(ok?0:1);
}
