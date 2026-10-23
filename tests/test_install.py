import hashlib
import os
import shutil
import subprocess
import tempfile
import time
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
INSTALLER = ROOT / "install" / "install.sh"
ROLLBACK = ROOT / "install" / "rollback.sh"


def synthetic_tool(version):
    return (
        "#!/usr/bin/env bash\n"
        "set -euo pipefail\n"
        f'VERSION="{version}"\n'
        'if [[ "${1-}" == "--version" ]]; then printf "devcore-project %s\\n" "$VERSION"; fi\n'
    ).encode()


class InstallerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="devcore-install-test-")
        self.root = Path(self.temp.name)
        self.home = self.root / "home"
        self.home.mkdir()
        self.target = self.home / ".local" / "bin" / "devcore-project"
        self.source = self.root / "release" / "devcore-project"
        self.source.parent.mkdir()
        self.env = {"HOME": str(self.home), "PATH": os.environ["PATH"], "LC_ALL": "C"}

    def tearDown(self):
        self.temp.cleanup()

    def write_source(self, version):
        data = synthetic_tool(version)
        self.source.write_bytes(data)
        self.source.chmod(0o700)
        return hashlib.sha256(data).hexdigest()

    def run_installer(self, version, checksum, env=None):
        return subprocess.run(
            [
                "bash",
                str(INSTALLER),
                "--source",
                str(self.source),
                "--version",
                version,
                "--sha256",
                checksum,
            ],
            env=env or self.env,
            capture_output=True,
            text=True,
            timeout=10,
        )

    def run_rollback(self):
        return subprocess.run(
            ["bash", str(ROLLBACK)],
            env=self.env,
            capture_output=True,
            text=True,
            timeout=10,
        )

    def test_install_updates_user_local_binary_and_keeps_backup(self):
        original_checksum = self.write_source("1.0.0")
        first = self.run_installer("1.0.0", original_checksum)
        self.assertEqual(first.returncode, 0, first.stderr)
        self.assertTrue(self.target.is_file())
        self.assertEqual(self.target.stat().st_mode & 0o777, 0o700)
        operation_lock = self.target.parent / ".devcore-project-operation.lock"
        self.assertTrue(operation_lock.is_file())
        self.assertEqual(operation_lock.stat().st_mode & 0o777, 0o600)
        original_bytes = self.target.read_bytes()

        next_checksum = self.write_source("1.0.1")
        update = self.run_installer("1.0.1", next_checksum)
        self.assertEqual(update.returncode, 0, update.stderr)
        self.assertIn("1.0.1", self.target.read_text())
        self.assertEqual(self.target.stat().st_mode & 0o777, 0o700)
        backups = list(self.target.parent.glob("devcore-project.previous.*"))
        self.assertEqual(len(backups), 1)
        self.assertEqual(backups[0].read_bytes(), original_bytes)

    def test_installer_sequences_backups_when_timestamp_repeats(self):
        date_bin = self.root / "mock-bin"
        date_bin.mkdir()
        date_command = date_bin / "date"
        date_command.write_text('#!/usr/bin/env bash\nprintf "%s\\n" "20261023T094600.100000000Z"\n')
        date_command.chmod(0o700)
        self.env["PATH"] = f"{date_bin}:{os.environ['PATH']}"

        for version in ("1.0.0", "1.0.1", "1.0.2"):
            checksum = self.write_source(version)
            result = self.run_installer(version, checksum)
            self.assertEqual(result.returncode, 0, result.stderr)

        backups = sorted(self.target.parent.glob("devcore-project.previous.*"))
        self.assertEqual([backup.name.split(".")[2] for backup in backups], ["000000000", "000000001"])
        self.assertEqual(backups[0].read_bytes(), synthetic_tool("1.0.0"))
        self.assertEqual(backups[1].read_bytes(), synthetic_tool("1.0.1"))

        rollback = self.run_rollback()
        self.assertEqual(rollback.returncode, 0, rollback.stderr)
        self.assertEqual(self.target.read_bytes(), synthetic_tool("1.0.1"))

    def test_rollback_uses_install_order_when_system_clock_moves_backwards(self):
        date_bin = self.root / "mock-bin"
        date_bin.mkdir()
        date_state = self.root / "date-used"
        date_command = date_bin / "date"
        date_command.write_text(
            '#!/usr/bin/env bash\n'
            'if [[ ! -e "$DATE_STATE" ]]; then\n'
            '  : > "$DATE_STATE"\n'
            '  printf "%s\\n" "20261023T094601.000000000Z"\n'
            'else\n'
            '  printf "%s\\n" "20261023T094600.000000000Z"\n'
            'fi\n'
        )
        date_command.chmod(0o700)
        self.env["PATH"] = f"{date_bin}:{os.environ['PATH']}"
        self.env["DATE_STATE"] = str(date_state)

        for version in ("1.0.0", "1.0.1", "1.0.2"):
            checksum = self.write_source(version)
            result = self.run_installer(version, checksum)
            self.assertEqual(result.returncode, 0, result.stderr)

        rollback = self.run_rollback()
        self.assertEqual(rollback.returncode, 0, rollback.stderr)
        self.assertEqual(self.target.read_bytes(), synthetic_tool("1.0.1"))

    def test_install_and_rollback_reject_insecure_existing_lock_file(self):
        lock_path = self.target.parent / ".devcore-project-operation.lock"
        lock_path.parent.mkdir(parents=True)
        lock_path.touch()
        lock_path.chmod(0o644)

        checksum = self.write_source("1.0.0")
        install = self.run_installer("1.0.0", checksum)
        self.assertNotEqual(install.returncode, 0)
        self.assertIn("operation lock must be owned by the current user with mode 0600", install.stderr)
        self.assertFalse(self.target.exists())

        self.target.parent.mkdir(parents=True, exist_ok=True)
        backup = self.target.parent / "devcore-project.previous.000000000.20261023T094600.100000000Z.1"
        backup.write_bytes(synthetic_tool("1.0.0"))
        backup.chmod(0o700)
        rollback = self.run_rollback()
        self.assertNotEqual(rollback.returncode, 0)
        self.assertIn("operation lock must be owned by the current user with mode 0600", rollback.stderr)
        self.assertFalse(self.target.exists())

    def test_concurrent_install_and_rollback_are_rejected(self):
        original_checksum = self.write_source("1.0.0")
        first_install = self.run_installer("1.0.0", original_checksum)
        self.assertEqual(first_install.returncode, 0, first_install.stderr)
        original_bytes = self.target.read_bytes()

        date_bin = self.root / "mock-bin"
        date_bin.mkdir()
        date_command = date_bin / "date"
        date_command.write_text('#!/usr/bin/env bash\nprintf "%s\\n" "20261023T094600.100000000Z"\n')
        date_command.chmod(0o700)
        install_wrapper = date_bin / "install"
        install_wrapper.write_text(
            "#!/usr/bin/env bash\n"
            "set -euo pipefail\n"
            '"$REAL_INSTALL" "$@"\n'
            'if [[ "${BLOCK_BACKUP_COPY:-0}" == 1 && "${4-}" == "$INSTALL_TARGET" && ! -e "$BLOCK_USED" ]]; then\n'
            '  : > "$BLOCK_USED"\n'
            '  while [[ ! -e "$BLOCK_RELEASE" ]]; do sleep 0.01; done\n'
            "fi\n"
        )
        install_wrapper.chmod(0o700)

        blocked_env = dict(self.env)
        blocked_env["PATH"] = f"{date_bin}:{os.environ['PATH']}"
        blocked_env["REAL_INSTALL"] = shutil.which("install")
        blocked_env["INSTALL_TARGET"] = str(self.target)
        blocked_env["BLOCK_BACKUP_COPY"] = "1"
        blocked_env["BLOCK_USED"] = str(self.root / "backup-copied")
        blocked_env["BLOCK_RELEASE"] = str(self.root / "release-backup-copy")

        update_checksum = self.write_source("1.0.1")
        first_update = subprocess.Popen(
            [
                "bash",
                str(INSTALLER),
                "--source",
                str(self.source),
                "--version",
                "1.0.1",
                "--sha256",
                update_checksum,
            ],
            env=blocked_env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )

        second_update = None
        concurrent_rollback = None
        first_stderr = ""
        try:
            deadline = time.monotonic() + 5
            while not Path(blocked_env["BLOCK_USED"]).exists() and time.monotonic() < deadline:
                time.sleep(0.01)
            self.assertTrue(Path(blocked_env["BLOCK_USED"]).exists(), "installer did not reach the backup snapshot")

            second_checksum = self.write_source("1.0.2")
            second_env = dict(blocked_env)
            second_env["BLOCK_BACKUP_COPY"] = "0"
            second_update = self.run_installer("1.0.2", second_checksum, second_env)
            concurrent_rollback = subprocess.run(
                ["bash", str(ROLLBACK)],
                env=second_env,
                capture_output=True,
                text=True,
                timeout=10,
            )
        finally:
            Path(blocked_env["BLOCK_RELEASE"]).touch()
            _, first_stderr = first_update.communicate(timeout=10)

        self.assertEqual(first_update.returncode, 0, first_stderr)
        self.assertIsNotNone(second_update)
        self.assertNotEqual(second_update.returncode, 0)
        self.assertIn("another DevCore install or rollback is active", second_update.stderr)
        self.assertIsNotNone(concurrent_rollback)
        self.assertNotEqual(concurrent_rollback.returncode, 0)
        self.assertIn("another DevCore install or rollback is active", concurrent_rollback.stderr)

        rollback = self.run_rollback()
        self.assertEqual(rollback.returncode, 0, rollback.stderr)
        self.assertEqual(self.target.read_bytes(), original_bytes)

    def test_bad_checksum_leaves_previous_install_unchanged(self):
        original_checksum = self.write_source("1.0.0")
        first = self.run_installer("1.0.0", original_checksum)
        self.assertEqual(first.returncode, 0, first.stderr)
        original = self.target.read_bytes()

        next_checksum = self.write_source("1.0.1")
        update = self.run_installer("1.0.1", "0" * 64)
        self.assertNotEqual(update.returncode, 0)
        self.assertEqual(self.target.read_bytes(), original)
        self.assertNotIn(next_checksum, update.stdout + update.stderr)

    def test_version_mismatch_leaves_previous_install_unchanged(self):
        first_checksum = self.write_source("1.0.0")
        first = self.run_installer("1.0.0", first_checksum)
        self.assertEqual(first.returncode, 0, first.stderr)
        original = self.target.read_bytes()

        checksum = self.write_source("1.0.1")
        result = self.run_installer("1.0.2", checksum)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.target.read_bytes(), original)

    def test_invalid_bash_syntax_leaves_previous_install_unchanged(self):
        first_checksum = self.write_source("1.0.0")
        first = self.run_installer("1.0.0", first_checksum)
        self.assertEqual(first.returncode, 0, first.stderr)
        original = self.target.read_bytes()

        invalid = b'#!/usr/bin/env bash\nVERSION="1.0.1"\nif then\n'
        self.source.write_bytes(invalid)
        invalid_checksum = hashlib.sha256(invalid).hexdigest()
        result = self.run_installer("1.0.1", invalid_checksum)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.target.read_bytes(), original)

    def test_rollback_restores_previous_version(self):
        original_checksum = self.write_source("1.0.0")
        first = self.run_installer("1.0.0", original_checksum)
        self.assertEqual(first.returncode, 0, first.stderr)
        original = self.target.read_bytes()
        next_checksum = self.write_source("1.0.1")
        update = self.run_installer("1.0.1", next_checksum)
        self.assertEqual(update.returncode, 0, update.stderr)

        rollback = self.run_rollback()
        self.assertEqual(rollback.returncode, 0, rollback.stderr)
        self.assertEqual(self.target.read_bytes(), original)
        self.assertEqual(self.target.stat().st_mode & 0o777, 0o700)
        self.assertEqual(len(list(self.target.parent.glob("devcore-project.rolled-back.*"))), 1)

    def test_rollback_uses_install_sequence_before_timestamp_and_pid(self):
        self.target.parent.mkdir(parents=True)
        self.target.write_bytes(synthetic_tool("1.0.2"))
        self.target.chmod(0o700)

        older = self.target.parent / "devcore-project.previous.000000000.20261023T094600.100000000Z.99999"
        newer = self.target.parent / "devcore-project.previous.000000001.20261023T094600.100000001Z.1"
        older.write_bytes(synthetic_tool("1.0.0"))
        newer.write_bytes(synthetic_tool("1.0.1"))
        older.chmod(0o700)
        newer.chmod(0o700)

        rollback = self.run_rollback()
        self.assertEqual(rollback.returncode, 0, rollback.stderr)
        self.assertEqual(self.target.read_bytes(), synthetic_tool("1.0.1"))

    def test_rollback_uses_install_sequence_when_backup_timestamps_match(self):
        self.target.parent.mkdir(parents=True)
        self.target.write_bytes(synthetic_tool("1.0.2"))
        self.target.chmod(0o700)

        older = self.target.parent / "devcore-project.previous.000000000.20261023T094600.100000000Z.99999"
        newer = self.target.parent / "devcore-project.previous.000000001.20261023T094600.100000000Z.1"
        older.write_bytes(synthetic_tool("1.0.0"))
        newer.write_bytes(synthetic_tool("1.0.1"))
        older.chmod(0o700)
        newer.chmod(0o700)

        rollback = self.run_rollback()
        self.assertEqual(rollback.returncode, 0, rollback.stderr)
        self.assertEqual(self.target.read_bytes(), synthetic_tool("1.0.1"))

    def test_symlink_target_is_rejected_without_changing_external_file(self):
        outside = self.root / "outside-tool"
        outside.write_bytes(b"preserve this file\n")
        self.target.parent.mkdir(parents=True)
        self.target.symlink_to(outside)
        checksum = self.write_source("1.0.0")
        result = self.run_installer("1.0.0", checksum)
        self.assertNotEqual(result.returncode, 0)
        self.assertTrue(self.target.is_symlink())
        self.assertEqual(outside.read_bytes(), b"preserve this file\n")

    def test_symlink_install_directory_is_rejected_before_outside_write(self):
        outside = self.root / "outside-home-path"
        outside.mkdir()
        (self.home / ".local").symlink_to(outside, target_is_directory=True)
        checksum = self.write_source("1.0.0")
        result = self.run_installer("1.0.0", checksum)
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse((outside / "bin").exists())

    def test_rollback_refuses_symlink_target(self):
        outside = self.root / "outside-tool"
        outside.write_bytes(b"preserve this file\n")
        self.target.parent.mkdir(parents=True)
        backup = self.target.parent / "devcore-project.previous.test"
        backup.write_bytes(synthetic_tool("1.0.0"))
        backup.chmod(0o700)
        self.target.symlink_to(outside)
        result = self.run_rollback()
        self.assertNotEqual(result.returncode, 0)
        self.assertTrue(self.target.is_symlink())
        self.assertEqual(outside.read_bytes(), b"preserve this file\n")

    def test_rollback_ignores_unrecognized_backup_names(self):
        self.target.parent.mkdir(parents=True)
        invalid_backup = self.target.parent / "devcore-project.previous.not-a-timestamp"
        invalid_backup.write_bytes(synthetic_tool("1.0.0"))
        invalid_backup.chmod(0o700)
        result = self.run_rollback()
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(self.target.exists())


if __name__ == "__main__":
    unittest.main()
