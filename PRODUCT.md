# Mandarin

<!-- impeccable:product-schema 1 -->

## Platform

Ubuntu Linux native desktop (GTK4/libadwaita); this is not a web application.

## Stack

The user authorized implementation of the reviewed plan. Implementation decision ADR-006 uses Python 3.12/PyGObject for native GTK4, a small C Landlock/seccomp launcher, and explicit bundled conversion engines. This replaces the proposed Rust supervisor to deliver and verify the application on the available Ubuntu toolchain. Packaging includes Python and its modules; users do not install a Python environment.

## Users

Ubuntu desktop users converting local files while working in Files and other applications.

## Product Purpose

Drag files through contextual radial categories, choose an output or editing operation, and receive validated copies without changing the originals.

## Operating Context

Ubuntu 24.04 GNOME Wayland is the current development environment. Ubuntu 26.04 is a qualification target, not a tested platform yet. A GNOME companion coordinates global invocation; the independent application accepts native drag/drop, a file picker, Open With and command-line entry.

## Capabilities and Constraints

The user explicitly requires automatic installation of all conversion tooling as part of the package. No host converter discovery, first-run asset download or untested format claim is acceptable for packaged mode. Use the parity register and runtime capability manifest separately. Pages output and native reference fidelity remain unresolved until real evidence exists.

## Product Principles

- Preserve originals and publish complete, collision-safe outputs.
- Context comes from file content and available encoders, not extensions alone.
- The same operations serve radial and keyboard interfaces.
- Conversion and editing remain local, with confined parsers.
- Show real progress, limitations and recovery actions.

## Accessibility & Inclusion

Native GTK controls, complete keyboard operation, labeled list alternative, high contrast, reduced motion, readable filenames and visible errors. English is the initial locale; gettext owns user-facing text for future translation.

## Evidence on Hand

The `.aiwg` planning baseline contains public vendor research, requirements and three independent planning reviews. It does not certify an implemented application or a native Tangerine comparison.
