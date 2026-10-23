# Security policy

DevCore handles workstation-local database credentials. Never put real secrets in this repository, its Git history, tests, CI, logs, issues, or release assets.

Report security defects through a private GitHub security advisory for this repository when that feature is available. If it is unavailable, contact the repository owner through GitHub privately. Do not include credentials or secret-bearing files in a report.

Tests must use synthetic, disposable values. Command failures and test diagnostics must not print secret values. Keep shell tracing disabled while handling secrets.

DevCore operates against services owned by the workstation's shared infrastructure contract. It may connect to those services or execute the configured PostgreSQL provisioning operations, but it must not start, stop, recreate, or replace those services unless a separately reviewed contract explicitly assigns that lifecycle to DevCore.
