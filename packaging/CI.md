# GitHub verification workflow

The tested verification definition is in `verify.github-actions.yml`. GitHub rejected the initial source push because the authenticated OAuth credential has repository permission but lacks the separate `workflow` scope. The application source was published with the definition retained as a template; no GitHub Actions success is claimed.

After completing `gh auth refresh --hostname github.com --scopes workflow`, activate it:

```bash
mkdir -p .github/workflows
git mv packaging/verify.github-actions.yml .github/workflows/verify.yml
git commit -m 'Enable Ubuntu verification workflow'
git push
```

The workflow installs explicit dependencies, compiles the native helpers, runs the application suite and real native GUI/drag/indicator checks, and validates the inventory. A manual input optionally builds and verifies the complete offline installer. Local evidence for the published installer is committed under `.aiwg/testing/evidence/0.1.0`.
