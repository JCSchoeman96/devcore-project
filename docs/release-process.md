# Release process

Status: current canonical process. The first repository-owned release, `v1.0.1`, was published on 2026-10-23 from source commit `1266b221af90c318db54306eeb926afb873088c6`. Post-merge CI run `39944654664` passed on that commit. The `devcore-project` asset SHA-256 is `7b9c5a17abcc3d5591e3ba872b87f4ec27cf17bf367ddc9b8e8bb6716b2b030d`.

The canonical source is the default branch of `JCSchoeman96/devcore-project`. Consumer repositories pin neither source files nor a moving executable URL; workstation users install explicit release assets.

Use SemVer tags named `vMAJOR.MINOR.PATCH`. Preserve the documented v1 consumer contract in patch releases. Add a minor version for backward-compatible contract capabilities. Use a major version for incompatible project declarations or command behavior. Record consumer migration steps before a breaking release.

For each release:

1. Review the exact source commit and its provenance changes.
2. Run Bash syntax checks, ShellCheck, checksum checks, and the complete unittest suite.
3. Create the executable asset from that exact commit and generate its SHA-256 file.
4. Publish the version and checksum manifest with the release.
5. Verify the release asset checksums and exercise install, update, and rollback in temporary `HOME` directories.
6. Record the release commit, tag, asset checksums, CI run, and migration impact.

TICK-45 established the canonical source without creating a tag or release. TICK-48 published the first repository-owned version, `1.0.1`, from the exact reviewed commit above. It preserves the installed snapshot's effective behavior and the existing v1 consumer contract, while recording canonical source, tests, installation, and rollback. The archived `-c` ownership query is a defect; this baseline retains the corrected stdin form from the installed snapshot. Existing v1-style consumer `.devcore/` declarations remain compatible. Supplemental-secret configuration is not included and remains TICK-43 work.
