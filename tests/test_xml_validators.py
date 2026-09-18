import subprocess
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BRIDGE_SOURCE = ROOT / "codex-test-bridge" / "src"


class XmlValidatorSmokeTests(unittest.TestCase):
    def run_validator(self, *arguments: str) -> None:
        result = subprocess.run(
            [sys.executable, *arguments],
            cwd=ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_extension_validator_on_bridge_sources(self):
        self.run_validator(
            str(ROOT / "cfe-validate" / "scripts" / "cfe-validate.py"),
            "-ExtensionPath",
            str(BRIDGE_SOURCE),
            "-Detailed",
        )

    def test_metadata_validator_on_bridge_objects(self):
        objects = [
            BRIDGE_SOURCE / "CommonModules" / "CodexUIJobsServer.xml",
            BRIDGE_SOURCE / "HTTPServices" / "CodexTestBridge.xml",
            BRIDGE_SOURCE / "InformationRegisters" / "CodexUIJobs.xml",
        ]
        self.run_validator(
            str(ROOT / "meta-validate" / "scripts" / "meta-validate.py"),
            "-ObjectPath",
            "|".join(map(str, objects)),
            "-Detailed",
        )


if __name__ == "__main__":
    unittest.main()
