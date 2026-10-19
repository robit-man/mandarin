# 0.1.0 evidence

Generated-fixture results and native screenshots from Ubuntu 24.04 amd64 development and offline package checks. Final evidence JSON records outcomes and limitations; this is not native Mac parity or global Wayland certification.

Reproduce using the [implementation report](../../../reports/implementation-0.1.0.md). The runtime manifest and artifact checksum are release assets. Reports identify the tested package. Fixtures use original synthetic content and the licensed presentation fixture in `tests/fixtures`.

- `summary.json`: implementation counts, fixture coverage and explicit absence of native parity certification.
- `package-verification.json`, `package-results.json`, `tool-results.json`: the final installer hash, 248 offline conversion cases and 32 tool cases across 28 operations.
- `application-tests.log`: 28 application/security/integration/packaging tests.
- `native-gui-tests.log`: native captures, actual held-file drag traversal and the separate GTK3 taskbar helper with the GTK4 application.
- `deb-desktop-results.json`: the installed native Ubuntu package's real GNOME Wayland GUI, indicator icon, menu, Open, Jobs and Quit.
- `snap-results.json`, `snap-desktop-results.json`: the installed strict Snap's 12 representative conversions and actual GNOME desktop indicator/menu lifecycle.
- `ui-static-audit.json`: deterministic UI audit, with zero findings.
- `source-archive-results.json`: all 1,316 exact source files checked inside five release archives, covering 413 source packages and 651 bundled binary packages.
- `fixtures.json`: hashes for 43 source formats. The screenshots show normal radial, keyboard, compact and editor states.

Synthetic fixtures establish basic output production/decoding. They do not establish arbitrary-file fidelity, every reference format, recognition efficacy, real-device sharing, every desktop source or global Wayland drag transfer. A private headless GNOME experiment did not complete a source drag; global qualification remains open.
