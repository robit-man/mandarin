# Snap Store preview submission

Registered name: `mandarin`. Snap ID: `tAdZZICCxYWgHTZ8UARl7mYrPdP5flwA`. Display name: Mandarin.

Summary: Offline file conversion through a contextual radial menu.

Category: Utilities. Publisher must be the authenticated Ubuntu One account; GitHub authentication does not authorize the store.

Description: Convert local images, video, audio, documents, PDFs, spreadsheets, subtitles and archives. Drag through contextual categories and release onto an operation, or use the grouped keyboard list. Image tools provide local previews. A native taskbar indicator opens the app, adds files, reports active jobs and quits. The complete conversion runtime, codecs, filters, fonts and recognition assets are included.

Preview limits: Pages output, editable PDF reconstruction, advanced editor modes, full global GNOME integration and all-reference fidelity remain qualification gates. The installed strict Snap passed health, 12 representative conversion routes, nested-worker confinement, GUI launch and taskbar menu lifecycle on Ubuntu 24.04 GNOME 46. Full strict-confinement file access and real-device sharing qualification remain open. External disks require the removable-media interface. The `.deb` remains the independently tested distribution lane. Do not publish this Snap as stable until these gates pass.

Submission status: Canonical's publisher agreement was accepted and `mandarin` was registered on 19 October 2026. Revision 1 (0.1.0 amd64) was uploaded through the [edge workflow](https://github.com/robit-man/mandarin/actions/runs/39340289856). Store metadata upload succeeded after the first revision arrived. The Store reports `ReviewInProgress`; no channel is released yet. The uploaded SHA3-384 matches the tested Snap. See [submission evidence](../.aiwg/testing/evidence/0.1.0/store-submission-results.json). The `.deb` and Snap payloads strip privileged modes, group/other write permissions and extended attributes.

Initial channel: edge. License: MIT for Mandarin; bundled components retain their own licenses and corresponding-source assets. Support/source: https://github.com/robit-man/mandarin.

Build: `python3 scripts/build_snap.py` after the full payload. Validate metadata with `snap pack --check-skeleton build/snap-root`. Qualify the resulting Snap on Ubuntu, then authenticate with `snapcraft login`, reserve the name using `snapcraft register mandarin`, upload using `snapcraft upload --release=edge dist/mandarin_0.1.0_amd64.snap`, and upload metadata with `snapcraft upload-metadata`. Store review or interface-connection approval may still be required; record the actual outcome.

The manual GitHub workflow `store-edge.yml` downloads the public release and requires the tested Snap SHA256. Its `SNAPCRAFT_EDGE_CREDENTIALS` secret must contain a short-lived `snapcraft export-login` credential restricted to `mandarin`, channel `edge`, and `package_access,package_push,package_release`. Delete that secret and the local export file after the submission finishes. The workflow does not publish stable releases.
