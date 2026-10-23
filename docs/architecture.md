# Architecture

Status: current canonical implementation baseline for DevCore 1.1.0 (proposed). Repository owner: `JCSchoeman96`, who created and owns all DevCore materials. Source history begins with the TICK-45 canonicalization branch. The recovered v1.0.0 artifacts have no recovered historical Git source history and are not represented as canonical Git source. See [provenance](provenance.md).

## Ownership

This repository owns the shared `devcore-project` executable, its project configuration contract, rendering and profile behavior, installer and rollback scripts, tests, CI, and release/versioning process.

Ticketing, EventSales, and other application repositories own only their tracked `.devcore/project.conf`, `render-map.tsv`, templates, and ignore rules. They are consumers of this tool.

The workstation-local secret file under `~/.config/dev-core/` is the source for DEV and TEST owner secrets. It is outside Git. The executable reads it to provision the configured database roles and render local environment files. It does not export the values in normal status output.

## Command flow

- `plan` parses the project and workstation allocation, then reports non-secret endpoints, role names, output paths, and whether each configured owner secret exists.
- `activate` initializes missing workstation config, creates missing DEV/TEST owner secrets, provisions the configured PostgreSQL roles and databases, renders ignored environment files, and checks configured services.
- `doctor` validates available credentials and checks configured endpoints. PostgreSQL checks authenticate without changing database state. Redis checks use a short-lived, project-prefixed probe key and remove it.
- `render` regenerates ignored environment files from the current templates and owner secrets.
- `run PROFILE -- COMMAND` removes declared supplemental variables from the parent environment, adds the rendered files for `PROFILE` and `all`, applies declared supplemental secrets from the workstation store, then replaces itself with the requested command.
- `rotate` rotates both owner credentials, synchronizes the configured database roles, re-renders local files, and checks connectivity.

The tool calls `docker exec` for existing PostgreSQL/Redis containers when required. It does not manage container lifecycle. Shared service ownership remains with the workstation infrastructure owner.

## Baseline limits

The contract has one DEV owner-secret binding and one TEST owner-secret binding. Optional supplemental-secret bindings (see [project contract](project-contract.md)) deliver additional workstation-local secrets without owner provisioning. Supplemental secrets are not generated or rotated by DevCore.

No application runtime should copy this executable into product code. The executable is a workstation development tool, not a production credential manager.
