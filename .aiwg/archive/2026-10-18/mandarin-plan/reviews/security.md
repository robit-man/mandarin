# Mandarin planning review — security and file safety

Review date: 2026-10-18. Role: independent SECURITY/SAFETY reviewer. Scope: README, PLAN, SOP, architecture, requirements, test plan and risk register. This is a design review of an unimplemented application; no vulnerability, sandbox, package or conversion test has been executed.

**Outcome: CONDITIONAL APPROVAL for the planning baseline.** The plan has sound fail-closed gates and makes its unproven status clear. Incorporate SEC-001 and SEC-002 into the architecture before worker/output/Move implementation. Assign SEC-003 through SEC-005 to the stated milestone gates. None of these findings certifies an implementation or authorizes a release.

## Findings

### SEC-001 — High: independent output validation must remain inside an untrusted parser boundary

**Location:** `.aiwg/architecture/sad.md`, sections 4, 9, 13 and 14; in particular the trusted output coordinator at lines 77–78, format/content validation at lines 192–194 and the coordinator sequence at lines 302–304. Also SOP Procedure C and TC-SAFETY.

**Problem:** The design correctly confines input probes and conversion/preview engines, but calls the output coordinator trusted and gives it “independent” content validation without specifying an isolated validator process. A compromised converter can produce a hostile PDF/image/archive or forged output manifest. Loading that result into a decoder inside the broker/coordinator would move the same parser attack back into a process with user-file access. Independence of the decoder does not provide confinement. The diagram currently permits this unsafe interpretation.

**Required fix:** State that every parser/decoder used for validation, thumbnail generation, previews and editor imports runs with scoped read-only artifact grants, network denial and the same resource/IPC restrictions as other workers. The trusted coordinator should check bounded, schema-validated results and filesystem metadata, never decode rich content. It must distrust worker-supplied paths and manifests: resolve only beneath the job staging descriptor, reject unexpected files, absolute/parent paths, devices/FIFOs/sockets, escaping links and unauthorized hard links, and copy only accepted artifact types. Do not publish until all producer descendants have exited and artifacts cannot still be modified by those producers. Clarify the editor boundary so hostile media is not decoded in the privileged GTK frontend merely for display.

**Acceptance/owner:** Systems engineer, S0/WP-007. Add a malicious-output fixture and forged artifact manifest that attempt to read outside staging through a validator, plus a validator crash/hang fixture. Show the broker survives and unrelated-file/network access stays denied. Add validator workers as explicit TC-SAFETY/TC-PRIVACY subjects.

### SEC-002 — High: verified cross-filesystem copy alone does not make source deletion race-safe

**Location:** `.aiwg/architecture/sad.md`, section 8 Move row and sections 9/13; `.aiwg/risks/risk-register.md`, R-009; test-plan E2E-006/010; SOP Procedures C/F.

**Problem:** “Copy, verify, then remove source,” open descriptors and identity rechecks do not define a safe source-removal transaction. A file can be replaced between the final check and a path-based unlink, or edited in place after the copy. An open input descriptor preserves access to an inode; it does not make the original pathname refer to that inode or freeze its content. The resulting Move implementation could delete the replacement or a newer version. This is a design gap, not a demonstrated defect. Linux describes `unlinkat` as deleting a name relative to a directory FD, rather than a conditional delete of an expected inode. [Linux unlink contract](https://man7.org/linux/man-pages/man2/unlink.2.html)

**Required fix:** Require a separately reviewed source-ownership/removal transaction for Move, including directories, same-filesystem moves, cross-filesystem moves, concurrent replacement and in-place modification. Explicitly prohibit check-then-unlink as sufficient proof. Evaluate a recoverable, no-clobber source-volume claim/quarantine protocol or another demonstrably safe strategy; retain all unexpected/replaced/changed objects and report where they are preserved. State the supported concurrency assumptions. If safe removal cannot be established for a source/filesystem, preserve the source and report an incomplete Move with verified destination, rather than deleting it or reporting full success. This is distinct from silently changing Move into Copy. Cross-filesystem directory moves also require complete member verification and an explicit special-file/link policy.

**Acceptance/owner:** Systems engineer + QA, WP-010/M2 and R-009. Inject replacement precisely after the last identity check, concurrent writes during/after copy, source-directory entry additions, crashes during any claim/removal step, and collisions during recovery. Assert that neither an unverified source version nor an unrelated replacement is deleted, and partial results are explicit.

### SEC-003 — Medium: process groups need an enforceable descendant lifecycle and aggregate quotas

**Location:** architecture sections 9/10 and cancellation sequence; REQ-JOB-003/004/006; SOP B.5/C.3; S0 and TC-SAFETY.

**Problem:** The required outcome (“no surviving descendants”) is correct, but the proposed mechanism is process-group TERM/KILL with per-process limits. A child can create a new session/process group if allowed, so signaling the original group does not establish whole-job termination. Per-process memory/CPU/file-size limits also do not establish aggregate limits across many children/files. [Linux setsid semantics](https://man7.org/linux/man-pages/man2/setsid.2.html)

**Required fix:** Make S0 choose and prove whole-job lifecycle/aggregate accounting independently of process-group membership, using a stock-compatible PID-namespace/cgroup design or explicit syscall restrictions plus a verified supervisor strategy. Confirm any user cgroup delegation requirements on both clean Ubuntu targets; do not assume it exists. Specify aggregate memory, process/thread count, CPU, output bytes and workspace consumption. Keep process groups as a cooperative shutdown mechanism. Worker exit must not trigger validation/publication while escaped descendants retain writable artifacts. Cgroup v2 is a candidate with hierarchical resource controls and whole-tree kill, subject to actual delegation/policy proof. [Kernel cgroup v2 documentation](https://www.kernel.org/doc/html/latest/admin-guide/cgroup-v2.html)

**Acceptance/owner:** Systems engineer, S0. Include double-fork/setsid, changed process groups, inherited writable output descriptors, rapid forking, many-small-output files and multi-child memory exhaustion. Verify no descendants remain before cleanup/publication and the desktop stays usable.

### SEC-004 — Medium: offline package authenticity needs a concrete trust/bootstrap and key lifecycle contract

**Location:** SOP E.7, F.1, G.1/3/4/6; PLAN release definition; architecture sections 11/16; NFR-011/TC-PACKAGE.

**Problem:** Detached signatures, a public verification key and a signing-process placeholder are sensible deliverables, but a downloaded local `.deb` with a sibling signature is not automatically authenticated by the normal installer. Downloading an unverified key next to the package leaves initial trust unresolved. Rotation, compromise/revocation and acceptance of older signed versions are also unspecified. APT's repository authentication and individual package signatures are distinct mechanisms. [APT secure documentation](https://manpages.debian.org/trixie/apt/apt-secure.8.en.html)

**Required fix:** Before first public build, select the distribution verification path and document its trust anchor. For offline delivery, specify verification of the exact package/manifest before installation using a pinned, independently authenticated fingerprint or already trusted keyring; no claim that detached signatures are automatically enforced by the stock local installer. For an APT channel, use authenticated repository metadata and a narrowly scoped keyring/Signed-By relationship. Assign signing custody, approved signer access, protected backup, key expiry/rotation, compromise/revocation communication and offline verification behavior. Allow explicit recovery rollback to retained known-good versions without silently accepting stale packages as current releases.

**Acceptance/owner:** Release owner, M6 before publication. Package qualification must reject changed payloads/manifests and wrong/unknown signatures; exercise key transition/expired or revoked-key handling and a documented older-version rollback. Record the verification commands and trusted fingerprint in release evidence.

### SEC-005 — Medium: archive safety should explicitly cover hard links, metadata and runtime budgets

**Location:** architecture sections 7/9; test-plan archive contract and adversarial coverage; R-008; WP-009.

**Problem:** Path traversal, symlinks, devices and expansion are already covered well. However, “list first” is a preflight rather than an enforcement boundary: claimed sizes can be false, and extraction order/duplicate entries/hard links or dangerous restored metadata can alter the result. The current text does not explicitly state a hard-link, duplicate-member or privilege-metadata policy.

**Required fix:** Define a conservative default: reject hard links or materialize only verified in-root regular-file data; reject absolute/escaping link targets and later type-changing duplicates; do not restore ownership, setuid/setgid bits, file capabilities or security-sensitive extended attributes. Apply byte/count/depth/time/workspace quotas while writing and decoding, not only from the listed manifest. Define sparse-file accounting and password/error/cancellation cleanup. Extraction should occur only in a fresh confined tree and publication should verify the complete final tree under SEC-001's manifest rules.

**Acceptance/owner:** Systems engineer/QA, WP-009/M2. Add hard-link escapes, duplicate-path type changes, forward links, sparse/false-size bombs, xattr/mode restoration and stream-time budget violations. Assert no published unsafe node and no modification outside staging.

## Boundaries already handled adequately at planning level

- AppArmor/user-namespace compatibility is explicitly an S0 experiment; there is no unsupported promise that bundling a launcher or an AppImage alone solves confinement. Global policy weakening and unconfined fallback are prohibited.
- Conversion/probe/editor processing has a no-network contract, and office macros/external links, FFmpeg protocols, SVG/document resource resolution and local file grants appear in the adversarial plan. These remain test obligations.
- IPC uses typed operations rather than arbitrary commands, bounded descriptors, major-version negotiation and same-user compromise limitations. During implementation, bind drag tokens, grants and idempotency keys to their owning caller/session and test cross-session replay; this is a detail to settle at WP-006/007, not evidence that session D-Bus isolates a compromised account.
- Atomic no-replace output publication, destination directory descriptors, source preservation, clear partial results and crash journaling are appropriate contracts.
- The package explicitly defers signed release production, publishing authorization, engine/model license closure and unsupported-format claims. No app or feasibility proof is misrepresented as delivered.

## Disposition

Accept the researched plan conditionally after the two High clarifications are integrated and the three Medium items are assigned as explicit gate criteria. Full construction and release remain blocked on the existing W0/S0/P0 and qualification evidence. No additional user approval is needed to repair these planning details; no main document was edited by this reviewer.

## Final disposition after incorporation — 2026-10-18

**APPROVE the planning baseline.** This disposition supersedes the conditional outcome above. I reread the revised architecture sections 4/5/8/9/14, SOP Procedures C/E/F and the targeted package, archive, Move and adversarial test provisions. All five findings are resolved at the planning level:

| Finding | Verified planning resolution |
| --- | --- |
| SEC-001 | Confined independent validators, preview/editor-import decoders and typed display buffers are explicit; trusted frontend/coordinator rich-format decoding is prohibited. Output manifests and artifact types are bounded and distrusted, and producers must terminate before validation/publication. Hostile outputs, forged manifests and validator crashes/hangs have required tests. |
| SEC-002 | Move requires a separately reviewed recoverable source-ownership/removal transaction; check-then-unlink is explicitly insufficient. Changed/replaced/uncertain objects are preserved and incomplete Move is visible. Immediate source replacement, concurrent writes, directory additions and claim/removal crash recovery are decisive qualification cases. |
| SEC-003 | S0 must select and prove stock-compatible whole-job namespace/cgroup lifecycle and aggregate resource quotas, including delegation requirements. Process-group escape, setsid/double-fork, inherited writable output handles and multi-child exhaustion are explicit adversarial cases. |
| SEC-004 | SOP E.7 and package tests require independent trust bootstrap and exact-byte verification before local installation, distinguish detached signatures from installer enforcement and APT repository authentication, scope Signed-By keys, and cover custody, rotation, expiry/revocation and explicit older-version recovery. |
| SEC-005 | Extraction rejects hard links by default and unsafe duplicate/forward/link/special-node cases, strips privilege-sensitive metadata, and enforces live quotas including sparse-file accounting. Final-tree validation and corresponding adversarial fixtures are explicit. |

No remaining security concern blocks this planning package. Approval establishes acceptable requirements and gate criteria only: the worker sandbox/aggregate accounting, exact Move protocol and supported filesystem/concurrency assumptions, signing channel/key lifecycle and archive implementation remain unimplemented and must pass their assigned evidence gates before certification or shipping. No application, package-authenticity, confinement or file-safety test was executed by this reviewer. Only this review file was edited during verification.
