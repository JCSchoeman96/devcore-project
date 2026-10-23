# Changelog

## 1.1.0 (unreleased)

Backward-compatible contract extension for explicit supplemental-secret delivery.

- Add optional `SUPPLEMENTAL_SECRETS` project declaration pointing at a tab-separated binding map: `PROFILE<TAB>ENV_VAR<TAB>SECRET_KEY`.
- Deliver declared workstation-local secrets into rendered profiles and `run` without generating, rotating, or provisioning owner credentials.
- Fail closed when a declared supplemental secret is missing; reject duplicate `(profile, env_var)` bindings and ambiguous profile overlap.
- Scrub declared supplemental variables from the parent shell before `run` applies governed profile values.

## 1.0.1 (released 2026-10-23)

The first repository-owned baseline adopts the behavior of the installed workstation snapshot, with an explicit version bump and canonical source history.

- Retain the stdin-based PostgreSQL ownership query from the installed snapshot. The recovered archive passes a psql variable expression through `-c`, where psql-specific variable interpolation is unsupported.
- Add automated tests for the v1 consumer contract, secret-safe output, profile rendering, mocked activation and doctor flows, and user-local installation and rollback.
- Add checksum-verified installation and backup-based rollback. The installer does not run as root.
- Preserve first-match configuration parsing across project, workstation, and secret files; reject unknown render and run profiles.
- Send PostgreSQL doctor fallback passwords through Docker stdin instead of Docker client arguments.
- Preserve both legacy artifacts with their original checksums and document their provenance limits.

Release provenance: tag [`v1.0.1`](https://github.com/JCSchoeman96/devcore-project/releases/tag/v1.0.1) points to source commit `1266b221af90c318db54306eeb926afb873088c6`. Post-merge CI run `39944654664` passed on that commit. The `devcore-project` asset SHA-256 is `7b9c5a17abcc3d5591e3ba872b87f4ec27cf17bf367ddc9b8e8bb6716b2b030d`. Existing v1-style consumer `.devcore/` declarations remain compatible.
