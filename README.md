# DevCore Project

`devcore-project` is the shared workstation tool for declaring and using project-local DEV and TEST environments. This repository owns the executable, project contract, rendering behavior, installer, tests, and releases.

Application repositories own only their tracked `.devcore/` declarations and templates. They consume DevCore and do not copy its executable into product code.

The current v1 contract binds one owner secret for DEV and one for TEST. It stores those values in the workstation-local DevCore secret file, renders ignored local environment files, and runs commands with the selected profile. TICK-45 does not add supplemental-secret bindings.

## Use

See [installation](docs/installation.md) for the user-local install and update procedure. See [project contract](docs/project-contract.md) before changing a consumer's `.devcore/` files.

Common commands from a consumer repository:

```sh
devcore-project plan
devcore-project doctor
devcore-project run dev -- <command>
devcore-project run test -- <command>
```

`activate` checks and provisions configured project database roles/databases, renders ignored environment files, and checks connectivity. It does not start, stop, or recreate shared services. Read the [security model](docs/security-model.md) before using credential-management commands.

## Repository status

The first repository-owned governed baseline was released as [`v1.0.1`](https://github.com/JCSchoeman96/devcore-project/releases/tag/v1.0.1) from source commit `1266b221af90c318db54306eeb926afb873088c6`. The `devcore-project` asset SHA-256 is `7b9c5a17abcc3d5591e3ba872b87f4ec27cf17bf367ddc9b8e8bb6716b2b030d`; post-merge CI run `39944654664` passed on that commit. The release preserves the v1 consumer contract and existing v1-style `.devcore/` declarations. Supplemental-secret support is not included and remains TICK-43 work. The recovered v1.0.0 files remain historical provenance, not canonical source. See [provenance](docs/provenance.md).

The user, JCSchoeman96, created and owns all DevCore materials. This repository is publicly visible on GitHub. It has no `LICENSE` file, and no additional open-source license grant has been declared. Historical Git provenance for the recovered v1.0.0 artifacts was not recovered; see [provenance](docs/provenance.md).

## Development

Requirements are Bash, Python 3, and standard Unix command-line utilities. The automated tests use temporary directories, synthetic credentials, and mocked Docker/PostgreSQL commands.

```sh
bash -n bin/devcore-project install/install.sh install/rollback.sh
shellcheck bin/devcore-project install/install.sh install/rollback.sh
python3 -m unittest discover -s tests -v
(cd provenance/legacy-v1.0.0 && sha256sum --check SHA256SUMS)
```

See [contributing](CONTRIBUTING.md), [architecture](docs/architecture.md), and [release process](docs/release-process.md).
