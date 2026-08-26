import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from unittest.mock import patch

from update_all_test_databases import (
    UpdateError, assert_no_bootstrap_users, cfe_variant, load_registry, read_compatibility_mode,
)


class UpdateAllTestDatabasesTests(unittest.TestCase):
    def test_variant_boundary(self):
        self.assertEqual(cfe_variant("Version8_3_8"), "legacy")
        self.assertEqual(cfe_variant("Version8_3_11"), "legacy")
        self.assertEqual(cfe_variant("Version8_3_12"), "full")
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


if __name__ == "__main__":
    unittest.main()
