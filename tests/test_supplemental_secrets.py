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
TOKEN_STYLE_SECRET = "synthetic+api:token-value"


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

    def test_run_dev_scrubs_test_only_parent_supplemental_var(self):
        self._write_supplemental_map(
            "test\tDEMO_SUPPLEMENTAL_TEST\tDEMO_SUPPLEMENTAL_TEST_KEY\n"
        )
        self._secrets_with_supplemental(DEMO_SUPPLEMENTAL_TEST_KEY=SUPPLEMENTAL_TEST_PASSWORD)
        (self.project / ".devcore" / "env.test.template").write_text(
            (self.project / ".devcore" / "env.test.template").read_text()
            + "DEMO_SUPPLEMENTAL_TEST={{DEMO_SUPPLEMENTAL_TEST}}\n"
        )
        self.run_tool("render")
        env = self.env()
        env["DEMO_SUPPLEMENTAL_TEST"] = "SYNTHETIC_PARENT_DECOY_FOR_TEST_ONLY_999999"
        code = "import os; print('absent' if not os.getenv('DEMO_SUPPLEMENTAL_TEST') else 'present')"
        run = self.run_tool("run", "dev", "--", "python3", "-c", code, env=env)
        self.assertEqual(run.returncode, 0, run.stderr)
        self.assertEqual(run.stdout.strip(), "absent")

    def test_run_test_scrubs_dev_only_parent_supplemental_var(self):
        self._write_supplemental_map(
            "dev\tDEMO_SUPPLEMENTAL_DEV\tDEMO_SUPPLEMENTAL_DEV_KEY\n"
        )
        self._secrets_with_supplemental(DEMO_SUPPLEMENTAL_DEV_KEY=SUPPLEMENTAL_DEV_PASSWORD)
        (self.project / ".devcore" / "env.dev.template").write_text(
            (self.project / ".devcore" / "env.dev.template").read_text()
            + "DEMO_SUPPLEMENTAL_DEV={{DEMO_SUPPLEMENTAL_DEV}}\n"
        )
        self.run_tool("render")
        env = self.env()
        env["DEMO_SUPPLEMENTAL_DEV"] = "SYNTHETIC_PARENT_DECOY_FOR_DEV_ONLY_88888888"
        code = "import os; print('absent' if not os.getenv('DEMO_SUPPLEMENTAL_DEV') else 'present')"
        run = self.run_tool("run", "test", "--", "python3", "-c", code, env=env)
        self.assertEqual(run.returncode, 0, run.stderr)
        self.assertEqual(run.stdout.strip(), "absent")

    def test_missing_test_supplemental_does_not_block_dev_run(self):
        self._write_supplemental_map(
            "dev\tDEMO_SUPPLEMENTAL_DEV\tDEMO_SUPPLEMENTAL_DEV_KEY\n"
            "test\tDEMO_SUPPLEMENTAL_TEST\tDEMO_SUPPLEMENTAL_TEST_KEY\n"
        )
        (self.project / ".devcore" / "env.dev.template").write_text(
            (self.project / ".devcore" / "env.dev.template").read_text()
            + "DEMO_SUPPLEMENTAL_DEV={{DEMO_SUPPLEMENTAL_DEV}}\n"
        )
        (self.project / ".devcore" / "env.test.template").write_text(
            (self.project / ".devcore" / "env.test.template").read_text()
            + "DEMO_SUPPLEMENTAL_TEST={{DEMO_SUPPLEMENTAL_TEST}}\n"
        )
        self._secrets_with_supplemental(
            DEMO_SUPPLEMENTAL_DEV_KEY=SUPPLEMENTAL_DEV_PASSWORD,
            DEMO_SUPPLEMENTAL_TEST_KEY=SUPPLEMENTAL_TEST_PASSWORD,
        )
        self.assertEqual(self.run_tool("render").returncode, 0)
        self._secrets_with_supplemental(DEMO_SUPPLEMENTAL_DEV_KEY=SUPPLEMENTAL_DEV_PASSWORD)
        code = "import os; print('ok' if os.getenv('DEMO_SUPPLEMENTAL_DEV') else 'missing')"
        run = self.run_tool("run", "dev", "--", "python3", "-c", code)
        self.assertEqual(run.returncode, 0, run.stderr)
        self.assertEqual(run.stdout.strip(), "ok")

    def test_missing_dev_supplemental_does_not_block_test_run(self):
        self._write_supplemental_map(
            "dev\tDEMO_SUPPLEMENTAL_DEV\tDEMO_SUPPLEMENTAL_DEV_KEY\n"
            "test\tDEMO_SUPPLEMENTAL_TEST\tDEMO_SUPPLEMENTAL_TEST_KEY\n"
        )
        (self.project / ".devcore" / "env.dev.template").write_text(
            (self.project / ".devcore" / "env.dev.template").read_text()
            + "DEMO_SUPPLEMENTAL_DEV={{DEMO_SUPPLEMENTAL_DEV}}\n"
        )
        (self.project / ".devcore" / "env.test.template").write_text(
            (self.project / ".devcore" / "env.test.template").read_text()
            + "DEMO_SUPPLEMENTAL_TEST={{DEMO_SUPPLEMENTAL_TEST}}\n"
        )
        self._secrets_with_supplemental(
            DEMO_SUPPLEMENTAL_DEV_KEY=SUPPLEMENTAL_DEV_PASSWORD,
            DEMO_SUPPLEMENTAL_TEST_KEY=SUPPLEMENTAL_TEST_PASSWORD,
        )
        self.assertEqual(self.run_tool("render").returncode, 0)
        self._secrets_with_supplemental(DEMO_SUPPLEMENTAL_TEST_KEY=SUPPLEMENTAL_TEST_PASSWORD)
        code = "import os; print('ok' if os.getenv('DEMO_SUPPLEMENTAL_TEST') else 'missing')"
        run = self.run_tool("run", "test", "--", "python3", "-c", code)
        self.assertEqual(run.returncode, 0, run.stderr)
        self.assertEqual(run.stdout.strip(), "ok")

    def test_missing_applicable_dev_supplemental_still_fails_dev_run(self):
        self._write_supplemental_map(
            "dev\tDEMO_SUPPLEMENTAL_DEV\tDEMO_SUPPLEMENTAL_DEV_KEY\n"
        )
        (self.project / ".devcore" / "env.dev.template").write_text(
            (self.project / ".devcore" / "env.dev.template").read_text()
            + "DEMO_SUPPLEMENTAL_DEV={{DEMO_SUPPLEMENTAL_DEV}}\n"
        )
        self._secrets_with_supplemental(DEMO_SUPPLEMENTAL_DEV_KEY=SUPPLEMENTAL_DEV_PASSWORD)
        self.assertEqual(self.run_tool("render").returncode, 0)
        self._secrets_with_supplemental()
        run = self.run_tool("run", "dev", "--", "python3", "-c", "print('ran')")
        self.assertNotEqual(run.returncode, 0)
        self.assertIn("missing DEMO_SUPPLEMENTAL_DEV_KEY", run.stderr)
        self.assertNotIn("ran", run.stdout)

    def test_reserved_env_var_collision_rejected(self):
        self._write_supplemental_map(
            "dev\tDEV_DB_PASSWORD\tDEMO_SUPPLEMENTAL_DEV_KEY\n"
        )
        result = self.run_tool("plan")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("reserved render token", result.stderr)

    def test_owner_secret_key_collision_rejected(self):
        self._write_supplemental_map(
            "dev\tDEMO_SUPPLEMENTAL_DEV\tDEMO_DEV_DB_PASSWORD\n"
        )
        result = self.run_tool("plan")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("cannot reuse owner secret key", result.stderr)

    def test_plan_fails_when_declared_supplemental_secret_missing(self):
        self._write_supplemental_map(
            "dev\tDEMO_SUPPLEMENTAL_DEV\tDEMO_SUPPLEMENTAL_DEV_KEY\n"
        )
        self._secrets_with_supplemental()
        result = self.run_tool("plan")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("missing DEMO_SUPPLEMENTAL_DEV_KEY", result.stderr)
        self.assertIn("[missing]", result.stdout)

    def test_ambiguous_all_and_dev_binding_fails_plan(self):
        self._write_supplemental_map(
            "all\tDEMO_SUPPLEMENTAL_SHARED\tDEMO_SUPPLEMENTAL_SHARED_KEY\n"
            "dev\tDEMO_SUPPLEMENTAL_SHARED\tDEMO_SUPPLEMENTAL_DEV_KEY\n"
        )
        self._secrets_with_supplemental(
            DEMO_SUPPLEMENTAL_SHARED_KEY=SUPPLEMENTAL_SHARED_PASSWORD,
            DEMO_SUPPLEMENTAL_DEV_KEY=SUPPLEMENTAL_DEV_PASSWORD,
        )
        result = self.run_tool("plan")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("ambiguous supplemental env_var", result.stderr)

    def test_supplemental_accepts_generic_token_style_value(self):
        self._write_supplemental_map(
            "dev\tDEMO_API_TOKEN\tDEMO_API_TOKEN_KEY\n"
        )
        self._secrets_with_supplemental(DEMO_API_TOKEN_KEY=TOKEN_STYLE_SECRET)
        (self.project / ".devcore" / "env.dev.template").write_text(
            (self.project / ".devcore" / "env.dev.template").read_text()
            + "DEMO_API_TOKEN={{DEMO_API_TOKEN}}\n"
        )
        rendered = self.run_tool("render")
        self.assertEqual(rendered.returncode, 0, rendered.stderr)
        self.assertIn(f"DEMO_API_TOKEN={TOKEN_STYLE_SECRET}", (self.project / ".env.dev").read_text())

    def test_rotate_preflight_aborts_without_owner_mutation_or_provisioning(self):
        self._write_supplemental_map(
            "dev\tDEMO_SUPPLEMENTAL_DEV\tDEMO_SUPPLEMENTAL_DEV_KEY\n"
        )
        self._secrets_with_supplemental()
        self._start_database_endpoints()
        self._install_database_mocks()
        env, log = self._mock_env()
        log.write_text("")
        before = self.secrets.read_text()
        result = self.run_tool("rotate", env=env)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.secrets.read_text(), before)
        self.assertNotIn("provision", log.read_text())
        self.assertIn("missing DEMO_SUPPLEMENTAL_DEV_KEY", result.stderr)

    def test_activate_preflight_aborts_before_provisioning_when_supplemental_missing(self):
        self._write_supplemental_map(
            "dev\tDEMO_SUPPLEMENTAL_DEV\tDEMO_SUPPLEMENTAL_DEV_KEY\n"
        )
        self._secrets_with_supplemental()
        self._start_database_endpoints()
        self._install_database_mocks()
        env, log = self._mock_env()
        log.write_text("")
        result = self.run_tool("activate", env=env)
        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn("provision", log.read_text())
        self.assertIn("missing DEMO_SUPPLEMENTAL_DEV_KEY", result.stderr)


if __name__ == "__main__":
    unittest.main()
