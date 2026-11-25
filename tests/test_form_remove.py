import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from xml.etree import ElementTree


ROOT = Path(__file__).resolve().parents[1]
REMOVE_FORM = ROOT / "forms" / "scripts" / "remove.py"
MD_NS = "http://v8.1c.ru/8.3/MDClasses"


class FormRemoveTests(unittest.TestCase):
    def test_catalog_default_list_form_is_cleared(self):
        with tempfile.TemporaryDirectory() as temporary:
            source = Path(temporary)
            form_name = "ВременнаяФорма"
            forms = source / "Товары" / "Forms"
            (forms / form_name / "Ext").mkdir(parents=True)
            (forms / f"{form_name}.xml").write_text("<form/>", encoding="utf-8")
            object_path = source / "Товары.xml"
            object_path.write_text(
                "<?xml version=\"1.0\" encoding=\"utf-8\"?>"
                f"<MetaDataObject xmlns=\"{MD_NS}\"><Catalog><Properties>"
                "<DefaultObjectForm/>"
                f"<DefaultListForm>Catalog.Товары.Form.{form_name}</DefaultListForm>"
                "</Properties><ChildObjects>"
                f"<Form>{form_name}</Form>"
                "</ChildObjects></Catalog></MetaDataObject>",
                encoding="utf-8",
            )

            result = subprocess.run(
                [
                    sys.executable,
                    str(REMOVE_FORM),
                    "-ObjectName",
                    "Товары",
                    "-FormName",
                    form_name,
                    "-SrcDir",
                    str(source),
                ],
                cwd=ROOT,
                capture_output=True,
                text=True,
                encoding="utf-8",
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            tree = ElementTree.parse(object_path)
            default_list = tree.find(f".//{{{MD_NS}}}DefaultListForm")
            self.assertIsNotNone(default_list)
            self.assertFalse((default_list.text or "").strip())
            self.assertIsNone(
                tree.find(f".//{{{MD_NS}}}ChildObjects/{{{MD_NS}}}Form")
            )


    def test_remove_preserves_bom_and_crlf(self):
        with tempfile.TemporaryDirectory() as temporary:
            source = Path(temporary)
            form_name = "ВременнаяФорма"
            forms = source / "Товары" / "Forms"
            (forms / form_name).mkdir(parents=True)
            (forms / f"{form_name}.xml").write_text("<form/>", encoding="utf-8")
            object_path = source / "Товары.xml"
            xml = (
                "<?xml version=\"1.0\" encoding=\"utf-8\"?>\r\n"
                f"<MetaDataObject xmlns=\"{MD_NS}\">\r\n"
                "\t<Catalog>\r\n"
                "\t\t<Properties>\r\n"
                f"\t\t\t<DefaultListForm>Catalog.Товары.Form.{form_name}</DefaultListForm>\r\n"
                "\t\t</Properties>\r\n"
                "\t\t<ChildObjects>\r\n"
                f"\t\t\t<Form>{form_name}</Form>\r\n"
                "\t\t</ChildObjects>\r\n"
                "\t</Catalog>\r\n"
                "</MetaDataObject>\r\n"
            ).encode("utf-8")
            object_path.write_bytes(b"\xef\xbb\xbf" + xml)

            result = subprocess.run(
                [
                    sys.executable, str(REMOVE_FORM),
                    "-ObjectName", "Товары",
                    "-FormName", form_name,
                    "-SrcDir", str(source),
                ],
                cwd=ROOT, capture_output=True, text=True, encoding="utf-8", check=False,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            after = object_path.read_bytes()
            self.assertTrue(after.startswith(b"\xef\xbb\xbf"))
            self.assertEqual(after.count(b"\n"), after.count(b"\r\n"))
            self.assertTrue(after.endswith(b"\r\n"))
            self.assertNotIn(form_name.encode("utf-8"), after)

    def test_dry_run_keeps_files_and_shows_diff(self):
        with tempfile.TemporaryDirectory() as temporary:
            source = Path(temporary)
            form_name = "ВременнаяФорма"
            forms = source / "Товары" / "Forms"
            (forms / form_name / "Ext").mkdir(parents=True)
            (forms / f"{form_name}.xml").write_text("<form/>", encoding="utf-8")
            object_path = source / "Товары.xml"
            object_path.write_text(
                "<?xml version=\"1.0\" encoding=\"utf-8\"?>"
                f"<MetaDataObject xmlns=\"{MD_NS}\"><Catalog><Properties>"
                "<DefaultObjectForm/>"
                f"<DefaultListForm>Catalog.Товары.Form.{form_name}</DefaultListForm>"
                "</Properties><ChildObjects>"
                f"<Form>{form_name}</Form>"
                "</ChildObjects></Catalog></MetaDataObject>",
                encoding="utf-8",
            )
            before = object_path.read_bytes()
            result = subprocess.run(
                [
                    sys.executable, str(REMOVE_FORM),
                    "-ObjectName", "Товары",
                    "-FormName", form_name,
                    "-SrcDir", str(source),
                    "-DryRun",
                ],
                cwd=ROOT, capture_output=True, text=True, encoding="utf-8", check=False,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertTrue((forms / f"{form_name}.xml").is_file())
            self.assertTrue((forms / form_name).is_dir())
            self.assertEqual(object_path.read_bytes(), before)
            self.assertIn("Dry run: unified diff", result.stdout)


if __name__ == "__main__":
    unittest.main()
