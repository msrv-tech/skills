import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from prepare_legacy_source import MD_NAMESPACE, prepare_legacy_source


class PrepareLegacySourceTests(unittest.TestCase):
    def test_prepares_server_only_legacy_sources(self):
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "source"
            prepare_legacy_source(ROOT / "src", output)
            module = (
                output / "HTTPServices" / "CodexTestBridge" / "Ext" / "Module.bsl"
            ).read_text(encoding="utf-8")
            configuration = ET.parse(output / "Configuration.xml").getroot().find(
                f"{{{MD_NAMESPACE}}}Configuration"
            )

        self.assertIsNotNone(configuration)
        self.assertNotIn("UIJobCreate", module)
        self.assertNotIn("UISuiteJobCreate", module)
        self.assertIn('"worker", Ложь', module)
        self.assertIn('"variant", "legacy"', module)
        self.assertIn('"bridgeVersion", "0.7.0"', module)
        properties = configuration.find(f"{{{MD_NAMESPACE}}}Properties")
        children = configuration.find(f"{{{MD_NAMESPACE}}}ChildObjects")
        self.assertEqual(
            properties.find(f"{{{MD_NAMESPACE}}}ConfigurationExtensionCompatibilityMode").text,
            "Version8_3_8",
        )
        self.assertIsNone(properties.find(f"{{{MD_NAMESPACE}}}DefaultRoles"))
        self.assertEqual([child.tag.rsplit("}", 1)[-1] for child in children], ["HTTPService"])


if __name__ == "__main__":
    unittest.main()
