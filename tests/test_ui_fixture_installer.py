import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
INSTALLER_PATH = ROOT / "codex-ui-test-fixtures" / "scripts" / "install_from_test_database.py"
SPEC = importlib.util.spec_from_file_location("install_ui_test_fixtures", INSTALLER_PATH)
INSTALLER = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(INSTALLER)


class UiFixtureInstallerTests(unittest.TestCase):
    def test_installer_uses_only_the_selected_registered_user(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            registry = root / "test-databases.json"
            registry.write_text(json.dumps({"databases": [{
                "Srvr": "registered-server",
                "Ref": "fixture-base",
                "User": "registered-user",
                "Password": "private-password",
                "Bridge": {"BaseUrl": "http://registered-bridge/hs/codex-test"},
            }]}), encoding="utf-8")
            platform = root / "1cv8"
            platform.write_text("", encoding="utf-8")
            cfe = root / "fixtures.cfe"
            cfe.write_bytes(b"fixture")

            completed = SimpleNamespace(returncode=0, stdout="", stderr="")
            with patch.object(INSTALLER.subprocess, "run", return_value=completed) as run, patch.object(
                INSTALLER, "verify_fixture"
            ) as verify:
                result = INSTALLER.main([
                    "--registry", str(registry),
                    "--database", "fixture-base",
                    "--platform", str(platform),
                    "--cfe", str(cfe),
                    "--timeout", "30",
                ])

        self.assertEqual(result, 0)
        command = run.call_args.args[0]
        environment = run.call_args.kwargs["env"]
        self.assertEqual(command[command.index("--server") + 1], "registered-server")
        self.assertEqual(command[command.index("--database") + 1], "fixture-base")
        self.assertEqual(command[command.index("--user") + 1], "registered-user")
        self.assertEqual(command[command.index("--extension") + 1], "CodexUITestFixtures")
        self.assertNotIn("private-password", command)
        self.assertEqual(environment["CODEX_CTF_REGISTERED_USER_PASSWORD"], "private-password")
        verify.assert_called_once()

    def test_fixture_verification_requires_both_reference_objects(self):
        database = {"Bridge": {"BaseUrl": "http://registered-bridge/hs/codex-test"}}
        response = {
            "catalogs": [{"name": "CodexUIFixtureCatalog"}],
            "documents": [{"name": "CodexUIFixtureDocument"}],
        }
        with patch.object(INSTALLER, "request_bridge", return_value=response) as request:
            INSTALLER.verify_fixture(database, 0.1)
        request.assert_called_once_with(
            database,
            "POST",
            "/command",
            {"command": "metadata", "sections": ["catalogs", "documents"]},
        )


if __name__ == "__main__":
    unittest.main()
