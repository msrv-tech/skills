import os
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RESOLVER = ROOT / "scripts" / "resolve_ibcmd_linux.sh"


@unittest.skipIf(os.name == "nt", "Linux executable layout test")
class LinuxIbcmdLayoutTests(unittest.TestCase):
    def resolve(self, value: Path) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["bash", "-c", '. "$1"; resolve_ibcmd_path "$2"', "bash", str(RESOLVER), str(value)],
            text=True,
            capture_output=True,
            check=False,
        )

    @staticmethod
    def executable(path: Path) -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
        path.chmod(0o755)
        return path

    def test_explicit_executable_is_used_unchanged(self):
        with tempfile.TemporaryDirectory() as directory:
            executable = self.executable(Path(directory) / "custom ibcmd")
            result = self.resolve(executable)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout.strip(), str(executable))

    def test_version_directory_supports_root_layout(self):
        with tempfile.TemporaryDirectory() as directory:
            executable = self.executable(Path(directory) / "ibcmd")
            result = self.resolve(Path(directory))
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout.strip(), str(executable))

    def test_version_directory_supports_bin_layout(self):
        with tempfile.TemporaryDirectory() as directory:
            executable = self.executable(Path(directory) / "bin" / "ibcmd")
            result = self.resolve(Path(directory))
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout.strip(), str(executable))

    def test_version_directory_rejects_ambiguous_layout(self):
        with tempfile.TemporaryDirectory() as directory:
            self.executable(Path(directory) / "ibcmd")
            self.executable(Path(directory) / "bin" / "ibcmd")
            result = self.resolve(Path(directory))
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("both ibcmd layouts exist", result.stderr)
            self.assertIn("specify the exact executable path", result.stderr)

    def test_missing_and_non_executable_candidates_fail(self):
        with tempfile.TemporaryDirectory() as directory:
            missing = self.resolve(Path(directory))
            self.assertNotEqual(missing.returncode, 0)
            self.assertIn("checked", missing.stderr)

            candidate = Path(directory) / "ibcmd"
            candidate.write_text("", encoding="utf-8")
            candidate.chmod(0o644)
            non_executable = self.resolve(Path(directory))
            self.assertNotEqual(non_executable.returncode, 0)
            self.assertIn("not executable", non_executable.stderr)


if __name__ == "__main__":
    unittest.main()
