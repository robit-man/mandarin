# Mandarin requirements baseline

Version: 1.0.0 · Date: 2026-10-18 · Status: planning baseline; implementation unstarted.

## Product outcome and boundaries

An Ubuntu user can select local files, invoke a radial menu during a drag, navigate relevant categories and submenus without releasing, and drop on a leaf operation. Mandarin creates a validated result beside the original, or opens a focused tool editor when parameters are necessary. Files remain local during conversion and editing.

The default product name is Mandarin, inferred from this workspace. Target Ubuntu 24.04 LTS and 26.04 LTS, amd64, GNOME on Wayland. Test 24.04 Xorg separately where available; 26.04's Ubuntu GNOME session is Wayland-only. ARM64 and other desktops follow only after their own qualification. See primary platform references in the [architecture](../architecture/sad.md).

“Self contained” means the release payload includes the application, conversion executables/libraries, fonts, profiles, local models, notices, and desktop companion. After installation on a documented stock OS, conversion does not require apt, pip, an account, a model download, or internet access. The base OS, graphics drivers, desktop session, and explicitly enabled desktop integration remain host facilities. Normal package installation may require administrator authentication; runtime does not.

“Equivalent” means the approved behavioral contract, supported input/output semantics, tools, actions, and reliability pass their acceptance tests. Marketing counts alone cannot establish equivalence. Ubuntu sharing is a functional replacement for AirDrop, not an AirDrop protocol implementation. Native Pages output and PDF reconstruction remain unresolved requirements, not silently excluded features. Any changed equivalence boundary needs an explicit product decision recorded in the parity report.

## Use cases

| ID | User outcome | Entry and completion |
| --- | --- | --- |
| UC-001 | Convert one file without changing applications | External drag invocation → contextual target → verified sibling output |
| UC-002 | Navigate nested radial categories | Drag → category dwell → submenu → back or leaf drop |
| UC-003 | Process compatible or mixed selections | Selection → capability intersection → per-file or aggregate job → itemized result |
| UC-004 | Apply a tool with preview | Tool leaf → focused editor → explicit apply → new output |
| UC-005 | Use general file actions | Files/folders → action → clipboard, move, shelf, terminal, or explicit share |
| UC-006 | Operate without dragging | Open-with, file picker, paste, or file-manager action → keyboard-accessible menu |
| UC-007 | Control and recover work | Queue/progress → cancel/retry/reveal → deterministic result or clean failure |
| UC-008 | Install, configure, update, and remove | Offline package → capability/desktop health check → functioning app → safe uninstall |

## Radial interaction

The following numerical interaction settings are initial design targets to validate in M0/M1, not claims about Tangerine.

| ID | Required behavior | Acceptance |
| --- | --- | --- |
| REQ-UI-001 | Invoke conversion, tools, and actions while dragging | On qualified GNOME integration, external Nautilus/native and XWayland file drags open the right wheel; tapping then releasing the configured key leaves it open |
| REQ-UI-002 | Refresh nested menus during the same drag | Enter a category wedge and dwell 250 ms by default, configurable 150–600 ms; replace its children without a button release; at least three levels work; after expansion no leaf arms until ≥8 logical pixels of fresh movement enters a child target, or explicit keyboard/click selection occurs |
| REQ-UI-003 | Avoid accidental execution during navigation | Category selection never submits work. Releasing over a category retains bounded input grants, acknowledges source COPY once and latches children with zero jobs; Escape releases grants; only an explicitly armed leaf submits work |
| REQ-UI-004 | Permit backtracking and cancellation | Center dead zone of 24 logical pixels; explicit back wedge and breadcrumb; Escape/outside drop cancels; no output on cancellation; hysteresis prevents boundary flicker |
| REQ-UI-005 | Keep selection geometry predictable | Initial ring anchors once per invocation; children reuse a stable center unless clamping is necessary; no menu chasing the pointer; at most eight primary wedges plus back/more navigation |
| REQ-UI-006 | Adapt to display geometry | Edge/corner clamping or fan layout; multi-monitor negative coordinates, 100/125/150/200% scale, monitor disconnect, high contrast and reduced motion; valid targets remain reachable |
| REQ-UI-007 | Provide complete keyboard and accessible alternatives | Equivalent labeled list view; arrow/Tab navigation, Enter/Space select, Escape/back; native focus and Orca announcements; no drag-only operations |
| REQ-UI-008 | Keep feedback legible | Filename/count in center, clear operation/target and breadcrumb, subtle optional hover sound, opaque labels above drag ghost, pending-probe feedback; color is not the sole signal |
| REQ-UI-009 | Separate quick operations from editors | Drop on a fixed conversion leaf submits once; tool/parameter leaf opens an editor with explicit Apply/Cancel, defaults, reset and preview; never silently apply an unfinished edit |
| REQ-UI-010 | Expose settings and health | Rebindable shortcuts, dwell, output policy, quality, metadata, resource limits, autostart opt-in, shelf persistence, capability health, integration status and version; import/export validated local preferences |

Initial menu structure: Convert → family/target/preset, Tools → relevant operation/settings, Actions → six actions. A small target set may appear directly on the first ring. Categories exist when options overflow or need grouping; this must not add compulsory extra gestures to every simple conversion. A leaf with meaningful variants can expose a child ring such as Compress → size/preset/custom. Freeze a menu generation for selection, and invalidate an old generation when new context arrives.

Global invocation key choices must be proved on GNOME. Suggested experiment: tap Shift for Convert; test configurable chords for Tools/Actions. Do not blindly map macOS Command to Super or consume file-manager Ctrl/Alt copy/move semantics. Preserve the original drag if the gesture is not accepted. A dock/drop-zone, file picker, Open With `%F` or `%U` as supported, and Nautilus action must work even without the companion; these are fallback access paths, not global-gesture certification. Touch/pen hold-to-invoke is a separate qualification case.

## Context and capability selection

| ID | Rule | Acceptance |
| --- | --- | --- |
| REQ-CTX-001 | Identify files from content and metadata | MIME signatures plus extension hints; container/codec/stream probe; dimensions/pages/duration; reject spoofed or unreadable inputs safely; never run file content |
| REQ-CTX-002 | Show only available directed paths | Lookup source → destination adapter edges with decoder, encoder, tool, model and policy availability; no Cartesian-product guesses or executable discovery from untrusted PATH |
| REQ-CTX-003 | Intersect capabilities for selections | A HEIC+PNG selection can target JPEG if both decode; PNG+MP3 has no common conversion and retains general actions; show why a requested option is absent |
| REQ-CTX-004 | Respect operation cardinality and order | Distinguish per-file and aggregate operations; merge PDF needs PDFs, collage/images-to-PDF need images, join needs clips; preserve supplied order and offer reorder; never claim unavailable file-manager selection order |
| REQ-CTX-005 | Bound preflight and revalidate on execution | Async probes outside UI/shell, cache by stable file identity, invalidate on change; reject stale drag/session tokens; recheck readable source and writable destination before dispatch |

Before payload inspection is possible, a desktop overlay may show only generic categories. M0 must determine whether correct contextual targets can be exposed before release from external drags. If it cannot, the zero-click requirement remains blocked; a release-to-inspect flow is a documented alternative awaiting product acceptance.

The [inventory](parity-inventory.json) is the authoritative list: CONV-001 through CONV-275, TOOL-001 through TOOL-026 from the simulated demo, TOOL-027 for separately observed QR reading, and ACT-001 through ACT-006. All start as planned. A backend appearing in a package is not enough to mark a route implemented or verified.

## Job and output requirements

| ID | Required behavior | Acceptance |
| --- | --- | --- |
| REQ-JOB-001 | Preserve source files and avoid overwrite | New sibling copy by default; race-safe unique names; originals and metadata unchanged after conversion failure; destructive Move is a separate chosen action |
| REQ-JOB-002 | Commit complete, validated results | Write private temporary output on destination filesystem; check actual decoded content/structure; atomic no-replace publication; multi-output jobs publish a complete new folder or report explicit partial results |
| REQ-JOB-003 | Bound queues and resources | Per-file status, byte/frame/page progress when available, honest indeterminate status otherwise; configurable concurrency; default two light jobs or one heavy media/office job; disk/memory preflight |
| REQ-JOB-004 | Cancel and retry predictably | Cancel terminates every job descendant within two seconds using a proved whole-job boundary, cleans owned temporary artifacts and leaves published results/source intact; retry only failed items with identical recorded parameters |
| REQ-JOB-005 | Survive crashes and changes to files | Journal queued/running/validated/published states; interrupted work never silently resumes edits; offer safe retry; guard against removed media, source replacement, symlink races and unavailable destinations |
| REQ-JOB-006 | Isolate parsers and avoid implicit network | Probe/conversion workers confined with scoped file access, no network, time/memory/CPU/output limits; macro/script/external-resource execution disabled; fail closed for unavailable confinement on certified builds |
| REQ-JOB-007 | Make results inspectable | Itemized success/failure, preserved error category, reveal/open/copy output paths; user-chosen destination for read-only sources; no silent skipping of incompatible or failed items |

Format semantics must be explicit: JPG means JPEG; GIF uses the video/animation paths in this reference graph; M4A/OGG/MKV are containers with selected codecs; “GZIP” and `.tar.gz` are not interchangeable for arbitrary inputs; SVG is input-only; HTML is output-only in the reference graph. PDF raster export covers all selected pages, defaults to 300 DPI, and groups results. RTFD packages must retain attachments. A TXT/CSV export cannot retain formatting or formulas; make that loss visible before execution when material.

## Quality attributes

All performance targets are provisional until M1 measures a baseline machine: four physical CPU cores, 8 GiB RAM, SSD, software rendering/encoding baseline, default power profile; record actual CPU/GPU/kernel/session per run. Report cold/warm results separately and never treat these targets as measured performance.

| ID | Target | Verification |
| --- | --- | --- |
| NFR-001 | Warm invocation p95 ≤100 ms; cold ready ≤1.5 s; menu refresh p95 ≤100 ms excluding deliberate dwell | 100 warm and 20 cold runs per certified OS; no blocking probes in shell |
| NFR-002 | Coarse context for 100 local small mixed files p95 ≤300 ms; complex probes show pending state, remain cancelable, and have per-format budgets | Recorded fixed corpus; pathological files/remote mounts cannot stall UI |
| NFR-003 | Typical conversion elapsed time ≤1.25× the same bundled engine invocation plus 250 ms fixed overhead | Ten repeat runs per representative route/profile; paired warm/cache conditions |
| NFR-004 | Zero source loss, overwrite, duplicate submission, or false-success results in qualification corpus | Failure injection, crash/restart and concurrent destination tests |
| NFR-005 | Zero outbound network from preflight/conversion/edit workers; only user-invoked Share sends file data | Network namespace/firewall observation, SVG/office external-resource fixtures |
| NFR-006 | Idle resident app budget ≤120 MiB and <0.5% of one CPU over 60 s; normal radial UI budget ≤250 MiB excluding spawned engines/editors | Warm idle and menu benchmark; measure shell extension overhead separately |
| NFR-007 | Cancellation acknowledgment ≤250 ms and whole-job descendant exit ≤2 s | Large jobs, hung/double-fork/setsid children and aggregate-resource fixtures |
| NFR-008 | All operations keyboard reachable and Orca labeled; 44 logical pixel minimum alternate-list targets; ≥90% success in scripted core tasks with at least ten Ubuntu users | Accessibility session and observed usability report |
| NFR-009 | Unicode, whitespace, leading dashes, shell punctuation and supported non-UTF-8 Linux names are safe; no archive traversal outside staging | Filesystem and hostile-input corpus; URI representation failure explained without mutation |
| NFR-010 | Offline install and every certified feature work on clean supported OS images with no host converter tools | Per-package/per-OS VM run with network disabled and empty user profile |
| NFR-011 | Release is attributable to source revision and dependency closure; checksums/signatures/SBOM/notices/source obligations complete | Reproducible build comparison or documented variance; dependency and model manifest audit |
| NFR-012 | History is local, bounded and clearable; diagnostics redact paths/metadata by default and require explicit user export | Settings/migration/removal and diagnostic inspection tests |

## Completion rules

Developer preview may support a tested subset with its exact manifest. A public 1.0 parity claim requires all accepted inventory rows and UCs to pass, both LTS targets to qualify, all critical defects closed, and unresolved reference differences to be resolved or explicitly accepted as product scope changes. A useful subset must not be described as fully equivalent.

No hands-on Tangerine execution, Ubuntu prototype, codec benchmark, package build, or application test occurred in creating this baseline. The [SOP](../../SOP.md) defines how to collect that evidence.
