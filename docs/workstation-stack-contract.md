# DevCore workstation stack contract

Status: observed workstation contract as of 2026-10-23.

## Ownership and source

The workstation infrastructure owner controls the shared service stack, its Compose file, local service credentials, containers, images, volumes, and lifecycle. DevCore uses the configured endpoints and existing containers to provision project PostgreSQL roles and databases. It does not start, stop, restart, recreate, upgrade, or remove shared services or volumes.

The current stack definition is `/opt/stacks/dev-core/compose.yaml`. The Compose project is `dev-core`, with working directory `/opt/stacks/dev-core`. Its `.env` supplies administrator credentials. This contract records names and non-secret settings only.

## PostgreSQL allocations

DEV and TEST use separate PostgreSQL containers, host ports, and persistent data volumes.

| Profile | Compose service and container | Workstation endpoint | Image and server version | Admin identity | Data and restart policy |
| --- | --- | --- | --- | --- | --- |
| DEV | `postgres-dev`, `dev-core-postgres-dev-1` | `127.0.0.1:55432` | `postgres:18.6-alpine`, server `18.6` | `devcore_admin` | `dev-core_postgres_dev_data` at `/var/lib/postgresql`; `unless-stopped` |
| TEST | `postgres-test`, `dev-core-postgres-test-1` | `127.0.0.1:55433` | `postgres:18.6-alpine`, server `18.6` | `devcore_admin` | `dev-core_postgres_test_data` at `/var/lib/postgresql`; `unless-stopped` |

Both active PostgreSQL containers use image ID and repository digest `sha256:77f585114c32fbca283dc835b0596f4e52b51b4c6662d7810b2f4084f60a1873`. The Compose file names a version tag but does not pin that digest, so a later pull may resolve to another image.

The Compose configuration initializes host authentication with `scram-sha-256`. The `devcore_admin` identity is the workstation bootstrap administrator used by DevCore for role and database provisioning. Project owner roles remain separate from this administrator. Each project declares its DEV and TEST owner roles and databases in `.devcore/project.conf`.

NewYou CI also uses the `postgres:18.6-alpine` image tag. Its current GitHub Actions service configuration sets `POSTGRES_HOST_AUTH_METHOD: trust`, while the workstation stack uses SCRAM host authentication. The image tag and PostgreSQL server version match; the authentication policy does not. CI also uses the image tag without pinning its digest.

## Optional Redis allocations

The shared stack also defines Redis DEV and TEST services for consumers that opt in. NewYou declares `USE_REDIS=no` and does not use either Redis endpoint.

| Profile | Compose service and container | Workstation endpoint | Image and observed version | Data policy |
| --- | --- | --- | --- | --- |
| DEV | `redis-dev`, `dev-core-redis-dev-1` | `127.0.0.1:56379` | `redis:7-alpine`, server `7.4.8` | Persistent `dev-core_redis_dev_data` volume at `/data`; AOF enabled; `unless-stopped` |
| TEST | `redis-test`, `dev-core-redis-test-1` | `127.0.0.1:56380` | `redis:7-alpine`, server `7.4.8` | `/data` uses `tmpfs`; persistence is disabled |

DevCore checks Redis only when a project sets `USE_REDIS=yes`. Its check uses a temporary probe key with the project prefix and removes it afterward.

## Observed service drift

The active Redis TEST container has `unless-stopped` as its restart policy. The current Compose definition omits a restart policy, whose default is `no`. The container's Compose metadata records version `5.5.1` and image digest `sha256:4bfd9eca23339865dc14fe75f6d9ae643f714924623978dd2798f1a673b08f43`; its current image ID is `sha256:8b81dd37ff027bec4e516d41acfbe9fe2460070dc6d4a4570a2ac5b9d59df065`. Its tag, `tmpfs` data policy, and lack of named mounts match the current Compose definition.

This is a recorded difference between the active container and its source definition. DevCore did not change the Compose file, containers, or volumes during this inspection. The workstation infrastructure owner retains lifecycle responsibility for reconciling the difference.
