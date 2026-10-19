# Mandarin standard operating procedure

SOP-001 · Version 1.0.0 · Effective planning baseline: 2026-10-18.

Purpose: take a verified reference feature through implementation, offline packaging, qualification and support without losing traceability or user files. The native 0.1.0 preview implements this workflow; its [evidence and remaining gates](.aiwg/reports/implementation-0.1.0.md) are separate from full-parity certification.

The package must include every conversion runtime, codec, filter, model, font and data file. `packaging/runtime-packages.json` defines required roots; `scripts/build_package.py` records their exact dependency closure and file hashes. `make package` must pass manifest verification and actual offline installation/conversion/tool checks in clean Ubuntu. Missing engines or failures reject the build. End users never run the build bootstrap or install converter dependencies themselves.

## Roles, inputs and evidence

Assign a product owner, desktop engineer, systems/adapter engineer, QA owner and release owner. One person may hold several roles, but a second reviewer should inspect source-loss, confinement, reference-scope and release decisions. Repository changes remain reviewable before any publication.

Inputs are the [requirements](.aiwg/requirements/srs.md), [inventory](.aiwg/requirements/parity-inventory.json), [architecture](.aiwg/architecture/sad.md), [test plan](.aiwg/testing/test-plan.md), [risks](.aiwg/risks/risk-register.md), licensed/generated fixtures and supported clean Ubuntu VM images. Record real owners when work begins.

For each experiment, work package or release, create an evidence record with: ID, source revision, reference app build, OS/kernel/GNOME/session, CPU/GPU/RAM, dependency/model manifest hash, fixture hashes, exact command/actions, expected and actual outcomes, elapsed time, logs/screenshots/video where useful, pass/fail, limitations, reviewer and follow-up issue. Store experiment evidence under `.aiwg/testing/evidence/<experiment-id>/` and release evidence under `.aiwg/deployment/releases/<version>/` when they exist. Never include personal user files or raw sensitive paths in shared diagnostics.

## Procedure A — Establish or refresh the reference

1. Read the current vendor product/tool/store/release pages and record retrieval date, version and conflicting claims in [sources.json](.aiwg/research/sources.json). Compare against the retained baseline rather than replacing it silently.
2. Obtain legitimate access to the current Mac application and use generated/licensed files. Record build/settings/shortcuts. Observe every conversion pair, tool, action, editor control, batch restriction, submenu behavior, output location/naming, progress and cancellation.
3. Label each reference observation `public-demo-only`, `store-listed-not-in-demo-catalog`, `hands-on-confirmed`, `not-observed`, or `contradicted`. Keep this separate from Mandarin's implementation and certification status.
4. Preserve stable CONV/TOOL/ACT identifiers. A new feature gets a new ID. Do not count identity conversions, extension aliases or unavailable encoders as additional parity paths.
5. For disputed behavior, record the fixture and result and assign a product decision. A website simulation cannot settle native behavior.
6. Review the baseline changes, requirements impact, build dependencies and test changes together. Existing implementation can continue on unaffected features while a reference question is open.

Exit: reviewed reference ledger and updated inventory; remaining unknowns have named owners and milestones. Native parity certification cannot close without this ledger.

## Procedure B — Prove the desktop and package design

1. Provision fresh 24.04 and 26.04 Ubuntu Desktop amd64 VMs. Record OS image checksums and installed session versions. Use full GNOME sessions; an Xvfb-only test cannot qualify Wayland integration. Add 24.04 Xorg and XWayland source-app lanes separately.
2. Run W0: start a real external file drag, invoke the wheel, release only the invocation key, descend at least three levels, backtrack and finally release onto a leaf. Verify pre-drop file context, correct transfer completion and exactly one queued operation.
3. Repeat with native GTK/Qt, XWayland, a browser/sandboxed source and portal file transfer. Include mixed/folder selections, missing files, URI escaping, source cancellation, edge/corner/multi-monitor scale and extension/broker failure. Record failed source combinations rather than generalizing from one successful drag.
4. Test modifier conflicts with ordinary file-manager copy/move behavior, accessibility tools and global shortcuts. Keep key bindings provisional until this evidence exists.
5. Run S0: package an image/media/office probe and worker using the proposed confinement. Show unrelated-file, network, session-bus and out-of-staging access are denied on stock Ubuntu policy. Test descendants and cancellation. Do not disable global AppArmor settings.
6. Run the OFFLINE profile: disconnect network, remove developer converter tools, and install the complete local payload. Verify bundled executables/models/fonts and all local features with no dependency/first-run downloads; measure payload/install/staging space. Qualify Share separately on a controlled LAN without WAN access using the same package; all conversion/probe/editor/validator workers stay network denied.
7. Run early P0 trials for native Pages output, Pages input variants, RTFD/textClipping and editable PDF reconstruction. Open results in independent consumers and score content, structure and editability.

Exit: W0/S0 reports pass or require an explicit architectural revision; P0 has real feasibility evidence and a decision owner. A failed blocking experiment must not be reclassified as completed just because a fallback window works.

## Procedure C — Implement one capability

1. Select a work package and inventory IDs. Write input/cardinality predicates, typed options/defaults, metadata/loss policy, resource limits, output semantics and independent validator before enabling the menu item.
2. Add representative and hostile fixtures with provenance/checksums. Describe what passing means beyond “the process returned zero.” Use real engine integration tests for parsing and output behavior.
3. Implement adapter execution with bundled absolute paths, typed argv, scoped grants/profiles and bounded logs. Confine probes, preview/editor imports and independent validators too; trusted frontends/coordinators do not decode untrusted rich content. Prove whole-job descendant termination and aggregate quotas independently of process groups, including setsid/double-fork and inherited writable output handles.
4. Implement bounded untrusted-manifest checks, confined content validation and atomic no-replace publication after all producer descendants exit. Test read-only sources, collisions, disk exhaustion, hostile outputs, symlinks and crash/cancel around flush/publish/journal steps. Move additionally needs a reviewed recoverable source-ownership/removal transaction: check-then-unlink is insufficient; retain changed/replaced/uncertain source objects and report incomplete Move. Never alter originals during conversion.
5. Connect the operation to the capability graph and all front ends. The same ID, options and eligibility logic must serve radial, list, picker and file-manager entry paths.
6. For a parameter tool, implement preview/reset/undo where applicable, explicit Apply/Cancel, keyboard focus, loading and error recovery. Cancel stale preview jobs when inputs/settings change.
7. Verify real external drag → contextual submenu → actual result → file-manager reveal in a packaged build. Add editor/manual accessibility checks where automation cannot judge the result.
8. Review the change and evidence. Update `implementation_status` only after actual implementation; record certification per package/platform separately. Do not edit the vendor observation to make a failing implementation appear equivalent.

Exit: accepted inventory rows have working code, validators, fixtures, packaged smoke evidence and no unresolved source-loss/confinement defect.

## Procedure D — Verify each increment

Build and verify the current Python/GTK/C implementation on Ubuntu 24.04:

```bash
sh scripts/bootstrap-build.sh
python3 -m compileall -q mandarin scripts tests
python3 -m unittest discover -s tests -v
make gui
python3 scripts/validate_plan.py
```

The native GUI checks include screenshots, real held-file drag traversal and GTK3 indicator/GTK4 application integration. The inventory validator checks documentation consistency only. Global GNOME Wayland/source-app qualification remains a separate lane.

With Docker running and the official Ubuntu 24.04 image available, produce and verify the full offline installer, then collect its exact redistribution sources:

```bash
docker pull ubuntu:24.04
make package
python3 scripts/collect_sources.py
python3 scripts/verify_sources.py
python3 scripts/record_evidence.py
```

`make package` rejects an incomplete runtime or a failure in the actual offline-installed conversion/tool corpus. `collect_sources.py` checks all exact source-package descriptors and source-file hashes and creates numbered release archives. `verify_sources.py` independently checks every file's presence, hash and size inside those archives. Never publish the bundled binary before every source archive is available with it. `record_evidence.py` binds the checked installer hash to inventory implementation status; it does not grant native parity certification. The [test plan](.aiwg/testing/test-plan.md) retains the full reference, desktop and release requirements.

For the Snap lane, run `python3 scripts/build_snap.py`, install the resulting local Snap with `sudo snap install --dangerous dist/mandarin_0.1.0_amd64.snap`, then run `python3 scripts/verify_snap.py` and `python3 scripts/snap_desktop_smoke.py` in the real desktop session with no existing Mandarin instance. The desktop check opens and quits the application through the real taskbar host. Store registration requires the account owner to accept Canonical's publisher agreement. Submit only to edge until the additional Snap and full-parity gates pass; see [submission record](packaging/STORE-LISTING.md).

For every increment, run relevant reducer/adapter/output-safety checks, then its affected desktop and package lanes. Before a release candidate, run the complete supported matrix once on the exact package bytes; repeat affected lanes only if changes or failures invalidate the result. Archive commands, exit status and content validators. If a test is unrun or blocked, record that explicitly.

## Procedure E — Build the self-contained release candidate

1. Select a reviewed source revision and release capability profile. Pin toolchain, dependencies, compiler flags, codecs, filters, fonts and local models; verify hashes before use. Builds may fetch pinned source dependencies in the controlled build environment; installed application features may not require downloads.
2. Build on the oldest supported Ubuntu ABI baseline or produce distinct target packages if necessary. Package private runtime libraries while using host graphics drivers and documented base OS facilities; avoid process-global library-path pollution of host apps.
3. Assemble a full-payload `.deb`: application, workers, converter/runtime closure, models/fonts/profiles, GNOME companion variants, desktop/D-Bus/AppStream metadata, confinement policy, notices and migration/uninstall logic. Preserve active user job safety across upgrades.
4. Package application files in the system prefix. Register the companion without silently enabling privileged desktop behavior in a user's session. Onboarding explains what it can access and offers the OS-supported enable flow. A session restart may be required by GNOME; record this in installation guidance.
5. Keep conversion network-disabled. Bundle the explicit sharing component separately within the payload and activate networking only for chosen sharing work. No telemetry or background update mechanism may upload user files.
6. Generate dependency/model inventory and SBOM, notices and required source material/offers for the exact build configuration. Run dependency advisories/applicability review and archive results. No vendor artwork/code is included.
7. Produce checksums and detached signatures with the release process. For offline installs, verify the exact payload/manifest before installation against a pinned fingerprint authenticated through a separately trusted owned channel or preinstalled keyring; downloading a key next to a package does not bootstrap trust, and a stock local `.deb` installer does not enforce its sibling signature. An APT channel instead uses authenticated repository metadata with a narrowly scoped Signed-By keyring. Record verification commands/fingerprint, signing custody/access, protected backup, key expiry/rotation, compromise/revocation communication and explicit known-good rollback rules. Keep credentials out of source/logs. Record package/install/peak-working sizes.
8. Test an independent rebuild and compare outputs. Where embedded timestamps or native tooling prevent byte equality, document the exact difference and compare unpacked payload hashes; do not label a merely repeatable build bit-reproducible.

Exit: immutable release candidate bytes and complete provenance/evidence manifest. Stable release requires signing, established public namespace/license/distribution and the qualification gates. The 0.1.0 GitHub prerelease is explicitly unsigned, carries checksums and complete sources, and does not claim those stable-release gates.

## Procedure F — Qualify installation, update and removal

1. From clean OS snapshots, disable network and use the stock package installer on the local full `.deb`. Ordinary installation may authenticate as administrator. All required user-space engines/assets must already be in the payload; no converter installation prompt is acceptable.
2. Launch as a normal user. Verify health detects actual versions, declared format capabilities, worker confinement, free space, desktop companion and optional sharing readiness. Enable the companion through the documented user flow and test both enabled and disabled modes.
3. Run every declared local route/tool/action in OFFLINE on the exact release package; verify Share's missing-network handling only. Then run LAN-SHARE with a consenting recipient and no WAN, while converter/validator isolation stays unchanged. Prove absent host FFmpeg/LibreOffice/model caches do not change capabilities; observe denial of external-resource requests.
4. Run all [test-plan](.aiwg/testing/test-plan.md) release lanes, including Orca/keyboard, scaling/multi-monitor, cancellation, crash recovery, filesystem safety and the reference-comparison corpus.
5. Upgrade from the last supported release with queued/running work: jobs finish or stop safely, journal/settings migration is backed up and recoverable, and mismatched companions disable themselves with a useful message. Never unload/replace running engines unsafely.
6. Test rollback using retained previous package bytes and a pre-migration settings/journal backup. A downgrade must not open an unsupported new schema or automatically rerun interrupted jobs. Record the supported migration/rollback range.
7. Uninstall and reinstall. System application/policy/companion files are removed through the package manager; originals and outputs remain. User history/cache removal is an explicit separately chosen operation. Verify no stale autostart, D-Bus activation or shell overlay remains.

Exit: per-OS package certification and signed parity report, or a failed release gate with a concrete issue. Package qualification is not complete based on a developer workstation installation.

## Procedure G — Ship and support

1. Assemble the reviewable release: signed package, checksums/public-key verification instructions, source revision, SBOM/notices, actual capability and compatibility manifests, test/parity evidence, known limitations, install/update/rollback/uninstall instructions and support diagnostics.
2. Confirm full-parity gates or use a preview/beta label with its exact tested subset. Release notes explicitly identify Ubuntu action substitutions and any accepted reference differences. Never imply native AirDrop compatibility or unsupported Pages/PDF fidelity.
3. Publish only to the authorized distribution channel under the user's established publishing authorization. If that authorization is absent, present the finished artifacts for the final publishing decision; do not stop before the package and evidence are reviewable.
4. Smoke-test download authenticity and install from the published bytes on a fresh snapshot. Retain prior signed packages and manifests for rollback.
5. During initial support, triage source preservation, confinement, conversion fidelity, desktop crashes and install failures first. Collect user-approved redacted diagnostics and synthetic reproductions; never ask users to upload private files by default.
6. For a bad release, stop further promotion, communicate the concrete affected capability, disable it through a signed replacement if required, and follow the tested rollback procedure. Preserve already converted outputs and user originals. Do not invent a remote kill switch.

## Operator troubleshooting

| Symptom | Inspect | Corrective action |
| --- | --- | --- |
| Wheel does not appear during external drag | Session, companion enabled state, Shell/IPC versions and W0 source-app compatibility | Use alternate entry temporarily; install matching tested companion or fix integration; do not claim global qualification |
| Missing target format | Capability reason: input probe, decoder/encoder/filter/model/profile | Repair packaged dependency closure or report unsupported input variant; do not offer an untested host tool automatically |
| Permission or output error | Source grant lifetime, destination free space/permissions, identity and confinement logs | Choose accessible destination or fix policy narrowly; preserve source; never run converter as root |
| Job hangs/cancel fails | Job state, whole-job containment, bounded stderr and engine deadline | Terminate/reap every job descendant; preserve published outputs; record interrupted state and offer explicit retry |
| Output looks correct but loses content | Streams/pages/sheets/attachments/metadata and semantic validators | Mark capability failed, retain fixtures, repair adapter; do not accept extension-only success |
| Offline first run wants a download | Manifest versus actual runtime/font/model closure | Rebuild full payload; no network workaround for an offline-certified feature |

Review this SOP at each milestone and after a release incident. Record revisions with evidence; documentation baseline status does not certify the application.
