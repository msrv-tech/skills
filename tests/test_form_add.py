import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CREATE_CONFIG = ROOT / "configuration" / "scripts" / "create.py"
CREATE_CATALOG = ROOT / "metadata" / "scripts" / "create.py"
ADD_FORM = ROOT / "forms" / "scripts" / "add.py"


def run(*arguments: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, *arguments],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )


class FormAddDiffGuardTests(unittest.TestCase):
    def test_add_form_passes_guard_and_creates_files(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "config"
            root.mkdir()
            config = run(str(CREATE_CONFIG), "-Name", "ФормыТест", "-OutputDir", str(root), "-Version", "0.0.1")
            self.assertEqual(config.returncode, 0, config.stdout + config.stderr)
            definition = Path(temporary) / "catalog.json"
            definition.write_text('{"type":"Catalog","name":"Товары"}', encoding="utf-8")
            catalog = run(
                str(CREATE_CATALOG), "-JsonPath", str(definition),
                "-OutputDir", str(root), "-FormatVersion", "2.17",
            )
            self.assertEqual(catalog.returncode, 0, catalog.stdout + catalog.stderr)

            result = run(
                str(ADD_FORM),
                "-ObjectPath", str(root / "Catalogs" / "Товары.xml"),
                "-FormName", "ФормаТоваров",
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertNotIn("Unexpected file changes", result.stderr)
            form = root / "Catalogs" / "Товары" / "Forms" / "ФормаТоваров.xml"
            self.assertTrue(form.is_file())
            self.assertIn("ФормаТоваров", (root / "Catalogs" / "Товары.xml").read_text(encoding="utf-8-sig"))


if __name__ == "__main__":
    unittest.main()
