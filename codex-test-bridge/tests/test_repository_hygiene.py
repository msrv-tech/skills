import subprocess
import sys
import unittest
from pathlib import Path


class RepositoryHygieneTests(unittest.TestCase):
    def test_distributable_files_do_not_contain_environment_access_data(self):
        root = Path(__file__).resolve().parents[1]
        result = subprocess.run(
            [sys.executable, str(root / "scripts" / "check_repository_hygiene.py")],
            cwd=root,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
