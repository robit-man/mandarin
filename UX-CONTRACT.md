# Mandarin interaction contract

Business sources: `.aiwg/requirements/srs.md`, `.aiwg/architecture/sad.md`, user requirement that the package install all tooling automatically.

## Canonical UI Map

| Capability | Canonical owner | Source of truth | Allowed variants | Verification |
| --- | --- | --- | --- | --- |
| Table Selection | `MainWindow` selected-file list | SRS context/cardinality rules | files/folders/mixed | GUI smoke + capability tests |
| Select/Listbox | Native Gtk.DropDown and Gtk.ListBox | Shared parameter schema | native GTK | keyboard/native popup |
| Form | `ParameterDialog` | `operations.py` parameter definitions | conversion/tool | validation and worker integration |
| Scrollbar | Global GTK CSS/native scrolled window | DESIGN.md | list/editor | GUI compact/normal |
| Toast | Shared persistent status and Adw.ToastOverlay | Job state machine | info/success/error | failure recovery |
| CRUD | `JobManager`/selected files/settings | SRS source preservation and journal | add/remove selection, queue/cancel/retry | core integration tests |

## Behavior ledger

Select/drop/paste → bounded context probe → operation tree → parameter form if needed → queued/running/validating/publishing → result with Reveal or persistent failure with Retry. Back and Cancel retain the selected files. No operation removes source content except an explicitly selected, separately verified Move. Stale probe/preview results are generation-checked. Duplicate apply is disabled after dispatch.

All rich input/output decoding runs in confined workers. The trusted UI displays bounded raw pixel buffers or trusted app icons, not untrusted encoded image content. Unsupported formats have an explanation; packaged mode must fail health checks instead of using tools from PATH. Job history is local and bounded. File selection and queues do not upload content.
