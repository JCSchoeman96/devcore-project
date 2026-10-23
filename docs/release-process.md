# Release process

Status: current canonical process. The latest release, `v1.1.0`, was published on 2026-10-23. Tag [`v1.1.0`](https://github.com/JCSchoeman96/devcore-project/releases/tag/v1.1.0) points exactly to source commit `60f2ef09e52abca7b20f1572795579a549ba9d61`. Post-merge CI run `39967037057` passed on that commit. The `devcore-project` asset SHA-256 is `df7dd3263197d33416b99699b5f09ee2b37bb4a45f55cc2a7bb4164dbbff9568`. This backward-compatible v1 contract extension adds optional supplemental-secret delivery; existing owner-only v1 consumers remain compatible. Durable Ticketing adoption remains TICK-42.

The canonical source is the default branch of `JCSchoeman96/devcore-project`. Consumer repositories pin neither source files nor a moving executable URL; workstation users install explicit release assets.

Use SemVer tags named `vMAJOR.MINOR.PATCH`. Preserve the documented v1 consumer contract in patch releases. Add a minor version for backward-compatible contract capabilities. Use a major version for incompatible project declarations or command behavior. Record consumer migration steps before a breaking release.

For each release:

1. Review the exact source commit and its provenance changes.
2. Run Bash syntax checks, ShellCheck, checksum checks, and the complete unittest suite.
3. Create the executable asset from that exact commit and generate its SHA-256 file.
4. Publish the version and checksum manifest with the release.
5. Verify the release asset checksums and exercise install, update, and rollback in temporary `HOME` directories.
6. Record the release commit, tag, asset checksums, CI run, and migration impact.

TICK-45 established the canonical source without creating a tag or release. TICK-48 published the first repository-owned version, `1.0.1`, from its exact reviewed commit. It preserves the installed snapshot's effective behavior and the existing v1 consumer contract, while recording canonical source, tests, installation, and rollback. The archived `-c` ownership query is a defect; that baseline retained the corrected stdin form from the installed snapshot. Existing v1-style consumer `.devcore/` declarations remain compatible. At the time of TICK-48, supplemental-secret configuration was not included. TICK-43 later delivered that backward-compatible extension in v1.1.0.
