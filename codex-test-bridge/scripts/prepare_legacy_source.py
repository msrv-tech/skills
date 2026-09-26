#!/usr/bin/env python3
"""Prepare server-only CodexTestBridge sources for legacy compatibility modes."""

from __future__ import annotations

import argparse
import re
import shutil
import xml.etree.ElementTree as ET
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MD_NAMESPACE = "http://v8.1c.ru/8.3/MDClasses"
UI_COMMANDS = (
    "UIJobCreate", "UISuiteJobCreate", "UIJobGet", "UIJobSet",
    "UIJobSetScenario", "UIJobPrepareTaskExecutionForm", "UIJobDelete",
)


def prepare_legacy_source(source: Path, output: Path) -> None:
    source = source.resolve()
    output = output.resolve()
    if output == source or source in output.parents:
        raise ValueError("Legacy output must not be the source directory or its child")
    if output.exists() and any(output.iterdir()):
        raise ValueError("Legacy output directory must be empty")
    output.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source / "Configuration.xml", output / "Configuration.xml")
    shutil.copytree(source / "HTTPServices", output / "HTTPServices", dirs_exist_ok=True)

    module_path = output / "HTTPServices" / "CodexTestBridge" / "Ext" / "Module.bsl"
    module = module_path.read_text(encoding="utf-8-sig")
    module = re.sub(
        r'(?ms)^[^\r\n]*"uijobcreate"[^\r\n]*\r?\n.*?^[^\r\n]*"uijobdelete"[^\r\n]*\r?\n^[^\r\n]*\r?\n',
        "", module,
    )
    module = re.sub(
        r"(?ms)^[^\r\n]*UIJobCreate\(.*?(?=^[^\r\n]*Capabilities\(\)[^\r\n]*$)",
        "", module,
    )
    module = re.sub(
        r'(?m)(^.*"worker", )[^\r\n]+(\); // CTB_FULL_UI.*$)',
        r"\1Ложь\2", module,
    )
    module = re.sub(
        r'(?m)(^.*"variant", )"full"(\); // CTB_FULL_VARIANT.*$)',
        r'\1"legacy"\2', module,
    )
    for command in UI_COMMANDS:
        module = module.replace(f",{command}", "")
    module_path.write_text(module, encoding="utf-8")

    configuration_path = output / "Configuration.xml"
    namespaces = {
        prefix: uri for _, (prefix, uri) in ET.iterparse(configuration_path, events=("start-ns",))
    }
    for prefix, uri in namespaces.items():
        ET.register_namespace(prefix, uri)
    tree = ET.parse(configuration_path)
    configuration = tree.getroot().find(f"{{{MD_NAMESPACE}}}Configuration")
    if configuration is None:
        raise ValueError("Configuration node was not found")
    properties = configuration.find(f"{{{MD_NAMESPACE}}}Properties")
    children = configuration.find(f"{{{MD_NAMESPACE}}}ChildObjects")
    if properties is None or children is None:
        raise ValueError("Configuration properties or child objects were not found")
    compatibility = properties.find(f"{{{MD_NAMESPACE}}}ConfigurationExtensionCompatibilityMode")
    if compatibility is None:
        raise ValueError("ConfigurationExtensionCompatibilityMode was not found")
    compatibility.text = "Version8_3_8"
    default_roles = properties.find(f"{{{MD_NAMESPACE}}}DefaultRoles")
    if default_roles is not None:
        properties.remove(default_roles)
    for child in list(children):
        if child.tag.rsplit("}", 1)[-1] != "HTTPService":
            children.remove(child)
    tree.write(configuration_path, encoding="utf-8", xml_declaration=True)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", default=str(ROOT / "src"))
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    prepare_legacy_source(Path(args.source), Path(args.output))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
