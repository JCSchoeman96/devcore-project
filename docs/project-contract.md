# Consumer project contract

Status: proposed canonical documentation of the v1.0.0-style `.devcore/` contract.

## Files a consumer owns

Each application repository owns the non-secret `.devcore/project.conf`, `.devcore/render-map.tsv`, and templates that adapt generic tokens to that application's configuration names. The consumer also owns Git ignore rules for every render target.

The workstation owns `~/.config/dev-core/dev-core.conf` and `~/.config/dev-core/project-db.env`. The latter contains owner credentials and must remain local with restrictive permissions.

## `project.conf`

The v1 parser reads these keys:

| Key | Purpose |
| --- | --- |
| `PROJECT_KEY` | Stable project allocation name. |
| `DEV_DB_ROLE`, `DEV_DB_NAME` | DEV PostgreSQL owner role and database. |
| `TEST_DB_ROLE`, `TEST_DB_NAME` | TEST PostgreSQL owner role and base database. |
| `DEV_SECRET_KEY`, `TEST_SECRET_KEY` | Names of the two owner secrets in the workstation secret file. |
| `TEST_ROLE_CREATEDB` | `yes` or `no`; controls `CREATEDB` for the TEST owner role. |
| `USE_REDIS` | `yes` or `no`. |
| `REDIS_PREFIX` | Project prefix used by scoped Redis probes. |
| `RENDER_MAP` | Path to the tab-separated render map. |

The project file contains secret names, never secret values. The contract does not include supplemental-secret bindings.

## `render-map.tsv` and templates

Each non-comment row has three required tab-separated columns and one optional column:

```text
PROFILE<TAB>TEMPLATE<TAB>TARGET<TAB>OPTIONAL_PURGE_KEYS
```

`PROFILE` is `dev`, `test`, or `all`. A `run dev` or `run test` command loads files for that profile and rows marked `all`. The invoking shell environment is inherited as well.

Templates can use the current generic tokens for project key, DEV/TEST PostgreSQL hosts, ports, roles, database names, the two owner passwords, and Redis endpoint/namespace values. The renderer rejects unresolved uppercase template tokens. Consumers choose application-specific output variable names.

Render targets must be ignored by Git. The tool writes them with mode `0600`, replaces its prior managed block, and removes variables named by the optional purge column.

## Compatibility

Repository-owned releases preserve existing v1 project files and the existing owner-secret model unless a reviewed versioned contract changes them. The examples in the recovered archive are historical evidence; this document and tests define the current supported baseline.
