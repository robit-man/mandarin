# Test and release review

Reviewer role: independent test/release review under artifact orchestration.
Reviewed snapshot: 2026-10-18; planning baseline only. Reviewed README, PLAN, SOP, SRS, SAD, test plan, risk register, JSON inventory and CSV conversion matrix.
Outcome: **conditional approval for the planning baseline**, subject to TR-001 through TR-004 being incorporated or explicitly dispositioned. This is not application, package, desktop, or full-parity release approval.

## Findings

### TR-001 — High: output-validation parsing needs an explicit confinement boundary

Location: `.aiwg/architecture/sad.md`, §§4, 9, 13–14; `.aiwg/testing/test-plan.md`, “Adversarial and failure coverage” and TC-SAFETY.

The design isolates input probes, previews and conversions, but the publication sequence has the trusted output coordinator independently validate the worker's artifact manifest/output. It is not explicit whether content decoders used for that independent validation run confined. A compromised conversion worker can produce hostile output just as an external source can provide hostile input; parsing it in the broker/coordinator would bypass S0.

Requested fix: require independent content validators to run in a disposable confined process with bounded read-only artifact grants and structured results. The coordinator checks bounded manifest fields, file identity and publication policy without hosting media/document decoders. Add hostile-output, malicious manifest/path, descriptor and timeout cases to S0/TC-SAFETY, asserting no unrelated-file/network/session-bus access from the validator. This is a design ambiguity, not a finding of an existing exploitable application.

### TR-002 — High: specify the destructive Move race and publication fault-injection cases

Location: `.aiwg/testing/test-plan.md`, E2E-007/E2E-010 and “Adversarial and failure coverage”; `.aiwg/architecture/sad.md`, §§8–9 and 13; `SOP.md`, Procedures C4 and F5–6.

Generic source-replacement and publication-crash coverage is present, but it does not prescribe the decisive destructive cases: source content changing during cross-filesystem copy; the source path being replaced immediately before removal; crash after destination publication but before journal update or source removal; and cancellation at those boundaries. These need explicit outcomes because “verified copy then remove source” alone does not identify which object it is safe to delete.

Requested fix: add named fault-injection cases with assertions that a replacement/changed source is never deleted, a verified published destination survives restart/cancel, and ambiguous state becomes an inspectable partial result instead of an automatic delete/retry. Enumerate crashes around staged-data flush, no-replace publication, destination-directory flush and journal update. Record the certified filesystem classes, including a no-replace-unsupported lane that must fail safely or use its qualified alternative.

### TR-003 — Medium: separate offline qualification from LAN-sharing qualification

Location: `SOP.md`, Procedures B6 and F1–3; `.aiwg/testing/test-plan.md`, TC-PACKAGE/TC-PRIVACY/E2E-011; `PLAN.md`, release evidence.

The SOP disconnects networking and subsequently calls for every declared route/tool/action to run. Share necessarily needs a recipient/network path, while the product correctly treats sharing as the explicit conversion-offline exception. One combined “offline all actions passed” result would be impossible or misleading.

Requested fix: define two evidence profiles on the same immutable package: (a) network-disabled install/first-run and all local conversion/edit/actions; (b) controlled LAN-only sender/receiver with no WAN route, explicit recipient consent and unchanged worker network denial. Keep missing-recipient/decline/cancel and conversion-during-share isolation tests. Do not count successful local-sharing tests as evidence that conversion may use networking.

### TR-004 — Medium: rich tool verification needs per-tool/profile obligations

Location: `.aiwg/testing/test-plan.md`, “Format-specific fidelity contracts,” TC-TOOLS-ALL and release-report schema; `.aiwg/requirements/parity-inventory.json`, TOOL-001/002/007/016/017/022 and tool scopes; `SOP.md`, Procedure C1.

The route corpus and generic editor states are concrete, but several advertised tool behaviors lack decisive acceptance obligations. Examples: normalization tests true peak but not requested integrated loudness/loudness range; channel conversion needs channel mapping/gain tests; speed changes need duration and pitch checks; joining mixed clips needs canvas/audio-boundary tests; metadata editing/removal needs a field-level preservation/removal contract. A pass keyed only to the tool ID could conceal untested modes or presets.

Requested fix: require a per-ID capability submatrix of declared families, controls, presets/options and loss policies before a tool is certified, with at least one positive/boundary/failure fixture for each materially different behavior. Add the above signal/content assertions and M0-fixed tolerances. Join release evidence by inventory ID plus declared mode/profile; one passing default preset cannot certify every exposed option. This can remain an implementation deliverable, but must be an explicit release obligation now.

### TR-005 — Low: M0 is a risk-investigation allowance, not a supported completion estimate

Location: `PLAN.md`, milestone M0 and estimate paragraph; `.aiwg/architecture/sad.md`, §3 W0; `SOP.md`, Procedures A and B.

The 38–60 engineer-week subtotal and 25% contingency arithmetic are correct, and the two-engineer 6–9 month range is appropriately provisional. However, M0 allocates 2–3 engineer-weeks for the reference ledger, W0/S0, engine manifest/offline package and Pages/PDF experiments while W0 alone is budgeted 5–10 engineer-days. Full native observation of 275 routes and 27 tools further stretches that allowance.

Requested fix: state what the initial M0 timebox actually includes, distinguish sampled feasibility observations from completion of the full native reference ledger, and require re-estimation/extension at the gate. Alternatively widen the M0 allowance and recalculate total/calendar range. Do not compress unresolved feasibility into a nominal completed milestone to preserve the headline estimate.

## Evidence and positive checks

Independently ran `python3 scripts/validate_plan.py`: exit 0; 275 directed routes, 26 catalog tools plus one additional tool, six actions, CSV/JSON consistency, source/test references, 42 requirement/use-case IDs, nine Markdown files and 31 local links passed for this snapshot. All **308/308** inventory entries remained `planned`.

Also independently checked inventory uniqueness and milestone counts: M2 = 66 conversion routes, M3 = 108, M4 = 101; CSV and JSON directed pairs agree. The requirement/test mapping covers every UC and named requirement/NFR group. No application tests were run or implied by these checks.

README and the core documents accurately disclose that implementation, packages and application qualification do not exist. W0/S0/P0 remain real blocking gates, fallback entry paths do not masquerade as global drag parity, Pages/PDF gaps are not silently excluded, and full-payload deb/AppImage/Flatpak limitations are distinguished. Preview/beta/full-parity labels are clear and should be preserved during construction.

After the requested dispositions, the package is suitable for authorizing M0 investigation and the first implementation increment. Shipping still requires the future test evidence and explicit release gates already specified.

## Final disposition after revision

Rechecked the targeted changes on 2026-10-18. **Approved as a planning baseline.** This supersedes the initial conditional disposition above; the original findings remain as the review history.

| Finding | Final planning disposition |
| --- | --- |
| TR-001 | Resolved: SAD §§4/9/14 and SOP C3–4 now require fresh confined independent validators, untrusted-manifest restrictions, and rich-content decoding outside trusted coordinators; the test plan adds hostile outputs/manifests/descriptors and validator failures. |
| TR-002 | Resolved: SAD §9 requires a separately reviewed recoverable source-ownership/removal transaction, prohibits check-then-unlink as proof, and retains changed/uncertain objects; E2E-010 and failure coverage name source swaps, concurrent edits/directory additions and flush/publication/journal/claim/removal crash boundaries, including unsupported filesystem semantics. |
| TR-003 | Resolved: SOP B6/F3 and the test plan define separate OFFLINE and LAN-SHARE profiles on identical package bytes, with no WAN for sharing and continuing conversion/validator network denial. |
| TR-004 | Resolved: the test plan requires the per-tool capability submatrix and mode/profile evidence, and explicitly adds loudness/range, channel/gain, speed/pitch, Join boundaries/canvas and metadata policy checks. Concrete fixtures and final tolerances remain future certification work. |
| TR-005 | Resolved: PLAN M0 is an initial sampled/prioritized timebox, explicitly extendable with gate re-estimation; full native reference reconciliation is deferred until before certification. The headline estimate states its M0 sufficiency assumption. |

Independently reran `python3 scripts/validate_plan.py` after these revisions: exit 0; 275 routes, 26+1 tools, six actions, 42 requirement/use-case IDs, 12 Markdown files and 31 local links passed; **308/308 inventory entries remain planned**. No application, desktop, conversion or package qualification was performed.

No remaining test/release planning concern blocks baselining. W0, S0, P0, safe Move transaction implementation, per-mode tool fixtures, offline closure and the complete release matrix still require their future evidence; this approval does not certify those gates or authorize a shipping claim.
