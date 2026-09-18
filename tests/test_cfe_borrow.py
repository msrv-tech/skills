import importlib.util
import re
import sys
import unittest
from pathlib import Path

from lxml import etree


ROOT = Path(__file__).resolve().parents[1]
CURRENT_CONFIG_NS = "http://v8.1c.ru/8.1/data/enterprise/current-config"
V8_NS = "http://v8.1c.ru/8.1/data/core"
NS_STRIP = re.compile(r'\s+xmlns(?::\w+)?="[^"]*"')


def load_cfe_borrow():
    spec = importlib.util.spec_from_file_location(
        "cfe_borrow",
        ROOT / "cfe-borrow" / "scripts" / "cfe-borrow.py",
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


CFE_BORROW = load_cfe_borrow()


def type_element(xml: str):
    return etree.fromstring(xml.encode("utf-8"))


class SerializeTypeXmlTests(unittest.TestCase):
    def test_enum_ref_prefix_becomes_cfg(self):
        node = type_element(
            f'<Type xmlns:v8="{V8_NS}">'
            f'<v8:Type xmlns:d5p1="{CURRENT_CONFIG_NS}">'
            "d5p1:EnumRef.СтатусыТовара"
            "</v8:Type></Type>"
        )
        serialized = CFE_BORROW.serialize_type_xml(node, NS_STRIP)
        self.assertIn("cfg:EnumRef.СтатусыТовара", serialized)
        self.assertNotIn("d5p1:", serialized)

    def test_same_namespace_prefixes_keep_distinct_local_names(self):
        node = type_element(
            f'<Type xmlns:v8="{V8_NS}" xmlns:p1="{CURRENT_CONFIG_NS}" '
            f'xmlns:d5p1="{CURRENT_CONFIG_NS}">'
            "<v8:Type>p1:CatalogRef.Товары</v8:Type>"
            "<v8:Type>d5p1:EnumRef.СтатусыТовара</v8:Type>"
            "</Type>"
        )
        serialized = CFE_BORROW.serialize_type_xml(node, NS_STRIP)
        self.assertIn("cfg:CatalogRef.Товары", serialized)
        self.assertIn("cfg:EnumRef.СтатусыТовара", serialized)
        self.assertNotIn("d5cfg:", serialized)
        self.assertNotIn("p1:", serialized)
        self.assertNotIn("d5p1:", serialized)

    def test_core_v8_prefix_is_not_rewritten(self):
        node = type_element(
            f'<Type xmlns:v8="{V8_NS}">'
            "<v8:Type>xs:string</v8:Type>"
            "<v8:StringQualifiers><v8:Length>30</v8:Length></v8:StringQualifiers>"
            "</Type>"
        )
        serialized = CFE_BORROW.serialize_type_xml(node, NS_STRIP)
        self.assertIn("<v8:Type>", serialized)
        self.assertIn("xs:string", serialized)
        self.assertIn("<v8:Length>30</v8:Length>", serialized)


if __name__ == "__main__":
    unittest.main()
