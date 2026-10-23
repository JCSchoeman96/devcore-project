# Release process

Status: proposed canonical process. No repository-owned version has been released.

The canonical source is the default branch of `JCSchoeman96/devcore-project`. Consumer repositories pin neither source files nor a moving executable URL; workstation users install explicit release assets.

Use SemVer tags named `vMAJOR.MINOR.PATCH`. Preserve the documented v1 consumer contract in patch releases. Add a minor version for backward-compatible contract capabilities. Use a major version for incompatible project declarations or command behavior. Record consumer migration steps before a breaking release.

For each release:

1. Review the exact source commit and its provenance changes.
2. Run Bash syntax checks, ShellCheck, checksum checks, and the complete unittest suite.
3. Create the executable asset from that exact commit and generate its SHA-256 file.
4. Publish the version and checksum manifest with the release.
5. Verify the release asset checksums and exercise install, update, and rollback in temporary `HOME` directories.
6. Record the release commit, tag, asset checksums, CI run, and migration impact.

No tag or release is part of TICK-45. The proposed first repository-owned version is `1.0.1`: the chosen code preserves the installed snapshot's effective behavior and the existing consumer contract, while the versioned change records canonical source, tests, installation, and rollback. The archived `-c` ownership query is a defect; this baseline retains the corrected stdin form from the installed snapshot. A later implementation that adds supplemental-secret configuration must use its own reviewed version decision.
