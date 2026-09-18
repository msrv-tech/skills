import importlib.util
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

from common.apache_linux import (
    ApacheLinuxError,
    _atomic_write,
    _owned_publication_names,
    _run_checked,
    build_connection_string,
    build_global_config,
    build_publication_config,
    build_vrd,
    configtest_command,
    derive_app_name,
    systemctl_command,
    validate_app_name,
)


ROOT = Path(__file__).resolve().parents[1]
BRIDGE_SCRIPT = ROOT / "codex-test-bridge" / "scripts" / "enable_vrd_linux.py"
SPEC = importlib.util.spec_from_file_location("enable_vrd_linux", BRIDGE_SCRIPT)
assert SPEC and SPEC.loader
BRIDGE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(BRIDGE)


class ApacheLinuxConfigTests(unittest.TestCase):
    def test_file_connection_and_vrd_are_xml_safe(self):
        connection = build_connection_string(
            file_path='/srv/1c/A&B"Base',
            username='user"name',
            password="p<&",
        )
        document = ET.fromstring(build_vrd("demo", connection))
        self.assertEqual(document.attrib["base"], "/demo")
        self.assertEqual(
            document.attrib["ib"],
            'File="/srv/1c/A&B""Base";Usr="user""name";Pwd="p<&";',
        )

    def test_server_connection_requires_complete_exclusive_input(self):
        self.assertEqual(
            build_connection_string(server="srv", reference="base"),
            'Srvr="srv";Ref="base";',
        )
        with self.assertRaises(ApacheLinuxError):
            build_connection_string(file_path="/db", server="srv", reference="base")
        with self.assertRaises(ApacheLinuxError):
            build_connection_string(server="srv")

    def test_publication_name_rejects_traversal_and_directives(self):
        self.assertEqual(validate_app_name("Demo-1"), "demo-1")
        self.assertEqual(derive_app_name("", "/srv/My Base", ""), "mybase")
        for invalid in ("../demo", "demo/name", "demo\nLoadModule", ""):
            with self.subTest(invalid=invalid):
                with self.assertRaises(ApacheLinuxError):
                    validate_app_name(invalid)

    def test_configs_are_separate_and_hardened(self):
        global_config = build_global_config("/opt/1cv8/8.3.27/wsap24.so")
        publication = build_publication_config(
            "demo",
            "/var/www/1c-publications/demo",
            "/var/www/1c-publications/demo/default.vrd",
        )
        self.assertIn("LoadModule _1cws_module", global_config)
        self.assertNotIn("Alias", global_config)
        self.assertIn("Alias /demo", publication)
        self.assertIn("AllowOverride None", publication)
        self.assertIn("Options None", publication)
        self.assertNotIn("demo2", publication)

    def test_commands_use_configtest_before_reload_contract(self):
        self.assertEqual(configtest_command("/usr/sbin/apache2ctl"), ["/usr/sbin/apache2ctl", "configtest"])
        self.assertEqual(
            systemctl_command("reload", "/usr/bin/systemctl"),
            ["/usr/bin/systemctl", "reload", "apache2"],
        )
        with self.assertRaises(ValueError):
            systemctl_command("stop")

    def test_command_failure_and_managed_file_helpers_are_strict(self):
        with self.assertRaisesRegex(ApacheLinuxError, "exit 7"):
            _run_checked(
                [sys.executable, "-c", "import sys; print('bad config'); sys.exit(7)"],
                "test command",
            )
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            _atomic_write(root / "1c-skills-publication-demo.conf", "demo\n")
            _atomic_write(root / "foreign.conf", "foreign\n")
            self.assertEqual(_owned_publication_names(root), ["demo"])
            self.assertEqual(
                (root / "1c-skills-publication-demo.conf").read_text(encoding="utf-8"),
                "demo\n",
            )


class BridgeVrdTests(unittest.TestCase):
    def test_bridge_update_preserves_unrelated_service(self):
        source = """<?xml version="1.0" encoding="UTF-8"?>
<point xmlns="http://v8.1c.ru/8.2/virtual-resource-system"
       base="/demo" ib="File=&quot;/srv/db&quot;;">
  <httpServices publishByDefault="false">
    <service name="Existing" rootUrl="existing" enable="true"/>
  </httpServices>
</point>
"""
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "default.vrd"
            path.write_text(source, encoding="utf-8")
            BRIDGE.update_vrd(path, "CodexTestBridge", "codex-test")
            root = ET.parse(path).getroot()
        namespace = {"v": BRIDGE.VRS_NAMESPACE}
        services = root.findall("v:httpServices/v:service", namespace)
        by_name = {service.attrib["name"]: service for service in services}
        self.assertEqual(set(by_name), {"Existing", "CodexTestBridge"})
        self.assertEqual(by_name["Existing"].attrib["rootUrl"], "existing")
        self.assertEqual(by_name["CodexTestBridge"].attrib["rootUrl"], "codex-test")
        http_services = root.find("v:httpServices", namespace)
        self.assertEqual(http_services.attrib["publishExtensionsByDefault"], "true")

    def test_bridge_rejects_non_vrd_xml(self):
        tree = ET.ElementTree(ET.fromstring("<point/>"))
        with self.assertRaises(ValueError):
            BRIDGE.enable_bridge(tree)

    def test_bridge_update_is_idempotent_when_http_services_are_absent(self):
        tree = ET.ElementTree(ET.fromstring(
            f'<point xmlns="{BRIDGE.VRS_NAMESPACE}" base="/demo" ib="File=&quot;/srv/db&quot;;"/>'
        ))

        BRIDGE.enable_bridge(tree)
        BRIDGE.enable_bridge(tree)

        namespace = {"v": BRIDGE.VRS_NAMESPACE}
        services = tree.getroot().findall("v:httpServices/v:service", namespace)
        self.assertEqual(len(services), 1)
        self.assertEqual(
            services[0].attrib,
            {
                "name": "CodexTestBridge",
                "rootUrl": "codex-test",
                "enable": "true",
                "reuseSessions": "dontuse",
                "sessionMaxAge": "20",
            },
        )

    def test_bridge_rejects_invalid_service_parameters(self):
        tree = ET.ElementTree(ET.fromstring(
            f'<point xmlns="{BRIDGE.VRS_NAMESPACE}"/>'
        ))
        for service_name, root_url in (("", "codex-test"), ("Bridge", ""), ("Bridge", "codex test")):
            with self.subTest(service_name=service_name, root_url=root_url):
                with self.assertRaises(ValueError):
                    BRIDGE.enable_bridge(tree, service_name, root_url)


if __name__ == "__main__":
    unittest.main()
