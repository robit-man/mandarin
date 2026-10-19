# Mandarin verification and release test plan

TP-001 · Version 1.0.0 · Baseline: 2026-10-18. All application tests below are planned, not executed. Documentation validation is reported separately.

## Environments and fixtures

Mandatory release environments: clean Ubuntu Desktop 24.04 LTS/GNOME 46 Wayland and 26.04 LTS/GNOME 50 Wayland, amd64, exact package/build recorded. Add 24.04 Xorg if advertised; XWayland source interoperability is mandatory on Wayland. Qualify 100/125/150/200% display scale, two monitors with mixed scales/negative origin, light/dark/high contrast/reduced motion and Orca. A full supported desktop VM or hardware session is required; pure headless tests qualify only their covered logic.

Use a four-core, 8 GiB RAM, SSD baseline and record actual hardware/power/graphics configuration. Separate cold/warm performance and software/hardware-accelerated engines. Stock VM snapshots must omit developer converter tools and user caches; disconnected tests must observe actual network behavior as well as unplugging ordinary access.

Build a provenance-tracked fixture corpus: tiny deterministic samples for every source format, larger representative files, and adversarial/malformed variants. Include HEIC/AVIF variants, ICC/alpha/EXIF orientation, multipage TIFF, GIF loops, variable-frame-rate/multi-stream/HDR/rotated media, silent video, multilingual documents, RTL/CJK/emoji fonts, tables/formulas/multiple sheets, encrypted PDFs/archives, scanned PDFs, Pages versions, RTFD attachments and native text clippings. Generate Mac-only fixtures on the licensed reference system and retain permission to redistribute or store locally.

Every CONV ID needs at least one ordinary and one nontrivial valid input on each supported OS; shared input fixtures may cover multiple destinations. Invalid-input families get additional negative cases. TOOL/ACT rows need applicable singleton, batch/cardinality, cancellation and error cases. Known untestable or missing fixtures remain a release gap, not an automatic skip success.

## Test levels and decisive assertions

| Suite | What runs | Required assertions |
| --- | --- | --- |
| TC-RADIAL | Pure reducer/geometry tests plus real GNOME drag E2E | Dwell/refresh/backtracking, stationary-pointer re-arm guard, overflow/More/Back, stable geometry, category latch/grant lifecycle with zero jobs, generations, exactly-once leaf commit, no input-grab leak |
| TC-CONTEXT | Signature/probe adapters and capability selection | Actual container/codec recognition, availability conjunction, batch intersection, aggregate ordering/cardinality, bounded preflight and stale-source handling |
| TC-CONV-ALL | All 275 directed routes using actual bundled adapters | Independent decode/open, format identity, content/fidelity/loss contract, naming/metadata, offline execution; attach evidence to each CONV ID |
| TC-TOOLS-ALL | 26 catalog tools and TOOL-027 QR | Required control surface, meaningful preview, Apply/Cancel/reset, result content, batch restrictions and local model availability |
| TC-ACTIONS-ALL | Six actions with files/folders/mixed selections | Actual native clipboard paste/drag-out, Move data safety, terminal cwd/arguments and explicit recipient-based sharing |
| TC-SAFETY | Worker/publish/recovery and hostile fixtures | Original preservation, no overwrite or unconfined/network access, bounded expansion, no command injection and honest terminal states |
| TC-DESKTOP | Full supported GNOME sessions and source apps | W0 transfer, native and XWayland drags, portals, modifier conflicts, extension disable/restart, multi-monitor and shelf behavior |
| TC-ACCESS | Keyboard and Orca sessions; usability exercises | Every operation reachable/labeled, focus restored, loading/error announced, non-color feedback, ≥90% core task success with at least ten Ubuntu users |
| TC-PERF | Recorded NFR fixture set | Invocation/probe/refresh/idle/cancel/throughput targets; UI and Shell stalls measured separately from engine time |
| TC-PACKAGE | Exact release candidate in fresh offline snapshots | Full dependency closure, integrity/signature checks, normal-user runtime, policy setup, update/migration/rollback/uninstall |
| TC-PRIVACY | Network observation and storage/diagnostic inspection | No conversion/probe/editor file egress, scoped sharing only, redacted exported diagnostics and bounded/clearable history |

Do not mock the engine, compositor, portal, filesystem publication or clipboard behavior when those are the subject of an integration/E2E claim. Use doubles for deterministic clocks/dwell, capability lookup and failure injection around actual interfaces. A passing pure menu test cannot certify a GNOME extension.

## Required end-to-end scenarios

| Case | Steps | Expected result |
| --- | --- | --- |
| E2E-001 | Native Files PNG drag → invoke → Convert category → JPEG preset → release | Context updates during uninterrupted drag; one validated JPEG beside original; source unchanged; reveal selects output |
| E2E-002 | Drag into Tools → Compress → preset; backtrack then choose custom | No conversion during category transitions; custom editor opens; Cancel yields no published file; Apply follows chosen settings |
| E2E-003 | Release over category/gap/loading; dwell into children then release without movement; More/Back, late probe results and modifier switch; Escape in latched menu | Category retains valid grants and acknowledges COPY once with zero jobs, including expiring portal transfers; explicit later click works once; stationary release never fires a newly drawn child; gap/loading never executes; Escape releases grants/overlay/preflight |
| E2E-004 | HEIC+PNG → JPEG; PNG+MP3 mixed selection | First enables actual shared path; second offers general actions and a clear conversion explanation; no silent dropping of files |
| E2E-005 | Reorder selected images/PDFs/clips in aggregate tool | Output page/clip ordering matches visible confirmed order; supplied file-manager order is not misrepresented |
| E2E-006 | Change source, remove drive, fill destination, collide on output name | Revalidate identity/grants; safe failure or destination choice; no source changes/overwrite and no false success |
| E2E-007 | Cancel long media job and crash broker during publication | Child group ends within bound; only unpublished temporary artifacts cleaned; journal prevents duplicate output on restart |
| E2E-008 | Portal file-transfer and sandboxed-browser local-file drag | Descriptor acquired once within grant lifetime; file access survives acknowledged transfer; remote URL/text never silently downloaded |
| E2E-009 | Copy and Float then paste/drag into native Files, GTK/Qt and XWayland app | Real file payload arrives; shelf survives intended lifetime; missing source is reported; no plain-text substitute for file copy |
| E2E-010 | Move across filesystems with collision/cancel/copy failure, source path swap or mid-copy edit, directory additions and crash after publish/before delete | No deletion of changed/replaced/unverified source; journaled source claim is recoverable; crash/cancel preserves verified destination; uncertainty yields source retention and explicit incomplete Move, never blind delete/retry |
| E2E-011 | Share to chosen compatible local recipient, decline then accept | Explicit recipient and authenticated transfer; cancellation works; conversion workers remain network denied |
| E2E-012 | Install offline; use keyboard/Orca; update then downgrade and uninstall | Declared capabilities work, settings/job schema handled safely, all entry paths accessible, originals/outputs survive removal |

## Format-specific fidelity contracts

Thresholds below are initial acceptance targets to tune against a fixed reference corpus in M0. Record any approved adjustment before testing; do not loosen thresholds after a failure without a reasoned product decision.

| Family/tool | Content validation |
| --- | --- |
| Images | Decode full output; exact dimensions/orientation/alpha policy/ICC; lossless paths pixel-equivalent under declared normalization; standard lossy fixtures SSIM ≥0.98 at agreed profile plus visual review; animation/multipage loss requires explicit policy |
| Video | Independent probe/decode; intended streams/languages/subtitles retained or deliberately removed; duration within one output frame for deterministic trims; A/V sync ≤one frame or 40 ms, whichever stricter; correct rotation/canvas; seeking and start/end decode succeed |
| Audio | Decode, sample rate/channels/duration; lossless PCM exact under declared conversion; PCM trim within one sample, compressed trim within documented encoder delay; normalization integrated loudness within 0.5 LU and true peak within 0.5 dB of target without unintended clipping; loudness range and mono/stereo channel/gain mapping independently measured |
| PDF structure/raster | Exact page count/order/rotation/boxes; all requested pages rendered at actual 300-DPI dimensions by default; images/content present; encryption/signature/annotation policy explicit; independent open and parser check |
| PDF reconstruction | Digital text token recall ≥99% and clean scanned baseline ≥95%; correct reading order; fixture tables ≥95% correct cells; content editable in the claimed native format; human review of columns/images/headings and major layout; blank/bitmap-only wrappers fail |
| Office/slides | Open in independent target consumer; paragraph/table/image/slide counts and content; fonts/fallback/pagination measured; PDF/raster covers all requested pages/slides; no macros or external links executed |
| Sheets | Sheet count/names and selected/all-sheet policy, cell types/values/formulas, locale/decimal/encoding handling; CSV/TSV loss of formulas/styles/multiple sheets disclosed; PDF print areas/pages checked |
| Pages/RTFD/clipping | Open true Pages output in current Pages and retain editable content; real input versions/attachments/Unicode checked; no extension-only workaround; unsupported variants remain blocked |
| EPUB/Markdown/HTML/TXT | Text/heading order, encoding, images/alt text/navigation and local resource links; no remote resource resolution; DRM/protection rejection explicit |
| Subtitles | Cue count, timing, multiline text and Unicode preserved within format precision; intentional cue-setting/style losses reported |
| Archives | Compare safe member hashes/modes/link policy; GZIP versus tarball semantics; reject hard-link escape, duplicate type-changing paths, forward links and unsafe metadata; enforce live/sparse/false-size byte/time/workspace quotas; no path escape or special-node publication |
| Compression | Achieved bytes recorded; maximum-size mode ≤requested maximum or explicit failure/quality choice; percentage mode within agreed tolerance (initially ±2 percentage points where feasible); target infeasibility never reported as met |
| Redaction | Solid replacements are present in final decoded pixels/samples/frames across every selected interval; sensitive alternate streams/previews/metadata absent; compare boundary frames/samples; detector suggestions have a separately measured false-negative rate and require review |
| QR | Payload matches fixture exactly; multiple/no-code/invalid cases handled; decoded commands/URLs never auto-execute |

For speed changes, measure duration against the chosen multiplier and pitch with a known tone, including silent clips and every supported rate. Mixed-clip Join must output MP4 on the first clip's canvas, with correct clip order, duration and audio continuity at boundaries. For metadata, compare an independent field/track/chapter/preview manifest against the edit/remove policy, including necessary orientation/ICC handling.

Before certifying a TOOL ID, create a capability submatrix of declared formats/cardinality, controls, materially different modes/presets/options, validators and loss policies, with positive/boundary/failure fixtures for each distinct behavior. Join release evidence by inventory ID plus mode/profile, not only one passing default. Compare public-demo eligibility with the retained observation predicates; broader Mandarin editor input support is separately certified.

Color/quality metrics and text recalls are necessary checks, not complete proof. Golden fixtures require content-aware and human review where generic metrics cannot establish usable fidelity.

## Package and network evidence profiles

Run two profiles on identical immutable package bytes: OFFLINE has networking disabled and tests install/first run plus every local conversion/tool/action; ACT-001 Share must explain missing network/recipient without attempting conversion egress. LAN-SHARE uses a controlled sender/receiver LAN with no WAN route and explicit recipient consent. Test decline, disappearance, cancellation and successful transfer, while simultaneous probes/conversions/editors/validators remain network denied. Do not report sharing as an offline action or use successful sharing to justify networking for converters.

Package authenticity tests verify the exact payload/manifest before local installation against an independently authenticated pinned key/fingerprint or existing trusted keyring. The local `.deb` installer does not automatically verify a sibling detached signature. Reject modified payloads, wrong/unknown keys, invalid/expired/revoked signatures according to the documented policy; exercise key rotation and explicitly requested older-version recovery. For an APT channel, qualify repository metadata authentication and a narrowly scoped Signed-By keyring separately.

## Adversarial and failure coverage

Inject source/destination symlink races and source replacement after preflight; leading-dash/shell punctuation/newline/Unicode/non-UTF-8 names; malformed/oversized URI lists; duplicate IDs/stale drag replies/replayed request IDs; broken portal grants; FIFOs/devices; corrupt/encrypted/polyglot files; compressed bombs, nested archives and path/link escapes; SVG/HTML/office external references and macros; FFmpeg playlists with unauthorized local/network protocols; oversized dimensions/pages/durations/model memory; output disk exhaustion and quota failure; hung children and full stderr pipes; extension crash/disable, broker restart, sleep/lock, monitor removal, active-job package update and migration interruption.

Probe workers, preview/editor-import decoders, conversion workers, independent output validators and sharing are separate test subjects. Inject hostile converted outputs, forged manifests/paths/descriptors and validator crashes/hangs. Exercise double-fork/setsid, changed process groups, inherited writable output FDs, fork/thread storms and aggregate multi-child memory/output exhaustion; all producers must terminate before publication. A denied-network screenshot alone cannot prove unrelated-file isolation. Assert scoped grants, no session bus/display/agent sockets, whole-job lifecycle/resource accounting and correct output state. Separate processes alone are not a sandbox.

Inject crashes around staged-data flush, no-replace publication, destination-directory flush, journal update, source claim and Move removal, including a replacement immediately after the last identity check and concurrent in-place writes. Record certified filesystem classes. An unsupported atomic no-replace operation must fail safely or use a separately qualified no-clobber strategy; rollback never deletes uncertain objects or blindly resubmits published work.

## Traceability and release reporting

| Coverage target | Primary suites |
| --- | --- |
| UC-001, UC-002; REQ-UI-001..006, REQ-UI-008 | TC-RADIAL, TC-DESKTOP, E2E-001..004 |
| UC-003; REQ-CTX-001..005 | TC-CONTEXT, TC-CONV-ALL, E2E-004..008 |
| UC-004; REQ-UI-009 | TC-TOOLS-ALL, TC-ACCESS, E2E-002/005 |
| UC-005 | TC-ACTIONS-ALL, E2E-009..011 |
| UC-006; REQ-UI-007 | TC-ACCESS, TC-DESKTOP, E2E-012 |
| UC-007; REQ-JOB-001..007 | TC-SAFETY, TC-PRIVACY, E2E-006/007/010 |
| UC-008; REQ-UI-010 | TC-PACKAGE, TC-ACCESS, E2E-012 |
| CONV-001..275 | TC-CONV-ALL with one independent result row per ID/OS/package/profile |
| TOOL-001..027; ACT-001..006 | TC-TOOLS-ALL and TC-ACTIONS-ALL, cardinality/preview/error rows included |
| NFR-001..003, NFR-006/007 | TC-PERF plus TC-DESKTOP/SAFETY for latency and cancel bounds |
| NFR-004/005/009/012 | TC-SAFETY, TC-PRIVACY, filesystem/diagnostic inspection |
| NFR-008 | TC-ACCESS and usability report |
| NFR-010/011 | TC-PACKAGE, build/dependency/signature evidence |

Release report schema: `test_id`, `inventory_id` when applicable, `requirement_ids`, `package_sha256`, `source_revision`, `os_image`, `desktop_session`, `capability_profile_hash`, `fixture_sha256`, `options_hash`, `status` (pass/fail/blocked/not-run), `validator_results`, `elapsed_ms`, `evidence_paths`, `reviewer`, `limitations`. Key results by ID and exact build; carry no pass forward across changed engines/models/options without impact analysis.

Release gates: W0 and S0 pass; P0 resolved; all accepted inventory rows pass on supported OS profiles; no hidden skip or disabled route counts as success; all critical functional/safety/accessibility defects closed; NFR evidence complete; offline install/update/rollback/uninstall pass; reference differences approved and disclosed. The final parity report includes counts of planned/implemented/verified/blocked rows, never only a single promotional count.
