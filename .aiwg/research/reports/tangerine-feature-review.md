# Tangerine feature review and Ubuntu parity assessment

Reviewed: 2026-10-18. Scope: publicly accessible vendor pages, release history, and simulated website data. This is a complete inventory of the exposed reference graph, not a claim that every feature of the installed Mac application has been observed.

## Evidence and limits

| Source | Observation | Confidence and limitation |
| --- | --- | --- |
| [SRC-001: product page](https://tangerineformac.com/) | Advertises 275 paths, 26 tools, six actions; offline workflow and file families | Published claim; page explicitly says its operations are simulated |
| [SRC-002: tools](https://tangerineformac.com/tools) | Detailed editors and controls for 22 tool entries | Helpful control-level evidence; does not list all 26 demo tool identifiers |
| [SRC-003: App Store](https://apps.apple.com/us/app/tangerine-file-converter/id6813034065?mt=12) | Version 2.0.1 observed; preceding 2.0 adds office/EPUB, actions and floating files; also mentions QR reading | Newer release record than press kit; description has older shortcut wording |
| [SRC-004: public demo data](https://tangerineformac.com/assets/home-BU_Sezi2.js) | 275 directed pairs, 26 tool identifiers, six action identifiers, per-format and batch filtering | Website simulation; no evidence of backend codecs, algorithm quality, private app APIs or exact app menu structure |
| [SRC-005: public tools data](https://tangerineformac.com/assets/tools-DHpyoIBf.js) | Tool group membership and editor descriptions | Public informational data; no installed-app testing |
| [SRC-006: press kit](https://tangerineformac.com/press) | Workflow, sibling outputs, Mac/Apple-silicon requirements | Still identifies version 1.4; not the release baseline |

Retrieval metadata and SHA-256 fingerprints of fetched pages/assets are recorded in [sources.json](../sources.json). Raw vendor JavaScript, media, screenshots and copy are not redistributed in this repository. Asset filenames can change; retain the fingerprint and rerun baseline capture when that occurs. Primary sources were checked on the date above; do not assume they remain unchanged.

Extraction method: read the public demo's source-format lists and deterministic target-selection logic in isolation, evaluate each unique offered source format, exclude identity conversions and input-only destinations, and enumerate ordered source/target pairs. The result is exactly 275. See the [CSV](../../requirements/conversion-matrix.csv) and [JSON inventory](../../requirements/parity-inventory.json). Those counts describe reference intent; Mandarin currently implements zero of them.

## Workflow findings

The current landing page describes tapping Shift during a drag for conversions, Command for tools, and Control for actions. The wheel remains open after the key is released. The store description still describes Shift and Option+Shift. Preserve the distinction as an unresolved reference-version detail; inspect Settings and record actual behavior on a licensed current Mac build before freezing shortcut parity.

The product is menu-bar resident, context-sensitive and local. Conversions/edits create copies beside sources; a progress surface and file-manager reveal complete the job. Batch behavior includes heterogeneous inputs with a common destination format, plus aggregate tools such as image-to-PDF, collage, video join and PDF merge. General file actions apply to folders and mixed selections even when there are no conversions. The store currently describes a 20-file trial and a one-time unlock; Mandarin's pricing/license is undecided and should not recreate that allowance accidentally. These observations come from the [product page](https://tangerineformac.com/) and [store listing](https://apps.apple.com/us/app/tangerine-file-converter/id6813034065?mt=12).

The user's requested progressive radial submenus are a Mandarin requirement. Public sources establish multiple context wheels and filtering, but do not establish that Tangerine has the exact dwell-to-descend mechanism the user described. Test and implement that interaction explicitly, including category release, backtracking, hover hysteresis and delayed payload inspection.

Keyboard/touch behavior on the public page is simulated. It is useful as a design reference, not proof of the native app's accessible keyboard support, touch support or Orca-equivalent semantics. No inference of native compatibility is made from the website.

## All conversion families

Every individual pair has a CONV identifier in the inventory. “Others” below excludes the same format, and an arrow is directional.

| Source family | Directed target contract from public demo | Paths | Ubuntu implementation lane |
| --- | --- | ---: | --- |
| JPG, PNG, WebP, HEIC, TIFF, AVIF, BMP; SVG input | Seven raster formats → other six + PDF; SVG → all seven + PDF | 57 | libvips/libheif plus safe SVG rendering and PDF assembly; test encoders, color, orientation, alpha and multipage policy |
| MP3, M4A, WAV, FLAC, OGG, Opus, AIFF, WMA | Each → other seven | 56 | FFmpeg; explicit codec/container presets, channel layouts and metadata policies |
| MP4, MOV, MKV, WebM, AVI, WMV; GIF | Six containers → other five + GIF + MP3; GIF → six video containers | 48 | FFmpeg; stream discovery, remux where valid, encode otherwise; animation and silent/audio behavior |
| PDF | DOCX, Pages, PPTX, XLSX, JPG, PNG, EPUB, TXT, Markdown | 9 | Raster/text paths practical; editable reconstruction and native Pages writing require dedicated feasibility work |
| DOCX, Pages, Markdown, TXT; RTF/RTFD/textClipping input | DOCX/Pages/Markdown/TXT → the other eligible document formats plus PDF/HTML/EPUB/PNG/JPG; three legacy inputs → nine eligible outputs | 59 | LibreOffice/Pandoc/render pipeline; Apple package readers/writer are unresolved |
| EPUB | PDF, DOCX, Pages, TXT, Markdown, HTML | 6 | Local document pipeline; navigation, images, reading order and DRM rejection |
| PPT/PPTX | PDF, JPG, PNG | 6 | LibreOffice Impress → PDF → all-page raster output |
| XLSX, ODS, CSV, TSV; XLS input | Four editable formats → other three + PDF; XLS → five eligible outputs | 21 | LibreOffice Calc/typed delimited parser; selected/all sheets, locale, encoding, formulas and print layout |
| SRT/VTT | Other subtitle format + TXT | 4 | Typed cue parser; preserve time precision; document loss of styling/cue metadata |
| ZIP, TAR, GZIP; RAR input | Three writable archive formats → other two; RAR → all three | 9 | libarchive; distinguish standalone `.gz`, `.tar.gz`, symlinks and actual member content |
| **Total** | **Directed edges, not all combinations of every extension** | **275** | **All planned** |

Important graph boundaries: HTML has no input edges; SVG, RTF, RTFD, textClipping, XLS, PPT and RAR are not output destinations. GIF is treated as an animation/video source, not a still-image target. Do not add formats to the parity count simply because an engine supports them. Additional useful routes can be tracked separately after the baseline.

## All tools

The numbering below matches the inventory. These are functional scopes to implement and verify, with details informed by the [tool catalog](https://tangerineformac.com/tools), [public demo catalog](https://tangerineformac.com/assets/home-BU_Sezi2.js), and [store list](https://apps.apple.com/us/app/tangerine-file-converter/id6813034065?mt=12).

| ID | Tool | Required scope and important parity check |
| --- | --- | --- |
| TOOL-001 | Compress | Size/percentage/preset targets; image resize; compatible batches; report when a target is impossible or lower quality is needed |
| TOOL-002 | Metadata | Inspect, search, edit and remove supported fields; per-file/track/chapter grouping; distinguish editable fields from read-only information |
| TOOL-003 | Edit photo | Live preview; light/color/detail, dehaze/clarity, grain and noise reduction; original remains intact |
| TOOL-004 | Annotate photo | Arrows/text/shapes/draw/highlight/callouts; numbered labels, magnifier and inserted images |
| TOOL-005 | Add background | Solid/gradient/image canvas; aspect ratio, padding, corners, blur and shadow |
| TOOL-006 | Crop image | Preset/custom aspect ratio, exact pixels, batch rules and EXIF orientation |
| TOOL-007 | Normalize audio | Loudness/true-peak/range controls; compare levels and avoid clipping |
| TOOL-008 | Remove audio | Correctly remove audio streams without silently losing video/subtitle streams |
| TOOL-009 | Trim video | Frame/timecode boundaries; distinguish exact re-encode from keyframe-only fast trim |
| TOOL-010 | Split PDF | Page/range selection; complete grouped outputs; encrypted files handled explicitly |
| TOOL-011 | Organize PDF | Reorder, rotate, duplicate and delete; preserve page geometry and document policies |
| TOOL-012 | Extract archive | Safe member paths, output limits and link policy; support advertised input types |
| TOOL-013 | Images to PDF | One image per page; mixed image formats; review/reorder rather than assuming supplied order |
| TOOL-014 | Merge PDF | Preview/reorder documents and preserve page count/geometry |
| TOOL-015 | Crop video | Exact output size; retain intended audio; validate even dimensions required by encoder |
| TOOL-016 | Change video speed | Faster/slower; pitch preservation when audio exists; silent files work |
| TOOL-017 | Join video | Mixed MP4/MOV/MKV → one MP4; ordering; normalization to first clip canvas; codec/audio mismatch handling |
| TOOL-018 | Save video frames | Selected exact full-resolution PNG frames; orientation and timestamps |
| TOOL-019 | Split video | Custom boundaries/equal parts; predictable grouped naming and timing |
| TOOL-020 | Audio visualizer | Waveform or still image → MP4; landscape/portrait/square; audio/video duration match |
| TOOL-021 | Trim audio | Waveform selection/exact times; leading/trailing silence removal without removing internal pauses |
| TOOL-022 | Audio channels | Mono/stereo and independent left/right gain/preview; avoid cancellation/clipping |
| TOOL-023 | Image collage | Grid/row/column/featured layout; order, size, spacing, corners and background |
| TOOL-024 | Redact image | Multiple solid/blur regions; local face/text suggestions; flatten committed pixels and remove sensitive embedded previews |
| TOOL-025 | Redact video | Time-ranged solid/blur regions; every rendered frame checked for coverage |
| TOOL-026 | Bleep audio | Movable bounded intervals; original/bleep preview; validate boundaries in output samples |
| TOOL-027 | Read QR | Store-only additional observation; local decode; preview content; do not automatically open links |

The 26 advertised demo tools and the additional store-listed QR reader are deliberately separate. Exact-size compression can be approximate or infeasible at a requested quality; the application must state achieved size and tolerances. Blur and automated detection must not be described as guaranteed removal of sensitive information; secure redaction requires explicit solid replacement and verification.

The public demo filters batch tools more narrowly than single-file tools. Exact predicates are retained on every tool's `reference_applicability` in the JSON inventory, separately from future Mandarin support. In that simulation, single-image tools use JPG/PNG/WebP/HEIC/TIFF; SVG offers aggregate image tools only; GIF offers metadata only; audio tools use MP3/M4A/WAV/FLAC; video tools use MP4/MOV/MKV; PDF and archives have their own sets. AVIF/BMP and other conversion inputs are not thereby demonstrated as editor inputs. There are 11 batch-eligible identifiers after format intersection; four are aggregate operations with at least two inputs (images-to-PDF, collage, PDF merge and video join). “Supports batches” does not establish every editor supports batch editing. Broader Mandarin support needs separate qualification; native behavior still needs hands-on validation.

## All six actions and Ubuntu equivalents

| ID | Reference action | Mandarin contract | Limitation to resolve |
| --- | --- | --- | --- |
| ACT-001 | AirDrop | Share through an explicit local-network recipient flow, initially a version-pinned interoperable LocalSend implementation/companion | Functional sharing equivalence only; protocol, receiver availability, pairing and network policy tested separately |
| ACT-002 | Float | Shelf retaining references, edge pinning and drag-out into other apps | Ordinary Wayland clients cannot assume arbitrary edge/always-on-top positioning; companion/shelf feasibility required |
| ACT-003 | Copy | Put files on the clipboard so Files can paste them | URI list plus relevant file-manager copy format; not merely path text; clipboard-owner lifecycle matters |
| ACT-004 | Move | Destination chooser, collision policy and actual original relocation | Cross-filesystem copy/verify/publish before deleting source; itemized failures and no false global Undo |
| ACT-005 | Copy Path | Absolute local paths, one per line, as clipboard text | Decode URIs safely; do not shell-escape paths as though they are commands |
| ACT-006 | Terminal | Open selected directory or source's parent in configured terminal | For multiple parents, choose one unique parent by default; explicit choice required to open several; no command interpolation |

File and folder action semantics are described by the [product page](https://tangerineformac.com/) and [press kit](https://tangerineformac.com/press). Apple-only service names are reference labels; Mandarin UI uses Share, Float, Copy, Move, Copy path and Terminal.

## Mandatory hands-on follow-up

Before claiming exhaustive native-app parity, record a current Tangerine version/build and settings, then exercise every inventory entry with licensed/generated fixtures. Record menus, option panels, ordering, output naming, metadata defaults, quality settings, progress, cancellation, unsupported files and batch rules. Compare actual results, not only the existence of a menu item.

Specifically resolve: current shortcut mapping, submenu transitions, native QR location, the extra four tools absent from the detailed tool page, behavior of modern Pages/RTFD/textClipping, archive repacking semantics, PDF-to-office editability, image multipage behavior, exact-size tolerances, free allowance rules, shortcuts/settings, shelf lifetime, and restart/update behavior. No access to a Mac is required to start Ubuntu feasibility work; it is required to certify this native reference baseline.

The [plan](../../../PLAN.md) puts these questions in M0; the [risk register](../../risks/risk-register.md) supplies owners and stop conditions.
