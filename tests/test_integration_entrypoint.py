import os
import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ENTRYPOINT = ROOT / "codex-test-bridge" / "scripts" / "linux_flow.sh"


class IntegrationEntrypointTests(unittest.TestCase):
    def test_doctor_fails_when_real_integration_environment_is_absent(self):
        environment = {
            "PATH": os.environ.get("PATH", ""),
            "HOME": os.environ.get("HOME", ""),
        }
        result = subprocess.run(
            ["bash", str(ENTRYPOINT), "doctor"],
            cwd=ROOT,
            env=environment,
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=False,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(result.stdout, "")
        self.assertIn("CODEX_IBCMD is required", result.stderr)


if __name__ == "__main__":
    unittest.main()
