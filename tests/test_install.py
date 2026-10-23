import hashlib
import os
import subprocess
import tempfile
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

    def run_installer(self, version, checksum):
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
            env=self.env,
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
        self.assertEqual([backup.name.split(".")[-2] for backup in backups], ["000000000", "000000001"])
        self.assertEqual(backups[0].read_bytes(), synthetic_tool("1.0.0"))
        self.assertEqual(backups[1].read_bytes(), synthetic_tool("1.0.1"))

        rollback = self.run_rollback()
        self.assertEqual(rollback.returncode, 0, rollback.stderr)
        self.assertEqual(self.target.read_bytes(), synthetic_tool("1.0.1"))

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

    def test_rollback_uses_timestamp_before_pid_when_updates_share_a_second(self):
        self.target.parent.mkdir(parents=True)
        self.target.write_bytes(synthetic_tool("1.0.2"))
        self.target.chmod(0o700)

        older = self.target.parent / "devcore-project.previous.20261023T094600.100000000Z.000000000.99999"
        newer = self.target.parent / "devcore-project.previous.20261023T094600.100000001Z.000000000.1"
        older.write_bytes(synthetic_tool("1.0.0"))
        newer.write_bytes(synthetic_tool("1.0.1"))
        older.chmod(0o700)
        newer.chmod(0o700)

        rollback = self.run_rollback()
        self.assertEqual(rollback.returncode, 0, rollback.stderr)
        self.assertEqual(self.target.read_bytes(), synthetic_tool("1.0.1"))

    def test_rollback_uses_sequence_when_backup_timestamps_match(self):
        self.target.parent.mkdir(parents=True)
        self.target.write_bytes(synthetic_tool("1.0.2"))
        self.target.chmod(0o700)

        older = self.target.parent / "devcore-project.previous.20261023T094600.100000000Z.000000000.99999"
        newer = self.target.parent / "devcore-project.previous.20261023T094600.100000000Z.000000001.1"
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
