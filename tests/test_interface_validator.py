import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
VALIDATOR = ROOT / "interface-validate" / "scripts" / "interface-validate.py"


class InterfaceValidatorTests(unittest.TestCase):
    def run_validator(self, group: str, custom_group: str | None = None):
        with tempfile.TemporaryDirectory() as temporary:
            config_root = Path(temporary)
            custom_xml = (
                f"<CommandGroup>{custom_group}</CommandGroup>"
                if custom_group
                else ""
            )
            (config_root / "Configuration.xml").write_text(
                "<?xml version=\"1.0\" encoding=\"utf-8\"?>"
                "<MetaDataObject><Configuration><ChildObjects>"
                f"{custom_xml}"
                "</ChildObjects></Configuration></MetaDataObject>",
                encoding="utf-8",
            )
            ci_dir = config_root / "Subsystems" / "Test" / "Ext"
            ci_dir.mkdir(parents=True)
            ci_path = ci_dir / "CommandInterface.xml"
            ci_path.write_text(
                "<?xml version=\"1.0\" encoding=\"utf-8\"?>"
                "<CommandInterface xmlns=\"http://v8.1c.ru/8.3/xcf/extrnprops\" "
                "version=\"2.17\"><CommandsPlacement>"
                "<Command name=\"Catalog.Test.StandardCommand.OpenList\">"
                f"<CommandGroup>{group}</CommandGroup><Placement>Auto</Placement>"
                "</Command></CommandsPlacement></CommandInterface>",
                encoding="utf-8",
            )
            return subprocess.run(
                [sys.executable, str(VALIDATOR), "-CIPath", str(ci_path)],
                cwd=ROOT,
                capture_output=True,
                text=True,
                encoding="utf-8",
                check=False,
            )

    def test_builtin_command_group_is_accepted(self):
        result = self.run_validator("NavigationPanelOrdinary")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_missing_custom_command_group_is_rejected(self):
        result = self.run_validator("CommandGroup.Сервис")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("unknown command group", result.stdout)

    def test_declared_custom_command_group_is_accepted(self):
        result = self.run_validator(
            "CommandGroup.Сервис",
            custom_group="Сервис",
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
