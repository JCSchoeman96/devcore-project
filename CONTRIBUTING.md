# Contributing

Keep this repository as the canonical shared-tool source. Consumer repositories may declare project-level `.devcore/` configuration, but they must not become alternate owners of the executable or renderer.

Before changing the tool, read [architecture](docs/architecture.md), [project contract](docs/project-contract.md), and [security model](docs/security-model.md). Preserve compatibility with v1 project declarations unless a reviewed change explicitly versions that contract.

Use synthetic credentials and temporary directories in tests. The fast unittest suite mocks Docker and database clients. A separate opt-in PostgreSQL integration suite uses two disposable `postgres:18.6-alpine` containers to exercise real database behavior; run it with `DEVCORE_RUN_POSTGRES_INTEGRATION=1 python3 -m unittest tests.test_postgres_integration -v`. The integration suite cleans up its containers. Do not run tests against workstation DEV or TEST databases, alter their service lifecycles, rotate their credentials, or print secret values.

Run the commands in the README and review the tracked diff for secrets, generated local files, and unrelated changes. Changes to the project contract or secret handling require focused security tests and a documented compatibility impact.

Repository changes are reviewed through pull requests. Do not tag or publish releases as part of an unapproved implementation task.
