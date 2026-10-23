# Changelog

## 1.0.1 (proposed, not released)

The first repository-owned baseline adopts the behavior of the installed workstation snapshot, with an explicit version bump and canonical source history.

- Retain the stdin-based PostgreSQL ownership query from the installed snapshot. The recovered archive passes a psql variable expression through `-c`, where psql-specific variable interpolation is unsupported.
- Add automated tests for the v1 consumer contract, secret-safe output, profile rendering, mocked activation and doctor flows, and user-local installation and rollback.
- Add checksum-verified installation and backup-based rollback. The installer does not run as root.
- Preserve first-match configuration parsing across project, workstation, and secret files; reject unknown render and run profiles.
- Send PostgreSQL doctor fallback passwords through Docker stdin instead of Docker client arguments.
- Preserve both legacy artifacts with their original checksums and document their provenance limits.

No release tag has been created. Independent review and later release authorization are required.
