import json
import os
import shutil
import subprocess
import unittest
from pathlib import Path

from test_devcore import DEV_PASSWORD, TEST_PASSWORD, DevCoreProjectFixture
from test_supplemental_secrets import SupplementalSecretsFixture


ARGV_PROBE_SECRET = "DISTINCTIVE_SUPPLEMENTAL_ARGV_PROBE_Z9Y8X7W6V5"
BASE64_LIKE_SECRET = "YWJjZGVmZ2hpamtsbW5vcA=="
JWT_LIKE_SECRET = "abc_DEF-123.xyz_456-789.sig_000"
COLON_SLASH_SECRET = "service:token/part+one@host%zone-1"


class ArgvSpyMixin:
    def _install_python_argv_spy(self):
        self.real_python3 = shutil.which("python3")
        self.assertIsNotNone(self.real_python3)
        self.python_argv_log = self.root / "python-argv.jsonl"
        self.python_argv_log.write_text("")
        spy = self.mock_bin / "python3"
        spy.write_text(
            f"#!{self.real_python3}\n"
            "import json, os, sys\n"
            "log=os.environ.get('DEVCORE_TEST_PYTHON_ARGV_LOG')\n"
            "if log:\n"
            "    with open(log, 'a') as out:\n"
            "        out.write(json.dumps(sys.argv)+'\\n')\n"
            "real=os.environ['DEVCORE_REAL_PYTHON3']\n"
            "argv=[real, *sys.argv[1:]]\n"
            "os.execv(real, argv)\n"
        )
        spy.chmod(0o700)

    def _spy_env(self):
        env, _ = self._mock_env()
        env.update(
            {
                "PATH": str(self.mock_bin) + os.pathsep + env["PATH"],
                "DEVCORE_TEST_PYTHON_ARGV_LOG": str(self.python_argv_log),
                "DEVCORE_REAL_PYTHON3": self.real_python3,
            }
        )
        return env

    def _assert_probe_not_in_child_argv(self):
        log = self.python_argv_log.read_text()
        self.assertNotIn(ARGV_PROBE_SECRET, log)
        for line in log.splitlines():
            if not line.strip():
                continue
            args = json.loads(line)
            joined = "\0".join(args)
            self.assertNotIn(ARGV_PROBE_SECRET, joined)


class SupplementalSecurityTests(SupplementalSecretsFixture, ArgvSpyMixin):
    def test_supplemental_validation_never_passes_secret_via_child_argv(self):
        self._write_supplemental_map(
            "dev\tDEMO_ARGV_PROBE\tDEMO_ARGV_PROBE_KEY\n"
        )
        self._secrets_with_supplemental(
            DEMO_ARGV_PROBE_KEY=ARGV_PROBE_SECRET,
        )
        (self.project / ".devcore" / "env.dev.template").write_text(
            (self.project / ".devcore" / "env.dev.template").read_text()
            + 'export DEMO_ARGV_PROBE="{{DEMO_ARGV_PROBE}}"\n'
        )
        self._install_python_argv_spy()
        env = self._spy_env()
        self.assertEqual(self.run_tool("plan", env=env).returncode, 0, "plan should pass")
        self.assertEqual(self.run_tool("render", env=env).returncode, 0, "render should pass")
        run = self.run_tool(
            "run",
            "dev",
            "--",
            "python3",
            "-c",
            "import os; print('present' if os.getenv('DEMO_ARGV_PROBE') else 'missing')",
            env=env,
        )
        self.assertEqual(run.returncode, 0, run.stderr)
        self._assert_probe_not_in_child_argv()
        self.assertNotIn(ARGV_PROBE_SECRET, run.stdout + run.stderr)

    def test_rejects_shell_quote_injection_before_render(self):
        marker = self.root / "supplemental-injection-marker"
        self.assertFalse(marker.exists())
        unsafe = f'"; touch {marker}; echo "'
        self._write_supplemental_map(
            "dev\tDEMO_SUPPLEMENTAL_DEV\tDEMO_SUPPLEMENTAL_DEV_KEY\n"
        )
        self._secrets_with_supplemental(DEMO_SUPPLEMENTAL_DEV_KEY=unsafe)
        (self.project / ".devcore" / "env.dev.template").write_text(
            (self.project / ".devcore" / "env.dev.template").read_text()
            + 'export DEMO_SUPPLEMENTAL_DEV="{{DEMO_SUPPLEMENTAL_DEV}}"\n'
        )
        result = self.run_tool("render")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("portable supplemental literal/token alphabet", result.stderr)
        self.assertFalse(marker.exists())
        self.assertNotIn(unsafe, result.stdout + result.stderr)
        target = self.project / ".env.dev"
        if target.exists():
            subprocess.run(["bash", "-c", f'source "{target}"'], check=False)
        self.assertFalse(marker.exists())

    def test_rejects_command_substitution_before_render(self):
        marker = self.root / "supplemental-subst-marker"
        self.assertFalse(marker.exists())
        unsafe = f"$(touch {marker})"
        self._write_supplemental_map(
            "dev\tDEMO_SUPPLEMENTAL_DEV\tDEMO_SUPPLEMENTAL_DEV_KEY\n"
        )
        self._secrets_with_supplemental(DEMO_SUPPLEMENTAL_DEV_KEY=unsafe)
        (self.project / ".devcore" / "env.dev.template").write_text(
            (self.project / ".devcore" / "env.dev.template").read_text()
            + 'export DEMO_SUPPLEMENTAL_DEV="{{DEMO_SUPPLEMENTAL_DEV}}"\n'
        )
        result = self.run_tool("render")
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(marker.exists())
        self.assertNotIn(unsafe, result.stdout + result.stderr)

    def test_safe_base64_like_value_preserved_through_render_and_run(self):
        self._write_supplemental_map("dev\tDEMO_BASE64\tDEMO_BASE64_KEY\n")
        self._secrets_with_supplemental(DEMO_BASE64_KEY=BASE64_LIKE_SECRET)
        (self.project / ".devcore" / "env.dev.template").write_text(
            (self.project / ".devcore" / "env.dev.template").read_text()
            + "DEMO_BASE64={{DEMO_BASE64}}\n"
        )
        self.assertEqual(self.run_tool("render").returncode, 0)
        self.assertIn(f"DEMO_BASE64={BASE64_LIKE_SECRET}", (self.project / ".env.dev").read_text())
        run = self.run_tool(
            "run",
            "dev",
            "--",
            "python3",
            "-c",
            f"import os; print('ok' if os.environ.get('DEMO_BASE64')=='{BASE64_LIKE_SECRET}' else 'bad')",
        )
        self.assertEqual(run.stdout.strip(), "ok")

    def test_safe_jwt_like_value_preserved_through_render_and_run(self):
        self._write_supplemental_map("dev\tDEMO_JWT\tDEMO_JWT_KEY\n")
        self._secrets_with_supplemental(DEMO_JWT_KEY=JWT_LIKE_SECRET)
        (self.project / ".devcore" / "env.dev.template").write_text(
            (self.project / ".devcore" / "env.dev.template").read_text()
            + 'export DEMO_JWT="{{DEMO_JWT}}"\n'
        )
        self.assertEqual(self.run_tool("render").returncode, 0)
        rendered = (self.project / ".env.dev").read_text()
        self.assertIn(f'export DEMO_JWT="{JWT_LIKE_SECRET}"', rendered)
        run = self.run_tool(
            "run",
            "dev",
            "--",
            "bash",
            "-c",
            'test "$DEMO_JWT" = "' + JWT_LIKE_SECRET + '"',
        )
        self.assertEqual(run.returncode, 0, run.stderr)

    def test_safe_colon_slash_token_preserved_through_render_and_run(self):
        self._write_supplemental_map("dev\tDEMO_TOKEN\tDEMO_TOKEN_KEY\n")
        self._secrets_with_supplemental(DEMO_TOKEN_KEY=COLON_SLASH_SECRET)
        (self.project / ".devcore" / "env.dev.template").write_text(
            (self.project / ".devcore" / "env.dev.template").read_text()
            + "DEMO_TOKEN={{DEMO_TOKEN}}\n"
        )
        self.assertEqual(self.run_tool("render").returncode, 0)
        run = self.run_tool(
            "run",
            "dev",
            "--",
            "python3",
            "-c",
            f"import os; print(os.environ.get('DEMO_TOKEN',''))",
        )
        self.assertEqual(run.stdout.strip(), COLON_SLASH_SECRET)


if __name__ == "__main__":
    unittest.main()
