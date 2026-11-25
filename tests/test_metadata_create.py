import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CREATE = ROOT / "metadata" / "scripts" / "create.py"
EDIT = ROOT / "metadata" / "scripts" / "edit.py"
VALIDATE = ROOT / "metadata" / "scripts" / "validate.py"


def run(*arguments: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, *arguments],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )


def write_configuration(directory: Path, version: str) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / "Configuration.xml"
    path.write_text(
        "<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n"
        f"<MetaDataObject xmlns=\"http://v8.1c.ru/8.3/MDClasses\" version=\"{version}\">\n"
        "\t<Configuration uuid=\"11111111-1111-1111-1111-111111111111\">\n"
        "\t\t<Properties>\n"
        "\t\t\t<Name>Тест</Name>\n"
        "\t\t</Properties>\n"
        "\t\t<ChildObjects/>\n"
        "\t</Configuration>\n"
        "</MetaDataObject>\n",
        encoding="utf-8",
    )
    return path


def write_catalog(directory: Path, hierarchy_type: str) -> Path:
    path = directory / "cat.json"
    path.write_text(
        "{"
        '"type":"Catalog","name":"ТестИерархия",'
        '"hierarchical":true,'
        f'"hierarchyType":"{hierarchy_type}"'
        "}",
        encoding="utf-8",
    )
    return path


def created_object(output: Path) -> Path:
    return output / "Catalogs" / "ТестИерархия.xml"


def root_version(path: Path) -> str:
    head = path.read_text(encoding="utf-8-sig")[:8192]
    match = re.search(r'<MetaDataObject[^>]*\bversion="([\d.]+)"', head)
    if match is None:
        raise AssertionError(f"MetaDataObject version not found in {path}")
    return match.group(1)


class MetadataCreateFormatTests(unittest.TestCase):
    def test_create_and_validate_hierarchy_of_items(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            output = root / "out"
            result = run(
                str(CREATE),
                "-JsonPath",
                str(write_catalog(root, "HierarchyOfItems")),
                "-OutputDir",
                str(output),
                "-FormatVersion",
                "2.20",
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            xml = created_object(output).read_text(encoding="utf-8-sig")
            self.assertIn("<HierarchyType>HierarchyOfItems</HierarchyType>", xml)

            validation = run(str(VALIDATE), "-ObjectPath", str(created_object(output)))
            self.assertEqual(validation.returncode, 0, validation.stdout + validation.stderr)
            self.assertNotIn("invalid value", validation.stdout.lower())

    def test_create_rejects_hierarchy_items_only(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            result = run(
                str(CREATE),
                "-JsonPath",
                str(write_catalog(root, "HierarchyItemsOnly")),
                "-OutputDir",
                str(root / "out"),
                "-FormatVersion",
                "2.20",
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("Invalid value 'HierarchyItemsOnly'", result.stderr)
            self.assertIn("HierarchyOfItems", result.stderr)

    def test_validate_rejects_legacy_hierarchy_items_only(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            output = root / "out"
            result = run(
                str(CREATE),
                "-JsonPath",
                str(write_catalog(root, "HierarchyOfItems")),
                "-OutputDir",
                str(output),
                "-FormatVersion",
                "2.20",
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            path = created_object(output)
            path.write_text(
                path.read_text(encoding="utf-8-sig").replace(
                    "<HierarchyType>HierarchyOfItems</HierarchyType>",
                    "<HierarchyType>HierarchyItemsOnly</HierarchyType>",
                ),
                encoding="utf-8-sig",
            )
            validation = run(str(VALIDATE), "-ObjectPath", str(path))
            self.assertNotEqual(validation.returncode, 0)
            self.assertIn("has invalid value 'HierarchyItemsOnly'", validation.stdout)

    def test_hierarchy_type_with_hierarchical_false_is_valid(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            output = root / "out"
            created = run(
                str(CREATE),
                "-JsonPath",
                str(write_catalog(root, "HierarchyOfItems")),
                "-OutputDir",
                str(output),
                "-FormatVersion",
                "2.20",
            )
            self.assertEqual(created.returncode, 0, created.stdout + created.stderr)
            path = created_object(output)
            path.write_text(
                path.read_text(encoding="utf-8-sig").replace(
                    "<Hierarchical>true</Hierarchical>",
                    "<Hierarchical>false</Hierarchical>",
                ),
                encoding="utf-8-sig",
            )
            validation = run(str(VALIDATE), "-ObjectPath", str(path))
            self.assertEqual(validation.returncode, 0, validation.stdout + validation.stderr)
            self.assertNotIn("HierarchyType", validation.stdout)

    def test_explicit_format_version_is_written_to_root(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            output = root / "out"
            result = run(
                str(CREATE),
                "-JsonPath",
                str(write_catalog(root, "HierarchyFoldersAndItems")),
                "-OutputDir",
                str(output),
                "-FormatVersion",
                "2.21",
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertEqual(root_version(created_object(output)), "2.21")
            root_line = created_object(output).read_text(encoding="utf-8-sig").splitlines()[1]
            self.assertIn('xmlns:pal="http://v8.1c.ru/8.1/data/ui/colors/palette"', root_line)
            self.assertIn("Format version: 2.21 (source: explicit -FormatVersion)", result.stdout)

    def test_source_config_dir_defines_target_format(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            target = root / "target"
            write_configuration(target, "2.20")
            output = root / "out"
            result = run(
                str(CREATE),
                "-JsonPath",
                str(write_catalog(root, "HierarchyFoldersAndItems")),
                "-OutputDir",
                str(output),
                "-SourceConfigDir",
                str(target),
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertEqual(root_version(created_object(output)), "2.20")
            root_line = created_object(output).read_text(encoding="utf-8-sig").splitlines()[1]
            self.assertNotIn("xmlns:pal", root_line)
            self.assertIn("Format version: 2.20", result.stdout)
            self.assertIn("Configuration.xml", result.stdout)

    def test_fallback_warns_and_uses_2_17(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            output = root / "out"
            result = run(
                str(CREATE),
                "-JsonPath",
                str(write_catalog(root, "HierarchyFoldersAndItems")),
                "-OutputDir",
                str(output),
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("Falling back to 2.17", result.stderr)
            self.assertEqual(root_version(created_object(output)), "2.17")

    def test_invalid_format_version_is_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            result = run(
                str(CREATE),
                "-JsonPath",
                str(write_catalog(root, "HierarchyFoldersAndItems")),
                "-OutputDir",
                str(root / "out"),
                "-FormatVersion",
                "2.x",
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("FormatVersion must look like 2.20", result.stderr)

    def test_source_config_dir_without_configuration_is_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            empty = root / "empty"
            empty.mkdir()
            result = run(
                str(CREATE),
                "-JsonPath",
                str(write_catalog(root, "HierarchyFoldersAndItems")),
                "-OutputDir",
                str(root / "out"),
                "-SourceConfigDir",
                str(empty),
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("Configuration.xml not found", result.stderr)

    def test_edit_sets_hierarchy_of_items(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            output = root / "out"
            created = run(
                str(CREATE),
                "-JsonPath",
                str(write_catalog(root, "HierarchyFoldersAndItems")),
                "-OutputDir",
                str(output),
                "-FormatVersion",
                "2.20",
            )
            self.assertEqual(created.returncode, 0, created.stdout + created.stderr)

            result = run(
                str(EDIT),
                "-ObjectPath",
                str(created_object(output)),
                "-Operation",
                "modify-property",
                "-Value",
                "HierarchyType=HierarchyOfItems",
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            xml = created_object(output).read_text(encoding="utf-8-sig")
            self.assertIn("<HierarchyType>HierarchyOfItems</HierarchyType>", xml)
            self.assertNotRegex(xml, re.compile(r"HierarchyItemsOnly"))


if __name__ == "__main__":
    unittest.main()
