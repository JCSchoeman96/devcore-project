"""Opt-in integration checks against disposable PostgreSQL containers."""

import os
import secrets
import shutil
import subprocess
import tempfile
import time
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / "bin" / "devcore-project"
RUN_INTEGRATION = os.environ.get("DEVCORE_RUN_POSTGRES_INTEGRATION") == "1"


@unittest.skipUnless(
    RUN_INTEGRATION,
    "set DEVCORE_RUN_POSTGRES_INTEGRATION=1 to run disposable PostgreSQL integration checks",
)
class PostgresIntegrationTests(unittest.TestCase):
    image = "postgres:18.6-alpine"

    def setUp(self):
        if not shutil.which("docker"):
            self.fail("Docker is required for the opt-in PostgreSQL integration check")
        self.temp = tempfile.TemporaryDirectory(prefix="devcore-postgres-integration-")
        self.root = Path(self.temp.name)
        self.home = self.root / "home"
        self.central = self.home / ".config" / "dev-core"
        self.project = self.root / "project"
        self.home.mkdir()
        self.central.mkdir(parents=True, mode=0o700)
        self.project.mkdir()
        self.containers = []
        self.container_names = [
            f"devcore-it-{secrets.token_hex(8)}-dev",
            f"devcore-it-{secrets.token_hex(8)}-test",
        ]
        self.admin_password = secrets.token_urlsafe(32)
        self.dev_password = secrets.token_urlsafe(32)
        self.test_password = secrets.token_urlsafe(32)
        self.new_passwords = None
        self._write_project()
        subprocess.run(
            ["git", "-c", "init.defaultBranch=main", "init", "-q"],
            cwd=self.project,
            check=True,
            capture_output=True,
            text=True,
        )
        try:
            ports = [self._start_container(name) for name in self.container_names]
            self._write_global_config(*ports)
            for name in self.container_names:
                self._create_admin(name)
        except Exception:
            self._remove_containers()
            self.temp.cleanup()
            raise

    def tearDown(self):
        try:
            self._remove_containers()
        finally:
            if hasattr(self, "temp"):
                self.temp.cleanup()

    def _write_project(self):
        config = self.project / ".devcore"
        config.mkdir()
        (self.project / ".gitignore").write_text(
            ".env.dev\n.env.test\n.env.shared\n.env.local\n"
        )
        (config / "project.conf").write_text(
            "PROJECT_KEY=integration\n"
            "DEV_DB_ROLE=integration_dev\n"
            "DEV_DB_NAME=integration_dev\n"
            "TEST_DB_ROLE=integration_test\n"
            "TEST_DB_NAME=integration_test\n"
            "DEV_SECRET_KEY=INTEGRATION_DEV_DB_PASSWORD\n"
            "TEST_SECRET_KEY=INTEGRATION_TEST_DB_PASSWORD\n"
            "TEST_ROLE_CREATEDB=no\n"
            "USE_REDIS=no\n"
            "REDIS_PREFIX=integration\n"
            "RENDER_MAP=.devcore/render-map.tsv\n"
        )
        (config / "env.dev.template").write_text(
            "DEV_DATABASE_USERNAME={{DEV_DB_ROLE}}\n"
            "DEV_DATABASE_PASSWORD={{DEV_DB_PASSWORD}}\n"
            "DEV_DATABASE_HOST={{DEV_DB_HOST}}\n"
            "DEV_DATABASE_PORT={{DEV_DB_PORT}}\n"
            "DEV_DATABASE_NAME={{DEV_DB_NAME}}\n"
        )
        (config / "env.test.template").write_text(
            "TEST_DATABASE_USERNAME={{TEST_DB_ROLE}}\n"
            "TEST_DATABASE_PASSWORD={{TEST_DB_PASSWORD}}\n"
            "TEST_DATABASE_HOST={{TEST_DB_HOST}}\n"
            "TEST_DATABASE_PORT={{TEST_DB_PORT}}\n"
            "TEST_DATABASE_NAME={{TEST_DB_NAME}}\n"
        )
        (config / "env.shared.template").write_text(
            "SHARED_PROJECT_KEY={{PROJECT_KEY}}\n"
        )
        (config / "render-map.tsv").write_text(
            "dev\t.devcore/env.dev.template\t.env.dev\t\n"
            "test\t.devcore/env.test.template\t.env.test\t\n"
            "all\t.devcore/env.shared.template\t.env.shared\t\n"
        )

    def _write_global_config(self, dev_port, test_port):
        (self.central / "dev-core.conf").write_text(
            "PG_DEV_HOST=127.0.0.1\n"
            f"PG_DEV_PORT={dev_port}\n"
            "PG_TEST_HOST=127.0.0.1\n"
            f"PG_TEST_PORT={test_port}\n"
            "REDIS_DEV_HOST=127.0.0.1\n"
            "REDIS_DEV_PORT=56379\n"
            "REDIS_TEST_HOST=127.0.0.1\n"
            "REDIS_TEST_PORT=56380\n"
            f"PG_DEV_CONTAINER={self.container_names[0]}\n"
            f"PG_TEST_CONTAINER={self.container_names[1]}\n"
            "REDIS_DEV_CONTAINER=unused-dev\n"
            "REDIS_TEST_CONTAINER=unused-test\n"
            "PG_ADMIN_ROLE=devcore_admin\n"
        )
        (self.central / "dev-core.conf").chmod(0o600)

    def _start_container(self, name):
        result = self._run(
            [
                "docker", "run", "--detach", "--name", name,
                "--label", "devcore.integration=true",
                "--label", f"devcore.integration.id={name}",
                "--env", "POSTGRES_USER=postgres",
                "--env", "POSTGRES_PASSWORD",
                "--env", "POSTGRES_HOST_AUTH_METHOD=scram-sha-256",
                "--publish", "127.0.0.1::5432", self.image,
            ],
            env={"POSTGRES_PASSWORD": self.admin_password},
            timeout=120,
        )
        self.assertEqual(result.returncode, 0, "could not start disposable PostgreSQL container")
        self.containers.append(name)
        port_result = self._run(["docker", "port", name, "5432/tcp"])
        self.assertEqual(port_result.returncode, 0, "could not read disposable PostgreSQL port")
        port = int(port_result.stdout.strip().rsplit(":", 1)[1])
        deadline = time.monotonic() + 60
        while time.monotonic() < deadline:
            ready = self._docker_psql(name, "SELECT 1", check=False)
            if ready.returncode == 0:
                return port
            time.sleep(0.5)
        self.fail("disposable PostgreSQL container did not become ready")

    def _create_admin(self, container):
        result = self._docker_psql(
            container,
            "CREATE ROLE devcore_admin WITH LOGIN SUPERUSER;",
            check=False,
        )
        self.assertEqual(result.returncode, 0, "could not create isolated DevCore admin role")

    def _docker_psql(self, container, sql, check=True):
        return self._run(
            ["docker", "exec", "-i", container, "psql", "-X", "-q", "-v",
             "ON_ERROR_STOP=1", "-U", "postgres", "-d", "postgres", "-c", sql],
            check=check,
        )

    def _run(self, args, *, env=None, timeout=30, check=True, input_text=None):
        child_env = os.environ.copy()
        child_env.update(env or {})
        return subprocess.run(
            args,
            cwd=self.project,
            env=child_env,
            capture_output=True,
            text=True,
            timeout=timeout,
            input=input_text,
        )

    def _tool(self, *args, expected=0):
        result = self._run(
            [str(TOOL), *args],
            env={
                "HOME": str(self.home),
                "DEVCORE_CONFIG_DIR": str(self.central),
                "DEVCORE_GLOBAL_CONF": str(self.central / "dev-core.conf"),
                "DEVCORE_SECRETS_FILE": str(self.central / "project-db.env"),
                "DEVCORE_PROJECT_CONF": ".devcore/project.conf",
            },
        )
        output = result.stdout + result.stderr
        secrets_to_check = [self.admin_password, self.dev_password, self.test_password]
        secrets_to_check.extend(getattr(self, "new_passwords", []) or [])
        for secret in secrets_to_check:
            self.assertNotIn(secret, output, "CLI output exposed a database credential")
        self.assertEqual(result.returncode, expected, "DevCore command returned an unexpected status")
        return result

    def _authenticate(self, container, role, password):
        address = self._run(
            [
                "docker", "inspect", "--format",
                "{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}",
                container,
            ]
        )
        self.assertEqual(address.returncode, 0, "could not inspect disposable PostgreSQL address")
        self.assertTrue(address.stdout.strip(), "disposable PostgreSQL container has no bridge address")
        return self._run(
            ["docker", "exec", "-i", container, "sh", "-c",
             'IFS= read -r PGPASSWORD || exit 1; export PGPASSWORD; exec psql -X -qAt -h "$2" -U "$1" -d "$1" -c "SELECT current_user"',
             "devcore-auth", role, address.stdout.strip()],
            input_text=password + "\n",
            check=False,
        )

    def test_activate_rotate_and_detect_database_and_render_drift(self):
        secrets_file = self.central / "project-db.env"
        secrets_file.write_text(
            f"INTEGRATION_DEV_DB_PASSWORD={self.dev_password}\n"
            f"INTEGRATION_TEST_DB_PASSWORD={self.test_password}\n"
        )
        secrets_file.chmod(0o600)

        self._tool("activate")
        self._assert_database_invariants(self.container_names[0], "integration_dev", "f")
        self._assert_database_invariants(self.container_names[1], "integration_test", "f")
        self._tool("doctor")

        self._tool("rotate")
        current_secrets = secrets_file.read_text().splitlines()
        self.new_passwords = [line.split("=", 1)[1] for line in current_secrets]
        for container, role, old_password, new_password in (
            (self.container_names[0], "integration_dev", self.dev_password, self.new_passwords[0]),
            (self.container_names[1], "integration_test", self.test_password, self.new_passwords[1]),
        ):
            old_auth = self._authenticate(container, role, old_password)
            self.assertNotEqual(
                old_auth.returncode,
                0,
                f"old credential still authenticated for {role}; changed={old_password != new_password}",
            )
            authenticated = self._authenticate(container, role, new_password)
            self.assertEqual(authenticated.returncode, 0, "rotated credential did not authenticate")

        self._tool("render")
        self._tool("doctor")

        self._docker_psql(
            self.container_names[1],
            "ALTER ROLE integration_test CREATEDB;",
        )
        self._tool("doctor", expected=1)
        self._docker_psql(
            self.container_names[1],
            "ALTER ROLE integration_test NOCREATEDB; ALTER DATABASE integration_test OWNER TO postgres;",
        )
        self._tool("doctor", expected=1)
        self._docker_psql(
            self.container_names[1],
            "ALTER DATABASE integration_test OWNER TO integration_test;",
        )
        self._tool("doctor")

        rendered = self.project / ".env.test"
        rendered.write_text(rendered.read_text().replace("TEST_DATABASE_NAME=integration_test", "TEST_DATABASE_NAME=wrong_db"))
        self._tool("doctor", expected=1)

    def test_doctor_detects_role_membership_drift_in_both_directions(self):
        secrets_file = self.central / "project-db.env"
        secrets_file.write_text(
            f"INTEGRATION_DEV_DB_PASSWORD={self.dev_password}\n"
            f"INTEGRATION_TEST_DB_PASSWORD={self.test_password}\n"
        )
        secrets_file.chmod(0o600)
        self._tool("activate")
        self._tool("doctor")

        container = self.container_names[0]
        self._docker_psql(container, "CREATE ROLE membership_drift;")
        try:
            for sql, revoke in (
                ("GRANT membership_drift TO integration_dev;", "REVOKE membership_drift FROM integration_dev;"),
                ("GRANT integration_dev TO membership_drift;", "REVOKE integration_dev FROM membership_drift;"),
            ):
                self._docker_psql(container, sql)
                self._tool("doctor", expected=1)
                self._docker_psql(container, revoke)
                self._tool("doctor")
        finally:
            self._docker_psql(
                container,
                "REVOKE membership_drift FROM integration_dev; "
                "REVOKE integration_dev FROM membership_drift; "
                "DROP ROLE IF EXISTS membership_drift;",
                check=False,
            )

    def _assert_database_invariants(self, container, role, createdb):
        query = (
            "SELECT r.rolcanlogin, r.rolsuper, r.rolcreatedb, r.rolcreaterole, "
            "r.rolreplication, r.rolbypassrls, pg_get_userbyid(d.datdba) "
            "FROM pg_roles r JOIN pg_database d ON d.datname = current_database() "
            f"WHERE r.rolname = '{role}'"
        )
        result = self._run(
            ["docker", "exec", container, "psql", "-X", "-qAt", "-F", "|",
             "-U", "postgres", "-d", role, "-c", query]
        )
        fields = result.stdout.strip().split("|")
        self.assertEqual(result.returncode, 0, "could not inspect disposable database role")
        self.assertEqual(fields, ["t", "f", createdb, "f", "f", "f", role])

    def _remove_containers(self):
        for name in getattr(self, "containers", []):
            try:
                subprocess.run(
                    ["docker", "rm", "--force", "--volumes", name],
                    capture_output=True,
                    text=True,
                    timeout=30,
                )
            except (OSError, subprocess.TimeoutExpired):
                pass
        self.containers = []


if __name__ == "__main__":
    unittest.main()
