# Third-party software

The MIT license covers Mandarin's own source. Separately distributed conversion engines, libraries, fonts, recognition data and test fixtures retain their respective upstream licenses.

The installer includes the exact package/version/file inventory in `/opt/mandarin/runtime-manifest.json` and the original Debian copyright/license notices under `/opt/mandarin/runtime/usr/share/doc`. No Tangerine code, artwork or binary is included.

Each binary release provides `corresponding-sources.json` and numbered `mandarin-0.1.0-corresponding-sources-*.tar` assets beside the installer. These contain the exact Ubuntu source packages, original tarballs and Debian/Ubuntu patches/build instructions for the bundled package versions. The manifest records source URLs, sizes and SHA256 checksums. The sources are separate downloads; installation does not fetch or build them.

Reproduce that collection with `python3 scripts/collect_sources.py` on the packaging machine. Collection fails on missing descriptors or checksum/size mismatches. Native app/launcher source and build scripts are in this repository. A release must not upload a bundled binary unless its complete source collection and notices are available alongside it.

The committed presentation fixture is original synthetic content generated using python-pptx; its tool license is in `tests/fixtures/python-pptx-LICENSE`. The RAR5 fixture comes from libarchive; its pinned origin/checksum and license are in `tests/fixtures/libarchive-source.json` and `tests/fixtures/libarchive-COPYING`.
