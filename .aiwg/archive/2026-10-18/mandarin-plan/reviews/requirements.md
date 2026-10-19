# Requirements, feature and interaction review

Reviewer role: requirements / reference feature / UX completeness. Reviewed 2026-10-18 against the planning baseline. Decision: **conditional approval**; resolve REQ-REV-001 through REQ-REV-003 before treating the documentation as the frozen construction contract. No application or native Mac parity certification is implied.

## Verified findings

- Inventory has 275 unique directed conversion edges and no identity edges. Family totals are 57 image, 56 audio, 48 video/GIF, 9 PDF, 59 document, 6 EPUB, 6 presentation, 21 spreadsheet, 4 subtitle and 9 archive: 275. Milestones account for 66 + 108 + 101 routes.
- All 26 public-demo tool IDs, the separately store-listed QR reader and six actions are present. All 308 entries remain planned. The validator passes its inventory, source/test reference, requirement and local-link checks.
- The documents consistently disclose that the public demo is simulated, the native Mac build was not run, and no Ubuntu application, package or application test exists. They explicitly separate the user's requested nested radial interaction from established native Tangerine behavior.
- Requirements cover external continuous dragging, three nested levels, backtracking, dwell/hysteresis, stable geometry, stale generations, edge/multi-monitor layouts, keyboard/Orca alternatives, context intersection, aggregate ordering, job safety, offline payloads and measurable verification.
- Wayland desktop access, worker confinement, Pages writing, PDF reconstruction, offline dependency closure and sharing substitution are appropriate explicit gates. The plan does not silently substitute fallback entry points, renamed extensions or screenshot wrappers for parity.

## Required reconciliation

| ID | Severity | Location | Finding and required action |
| --- | --- | --- | --- |
| REQ-REV-001 | Medium | `.aiwg/research/reports/tangerine-feature-review.md:86`; `.aiwg/requirements/parity-inventory.json` tool rows | The report says batch filtering differs, but does not retain the exact public-demo singleton/batch predicates. Broad family labels can obscure known reference boundaries: the demo's image tools use JPG/PNG/WebP/HEIC/TIFF, SVG offers aggregate image tools only, GIF offers metadata only, audio tools use MP3/M4A/WAV/FLAC, and video tools use MP4/MOV/MKV. Add source-classified singleton and batch formats, aggregate/per-file mode and observed minimum cardinality for every tool. Preserve these as public-demo observations pending native reconciliation; wider Mandarin support is a separate qualified extension, and no native limit should be inferred from the simulation alone. Verify eligibility is the conjunction of format selection and the 11-ID batch allowlist, including the four aggregate tool IDs. |
| REQ-REV-002 | Medium | `.aiwg/architecture/sad.md:101`, `:120` and `:124`; `.aiwg/requirements/srs.md:36`; `.aiwg/testing/test-plan.md:39` | Category release must latch context for click/keyboard continuation, but the protocol/state path only describes a leaf commit followed by queuing. Define a separate category-drop acceptance/latching state: acquire and retain input grants, acknowledge one COPY transfer after acquisition, enqueue zero jobs, continue with the same input snapshot, and release owned grants on cancel. Leaf selection from the latched state submits exactly once. Add a real external-drag case, including a portal source whose transfer grant expires after acknowledgment. |
| REQ-REV-003 | Medium | `.aiwg/architecture/sad.md:123`; `.aiwg/requirements/srs.md:35` and `:45`; `.aiwg/testing/test-plan.md:37-39` | The architecture prohibits accidental child execution, but leaves the re-arming event undefined. State exactly how a child leaf becomes armed after a stationary pointer causes category expansion. Add decisive reducer and desktop cases for immediate release without further motion, an explicit re-arm gesture followed by release, rapid consecutive expansions/backtracking, eight-plus-item overflow/More/back, late probe/context replacement and modifier switching. An unarmed newly exposed child must never execute merely because it occupies its parent's former wedge. |

## Minor follow-up

| ID | Severity | Location | Action |
| --- | --- | --- | --- |
| REQ-REV-004 | Low | Feature review TOOL-017; inventory `joinVideos` | The detailed public tool catalog specifies a single MP4 output for Join Video. Record that output contract explicitly alongside mixed clip and first-canvas handling. |
| REQ-REV-005 | Low | Inventory action rows; SOP Procedure A step 3 | Give each action the same explicit reference-validation classification as conversion/tool observations so the promised per-observation ledger is uniform. |
| REQ-REV-006 | Low | Feature review ACT-006; architecture actions | Multi-parent Terminal behavior is described as needing definition but no policy is selected. Choose a clear parent-selection/launch policy during M0 and test multiple source directories rather than leaving that sentence as an apparent completed contract. |

## Review evidence and limit

Read README, PLAN, SOP, feature review, SRS, complete machine inventory, SAD, test plan, risk register and public source manifest. Independently counted route identities/families/milestones and ran `python3 scripts/validate_plan.py` successfully. Inspected the retained public demo's tool-selection function/allowlists and the current vendor tool-data descriptions, plus current vendor and App Store pages. Public primary sources are [Tangerine](https://tangerineformac.com/), [tool catalog](https://tangerineformac.com/tools), and [App Store](https://apps.apple.com/us/app/tangerine-file-converter/id6813034065?mt=12). The installed Mac application was not accessed and no future GNOME, conversion, package or performance assertion was tested.

Approval condition: close the three medium items in the integrated documents, rerun planning validation and record their dispositions. The minor items can be resolved now or tracked as explicit M0 decisions. After those changes this is sufficient as a construction baseline; full-equivalence release remains blocked until the documented reference and application evidence exists.

## Final disposition after reconciliation

Rechecked the targeted changes on 2026-10-18. **Approved as a planning and construction baseline.** This disposition supersedes the initial conditional approval above.

| Finding | Disposition and verified evidence |
| --- | --- |
| REQ-REV-001 | Closed. All 26 demo tools now retain source-qualified singleton/batch formats, selection intersection, per-file/aggregate mode and observed minimum input count in `reference_applicability`. The 11 batch-eligible IDs and four aggregate IDs match the reviewed public-demo selection logic. Feature review explicitly separates these observations from native behavior and wider future Mandarin support. |
| REQ-REV-002 | Closed. SAD defines `AcquiringGrants → LatchedSelection`, `LatchCategoryDrop`, `CommitLatched` and `ReleaseSelection`; acquisition precedes exactly-once COPY acknowledgment, category latching creates zero jobs, retained grants support later explicit selection, and cancel/expiry releases them. E2E-003 includes expiring portal transfers and subsequent explicit selection. |
| REQ-REV-003 | Closed. SRS and SAD require at least eight logical pixels of fresh movement into a child or explicit keyboard/click selection after expansion, and clear the armed leaf. Back/More and context replacements use the guard. TC-RADIAL/E2E-003 explicitly cover stationary immediate release, overflow/back, late results and modifier switching; the existing three-level continuous-drag requirement remains. |
| REQ-REV-004 | Closed. Tool inventory, feature review and content verification now specify one MP4 with first-clip canvas and clip/audio boundary checks. |
| REQ-REV-005 | Closed. All six action entries now explicitly classify their reference evidence as public demo/vendor listings without hands-on validation. |
| REQ-REV-006 | Closed. SAD, feature review and inventory select a unique-parent chooser with one terminal destination by default and explicit opt-in for several parents. |

Re-ran `python3 scripts/validate_plan.py`: pass for 275 directed conversions, 26 catalog tools, one additional tool, six actions, CSV/JSON consistency, source/test references, 42 requirement/use-case IDs and local document links. All 308 inventory entries remain planned. No further blocking requirements-review concerns remain in this planning scope. Native reference reconciliation, W0/S0/P0 feasibility, implementation, package qualification and full-parity release approval remain future evidence gates; this review does not certify any application behavior.
