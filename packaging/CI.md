# GitHub verification workflows

GitHub workflow authorization is complete. `.github/workflows/verify.yml` installs explicit dependencies, compiles the native helpers, runs application and native GUI/drag/indicator checks, and validates the inventory. A manual input optionally builds the complete offline installer.

The manual `mirror-sources.yml` workflow reconstructs the five corresponding-source assets from their pinned original URLs, verifies every content hash and reproduces the exact archive hashes recorded in `packaging/source-archives-0.1.0.json`, then uploads them to the existing draft release. It uses only the current repository’s temporary GitHub token. It does not publish the draft or alter the tested installer.

Local evidence is committed under `.aiwg/testing/evidence/0.1.0`. CI outcomes are recorded separately after the runs complete.
