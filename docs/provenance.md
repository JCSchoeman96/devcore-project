# Provenance and baseline decision

Status: provenance record for canonical source and releases. Updated during TICK-49 on 2026-10-23. Neither historical artifact below is represented as historical canonical source.

## Recovered artifacts

The recovered distribution was `/home/jcschoeman96/projects/Development Docs/New Projects/devcore-project-bootstrap-v1.0.0.zip`.

- ZIP SHA-256: `011f2f0feff7943f4387d2170bfc6b2ac6a83ad63d91fe411cd21564ea78d61d`
- Bundled `bin/devcore-project` SHA-256: `d30a90ba12c5394ec573ced1cdf80362c428280f7231c186ef7d05aa489adfd5`
- All six entries named by the archive's internal checksum manifest verified against the archive.

The archive bundled script at `bin/devcore-project` is 28,577 bytes. It is preserved with the entire archive at [provenance/legacy-v1.0.0](../provenance/legacy-v1.0.0/).

The installed workstation executable was `/home/jcschoeman96/.local/bin/devcore-project`.

- File type: regular Bash script
- Mode at discovery: `0700`
- Self-reported version: `v1.0.0`
- SHA-256: `2de6b8a519e7c860eed8727d875e76ee345b6fd54a121c653e5ffb74b3ada7e8`
- Size: 28,589 bytes

An exact byte-for-byte copy of the installed file is preserved as `installed-devcore-project`. The installed file was not replaced during TICK-45.

## One known code delta

The only script diff is in the PostgreSQL database-owner verification query in `provision_database`.

The archive uses `psql -c` and supplies the query as a command-line string:

```bash
docker exec "$container" psql ... -v db="$db" \
  -c "SELECT pg_get_userbyid(datdba) FROM pg_database WHERE datname = :'db';"
```

The installed script sends the same `SELECT` through a quoted shell here-document and passes `-i` to `docker exec`:

```bash
docker exec -i "$container" psql ... -v db="$db" <<'SQL'
SELECT pg_get_userbyid(datdba)
FROM pg_database
WHERE datname = :'db';
SQL
```

Both queries read `pg_database.datdba` and return the database owner's role name. The `:'db'` syntax is psql's quoted SQL-literal variable interpolation. PostgreSQL documents that SQL passed to `-c` must be directly parsable by the server and cannot use psql-specific features; the archive form therefore does not substitute `db` and is not a valid implementation of this query. Standard input is a documented psql script input path, and psql applies its variable interpolation there. See the [PostgreSQL 18 psql documentation for `-c` and variable interpolation](https://www.postgresql.org/docs/18/app-psql.html).

The installed form is the correct behavior and the selected canonical baseline. It prevents Bash expansion through a quoted here-document and allows psql to quote the database name as a SQL literal. It does not change intended behavior: both forms express the same read-only owner lookup, but only the stdin form supports the psql variable used by the query. The canonical tests assert that the owner query travels over stdin and that the operation rejects an unexpected owner.

## Historical source provenance and ownership

The user, JCSchoeman96, created and owns all DevCore materials, including the recovered archive and installed executable. No historical Git repository, source commit, tag, signature, or supported executable updater was recovered for these artifacts. The archive's `install.sh` configures consumer project files; it does not install or update the executable. The installed script differs from the archive in the database-owner query described above. The recovered files do not establish when that change was made or when the installed version was distributed. These limits describe historical Git provenance, not authorship or ownership.

The archive and installed artifact are retained as legacy evidence. Neither is declared the original canonical Git source. The new Git history begins with this repository's bootstrap and canonicalization commits. This repository is publicly visible on GitHub and has no `LICENSE` file. No additional open-source license grant has been declared.

## First repository-owned version 1.0.1

The executable and changelog establish `1.0.1`, not historical `1.0.0`. The selected baseline preserves the installed tool's effective command and project-contract behavior, and fixes the archive query defect by retaining the installed implementation. The new installer, tests, and documentation do not expand the consumer contract. TICK-45 did not create a tag or release. TICK-48 published [`v1.0.1`](https://github.com/JCSchoeman96/devcore-project/releases/tag/v1.0.1) from the exact reviewed source commit.

- Source commit: `1266b221af90c318db54306eeb926afb873088c6`
- Post-merge CI run: `39944654664` (`SUCCESS` on the source commit)
- Release executable `devcore-project` SHA-256: `7b9c5a17abcc3d5591e3ba872b87f4ec27cf17bf367ddc9b8e8bb6716b2b030d`
- Existing v1-style consumer `.devcore/` declarations remain compatible.
- At the time of TICK-48, supplemental-secret support was not included. TICK-43 later delivered the capability in the backward-compatible v1.1.0 release below.

## Repository-owned version 1.1.0

TICK-43 added optional supplemental-secret delivery as a backward-compatible extension to the v1 consumer contract. Existing owner-only consumers remain compatible. Supplemental secrets are delivery-only: DevCore does not generate, rotate, or provision them. Durable Ticketing adoption remains TICK-42.

- Release date: 2026-10-23
- Tag: [`v1.1.0`](https://github.com/JCSchoeman96/devcore-project/releases/tag/v1.1.0)
- Source commit: `60f2ef09e52abca7b20f1572795579a549ba9d61`
- Post-merge CI run: `39967037057` (`SUCCESS` on the source commit)
- Release executable `devcore-project` SHA-256: `df7dd3263197d33416b99699b5f09ee2b37bb4a45f55cc2a7bb4164dbbff9568`
- Release assets: `devcore-project` and `devcore-project.sha256`
