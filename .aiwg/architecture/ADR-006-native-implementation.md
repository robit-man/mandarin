# ADR-006 — Native preview and complete offline payload

Status: accepted for 0.1.0 construction, 18 October 2026. Amends the Rust implementation proposal. Full-parity release gates remain open.

The available toolchain supplies Python 3.12, PyGObject, GTK4/libadwaita and C. The native preview uses those components with a C confinement launcher and synchronous LibreOfficeKit adapter. Python is bundled; users do not provision a language environment. Shared schemas and one job engine serve radial, keyboard and CLI entry points.

The `.deb` stages the installed dependency closure of explicit package roots into `/opt/mandarin/runtime`: codecs, fonts, OCR models, icons, data, notices and a private dynamic loader. Commands use fixed paths and private libraries. LibreOffice's program directory precedes generic libraries for UNO bootstrap; PulseAudio/BLAS/LAPACK directories are explicit. Pandoc's compiled data root is relocated separately from its user-data override. A hashed manifest records the payload. There are no first-run downloads or host-converter fallbacks.

Ubuntu policy denies unprivileged namespace creation in this environment. Workers instead require Landlock ABI≥3 and seccomp. They receive the runtime, selected snapshot files, minimal system configuration and a private writable workspace. Internet sockets/connections, process-group escape, introspection, namespace creation and privileged syscalls are denied. LibreOfficeKit explicitly disables macros. Unavailable confinement causes failure without an unconfined retry.

A trusted C subreaper supervises the process group and bounds elapsed time, sampled aggregate RSS/process/thread counts, output bytes, CPU affinity and per-process resources. Parent death/cancellation kills descendants. These are sampled limits, not cgroup accounting; hostile same-user host processes are outside the threat model. Linux shared-kernel/desktop prerequisites remain.

The UI/broker do not decode rich input. Confined workers probe, execute, preview and validate. Previews cross the boundary as bounded raw pixels. The broker snapshots sources, checks output manifests/hashes, strips modes/xattrs and publishes using directory FDs and no-replace renames. Move retains recovery sources under concurrent writers. Conversion stays local; explicit Share uses a separate certificate-pinned LocalSend sender.

The build fails on missing roots, engines/assets, manifest mismatches, offline installation, corpus or packaged-tool failures. Headless conversion and native X11 drag proof do not qualify GNOME global Wayland behavior, Mac fidelity or all 275 reference pairs. Original desktop/reference/consumer acceptance lanes remain required.
