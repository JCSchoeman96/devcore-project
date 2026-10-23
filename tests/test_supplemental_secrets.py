import os
import subprocess
import unittest
from pathlib import Path

from test_devcore import (
    ALTERNATE_DEV_PASSWORD,
    DEV_PASSWORD,
    DevCoreProjectFixture,
    TEST_PASSWORD,
    TOOL,
)


SUPPLEMENTAL_DEV_PASSWORD = "SYNTHETIC_SUPPLEMENTAL_DEV_PASSWORD_0123456789"
SUPPLEMENTAL_TEST_PASSWORD = "SYNTHETIC_SUPPLEMENTAL_TEST_PASSWORD_9876543210"
SUPPLEMENTAL_SHARED_PASSWORD = "SYNTHETIC_SHARED_SUPPLEMENTAL_PASSWORD_1111111111"
SUPPLEMENTAL_EXTRA_ONE = "SYNTHETIC_SUPPLEMENTAL_EXTRA_ONE_PASSWORD_2222222222"
SUPPLEMENTAL_EXTRA_TWO = "SYNTHETIC_SUPPLEMENTAL_EXTRA_TWO_PASSWORD_3333333333"


class SupplementalSecretsFixture(DevCoreProjectFixture):
    def _write_supplemental_map(self, content: str):
        config = self.project / ".devcore"
        (config / "project.conf").write_text(
            (config / "project.conf").read_text()
            + "SUPPLEMENTAL_SECRETS=.devcore/supplemental-secrets.tsv\n"
        )
        (config / "supplemental-secrets.tsv").write_text(content)

    def _secrets_with_supplemental(self, **extra):
        lines = [
            f"DEMO_DEV_DB_PASSWORD={DEV_PASSWORD}",
            f"DEMO_TEST_DB_PASSWORD={TEST_PASSWORD}",
        ]
        for key, value in extra.items():
            lines.append(f"{key}={value}")
        self.secrets.write_text("\n".join(lines) + "\n")
        self.secrets.chmod(0o600)


class SupplementalSecretsTests(SupplementalSecretsFixture):
    def test_owner_plus_one_supplemental_renders_and_runs(self):
        self._write_supplemental_map(
            "dev\tDEMO_SUPPLEMENTAL_DEV\tDEMO_SUPPLEMENTAL_DEV_KEY\n"
        )
        self._secrets_with_supplemental(DEMO_SUPPLEMENTAL_DEV_KEY=SUPPLEMENTAL_DEV_PASSWORD)
        (self.project / ".devcore" / "env.dev.template").write_text(
            (self.project / ".devcore" / "env.dev.template").read_text()
            + "DEMO_SUPPLEMENTAL_DEV={{DEMO_SUPPLEMENTAL_DEV}}\n"
        )
        rendered = self.run_tool("render")
        self.assertEqual(rendered.returncode, 0, rendered.stderr)
        dev_env = (self.project / ".env.dev").read_text()
        self.assertIn(f"DEMO_SUPPLEMENTAL_DEV={SUPPLEMENTAL_DEV_PASSWORD}", dev_env)
        code = (
            "import os; print('yes' if os.environ.get('DEMO_SUPPLEMENTAL_DEV') == "
            f"'{SUPPLEMENTAL_DEV_PASSWORD}' else 'no')"
        )
        run = self.run_tool("run", "dev", "--", "python3", "-c", code)
        self.assertEqual(run.returncode, 0, run.stderr)
        self.assertEqual(run.stdout.strip(), "yes")
        self.assertNotIn(SUPPLEMENTAL_DEV_PASSWORD, rendered.stdout + rendered.stderr + run.stdout + run.stderr)

    def test_dev_only_supplemental_not_visible_on_test_profile(self):
        self._write_supplemental_map(
            "dev\tDEMO_SUPPLEMENTAL_DEV\tDEMO_SUPPLEMENTAL_DEV_KEY\n"
        )
        self._secrets_with_supplemental(DEMO_SUPPLEMENTAL_DEV_KEY=SUPPLEMENTAL_DEV_PASSWORD)
        (self.project / ".devcore" / "env.dev.template").write_text(
            (self.project / ".devcore" / "env.dev.template").read_text()
            + "DEMO_SUPPLEMENTAL_DEV={{DEMO_SUPPLEMENTAL_DEV}}\n"
        )
        self.run_tool("render")
        code = "import os; print('present' if os.getenv('DEMO_SUPPLEMENTAL_DEV') else 'absent')"
        dev = self.run_tool("run", "dev", "--", "python3", "-c", code)
        test = self.run_tool("run", "test", "--", "python3", "-c", code)
        self.assertEqual(dev.stdout.strip(), "present")
        self.assertEqual(test.stdout.strip(), "absent")

    def test_test_only_supplemental_not_visible_on_dev_profile(self):
        self._write_supplemental_map(
            "test\tDEMO_SUPPLEMENTAL_TEST\tDEMO_SUPPLEMENTAL_TEST_KEY\n"
        )
        self._secrets_with_supplemental(DEMO_SUPPLEMENTAL_TEST_KEY=SUPPLEMENTAL_TEST_PASSWORD)
        (self.project / ".devcore" / "env.test.template").write_text(
            (self.project / ".devcore" / "env.test.template").read_text()
            + "DEMO_SUPPLEMENTAL_TEST={{DEMO_SUPPLEMENTAL_TEST}}\n"
        )
        self.run_tool("render")
        code = "import os; print('present' if os.getenv('DEMO_SUPPLEMENTAL_TEST') else 'absent')"
        dev = self.run_tool("run", "dev", "--", "python3", "-c", code)
        test = self.run_tool("run", "test", "--", "python3", "-c", code)
        self.assertEqual(dev.stdout.strip(), "absent")
        self.assertEqual(test.stdout.strip(), "present")

    def test_all_profile_supplemental_visible_on_dev_test_and_all(self):
        self._write_supplemental_map(
            "all\tDEMO_SUPPLEMENTAL_SHARED\tDEMO_SUPPLEMENTAL_SHARED_KEY\n"
        )
        self._secrets_with_supplemental(DEMO_SUPPLEMENTAL_SHARED_KEY=SUPPLEMENTAL_SHARED_PASSWORD)
        (self.project / ".devcore" / "env.shared.template").write_text(
            (self.project / ".devcore" / "env.shared.template").read_text()
            + "DEMO_SUPPLEMENTAL_SHARED={{DEMO_SUPPLEMENTAL_SHARED}}\n"
        )
        self.run_tool("render")
        code = "import os; print('present' if os.getenv('DEMO_SUPPLEMENTAL_SHARED') else 'absent')"
        for profile in ("dev", "test", "all"):
            result = self.run_tool("run", profile, "--", "python3", "-c", code)
            self.assertEqual(result.stdout.strip(), "present", profile)

    def test_multiple_supplemental_secrets_bind(self):
        self._write_supplemental_map(
            "dev\tDEMO_SUPPLEMENTAL_ONE\tDEMO_SUPPLEMENTAL_ONE_KEY\n"
            "dev\tDEMO_SUPPLEMENTAL_TWO\tDEMO_SUPPLEMENTAL_TWO_KEY\n"
        )
        self._secrets_with_supplemental(
            DEMO_SUPPLEMENTAL_ONE_KEY=SUPPLEMENTAL_EXTRA_ONE,
            DEMO_SUPPLEMENTAL_TWO_KEY=SUPPLEMENTAL_EXTRA_TWO,
        )
        template = self.project / ".devcore" / "env.dev.template"
        template.write_text(
            template.read_text()
            + "DEMO_SUPPLEMENTAL_ONE={{DEMO_SUPPLEMENTAL_ONE}}\n"
            + "DEMO_SUPPLEMENTAL_TWO={{DEMO_SUPPLEMENTAL_TWO}}\n"
        )
        self.run_tool("render")
        code = (
            "import os; print('|'.join(sorted(["
            "'one' if os.environ.get('DEMO_SUPPLEMENTAL_ONE') else 'one-miss',"
            "'two' if os.environ.get('DEMO_SUPPLEMENTAL_TWO') else 'two-miss'"
            "])))"
        )
        run = self.run_tool("run", "dev", "--", "python3", "-c", code)
        self.assertEqual(run.stdout.strip(), "one|two")

    def test_missing_required_supplemental_fails_closed(self):
        self._write_supplemental_map(
            "dev\tDEMO_SUPPLEMENTAL_DEV\tDEMO_SUPPLEMENTAL_DEV_KEY\n"
        )
        self._secrets_with_supplemental()
        result = self.run_tool("render")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("missing DEMO_SUPPLEMENTAL_DEV_KEY", result.stderr)

    def test_missing_supplemental_error_does_not_print_other_secret_values(self):
        self._write_supplemental_map(
            "dev\tDEMO_SUPPLEMENTAL_DEV\tDEMO_SUPPLEMENTAL_DEV_KEY\n"
        )
        self._secrets_with_supplemental()
        result = self.run_tool("render")
        self.assertNotIn(DEV_PASSWORD, result.stdout + result.stderr)
        self.assertNotIn(TEST_PASSWORD, result.stdout + result.stderr)

    def test_owner_only_v1_consumer_unchanged_without_supplemental_map(self):
        result = self.run_tool("render")
        self.assertEqual(result.returncode, 0, result.stderr)
        dev_env = (self.project / ".env.dev").read_text()
        self.assertIn(f"DEV_DATABASE_PASSWORD={DEV_PASSWORD}", dev_env)

    def test_render_map_token_without_supplemental_declaration_does_not_bind_secret(self):
        template = self.project / ".devcore" / "env.dev.template"
        template.write_text(template.read_text() + "UNDECLARED={{UNDECLARED_SECRET}}\n")
        self.secrets.write_text(
            self.secrets.read_text() + "UNDECLARED_SECRET=" + SUPPLEMENTAL_DEV_PASSWORD + "\n"
        )
        self.secrets.chmod(0o600)
        result = self.run_tool("render")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Unresolved template tokens", result.stderr)
        self.assertNotIn(SUPPLEMENTAL_DEV_PASSWORD, result.stdout + result.stderr)

    def test_run_scrubs_parent_supplemental_and_uses_rendered_value(self):
        self._write_supplemental_map(
            "dev\tDEMO_SUPPLEMENTAL_DEV\tDEMO_SUPPLEMENTAL_DEV_KEY\n"
        )
        self._secrets_with_supplemental(DEMO_SUPPLEMENTAL_DEV_KEY=SUPPLEMENTAL_DEV_PASSWORD)
        (self.project / ".devcore" / "env.dev.template").write_text(
            (self.project / ".devcore" / "env.dev.template").read_text()
            + "DEMO_SUPPLEMENTAL_DEV={{DEMO_SUPPLEMENTAL_DEV}}\n"
        )
        self.run_tool("render")
        decoy = "SYNTHETIC_PARENT_DECOY_PASSWORD_4444444444444"
        env = self.env()
        env["DEMO_SUPPLEMENTAL_DEV"] = decoy
        code = (
            "import os; print('governed' if os.environ.get('DEMO_SUPPLEMENTAL_DEV') == "
            f"'{SUPPLEMENTAL_DEV_PASSWORD}' else 'inherited')"
        )
        run = self.run_tool("run", "dev", "--", "python3", "-c", code, env=env)
        self.assertEqual(run.returncode, 0, run.stderr)
        self.assertEqual(run.stdout.strip(), "governed")
        self.assertNotIn(decoy, run.stdout + run.stderr)
        self.assertNotIn(SUPPLEMENTAL_DEV_PASSWORD, run.stdout + run.stderr)

    def test_invalid_supplemental_declaration_fails_contract_validation(self):
        self._write_supplemental_map("dev\tbad env\tDEMO_SUPPLEMENTAL_DEV_KEY\n")
        result = self.run_tool("plan")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("ENV_VAR", result.stderr)

    def test_duplicate_supplemental_binding_fails_closed(self):
        self._write_supplemental_map(
            "dev\tDEMO_SUPPLEMENTAL_DEV\tDEMO_SUPPLEMENTAL_DEV_KEY\n"
            "dev\tDEMO_SUPPLEMENTAL_DEV\tDEMO_SUPPLEMENTAL_DEV_KEY_ALT\n"
        )
        result = self.run_tool("plan")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("duplicate supplemental binding", result.stderr)


if __name__ == "__main__":
    unittest.main()
