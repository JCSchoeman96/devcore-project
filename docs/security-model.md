# Security model

Status: current security baseline for the repository-owned DevCore 1.0.1 v1-compatible tool.

## Secret storage and handling

The v1 contract stores DEV and TEST owner passwords in the workstation-local `~/.config/dev-core/project-db.env` file, normally with mode `0600`; the containing config directory uses mode `0700`. Real values must never enter Git, tests, CI, issue trackers, logs, or release files.

The renderer writes secret-bearing local environment files with mode `0600`. A consumer must ensure every render target is ignored by Git. The tool refuses to render a tracked or otherwise non-ignored target when it detects a Git worktree.

The CLI disables shell xtrace and rejects secret-handling commands if xtrace is enabled. `plan`, `doctor`, and ordinary errors report secret-key names or presence, not values. Tests use synthetic values and assert that captured command output does not contain them.

`activate`, `rotate`, and `render` take one nonblocking exclusive lock at `.devcore-project.lock` beneath the configured central directory (default `~/.config/dev-core`) before changing workstation state or reading secrets for output. The lock directory must be owned by the current user with mode `0700`. The lock must be a regular, non-symlink file owned by the current user with mode `0600`. A command exits before provisioning or rendering if another mutation holds the lock or if either path fails validation. The operating system releases the lock when its process exits.

When workstation `psql` is unavailable, `doctor` sends the password to the existing container over `docker exec -i` standard input. The container shell exports it for `psql`; the local Docker client's argument vector and temporary files do not contain the password.

The PostgreSQL portion of `doctor` uses an authenticated, read-only query to check role identity, database ownership, privilege flags, and role memberships. DEV must remain NOCREATEDB; TEST `CREATEDB` must match the consumer contract. Neither owner role may have role memberships. Drift is reported without revoking memberships or changing PostgreSQL state.

## Database and service boundaries

`activate` may create or alter the configured PostgreSQL owner roles and create their databases. `rotate` changes both configured owner passwords. These operations run only when a workstation user invokes the relevant command. DEV is provisioned without `CREATEDB`; the configured TEST role may use it when the consumer contract says `TEST_ROLE_CREATEDB=yes`.

DevCore expects shared services to exist already. It may inspect containers and execute SQL or Redis probes through them. It does not start, stop, recreate, delete, or replace those services.

The tool does not treat workstation credentials as production credentials. Application repositories remain responsible for their own deployment secrets and runtime identities.

## Repository and CI

CI uses synthetic data and local mocks. It has no access to workstation secret files or databases. Do not add a real `.env`, secret-bearing fixture, private key, or credential-bearing command transcript.

The user, JCSchoeman96, created and owns all DevCore materials. This repository is publicly visible on GitHub. It has no `LICENSE` file, and no additional open-source license grant has been declared. Historical Git provenance for the recovered artifacts was not recovered; see [provenance](provenance.md).
