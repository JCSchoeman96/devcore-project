# DevCore Project

`devcore-project` is the shared workstation tool for declaring and using project-local DEV and TEST environments. This repository owns the executable, project contract, rendering behavior, installer, tests, and releases.

Application repositories own only their tracked `.devcore/` declarations and templates. They consume DevCore and do not copy its executable into product code.

The contract binds one owner secret for DEV and one for TEST. Optional supplemental-secret bindings (v1.1.0+) deliver additional workstation-local secrets into declared profiles without changing owner provisioning. See [project contract](docs/project-contract.md).

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

The current release is [`v1.1.0`](https://github.com/JCSchoeman96/devcore-project/releases/tag/v1.1.0), from source commit `60f2ef09e52abca7b20f1572795579a549ba9d61`. The `devcore-project` asset SHA-256 is `df7dd3263197d33416b99699b5f09ee2b37bb4a45f55cc2a7bb4164dbbff9568`; post-merge CI run `39967037057` passed on that commit. It preserves existing v1 owner-only consumers and adds optional, backward-compatible supplemental-secret delivery through `SUPPLEMENTAL_SECRETS`. Durable Ticketing adoption remains TICK-42. The first repository-owned baseline, [`v1.0.1`](https://github.com/JCSchoeman96/devcore-project/releases/tag/v1.0.1), and recovered v1.0.0 files remain part of the release history; the recovered files are provenance evidence, not canonical source. See [provenance](docs/provenance.md).

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
