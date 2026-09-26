import os
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from run_ui_from_test_database import database_environment, select_database, temporary_environment


class RunUiFromTestDatabaseTests(unittest.TestCase):
    def test_default_credentials_worker_is_cross_platform(self):
        config = (ROOT / "ui-worker.cross-db.credentials.example.json").read_text(encoding="utf-8")
        self.assertIn('"backend": "auto"', config)
        self.assertIn('"/S{clientServerConnection}"', config)
        self.assertIn('"/N{clientUsername}"', config)
        self.assertIn('"/P{clientPassword}"', config)

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

    def test_missing_password_means_empty_password(self):
        entry = {
            "path": "X:/bp", "Srvr": "server", "Ref": "bp", "User": "user",
            "Bridge": {"BaseUrl": "http://localhost/bp"},
        }
        self.assertIs(select_database({"databases": [entry]}, "bp"), entry)

    def test_rejects_entry_without_registered_user(self):
        with self.assertRaisesRegex(ValueError, "User"):
            select_database({"databases": [{
                "path": "X:/bp", "Srvr": "server", "Ref": "bp",
                "Bridge": {"BaseUrl": "http://localhost/bp"},
            }]}, "bp")

    def test_environment_is_restored(self):
        name = "CODEX_TEST_BRIDGE_TEMP_ENV_TEST"
        os.environ.pop(name, None)
        with temporary_environment({name: "temporary-secret"}):
            self.assertEqual(os.environ[name], "temporary-secret")
        self.assertNotIn(name, os.environ)

    def test_database_environment_supports_an_explicitly_empty_password(self):
        entry = {
            "Srvr": "server", "Ref": "base", "User": "tester",
            "Bridge": {"BaseUrl": "http://localhost/base"},
        }
        environment = database_environment(entry, "/opt/1cv8")
        self.assertEqual(environment["CODEX_1C_CLIENT_PASSWORD"], "")
        self.assertEqual(environment["CODEX_1C_MANAGER_PASSWORD"], "")
        self.assertEqual(environment["CODEX_1C_CLIENT_USERNAME"], "tester")


if __name__ == "__main__":
    unittest.main()
