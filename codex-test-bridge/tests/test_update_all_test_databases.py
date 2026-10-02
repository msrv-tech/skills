import json
import io
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from unittest.mock import patch

from update_all_test_databases import (
    LOCAL_COMPONENTS, LOCAL_SKILLS, UpdateError, assert_no_bootstrap_users, cfe_variant, install_database, load_registry, main,
    read_compatibility_mode, source_bridge_version, unsupported_database_reason,
    sanitized_process_error, sync_local_skills, validate_registered_credentials, verify_bridge,
)


class UpdateAllTestDatabasesTests(unittest.TestCase):
    def test_local_sync_contains_the_complete_domain_set(self):
        self.assertEqual(13, len(LOCAL_SKILLS))
        self.assertEqual(len(LOCAL_SKILLS), len(set(LOCAL_SKILLS)))
        self.assertEqual("common", LOCAL_COMPONENTS[-1])

    def test_variant_boundary(self):
        self.assertEqual(cfe_variant("Version8_3_8"), "legacy")
        self.assertEqual(cfe_variant("Version8_3_11"), "legacy")
        self.assertEqual(cfe_variant("Version8_3_12"), "legacy")
        self.assertEqual(cfe_variant("Version8_3_13"), "full")
        self.assertEqual(cfe_variant("Version8_3_27"), "full")
        self.assertEqual(cfe_variant("DontUse"), "full")

    def test_reads_utf8_registry_and_local_configuration(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "xml").mkdir()
            (root / "xml" / "Configuration.xml").write_text(
                '<MetaDataObject xmlns="urn:test"><CompatibilityMode>Version8_3_12</CompatibilityMode></MetaDataObject>',
                encoding="utf-8",
            )
            registry = root / "test-databases.json"
            registry.write_text(
                json.dumps({"databases": [{"path": str(root), "User": "ТестовыйПользователь"}]}, ensure_ascii=False),
                encoding="utf-8",
            )
            database = load_registry(registry)[0]
            self.assertEqual(read_compatibility_mode(database), "Version8_3_12")

    def test_private_registry_can_override_compatibility(self):
        self.assertEqual(read_compatibility_mode({"BridgeCompatibilityMode": "Version8_3_8"}), "Version8_3_8")

    def test_unknown_compatibility_is_rejected(self):
        with self.assertRaises(UpdateError):
            cfe_variant("Auto")

    def test_bootstrap_user_audit_rejects_leftovers(self):
        with patch("update_all_test_databases.request_bridge", return_value={"ok": True, "result": 1}):
            with self.assertRaisesRegex(UpdateError, "Temporary bootstrap users exist"):
                assert_no_bootstrap_users({})

    def test_source_bridge_version_is_read_from_module(self):
        self.assertEqual(source_bridge_version(), "0.8.0")

    def test_only_server_bridge_entries_are_deployable(self):
        deployable = {"Srvr": "server", "Ref": "base", "Bridge": {"BaseUrl": "http://bridge"}}
        self.assertIsNone(unsupported_database_reason(deployable))
        self.assertEqual(unsupported_database_reason({"User": "demo"}), "not a server infobase")
        self.assertEqual(
            unsupported_database_reason({"Srvr": "server", "Ref": "base"}),
            "Bridge.BaseUrl is not configured",
        )

    def test_registered_user_is_required_and_missing_password_means_empty(self):
        validate_registered_credentials({"User": "ТестовыйПользователь", "Password": ""})
        validate_registered_credentials({"User": "ТестовыйПользователь"})
        with self.assertRaisesRegex(UpdateError, "registered User"):
            validate_registered_credentials({"Password": "secret"})
        with self.assertRaisesRegex(UpdateError, "Password must be a string"):
            validate_registered_credentials({"User": "demo", "Password": None})

    def test_install_uses_registry_user_without_bootstrap(self):
        database = {
            "Srvr": "server", "Ref": "base", "User": "ТестовыйПользователь", "Password": "secret",
            "Bridge": {"BaseUrl": "http://bridge"},
        }
        with patch("update_all_test_databases.subprocess.run", return_value=SimpleNamespace(returncode=0)) as run:
            install_database(database, Path("/platform/1cv8"), Path("/artifact/bridge.cfe"), 30)
        command = run.call_args.args[0]
        environment = run.call_args.kwargs["env"]
        self.assertIn("install_cfe_designer_hidden.py", command[1])
        self.assertNotIn("install_cfe_with_bridge_bootstrap.py", " ".join(command))
        self.assertNotIn("--allow-bootstrap-user", command)
        self.assertEqual(command[command.index("--user") + 1], "ТестовыйПользователь")
        self.assertEqual(environment["CODEX_CTB_REGISTERED_USER_PASSWORD"], "secret")
        self.assertNotIn("secret", command)

    def test_child_process_diagnostics_are_redacted(self):
        completed = SimpleNamespace(stderr="RuntimeError: failed for demo on server/base with secret", stdout="")
        detail = sanitized_process_error(completed, {
            "User": "demo", "Password": "secret", "Srvr": "server", "Ref": "base",
            "Bridge": {"BaseUrl": "http://server/base"},
        })
        self.assertEqual(detail, "RuntimeError: failed for <redacted> on <redacted>/<redacted> with <redacted>")

    def test_health_verification_requires_requested_version(self):
        responses = [
            {"ok": True}, {"ok": True}, {"ok": True, "bridgeVersion": "0.5.0"},
        ]
        with patch("update_all_test_databases.request_bridge", side_effect=responses) as request:
            verify_bridge({}, "0.5.0", timeout=0.1)
        self.assertEqual(request.call_count, 3)

    def test_dry_run_skips_non_server_records(self):
        with tempfile.TemporaryDirectory() as temporary:
            registry = Path(temporary) / "registry.json"
            registry.write_text(json.dumps({"databases": [
                {
                    "Srvr": "server", "Ref": "base", "User": "demo", "Password": "",
                    "Bridge": {"BaseUrl": "http://bridge"}, "BridgeCompatibilityMode": "Version8_3_12",
                },
                {"path": "/cloud", "User": "demo", "Password": ""},
            ]}), encoding="utf-8")
            output = io.StringIO()
            with redirect_stdout(output):
                result = main(["--registry", str(registry), "--dry-run", "--skip-local-skills-sync"])
        self.assertEqual(result, 0)
        self.assertIn("passed=1, skipped=1, failed=0", output.getvalue())

    def test_syncs_domain_set_and_common_runtime_for_both_agents(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "source"
            for component in LOCAL_COMPONENTS:
                (source / component).mkdir(parents=True)
                (source / component / "content.txt").write_text(component, encoding="utf-8")
            (source / "codex-test-bridge" / "__pycache__").mkdir()
            (source / "codex-test-bridge" / "__pycache__" / "cached.pyc").write_bytes(b"cache")
            (source / "common" / "runtime.pyc").write_bytes(b"cache")
            (source / "ui-testing" / "scripts" / "node_modules").mkdir(parents=True)
            (source / "ui-testing" / "scripts" / "node_modules" / "package.json").write_text("{}", encoding="utf-8")

            codex = root / "codex" / "skills"
            cursor = root / "cursor" / "skills"
            for destination in (codex, cursor):
                (destination / "cf-init").mkdir(parents=True)
                (destination / "cf-init" / "SKILL.md").write_text("obsolete", encoding="utf-8")
                stale = destination / "forms" / "scripts" / "edit.py"
                stale.parent.mkdir(parents=True)
                stale.write_text("obsolete", encoding="utf-8")
                private = destination / "test-databases" / "private-registry.json"
                private.parent.mkdir(parents=True, exist_ok=True)
                private.write_text('{"keep":true}', encoding="utf-8")
            agents = sync_local_skills(source, {"Codex": codex, "Cursor": cursor})

            self.assertEqual(agents, ["Codex", "Cursor"])
            for destination in (codex, cursor):
                for component in LOCAL_COMPONENTS:
                    self.assertEqual(
                        (destination / component / "content.txt").read_text(encoding="utf-8"),
                        component,
                    )
                self.assertFalse((destination / "codex-test-bridge" / "__pycache__").exists())
                self.assertFalse((destination / "common" / "runtime.pyc").exists())
                self.assertFalse((destination / "ui-testing" / "scripts" / "node_modules").exists())
                self.assertFalse((destination / "cf-init").exists())
                self.assertFalse((destination / "forms" / "scripts" / "edit.py").exists())
                self.assertEqual(
                    {"keep": True},
                    json.loads((destination / "test-databases" / "private-registry.json").read_text(encoding="utf-8")),
                )

    def test_local_skills_dry_run_validates_sources_without_writing(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "source"
            for component in LOCAL_COMPONENTS:
                (source / component).mkdir(parents=True)
            destination = root / "destination"

            self.assertEqual(sync_local_skills(source, {"Codex": destination}, dry_run=True), ["Codex"])
            self.assertFalse(destination.exists())

    def test_local_skills_sync_rejects_incomplete_source(self):
        with tempfile.TemporaryDirectory() as temporary:
            with self.assertRaisesRegex(UpdateError, "configuration"):
                sync_local_skills(Path(temporary), {"Codex": Path(temporary) / "target"})


if __name__ == "__main__":
    unittest.main()
