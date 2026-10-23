# Consumer project contract

Status: current documented consumer contract. DevCore 1.0.1 projects remain compatible; 1.1.0 adds optional supplemental-secret delivery.

## Files a consumer owns

Each application repository owns the non-secret `.devcore/project.conf`, `.devcore/render-map.tsv`, and templates that adapt generic tokens to that application's configuration names. The consumer also owns Git ignore rules for every render target.

The workstation owns `~/.config/dev-core/dev-core.conf` and `~/.config/dev-core/project-db.env`. The latter contains owner credentials and must remain local with restrictive permissions.

## `project.conf`

The v1 parser reads plain `KEY=value` lines. It ignores blank lines and lines whose first non-space character is `#`; it does not evaluate shell syntax. The first matching key wins in `.devcore/project.conf`, `dev-core.conf`, and `project-db.env`. These fields define the complete current project-file contract:

| Key | Requirement | Validation or default | Purpose |
| --- | --- | --- | --- |
| `PROJECT_KEY` | Required | `^[a-z0-9][a-z0-9_-]*$` | Stable project allocation name. |
| `DEV_DB_ROLE` | Required | `^[a-z][a-z0-9_]{0,62}$` | DEV PostgreSQL owner role. |
| `DEV_DB_NAME` | Required | `^[a-z][a-z0-9_]{0,62}$` | DEV PostgreSQL database. |
| `TEST_DB_ROLE` | Required | `^[a-z][a-z0-9_]{0,62}$` | TEST PostgreSQL owner role. |
| `TEST_DB_NAME` | Required | `^[a-z][a-z0-9_]{0,62}$` | TEST PostgreSQL base database. |
| `DEV_SECRET_KEY` | Required | `^[A-Z_][A-Z0-9_]*$` | Name of the DEV owner secret in the workstation secret file. |
| `TEST_SECRET_KEY` | Required | `^[A-Z_][A-Z0-9_]*$` | Name of the TEST owner secret in the workstation secret file. |
| `TEST_ROLE_CREATEDB` | Optional | `yes` | Whether the TEST owner role receives `CREATEDB`; valid values are `yes` and `no`. |
| `USE_REDIS` | Optional | `yes` | Whether plan/activate/doctor run the scoped Redis checks; valid values are `yes` and `no`. |
| `REDIS_PREFIX` | Optional | `PROJECT_KEY` | Prefix for DEV and TEST Redis namespaces; must match `^[A-Za-z0-9][A-Za-z0-9:_-]*$`. |
| `RENDER_MAP` | Optional | `.devcore/render-map.tsv` | Path to the required tab-separated render map. |
| `SUPPLEMENTAL_SECRETS` | Optional | unset | Path to the optional tab-separated supplemental-secret binding map. |

`devcore-project init` writes every required field, using those same defaults. The project file contains secret names, never secret values.

### Supplemental secrets (1.1.0+)

When `SUPPLEMENTAL_SECRETS` is set, the referenced file declares delivery-only bindings from the workstation secret store into rendered profiles and `run`. DevCore does not generate, rotate, or provision these secrets and does not treat them as owner credentials.

Each non-comment row has three tab-separated columns:

```text
PROFILE<TAB>ENV_VAR<TAB>SECRET_KEY
```

- `PROFILE` is `dev`, `test`, or `all`. A `dev` or `test` binding applies to that profile and to rendered rows for that profile. An `all` binding applies to every `run` profile and only to render-map rows whose profile is `all`.
- `ENV_VAR` is the output environment variable name (`^[A-Z_][A-Z0-9_]*$`). Templates may reference it as `{{ENV_VAR}}` only when the same variable is declared here.
- `SECRET_KEY` is the workstation-local secret name (`^[A-Z_][A-Z0-9_]*$`) whose value is delivered.

Duplicate `(PROFILE, ENV_VAR)` rows are rejected. If the same `ENV_VAR` would be supplied by more than one applicable binding for a profile, validation fails closed. Missing declared secrets fail `plan`, `render`, `doctor`, `activate`, and `run` without printing secret values. `run` removes declared supplemental variables from the parent environment before applying governed profile values.

### Workstation `dev-core.conf`

The optional `~/.config/dev-core/dev-core.conf` file uses the same plain `KEY=value` syntax. Each key is optional; these are the v1 defaults:

| Key | Default | Use |
| --- | --- | --- |
| `PG_DEV_HOST` | `127.0.0.1` | DEV PostgreSQL host and `DEV_DB_HOST` template value. |
| `PG_DEV_PORT` | `55432` | DEV PostgreSQL port and `DEV_DB_PORT` template value. |
| `PG_TEST_HOST` | `127.0.0.1` | TEST PostgreSQL host and `TEST_DB_HOST` template value. |
| `PG_TEST_PORT` | `55433` | TEST PostgreSQL port and `TEST_DB_PORT` template value. |
| `REDIS_DEV_HOST` | `127.0.0.1` | DEV Redis host and `REDIS_DEV_HOST` template value. |
| `REDIS_DEV_PORT` | `56379` | DEV Redis port and `REDIS_DEV_PORT` template value. |
| `REDIS_TEST_HOST` | `127.0.0.1` | TEST Redis host and `REDIS_TEST_HOST` template value. |
| `REDIS_TEST_PORT` | `56380` | TEST Redis port and `REDIS_TEST_PORT` template value. |
| `PG_DEV_CONTAINER` | `dev-core-postgres-dev-1` | Container used for DEV PostgreSQL administration. |
| `PG_TEST_CONTAINER` | `dev-core-postgres-test-1` | Container used for TEST PostgreSQL administration. |
| `REDIS_DEV_CONTAINER` | `dev-core-redis-dev-1` | Container used for DEV Redis checks. |
| `REDIS_TEST_CONTAINER` | `dev-core-redis-test-1` | Container used for TEST Redis checks. |
| `PG_ADMIN_ROLE` | `devcore_admin` | PostgreSQL administration role used by activation. |

## `render-map.tsv` and templates

Each non-comment row has three required tab-separated columns and one optional column:

```text
PROFILE<TAB>TEMPLATE<TAB>TARGET<TAB>OPTIONAL_PURGE_KEYS
```

`PROFILE` is `dev`, `test`, or `all`. Render-map validation rejects any other value, and `run PROFILE` exits before starting its child command when given an unsupported value. A `run dev` or `run test` command loads files for that profile and rows marked `all`. The invoking shell environment is inherited as well.

Templates may use these exact tokens. Consumers choose application-specific output variable names around them.

| Token | Source |
| --- | --- |
| `{{PROJECT_KEY}}` | `PROJECT_KEY`. |
| `{{DEV_DB_HOST}}`, `{{DEV_DB_PORT}}` | `PG_DEV_HOST`, `PG_DEV_PORT` from workstation config, or their defaults above. |
| `{{DEV_DB_ROLE}}`, `{{DEV_DB_NAME}}` | `DEV_DB_ROLE`, `DEV_DB_NAME`. |
| `{{DEV_DB_PASSWORD}}` | Workstation secret value named by `DEV_SECRET_KEY`. |
| `{{TEST_DB_HOST}}`, `{{TEST_DB_PORT}}` | `PG_TEST_HOST`, `PG_TEST_PORT` from workstation config, or their defaults above. |
| `{{TEST_DB_ROLE}}`, `{{TEST_DB_NAME}}` | `TEST_DB_ROLE`, `TEST_DB_NAME`. |
| `{{TEST_DB_PASSWORD}}` | Workstation secret value named by `TEST_SECRET_KEY`. |
| `{{REDIS_DEV_HOST}}`, `{{REDIS_DEV_PORT}}` | DEV Redis workstation configuration, or its defaults above. |
| `{{REDIS_TEST_HOST}}`, `{{REDIS_TEST_PORT}}` | TEST Redis workstation configuration, or its defaults above. |
| `{{REDIS_DEV_NAMESPACE}}` | `REDIS_PREFIX` (or `PROJECT_KEY`) followed by `:dev`. |
| `{{REDIS_TEST_NAMESPACE_BASE}}` | `REDIS_PREFIX` (or `PROJECT_KEY`) followed by `:test`. |

The renderer rejects unresolved uppercase template tokens. Password tokens resolve only from the local workstation secret store and must be written only to ignored render targets.

Render targets must be ignored by Git. The tool writes them with mode `0600`, replaces its prior managed block, and removes variables named by the optional purge column.

## Compatibility

Repository-owned releases preserve existing v1 project files and the existing owner-secret model unless a reviewed versioned contract changes them. The examples in the recovered archive are historical evidence; this document and tests define the current supported baseline.
