import os
import socketserver
import subprocess
import tempfile
import threading
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / "bin" / "devcore-project"

DEV_PASSWORD = "SYNTHETIC_DEV_PASSWORD_FOR_TESTS_012345"
TEST_PASSWORD = "SYNTHETIC_TEST_PASSWORD_FOR_TESTS_987654"


class _TCPHandler(socketserver.BaseRequestHandler):
    def handle(self):
        return


class DevCoreProjectFixture(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="devcore-test-")
        self.root = Path(self.temp.name)
        self.home = self.root / "home"
        self.home.mkdir()
        self.project = self.root / "project"
        self.project.mkdir()
        self.central = self.home / ".config" / "dev-core"
        self.central.mkdir(parents=True)
        self.secrets = self.central / "project-db.env"
        self.global_conf = self.central / "dev-core.conf"
        self.secrets.write_text(
            "DEMO_DEV_DB_PASSWORD=" + DEV_PASSWORD + "\n"
            "DEMO_TEST_DB_PASSWORD=" + TEST_PASSWORD + "\n"
        )
        self.secrets.chmod(0o600)
        self._write_global_conf(55432, 55433)
        self._write_profile_contract()
        subprocess.run(
            ["git", "-c", "init.defaultBranch=main", "init", "-q"],
            cwd=self.project,
            check=True,
            capture_output=True,
            text=True,
        )
        self.mock_bin = self.root / "mock-bin"
        self.mock_bin.mkdir()
        self.servers = []

    def tearDown(self):
        for server, thread in self.servers:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)
        self.temp.cleanup()

    def env(self):
        return {
            "HOME": str(self.home),
            "PATH": os.environ["PATH"],
            "LC_ALL": "C",
            "DEVCORE_CONFIG_DIR": str(self.central),
            "DEVCORE_GLOBAL_CONF": str(self.global_conf),
            "DEVCORE_SECRETS_FILE": str(self.secrets),
            "DEVCORE_PROJECT_CONF": ".devcore/project.conf",
        }

    def run_tool(self, *args, env=None):
        child_env = self.env()
        if env:
            child_env.update(env)
        return subprocess.run(
            [str(TOOL), *args],
            cwd=self.project,
            env=child_env,
            capture_output=True,
            text=True,
            timeout=15,
        )

    def _write_global_conf(self, dev_port, test_port):
        self.global_conf.write_text(
            "PG_DEV_HOST=127.0.0.1\n"
            f"PG_DEV_PORT={dev_port}\n"
            "PG_TEST_HOST=127.0.0.1\n"
            f"PG_TEST_PORT={test_port}\n"
            "REDIS_DEV_HOST=127.0.0.1\n"
            "REDIS_DEV_PORT=56379\n"
            "REDIS_TEST_HOST=127.0.0.1\n"
            "REDIS_TEST_PORT=56380\n"
            "PG_DEV_CONTAINER=devcore-test-dev\n"
            "PG_TEST_CONTAINER=devcore-test-test\n"
            "REDIS_DEV_CONTAINER=devcore-test-redis-dev\n"
            "REDIS_TEST_CONTAINER=devcore-test-redis-test\n"
            "PG_ADMIN_ROLE=devcore_test_admin\n"
        )
        self.global_conf.chmod(0o600)

    def _write_profile_contract(self):
        config = self.project / ".devcore"
        config.mkdir()
        (self.project / ".gitignore").write_text(
            ".env.dev\n.env.test\n.env.shared\n.env.local\n"
        )
        (config / "project.conf").write_text(
            "PROJECT_KEY=demo\n"
            "DEV_DB_ROLE=demo_dev\n"
            "DEV_DB_NAME=demo_dev\n"
            "TEST_DB_ROLE=demo_test\n"
            "TEST_DB_NAME=demo_test\n"
            "DEV_SECRET_KEY=DEMO_DEV_DB_PASSWORD\n"
            "TEST_SECRET_KEY=DEMO_TEST_DB_PASSWORD\n"
            "TEST_ROLE_CREATEDB=yes\n"
            "USE_REDIS=no\n"
            "REDIS_PREFIX=demo\n"
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

    def _start_database_endpoints(self):
        ports = []
        for _ in range(2):
            server = socketserver.ThreadingTCPServer(
                ("127.0.0.1", 0), _TCPHandler
            )
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            self.servers.append((server, thread))
            ports.append(server.server_address[1])
        self._write_global_conf(*ports)

    def _install_database_mocks(self):
        docker = self.mock_bin / "docker"
        docker.write_text(
            "#!/usr/bin/env python3\n"
            "import os, sys\n"
            "args=sys.argv[1:]\n"
            "log=os.environ['DEVCORE_TEST_DOCKER_LOG']\n"
            "if args and args[0]=='inspect':\n"
            "    print('true')\n"
            "elif args and args[0]=='exec':\n"
            "    data=sys.stdin.read()\n"
            "    if '-qAt' in args:\n"
            "        if '-c' in args or \"WHERE datname = :'db';\" not in data:\n"
            "            raise SystemExit('owner query must use psql stdin interpolation')\n"
            "        index=args.index('-v')\n"
            "        db=args[index+1].removeprefix('db=')\n"
            "        owners={'demo_dev':'demo_dev','demo_test':'demo_test'}\n"
            "        print(owners.get(db, 'unknown'))\n"
            "        event='owner-check'\n"
            "    else:\n"
            "        event='provision'\n"
            "    with open(log, 'a') as stream: stream.write(event+'\\n')\n"
            "else:\n"
            "    raise SystemExit(2)\n"
        )
        docker.chmod(0o700)
        psql = self.mock_bin / "psql"
        psql.write_text(
            "#!/usr/bin/env python3\n"
            "import sys\n"
            "args=sys.argv[1:]\n"
            "role=args[args.index('-U')+1]\n"
            "db=args[args.index('-d')+1]\n"
            "print(f'{role}|{db}|180006')\n"
        )
        psql.chmod(0o700)

    def _mock_env(self):
        log = self.root / "docker.log"
        env = self.env()
        env.update(
            {
                "PATH": str(self.mock_bin) + os.pathsep + os.environ["PATH"],
                "DEVCORE_TEST_DOCKER_LOG": str(log),
            }
        )
        return env, log


class DevCoreBaselineTests(DevCoreProjectFixture):
    def test_repository_owned_version_is_reported(self):
        result = self.run_tool("version")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, "devcore-project 1.0.1\n")

    def test_plan_parses_contract_and_reports_only_secret_presence(self):
        result = self.run_tool("plan")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Project: demo", result.stdout)
        self.assertIn("demo_dev@127.0.0.1:55432/demo_dev", result.stdout)
        self.assertIn("DEMO_DEV_DB_PASSWORD [present]", result.stdout)
        self.assertIn("DEMO_TEST_DB_PASSWORD [present]", result.stdout)
        for value in (DEV_PASSWORD, TEST_PASSWORD):
            self.assertNotIn(value, result.stdout + result.stderr)

    def test_render_binds_owner_secrets_and_run_isolates_profiles(self):
        rendered = self.run_tool("render")
        self.assertEqual(rendered.returncode, 0, rendered.stderr)
        dev_file = self.project / ".env.dev"
        test_file = self.project / ".env.test"
        self.assertEqual(dev_file.stat().st_mode & 0o777, 0o600)
        self.assertEqual(test_file.stat().st_mode & 0o777, 0o600)
        self.assertIn(DEV_PASSWORD, dev_file.read_text(), "DEV owner binding missing")
        self.assertNotIn(TEST_PASSWORD, dev_file.read_text(), "TEST value crossed into DEV")
        self.assertIn(TEST_PASSWORD, test_file.read_text(), "TEST owner binding missing")
        self.assertNotIn(DEV_PASSWORD, test_file.read_text(), "DEV value crossed into TEST")

        code = (
            "import os; "
            "print(('dev-present' if os.getenv('DEV_DATABASE_PASSWORD') else 'dev-absent')"
            "+'|'+('test-present' if os.getenv('TEST_DATABASE_PASSWORD') else 'test-absent'))"
        )
        dev = self.run_tool("run", "dev", "--", "python3", "-c", code)
        test = self.run_tool("run", "test", "--", "python3", "-c", code)
        self.assertEqual(dev.returncode, 0, dev.stderr)
        self.assertEqual(test.returncode, 0, test.stderr)
        self.assertEqual(dev.stdout.strip(), "dev-present|test-absent")
        self.assertEqual(test.stdout.strip(), "dev-absent|test-present")
        self.assertNotIn(DEV_PASSWORD, dev.stdout + dev.stderr)
        self.assertNotIn(TEST_PASSWORD, test.stdout + test.stderr)

    def test_activate_uses_mocked_services_and_renders_restricted_files(self):
        self._start_database_endpoints()
        self._install_database_mocks()
        env, log = self._mock_env()
        result = self.run_tool("activate", env=env)
        self.assertEqual(result.returncode, 0, result.stderr)
        events = log.read_text().splitlines()
        self.assertEqual(events.count("provision"), 2)
        self.assertEqual(events.count("owner-check"), 2)
        for path in (self.project / ".env.dev", self.project / ".env.test"):
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)
        self.assertNotIn(DEV_PASSWORD, result.stdout + result.stderr)
        self.assertNotIn(TEST_PASSWORD, result.stdout + result.stderr)

    def test_doctor_checks_mocked_services_without_provisioning(self):
        self._start_database_endpoints()
        self._install_database_mocks()
        env, log = self._mock_env()
        rendered = self.run_tool("render", env=env)
        self.assertEqual(rendered.returncode, 0, rendered.stderr)
        log.write_text("")
        result = self.run_tool("doctor", env=env)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("DEV PostgreSQL authentication", result.stdout)
        self.assertIn("TEST PostgreSQL authentication", result.stdout)
        self.assertNotIn("provision", log.read_text())
        self.assertNotIn(DEV_PASSWORD, result.stdout + result.stderr)
        self.assertNotIn(TEST_PASSWORD, result.stdout + result.stderr)

    def test_missing_secret_fails_without_printing_other_values(self):
        self.secrets.write_text("DEMO_DEV_DB_PASSWORD=" + DEV_PASSWORD + "\n")
        self.secrets.chmod(0o600)
        result = self.run_tool("doctor")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("missing DEMO_TEST_DB_PASSWORD", result.stderr)
        self.assertNotIn(DEV_PASSWORD, result.stdout + result.stderr)

    def test_invalid_secret_fails_without_printing_its_value(self):
        invalid = "synthetic-too-short"
        self.secrets.write_text(
            "DEMO_DEV_DB_PASSWORD=" + invalid + "\n"
            "DEMO_TEST_DB_PASSWORD=" + TEST_PASSWORD + "\n"
        )
        self.secrets.chmod(0o600)
        result = self.run_tool("doctor")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("contains unsupported characters or is too short", result.stderr)
        self.assertNotIn(invalid, result.stdout + result.stderr)

    def test_invalid_project_fields_fail_closed(self):
        config = self.project / ".devcore" / "project.conf"
        config.write_text(config.read_text().replace("PROJECT_KEY=demo", "PROJECT_KEY="))
        result = self.run_tool("plan")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("invalid PROJECT_KEY", result.stderr)
        self.assertNotIn(DEV_PASSWORD, result.stdout + result.stderr)

    def test_malformed_render_map_fails_closed(self):
        (self.project / ".devcore" / "render-map.tsv").write_text("broken\trow\n")
        result = self.run_tool("render")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Invalid render-map row", result.stderr)
        self.assertNotIn(DEV_PASSWORD, result.stdout + result.stderr)

    def test_unresolved_template_tokens_fail_without_secret_disclosure(self):
        template = self.project / ".devcore" / "env.dev.template"
        template.write_text("VALUE={{UNSUPPORTED_TOKEN}}\n")
        result = self.run_tool("render")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Unresolved template tokens", result.stderr)
        self.assertNotIn(DEV_PASSWORD, result.stdout + result.stderr)
        self.assertNotIn(TEST_PASSWORD, result.stdout + result.stderr)

    def test_install_creates_private_local_secret_files(self):
        result = self.run_tool("install")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.central.stat().st_mode & 0o777, 0o700)
        self.assertEqual(self.secrets.stat().st_mode & 0o777, 0o600)
        self.assertEqual(self.global_conf.stat().st_mode & 0o777, 0o600)

    def test_documented_v1_consumer_contract_still_renders(self):
        config = self.project / ".devcore"
        (config / "project.conf").write_text(
            "PROJECT_KEY=myapp\n"
            "DEV_DB_ROLE=myapp_dev\n"
            "DEV_DB_NAME=myapp_dev\n"
            "TEST_DB_ROLE=myapp_test\n"
            "TEST_DB_NAME=myapp_test\n"
            "DEV_SECRET_KEY=DEMO_DEV_DB_PASSWORD\n"
            "TEST_SECRET_KEY=DEMO_TEST_DB_PASSWORD\n"
            "TEST_ROLE_CREATEDB=yes\n"
            "USE_REDIS=no\n"
            "REDIS_PREFIX=myapp\n"
            "RENDER_MAP=.devcore/render-map.tsv\n"
        )
        (config / "env.local.template").write_text(
            "MYAPP_DEV_DATABASE_USERNAME={{DEV_DB_ROLE}}\n"
            "MYAPP_DEV_DATABASE_PASSWORD={{DEV_DB_PASSWORD}}\n"
            "MYAPP_TEST_DATABASE_USERNAME={{TEST_DB_ROLE}}\n"
            "MYAPP_TEST_DATABASE_PASSWORD={{TEST_DB_PASSWORD}}\n"
        )
        (self.project / ".gitignore").write_text(".env.local\n")
        (config / "render-map.tsv").write_text(
            "all\t.devcore/env.local.template\t.env.local\tDATABASE_URL,DB_PASSWORD\n"
        )
        result = self.run_tool("render")
        self.assertEqual(result.returncode, 0, result.stderr)
        rendered = (self.project / ".env.local").read_text()
        self.assertIn(DEV_PASSWORD, rendered, "legacy DEV binding missing")
        self.assertIn(TEST_PASSWORD, rendered, "legacy TEST binding missing")
        self.assertEqual((self.project / ".env.local").stat().st_mode & 0o777, 0o600)


if __name__ == "__main__":
    unittest.main()
