import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
LOAD_XML = ROOT / "database" / "scripts" / "load-xml.py"


def load_module():
    spec = importlib.util.spec_from_file_location("db_load_xml", LOAD_XML)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class PartialWorkspaceTests(unittest.TestCase):
    def setUp(self):
        self.module = load_module()

    def make_tree(self, root: Path) -> Path:
        config = root / "config"
        (config / "Catalogs" / "Товары").mkdir(parents=True)
        (config / "Catalogs" / "Услуги").mkdir(parents=True)
        (config / "Documents" / "Заказ").mkdir(parents=True)
        (config / "Configuration.xml").write_text("<MetaDataObject/>", encoding="utf-8")
        (config / "ConfigDumpInfo.xml").write_text("<ConfigDumpInfo/>", encoding="utf-8")
        (config / "Catalogs" / "Товары.xml").write_text("<Catalog/>", encoding="utf-8")
        (config / "Catalogs" / "Товары" / "Ext").mkdir()
        (config / "Catalogs" / "Товары" / "Ext" / "ObjectModule.bsl").write_text("// module", encoding="utf-8")
        (config / "Catalogs" / "Услуги.xml").write_text("<Catalog/>", encoding="utf-8")
        (config / "Documents" / "Заказ.xml").write_text("<Document/>", encoding="utf-8")
        return config

    def test_workspace_mirrors_all_files_read_only_by_link(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            config = self.make_tree(root)
            target = root / "workspace"
            result, linked, copied = self.module.build_partial_workspace(str(config), str(target))
            self.assertEqual(result, str(target))
            self.assertGreaterEqual(linked, 4)
            self.assertEqual(copied, 2)
            self.assertTrue((target / "Catalogs" / "Товары.xml").is_file())
            self.assertTrue((target / "Documents" / "Заказ.xml").is_file())
            self.assertTrue((target / "Catalogs" / "Товары" / "Ext" / "ObjectModule.bsl").is_file())

    def test_workspace_dump_info_is_a_copy(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            config = self.make_tree(root)
            target = root / "workspace"
            self.module.build_partial_workspace(str(config), str(target))
            source = config / "ConfigDumpInfo.xml"
            copy = target / "ConfigDumpInfo.xml"
            self.assertNotEqual(source.stat().st_ino, copy.stat().st_ino)
            copy.write_text("<ConfigDumpInfo>updated</ConfigDumpInfo>", encoding="utf-8")
            self.assertEqual(source.read_text(encoding="utf-8"), "<ConfigDumpInfo/>")

    def test_workspace_configuration_is_a_copy(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            config = self.make_tree(root)
            target = root / "workspace"
            self.module.build_partial_workspace(str(config), str(target))
            self.assertNotEqual(
                (config / "Configuration.xml").stat().st_ino,
                (target / "Configuration.xml").stat().st_ino,
            )


    def test_source_guard_restores_changed_root_files(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            config = self.make_tree(root)
            snapshot = self.module.snapshot_source_files(str(config))
            self.assertEqual(set(snapshot), {"Configuration.xml", "ConfigDumpInfo.xml"})

            (config / "ConfigDumpInfo.xml").write_text("<changed/>", encoding="utf-8")
            (config / "Configuration.xml").write_text("<changed/>", encoding="utf-8")
            restored = self.module.restore_changed_source_files(str(config), snapshot)

            self.assertEqual(sorted(restored), ["ConfigDumpInfo.xml", "Configuration.xml"])
            self.assertEqual(
                (config / "ConfigDumpInfo.xml").read_text(encoding="utf-8"),
                "<ConfigDumpInfo/>",
            )
            self.assertEqual(
                (config / "Configuration.xml").read_text(encoding="utf-8"),
                "<MetaDataObject/>",
            )

    def test_source_guard_reports_no_changes(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            config = self.make_tree(root)
            snapshot = self.module.snapshot_source_files(str(config))
            self.assertEqual(self.module.restore_changed_source_files(str(config), snapshot), [])


if __name__ == "__main__":
    unittest.main()
