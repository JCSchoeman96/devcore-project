import json
import os
import shutil
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
LATER_DEV_PASSWORD = "SYNTHETIC_LATER_DEV_PASSWORD_FOR_TESTS_123456"
ALTERNATE_DEV_PASSWORD = "SYNTHETIC_ALTERNATE_DEV_PASSWORD_FOR_TESTS_654321"


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
            "import os, sys\n"
            "args=sys.argv[1:]\n"
            "role=args[args.index('-U')+1]\n"
            "db=args[args.index('-d')+1]\n"
            "expected={'demo_dev':os.environ.get('DEVCORE_TEST_EXPECTED_DEV_PASSWORD'),"
            "'demo_test':os.environ.get('DEVCORE_TEST_EXPECTED_TEST_PASSWORD')}\n"
            "if expected.get(role) is not None and os.environ.get('PGPASSWORD') != expected[role]:\n"
            "    raise SystemExit('synthetic authentication rejected')\n"
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
        self.assertEqual(result.stdout, "devcore-project 1.1.0\n")

    def test_plan_parses_contract_and_reports_only_secret_presence(self):
        result = self.run_tool("plan")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Project: demo", result.stdout)
        self.assertIn("demo_dev@127.0.0.1:55432/demo_dev", result.stdout)
        self.assertIn("DEMO_DEV_DB_PASSWORD [present]", result.stdout)
        self.assertIn("DEMO_TEST_DB_PASSWORD [present]", result.stdout)
        for value in (DEV_PASSWORD, TEST_PASSWORD):
            self.assertNotIn(value, result.stdout + result.stderr)

    def test_duplicate_config_keys_use_first_value_in_plan_render_doctor_and_run(self):
        self._start_database_endpoints()
        dev_port = next(
            line.split("=", 1)[1]
            for line in self.global_conf.read_text().splitlines()
            if line.startswith("PG_DEV_PORT=")
        )

        project_conf = self.project / ".devcore" / "project.conf"
        project_conf.write_text(
            project_conf.read_text()
            + "DEV_DB_ROLE=wrong_dev\n"
            + "DEV_DB_NAME=wrong_dev_db\n"
            + "DEV_SECRET_KEY=DEMO_ALTERNATE_DEV_PASSWORD\n"
        )
        self.global_conf.write_text(
            self.global_conf.read_text()
            + "PG_DEV_HOST=192.0.2.1\n"
            + "PG_DEV_PORT=1\n"
        )
        self.secrets.write_text(
            f"DEMO_DEV_DB_PASSWORD={DEV_PASSWORD}\n"
            f"DEMO_DEV_DB_PASSWORD={LATER_DEV_PASSWORD}\n"
            f"DEMO_ALTERNATE_DEV_PASSWORD={ALTERNATE_DEV_PASSWORD}\n"
            f"DEMO_TEST_DB_PASSWORD={TEST_PASSWORD}\n"
        )
        self.secrets.chmod(0o600)

        self._install_database_mocks()
        env, _ = self._mock_env()
        env["DEVCORE_TEST_EXPECTED_DEV_PASSWORD"] = DEV_PASSWORD
        env["DEVCORE_TEST_EXPECTED_TEST_PASSWORD"] = TEST_PASSWORD

        plan = self.run_tool("plan", env=env)
        self.assertEqual(plan.returncode, 0, plan.stderr)
        self.assertIn(f"demo_dev@127.0.0.1:{dev_port}/demo_dev", plan.stdout)
        self.assertIn("DEV secret key:  DEMO_DEV_DB_PASSWORD [present]", plan.stdout)
        self.assertNotIn("wrong_dev", plan.stdout)
        self.assertNotIn("DEMO_ALTERNATE_DEV_PASSWORD", plan.stdout)

        rendered = self.run_tool("render", env=env)
        self.assertEqual(rendered.returncode, 0, rendered.stderr)
        dev_env = (self.project / ".env.dev").read_text()
        self.assertIn("DEV_DATABASE_USERNAME=demo_dev", dev_env)
        self.assertIn("DEV_DATABASE_HOST=127.0.0.1", dev_env)
        self.assertIn(f"DEV_DATABASE_PORT={dev_port}", dev_env)
        self.assertEqual(
            "first" if f"DEV_DATABASE_PASSWORD={DEV_PASSWORD}" in dev_env else "other",
            "first",
            "render did not use the first project and secret bindings",
        )
        self.assertNotIn("wrong_dev", dev_env)
        self.assertNotIn(ALTERNATE_DEV_PASSWORD, dev_env)
        self.assertNotIn(LATER_DEV_PASSWORD, dev_env)

        doctor = self.run_tool("doctor", env=env)
        self.assertEqual(doctor.returncode, 0, doctor.stderr)
        self.assertIn("DEV PostgreSQL authentication: demo_dev / demo_dev", doctor.stdout)
        self.assertNotIn(DEV_PASSWORD, doctor.stdout + doctor.stderr)

        code = (
            "import os; print('|'.join((os.environ['DEV_DATABASE_USERNAME'], "
            "os.environ['DEV_DATABASE_HOST'], os.environ['DEV_DATABASE_PORT'], "
            "'first' if os.environ['DEV_DATABASE_PASSWORD'] == "
            "os.environ['DEVCORE_TEST_EXPECTED_DEV_PASSWORD'] else 'other')))"
        )
        run = self.run_tool("run", "dev", "--", "python3", "-c", code, env=env)
        self.assertEqual(run.returncode, 0, run.stderr)
        self.assertEqual(run.stdout.strip(), f"demo_dev|127.0.0.1|{dev_port}|first")
        for value in (DEV_PASSWORD, LATER_DEV_PASSWORD, ALTERNATE_DEV_PASSWORD):
            self.assertNotIn(value, plan.stdout + plan.stderr + rendered.stdout + rendered.stderr)
            self.assertNotIn(value, doctor.stdout + doctor.stderr + run.stdout + run.stderr)

    def test_duplicate_secret_file_entries_use_first_value_for_render_doctor_and_run(self):
        self._start_database_endpoints()
        self.secrets.write_text(
            f"DEMO_DEV_DB_PASSWORD={DEV_PASSWORD}\n"
            f"DEMO_DEV_DB_PASSWORD={LATER_DEV_PASSWORD}\n"
            f"DEMO_TEST_DB_PASSWORD={TEST_PASSWORD}\n"
        )
        self.secrets.chmod(0o600)
        self._install_database_mocks()
        env, _ = self._mock_env()
        env["DEVCORE_TEST_EXPECTED_DEV_PASSWORD"] = DEV_PASSWORD
        env["DEVCORE_TEST_EXPECTED_TEST_PASSWORD"] = TEST_PASSWORD

        plan = self.run_tool("plan", env=env)
        self.assertEqual(plan.returncode, 0, plan.stderr)
        self.assertIn("DEV secret key:  DEMO_DEV_DB_PASSWORD [present]", plan.stdout)

        rendered = self.run_tool("render", env=env)
        self.assertEqual(rendered.returncode, 0, rendered.stderr)
        dev_env = (self.project / ".env.dev").read_text()
        self.assertEqual(
            "first" if f"DEV_DATABASE_PASSWORD={DEV_PASSWORD}" in dev_env else "other",
            "first",
            "render did not use the first matching secret entry",
        )
        self.assertNotIn(LATER_DEV_PASSWORD, dev_env)

        doctor = self.run_tool("doctor", env=env)
        self.assertEqual(doctor.returncode, 0, doctor.stderr)
        self.assertIn("DEV PostgreSQL authentication: demo_dev / demo_dev", doctor.stdout)

        code = (
            "import os; print('first' if os.environ['DEV_DATABASE_PASSWORD'] == "
            "os.environ['DEVCORE_TEST_EXPECTED_DEV_PASSWORD'] else 'other')"
        )
        run = self.run_tool("run", "dev", "--", "python3", "-c", code, env=env)
        self.assertEqual(run.returncode, 0, run.stderr)
        self.assertEqual(run.stdout.strip(), "first")
        for value in (DEV_PASSWORD, LATER_DEV_PASSWORD):
            self.assertNotIn(value, plan.stdout + plan.stderr + rendered.stdout + rendered.stderr)
            self.assertNotIn(value, doctor.stdout + doctor.stderr + run.stdout + run.stderr)

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
        all_profiles = self.run_tool(
            "run",
            "all",
            "--",
            "python3",
            "-c",
            "import os; print(os.getenv('SHARED_PROJECT_KEY', 'absent'))",
        )
        self.assertEqual(dev.returncode, 0, dev.stderr)
        self.assertEqual(test.returncode, 0, test.stderr)
        self.assertEqual(all_profiles.returncode, 0, all_profiles.stderr)
        self.assertEqual(dev.stdout.strip(), "dev-present|test-absent")
        self.assertEqual(test.stdout.strip(), "dev-absent|test-present")
        self.assertEqual(all_profiles.stdout.strip(), "demo")
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

    def test_render_rejects_unknown_profile_during_contract_validation(self):
        render_map = self.project / ".devcore" / "render-map.tsv"
        render_map.write_text(
            "tesst\t.devcore/env.dev.template\t.env.dev\t\n"
        )
        result = self.run_tool("render")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("invalid render profile", result.stderr)
        self.assertFalse((self.project / ".env.dev").exists())
        self.assertNotIn(DEV_PASSWORD, result.stdout + result.stderr)

    def test_run_rejects_unknown_profile_before_executing_command(self):
        rendered = self.run_tool("render")
        self.assertEqual(rendered.returncode, 0, rendered.stderr)
        marker = self.root / "child-command-ran"
        code = "from pathlib import Path; Path(%r).touch()" % str(marker)
        result = self.run_tool("run", "tesst", "--", "python3", "-c", code)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("invalid run profile", result.stderr)
        self.assertFalse(marker.exists())
        self.assertNotIn(DEV_PASSWORD, result.stdout + result.stderr)

    def test_docker_doctor_fallback_sends_password_on_stdin_not_argv(self):
        self._start_database_endpoints()
        docker_log = self.root / "docker-argv.jsonl"
        docker = self.mock_bin / "docker"
        docker.write_text(
            "#!/usr/bin/env python3\n"
            "import json, os, sys\n"
            "args=sys.argv[1:]\n"
            "if args and args[0]=='inspect':\n"
            "    print('true')\n"
            "elif args and args[0]=='exec':\n"
            "    with open(os.environ['DEVCORE_TEST_DOCKER_ARGV_LOG'], 'a') as out:\n"
            "        out.write(json.dumps(args)+'\\n')\n"
            "    if '-e' in args:\n"
            "        raise SystemExit('environment argument is forbidden')\n"
            "    password=sys.stdin.buffer.readline().rstrip(b'\\n').decode()\n"
            "    role=args[args.index('-U')+1]\n"
            "    db=args[args.index('-d')+1]\n"
            "    expected={'demo_dev':os.environ['DEVCORE_TEST_EXPECTED_DEV_PASSWORD'],"
            "'demo_test':os.environ['DEVCORE_TEST_EXPECTED_TEST_PASSWORD']}\n"
            "    if password != expected[role]:\n"
            "        raise SystemExit('synthetic authentication rejected')\n"
            "    print(f'{role}|{db}|180006')\n"
            "else:\n"
            "    raise SystemExit(2)\n"
        )
        docker.chmod(0o700)
        docker_log.write_text("")

        path_without_psql = self.root / "path-without-psql"
        path_without_psql.mkdir()
        seen = set()
        for entry in os.environ["PATH"].split(os.pathsep):
            directory = Path(entry)
            if not directory.is_dir():
                continue
            for executable in directory.iterdir():
                if executable.name == "psql" or executable.name in seen:
                    continue
                if executable.is_file() and os.access(executable, os.X_OK):
                    (path_without_psql / executable.name).symlink_to(executable.resolve())
                    seen.add(executable.name)

        env = self.env()
        env.update(
            {
                "PATH": str(self.mock_bin) + os.pathsep + str(path_without_psql),
                "DEVCORE_TEST_DOCKER_ARGV_LOG": str(docker_log),
                "DEVCORE_TEST_EXPECTED_DEV_PASSWORD": DEV_PASSWORD,
                "DEVCORE_TEST_EXPECTED_TEST_PASSWORD": TEST_PASSWORD,
            }
        )
        self.assertIsNone(shutil.which("psql", path=env["PATH"]))
        rendered = self.run_tool("render", env=env)
        self.assertEqual(rendered.returncode, 0, rendered.stderr)
        preexisting_files = {path for path in self.root.rglob("*") if path.is_file()}

        result = self.run_tool("doctor", env=env)

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("DEV PostgreSQL authentication: demo_dev / demo_dev", result.stdout)
        self.assertIn("TEST PostgreSQL authentication: demo_test / demo_test", result.stdout)
        argv_log = docker_log.read_text()
        self.assertNotIn(DEV_PASSWORD, argv_log)
        self.assertNotIn(TEST_PASSWORD, argv_log)
        self.assertEqual(len(argv_log.splitlines()), 2)
        for line in argv_log.splitlines():
            args = json.loads(line)
            self.assertNotIn("-e", args)
            self.assertIn("-i", args)
        self.assertNotIn(DEV_PASSWORD, result.stdout + result.stderr)
        self.assertNotIn(TEST_PASSWORD, result.stdout + result.stderr)
        self.assertNotIn(DEV_PASSWORD, rendered.stdout + rendered.stderr)
        self.assertNotIn(TEST_PASSWORD, rendered.stdout + rendered.stderr)
        self.assertEqual(
            preexisting_files,
            {path for path in self.root.rglob("*") if path.is_file()},
            "doctor created a persistent file during Docker fallback",
        )

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
