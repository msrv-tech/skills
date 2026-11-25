import tempfile
import unittest
from pathlib import Path

from common.diff_guard import TreeGuard


class TreeGuardTests(unittest.TestCase):
    def make_tree(self, root: Path) -> Path:
        config = root / "config"
        (config / "Catalogs").mkdir(parents=True)
        (config / "Configuration.xml").write_text("<MetaDataObject/>", encoding="utf-8")
        (config / "Catalogs" / "Товары.xml").write_text("<Catalog/>", encoding="utf-8")
        (config / "Catalogs" / "Услуги.xml").write_text("<Catalog/>", encoding="utf-8")
        return config

    def test_allowed_file_change_is_not_reported(self):
        with tempfile.TemporaryDirectory() as temporary:
            config = self.make_tree(Path(temporary))
            target = config / "Catalogs" / "Товары.xml"
            guard = TreeGuard(config)
            target.write_text("<Catalog><Changed/></Catalog>", encoding="utf-8")
            self.assertEqual(guard.changed_except([target]), [])

    def test_unexpected_change_is_reported(self):
        with tempfile.TemporaryDirectory() as temporary:
            config = self.make_tree(Path(temporary))
            target = config / "Catalogs" / "Товары.xml"
            guard = TreeGuard(config)
            target.write_text("<Catalog><Changed/></Catalog>", encoding="utf-8")
            (config / "Catalogs" / "Услуги.xml").write_text("<Catalog><Other/></Catalog>", encoding="utf-8")
            self.assertEqual(guard.changed_except([target]), ["Catalogs/Услуги.xml"])

    def test_allowed_prefix_covers_new_and_deleted_form_files(self):
        with tempfile.TemporaryDirectory() as temporary:
            config = self.make_tree(Path(temporary))
            form_dir = config / "Catalogs" / "Товары" / "Forms" / "Форма"
            form_dir.mkdir(parents=True)
            (form_dir / "old.xml").write_text("<form/>", encoding="utf-8")
            guard = TreeGuard(config)
            (form_dir / "old.xml").unlink()
            (form_dir / "new.xml").write_text("<form/>", encoding="utf-8")
            self.assertEqual(
                guard.changed_except([], allowed_prefixes=[form_dir]),
                [],
            )

    def test_added_and_deleted_files_are_reported(self):
        with tempfile.TemporaryDirectory() as temporary:
            config = self.make_tree(Path(temporary))
            target = config / "Catalogs" / "Товары.xml"
            guard = TreeGuard(config)
            (config / "Catalogs" / "Новый.xml").write_text("<Catalog/>", encoding="utf-8")
            (config / "Catalogs" / "Услуги.xml").unlink()
            changed = guard.changed_except([target])
            self.assertEqual(changed, ["Catalogs/Новый.xml", "Catalogs/Услуги.xml"])


if __name__ == "__main__":
    unittest.main()
