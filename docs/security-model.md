# Security model

Status: current security baseline for the repository-owned DevCore 1.0.1 v1-compatible tool.

## Secret storage and handling

The v1 contract stores DEV and TEST owner passwords in the workstation-local `~/.config/dev-core/project-db.env` file, normally with mode `0600`; the containing config directory uses mode `0700`. Real values must never enter Git, tests, CI, issue trackers, logs, or release files.

The renderer writes secret-bearing local environment files with mode `0600`. A consumer must ensure every render target is ignored by Git. The tool refuses to render a tracked or otherwise non-ignored target when it detects a Git worktree.

The CLI disables shell xtrace and rejects secret-handling commands if xtrace is enabled. `plan`, `doctor`, and ordinary errors report secret-key names or presence, not values. Tests use synthetic values and assert that captured command output does not contain them.

`install`, `activate`, `rotate`, and `render` take nonblocking exclusive locks before changing workstation state or reading secrets for output. The lock files live in the fixed account-owned `~/.config/dev-core/locks` directory and are named from SHA-256 hashes of the normalized secret-store and global-configuration paths. Commands acquire both locks in sorted filename order and keep both descriptors open through execution. The lock directory must be owned by the current user with mode `0700`; each lock must be a regular, non-symlink file owned by the current user with mode `0600`, have one link, and match its open descriptor's device and inode. A command exits before provisioning or rendering if another mutation holds either lock or if validation fails. The operating system releases the locks when the process exits.

`DEVCORE_SECRETS_FILE` and `DEVCORE_GLOBAL_CONF` remain arbitrary file-path overrides. Their normalized paths determine the lock identities, so processes with different `DEVCORE_CONFIG_DIR` values still contend when they point at the same state file. Final-component symlinks are rejected, while symlinked parent paths resolve to the same lock identity. Existing central state files must be regular files owned by the current user with mode `0600`; symlinks and files with additional hard links fail closed. Initialization creates each missing file atomically without replacing a file that appears concurrently.

`plan`, `doctor`, and `run` do not initialize or repair central state. They read existing files, use documented endpoint defaults where possible, and report missing required credentials or rendered files. Use `install` or `activate` to initialize workstation state.

When workstation `psql` is unavailable, `doctor` sends the password to the existing container over `docker exec -i` standard input. The container shell exports it for `psql`; the local Docker client's argument vector and temporary files do not contain the password.

The PostgreSQL portion of `doctor` uses an authenticated, read-only query to check role identity, database ownership, privilege flags, and role memberships. DEV must remain NOCREATEDB; TEST `CREATEDB` must match the consumer contract. Neither owner role may have role memberships. Drift is reported without revoking memberships or changing PostgreSQL state.

## Database and service boundaries

`activate` may create or alter the configured PostgreSQL owner roles and create their databases. `rotate` changes both configured owner passwords. These operations run only when a workstation user invokes the relevant command. DEV is provisioned without `CREATEDB`; the configured TEST role may use it when the consumer contract says `TEST_ROLE_CREATEDB=yes`.

DevCore expects shared services to exist already. It may inspect containers and execute SQL or Redis probes through them. It does not start, stop, recreate, delete, or replace those services.

The tool does not treat workstation credentials as production credentials. Application repositories remain responsible for their own deployment secrets and runtime identities.

## Repository and CI

CI uses synthetic data and local mocks. It has no access to workstation secret files or databases. Do not add a real `.env`, secret-bearing fixture, private key, or credential-bearing command transcript.

The user, JCSchoeman96, created and owns all DevCore materials. This repository is publicly visible on GitHub. It has no `LICENSE` file, and no additional open-source license grant has been declared. Historical Git provenance for the recovered artifacts was not recovered; see [provenance](provenance.md).
