#!/usr/bin/env python3
"""Enable CodexTestBridge in an existing 1C publication VRD."""

from __future__ import annotations

import argparse
import os
import sys
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path


VRS_NAMESPACE = "http://v8.1c.ru/8.2/virtual-resource-system"


def enable_bridge(
    tree: ET.ElementTree,
    service_name: str = "CodexTestBridge",
    root_url: str = "codex-test",
) -> ET.ElementTree:
    """Add or update the bridge service without changing unrelated services."""
    if not service_name or not root_url or any(char.isspace() for char in root_url):
        raise ValueError("service name and root URL must be non-empty; root URL cannot contain whitespace")
    point = tree.getroot()
    namespace = point.tag.partition("}")[0].lstrip("{") if point.tag.startswith("{") else ""
    if namespace != VRS_NAMESPACE or point.tag != f"{{{VRS_NAMESPACE}}}point":
        raise ValueError("file is not a 1C virtual resource descriptor")
    tag = lambda name: f"{{{namespace}}}{name}"
    http_services = point.find(tag("httpServices"))
    if http_services is None:
        http_services = ET.SubElement(point, tag("httpServices"))
    http_services.set("publishByDefault", "true")
    http_services.set("publishExtensionsByDefault", "true")
    service = next(
        (
            item
            for item in http_services.findall(tag("service"))
            if item.get("name") == service_name
        ),
        None,
    )
    if service is None:
        service = ET.SubElement(http_services, tag("service"))
    service.attrib.update(
        {
            "name": service_name,
            "rootUrl": root_url,
            "enable": "true",
            "reuseSessions": "dontuse",
            "sessionMaxAge": "20",
        }
    )
    return tree


def update_vrd(path: Path, service_name: str, root_url: str) -> None:
    if not path.is_file():
        raise FileNotFoundError(f"VRD file not found: {path}")
    ET.register_namespace("", VRS_NAMESPACE)
    try:
        tree = ET.parse(path)
        enable_bridge(tree, service_name, root_url)
    except ET.ParseError as exc:
        raise ValueError(f"invalid VRD XML: {exc}") from exc
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as stream:
            tree.write(stream, encoding="utf-8", xml_declaration=True)
        os.chmod(temporary, path.stat().st_mode)
        os.replace(temporary, path)
    except Exception:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass
        raise


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Enable CodexTestBridge in a Linux VRD")
    parser.add_argument("vrd_path", type=Path)
    parser.add_argument("--service-name", default="CodexTestBridge")
    parser.add_argument("--root-url", default="codex-test")
    args = parser.parse_args(argv)
    update_vrd(args.vrd_path, args.service_name, args.root_url)
    print(f"CodexTestBridge HTTP service enabled in {args.vrd_path}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
