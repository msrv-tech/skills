import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from xml.etree import ElementTree

from common.xml_preserve import read_source_style, serialize_preserving, write_text_preserving


ROOT = Path(__file__).resolve().parents[1]
CREATE = ROOT / "metadata" / "scripts" / "create.py"
EDIT = ROOT / "metadata" / "scripts" / "edit.py"

CRLF_BOM_XML = (
    b"\xef\xbb\xbf<?xml version=\"1.0\" encoding=\"utf-8\" standalone=\"no\"?>\r\n"
    b"<Root>\r\n"
    b"\t<Empty></Empty>\r\n"
    b"\t<Value>1</Value>\r\n"
    b"</Root>\r\n"
)


class SerializePreservingTests(unittest.TestCase):
    def test_restores_bom_declaration_eol_paired_empty_and_final_newline(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "source.xml"
            path.write_bytes(CRLF_BOM_XML)
            tree = ElementTree.parse(path)
            output = serialize_preserving(tree, read_source_style(path))

            self.assertTrue(output.startswith(b"\xef\xbb\xbf"))
            self.assertIn(b"<?xml version=\"1.0\" encoding=\"utf-8\" standalone=\"no\"?>", output)
            self.assertEqual(output.count(b"\n"), output.count(b"\r\n"))
            self.assertIn(b"<Empty></Empty>", output)
            self.assertTrue(output.endswith(b"\r\n"))

    def test_restores_absence_of_declaration(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "source.xml"
            path.write_bytes(b"<Root><Value>1</Value></Root>\n")
            tree = ElementTree.parse(path)
            output = serialize_preserving(tree, read_source_style(path))
            self.assertFalse(output.startswith(b"<?xml"))
            self.assertTrue(output.startswith(b"<Root>"))

    def test_restores_absence_of_bom_and_final_newline(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "source.xml"
            path.write_bytes(b"<Root><Value>1</Value></Root>")
            tree = ElementTree.parse(path)
            output = serialize_preserving(tree, read_source_style(path))
            self.assertFalse(output.startswith(b"\xef\xbb\xbf"))
            self.assertFalse(output.endswith(b"\n"))


class MetadataEditByteStabilityTests(unittest.TestCase):
    def make_catalog(self, root: Path) -> Path:
        output = root / "out"
        definition = root / "cat.json"
        definition.write_text(
            '{"type":"Catalog","name":"ТестИерархия"}',
            encoding="utf-8",
        )
        result = subprocess.run(
            [
                sys.executable,
                str(CREATE),
                "-JsonPath",
                str(definition),
                "-OutputDir",
                str(output),
                "-FormatVersion",
                "2.20",
            ],
            cwd=ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        return output / "Catalogs" / "ТестИерархия.xml"

    def test_edit_preserves_crlf_bom_declaration_and_diff_scope(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            path = self.make_catalog(root)
            path.write_bytes(path.read_bytes().replace(b"\n", b"\r\n"))
            before = path.read_bytes()
            before_lines = before.decode("utf-8-sig").splitlines()

            result = subprocess.run(
                [
                    sys.executable,
                    str(EDIT),
                    "-ObjectPath",
                    str(path),
                    "-Operation",
                    "modify-property",
                    "-Value",
                    "DescriptionLength=77",
                ],
                cwd=ROOT,
                capture_output=True,
                text=True,
                encoding="utf-8",
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

            after = path.read_bytes()
            self.assertTrue(after.startswith(b"\xef\xbb\xbf"))
            self.assertEqual(after.count(b"\n"), after.count(b"\r\n"))
            self.assertTrue(after.endswith(b"\r\n"))
            self.assertIn(b'<?xml version="1.0" encoding="UTF-8"?>', after)

            after_lines = after.decode("utf-8-sig").splitlines()
            self.assertEqual(len(before_lines), len(after_lines))
            changed = [
                (left, right)
                for left, right in zip(before_lines, after_lines)
                if left != right
            ]
            self.assertEqual(len(changed), 1)
            self.assertIn("DescriptionLength", changed[0][1])
            self.assertIn("<DescriptionLength>77</DescriptionLength>", changed[0][1])

    def test_edit_preserves_absence_of_bom(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            path = self.make_catalog(root)
            path.write_bytes(path.read_bytes().lstrip(b"\xef\xbb\xbf"))

            result = subprocess.run(
                [
                    sys.executable,
                    str(EDIT),
                    "-ObjectPath",
                    str(path),
                    "-Operation",
                    "modify-property",
                    "-Value",
                    "DescriptionLength=88",
                ],
                cwd=ROOT,
                capture_output=True,
                text=True,
                encoding="utf-8",
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertFalse(path.read_bytes().startswith(b"\xef\xbb\xbf"))
            self.assertIn("<DescriptionLength>88</DescriptionLength>", path.read_text(encoding="utf-8"))


class TextWritePreservingTests(unittest.TestCase):
    def test_text_writer_restores_crlf_bom_and_final_newline(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "Configuration.xml"
            path.write_bytes(b"\xef\xbb\xbf" + b"<Root>\r\n</Root>\r\n")
            write_text_preserving(path, "<Root>\n\t<Child/>\n</Root>\n")
            data = path.read_bytes()
            self.assertTrue(data.startswith(b"\xef\xbb\xbf"))
            self.assertEqual(data.count(b"\n"), data.count(b"\r\n"))
            self.assertTrue(data.endswith(b"\r\n"))
            self.assertIn(b"\t<Child/>", data)


class CreateRegistrationByteStabilityTests(unittest.TestCase):
    CONFIG = (
        "<?xml version=\"1.0\" encoding=\"UTF-8\"?>\r\n"
        "<MetaDataObject xmlns=\"http://v8.1c.ru/8.3/MDClasses\" "
        "xmlns:pal=\"http://v8.1c.ru/8.1/data/ui/colors/palette\" "
        "xmlns:xr=\"http://v8.1c.ru/8.3/xcf/readable\" version=\"2.21\">\r\n"
        "\t<Configuration uuid=\"11111111-1111-1111-1111-111111111111\">\r\n"
        "\t\t<Properties>\r\n"
        "\t\t\t<Name>Тест</Name>\r\n"
        "\t\t</Properties>\r\n"
        "\t\t<ChildObjects>\r\n"
        "\t\t\t<Catalog>Существующий</Catalog>\r\n"
        "\t\t\t<Document>Заказ</Document>\r\n"
        "\t\t</ChildObjects>\r\n"
        "\t</Configuration>\r\n"
        "</MetaDataObject>\r\n"
    ).encode("utf-8")

    def test_registration_adds_one_line_and_keeps_root_tag(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "config"
            root.mkdir()
            config_path = root / "Configuration.xml"
            config_path.write_bytes(self.CONFIG)
            definition = Path(temporary) / "cat.json"
            definition.write_text(
                '{"type":"Catalog","name":"НовыйКодекс","hierarchical":true,'
                '"hierarchyType":"HierarchyOfItems"}',
                encoding="utf-8",
            )
            result = subprocess.run(
                [
                    sys.executable, str(CREATE), "-JsonPath", str(definition),
                    "-OutputDir", str(root), "-FormatVersion", "2.21",
                ],
                cwd=ROOT, capture_output=True, text=True, encoding="utf-8", check=False,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            after = config_path.read_bytes()
            # The source has no BOM, so the writer must not invent one.
            self.assertFalse(after.startswith(b"\xef\xbb\xbf"))
            self.assertEqual(after.count(b"\n"), after.count(b"\r\n"))
            before_lines = self.CONFIG.decode("utf-8-sig").splitlines()
            after_lines = after.decode("utf-8-sig").splitlines()
            import difflib

            changes = [
                line
                for line in difflib.unified_diff(before_lines, after_lines, lineterm="")
                if line.startswith(("+", "-")) and not line.startswith(("+++", "---"))
            ]
            self.assertEqual(len(before_lines) + 1, len(after_lines))
            self.assertEqual(["+\t\t\t<Catalog>НовыйКодекс</Catalog>"], changes)
            self.assertIn(
                "\t\t\t<Catalog>НовыйКодекс</Catalog>",
                after_lines,
            )
            self.assertIn(
                "xmlns:pal=\"http://v8.1c.ru/8.1/data/ui/colors/palette\"",
                after_lines[1],
            )


class MetadataEditDiffGuardTests(unittest.TestCase):
    def test_edit_in_config_tree_does_not_report_false_positive(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "config"
            root.mkdir()
            (root / "Configuration.xml").write_text(
                "<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n"
                "<MetaDataObject xmlns=\"http://v8.1c.ru/8.3/MDClasses\" version=\"2.20\">\n"
                "\t<Configuration uuid=\"11111111-1111-1111-1111-111111111111\">\n"
                "\t\t<Properties>\n\t\t\t<Name>Тест</Name>\n\t\t</Properties>\n"
                "\t\t<ChildObjects/>\n\t</Configuration>\n</MetaDataObject>\n",
                encoding="utf-8",
            )
            definition = Path(temporary) / "cat.json"
            definition.write_text(
                '{"type":"Catalog","name":"Товары"}',
                encoding="utf-8",
            )
            created = subprocess.run(
                [
                    sys.executable, str(CREATE), "-JsonPath", str(definition),
                    "-OutputDir", str(root), "-FormatVersion", "2.20",
                ],
                cwd=ROOT, capture_output=True, text=True, encoding="utf-8", check=False,
            )
            self.assertEqual(created.returncode, 0, created.stdout + created.stderr)
            object_path = root / "Catalogs" / "Товары.xml"
            result = subprocess.run(
                [
                    sys.executable, str(EDIT), "-ObjectPath", str(object_path),
                    "-Operation", "modify-property", "-Value", "DescriptionLength=42",
                    "-NoValidate",
                ],
                cwd=ROOT, capture_output=True, text=True, encoding="utf-8", check=False,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertNotIn("Unexpected file changes", result.stderr)
            self.assertIn("<DescriptionLength>42</DescriptionLength>", object_path.read_text(encoding="utf-8-sig"))


class MetadataEditDryRunTests(unittest.TestCase):
    def test_dry_run_prints_diff_without_writing(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            output = root / "out"
            definition = root / "cat.json"
            definition.write_text('{"type":"Catalog","name":"ТестИерархия"}', encoding="utf-8")
            created = subprocess.run(
                [
                    sys.executable, str(CREATE), "-JsonPath", str(definition),
                    "-OutputDir", str(output), "-FormatVersion", "2.20",
                ],
                cwd=ROOT, capture_output=True, text=True, encoding="utf-8", check=False,
            )
            self.assertEqual(created.returncode, 0, created.stdout + created.stderr)
            path = output / "Catalogs" / "ТестИерархия.xml"
            before = path.read_bytes()

            result = subprocess.run(
                [
                    sys.executable, str(EDIT), "-ObjectPath", str(path),
                    "-Operation", "modify-property", "-Value", "DescriptionLength=77",
                    "-DryRun",
                ],
                cwd=ROOT, capture_output=True, text=True, encoding="utf-8", check=False,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("Dry run: unified diff", result.stdout)
            self.assertIn("+\t\t\t<DescriptionLength>77</DescriptionLength>", result.stdout)
            self.assertEqual(path.read_bytes(), before)


if __name__ == "__main__":
    unittest.main()
