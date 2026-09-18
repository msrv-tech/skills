import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from xml.etree import ElementTree


ROOT = Path(__file__).resolve().parents[1]
REMOVE_FORM = ROOT / "form-remove" / "scripts" / "remove-form.py"
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


if __name__ == "__main__":
    unittest.main()
