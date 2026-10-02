import subprocess
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BRIDGE_SOURCE = ROOT / "codex-test-bridge" / "src"
FIXTURE_SOURCE = ROOT / "codex-ui-test-fixtures" / "src"


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
            str(ROOT / "extension" / "scripts" / "validate.py"),
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
            str(ROOT / "metadata" / "scripts" / "validate.py"),
            "-ObjectPath",
            "|".join(map(str, objects)),
            "-Detailed",
        )

    def test_extension_validator_on_fixture_sources(self):
        self.run_validator(
            str(ROOT / "extension" / "scripts" / "validate.py"),
            "-ExtensionPath",
            str(FIXTURE_SOURCE),
            "-Detailed",
        )

    def test_metadata_validator_on_fixture_objects(self):
        objects = sorted(
            path for path in FIXTURE_SOURCE.glob("*/*.xml")
            if path.parent.name not in {"CommonCommands", "CommonForms", "Subsystems"}
        )
        self.assertTrue(objects)
        self.run_validator(
            str(ROOT / "metadata" / "scripts" / "validate.py"),
            "-ObjectPath",
            "|".join(map(str, objects)),
            "-Detailed",
        )

    def test_form_validator_on_fixture_forms(self):
        forms = sorted(FIXTURE_SOURCE.glob("**/Ext/Form.xml"))
        self.assertTrue(forms)
        for form in forms:
            with self.subTest(form=form):
                self.run_validator(
                    str(ROOT / "forms" / "scripts" / "validate.py"),
                    "-FormPath",
                    str(form),
                    "-Detailed",
                )


if __name__ == "__main__":
    unittest.main()
