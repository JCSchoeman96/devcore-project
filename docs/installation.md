# Installation and update

Status: proposed user-local installer. It has been tested only in temporary directories for this review. It has not replaced the installed workstation executable.

## Requirements

Use Bash, GNU `date` with nanosecond formatting, `flock`, `stat`, `sha256sum`, `awk`, `install`, `mktemp`, `mv`, and a non-root user account. Install and update use the same checksum-verifying script.

## Install or update

Download the executable and checksum file from an authorized repository release. Verify the checksum before installation, then pass the exact release version and digest to the installer:

```sh
gh release download v1.0.1 --repo JCSchoeman96/devcore-project \
  --pattern devcore-project --pattern devcore-project.sha256
sha256sum --check --status devcore-project.sha256
expected_sha256="$(awk 'NR == 1 { print $1 }' devcore-project.sha256)"
bash install/install.sh \
  --source ./devcore-project \
  --version 1.0.1 \
  --sha256 "$expected_sha256"
```

The example version is proposed only. No `v1.0.1` release exists yet.

The installer validates the supplied digest, the executable's embedded version, its Bash syntax, and its interpreter line before writing. It installs to `~/.local/bin/devcore-project` with mode `0700`. Install, update, and rollback share an exclusive non-blocking lock at `~/.local/bin/.devcore-project-operation.lock`; an overlapping operation fails without changing the executable. The lock must be owned by the current user and have mode `0600`; symlinks and non-regular lock paths are rejected. The kernel releases the lock when the process exits. Updates stage the verified file in the same directory and atomically replace the target. If a prior target exists, the installer saves a mode `0700` copy as `devcore-project.previous.<global sequence>.<nanosecond UTC timestamp>.<pid>` before replacement. The fixed-width global sequence determines rollback order, so wall-clock adjustments cannot reorder backups; the timestamp and PID remain diagnostic metadata. It refuses symlink targets, symlinked `~/.local` or `~/.local/bin` directories, and paths that resolve outside `HOME`.

The installer never downloads unpinned content, uses `sudo`, or changes the user's installed command unless the user runs it. Failed verification leaves the existing executable untouched.

## Roll back

Run:

```sh
bash install/rollback.sh
```

Rollback selects the valid backup with the greatest global sequence, validates its Bash syntax and version marker, stages it in the same directory, and atomically restores it. The replaced executable is kept as `devcore-project.rolled-back.<nanosecond UTC timestamp>.<pid>`. Rollback rejects symlink targets and does not accept a caller-supplied destination path.

## Release asset contract

A future release must attach the executable as `devcore-project` and its SHA-256 manifest as `devcore-project.sha256`. CI and the release process must derive both from the exact tagged commit. The checksum authenticates bytes against the release manifest; it is not a digital signature. Do not tag or install a release until its exact source and checks have been reviewed and release authorization is recorded.
