import os
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from run_ui_from_test_database import select_database, temporary_environment


class RunUiFromTestDatabaseTests(unittest.TestCase):
    def test_selects_by_project_folder_without_exposing_credentials(self):
        entry = {
            "path": "X:/private/bp",
            "Srvr": "server",
            "Ref": "accounting",
            "User": "secret-user",
            "Password": "secret-password",
            "Bridge": {"AppName": "bp-test", "BaseUrl": "http://localhost/bp"},
        }
        self.assertIs(select_database({"databases": [entry]}, "BP"), entry)

    def test_rejects_incomplete_entry(self):
        with self.assertRaisesRegex(ValueError, "Password"):
            select_database(
                {
                    "databases": [
                        {
                            "path": "X:/bp",
                            "Srvr": "server",
                            "Ref": "bp",
                            "User": "user",
                            "Bridge": {"BaseUrl": "http://localhost/bp"},
                        }
                    ]
                },
                "bp",
            )

    def test_environment_is_restored(self):
        name = "CODEX_TEST_BRIDGE_TEMP_ENV_TEST"
        os.environ.pop(name, None)
        with temporary_environment({name: "temporary-secret"}):
            self.assertEqual(os.environ[name], "temporary-secret")
        self.assertNotIn(name, os.environ)


if __name__ == "__main__":
    unittest.main()
