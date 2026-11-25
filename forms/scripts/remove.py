#!/usr/bin/env python3
# remove-form v1.0 — Remove form from 1C object
# Source: https://github.com/Desko77/claude-code-skills-1c

import argparse
import os
import re
import shutil
import sys
from pathlib import Path

from lxml import etree

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)
from common.diff_guard import TreeGuard
from common.xml_preserve import read_source_style, serialize_preserving, write_tree_preserving

NSMAP = {"md": "http://v8.1c.ru/8.3/MDClasses"}


def save_xml_with_bom(tree, path):
    """Save XML tree to file with UTF-8 BOM."""
    write_tree_preserving(tree, path)


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="Remove form from 1C object", allow_abbrev=False)
    parser.add_argument("-ObjectName", "-ProcessorName", required=True)
    parser.add_argument("-FormName", required=True)
    parser.add_argument("-SrcDir", default="src")
    parser.add_argument("-DryRun", action="store_true", help="Print the diff and do not change files")
    args = parser.parse_args()

    object_name = args.ObjectName
    form_name = args.FormName
    src_dir = args.SrcDir

    # --- Checks ---

    root_xml_path = os.path.join(src_dir, f"{object_name}.xml")
    if not os.path.exists(root_xml_path):
        print(f"Корневой файл обработки не найден: {root_xml_path}", file=sys.stderr)
        sys.exit(1)

    processor_dir = os.path.join(src_dir, object_name)
    forms_dir = os.path.join(processor_dir, "Forms")
    form_meta_path = os.path.join(forms_dir, f"{form_name}.xml")
    form_dir = os.path.join(forms_dir, form_name)

    if not os.path.exists(form_meta_path):
        print(f"Метаданные формы не найдены: {form_meta_path}", file=sys.stderr)
        sys.exit(1)

    guard = None if args.DryRun else TreeGuard(src_dir)

    # --- Delete files ---

    if args.DryRun:
        if os.path.isdir(form_dir):
            print(f"[DRY-RUN] Будет удалён каталог: {form_dir}")
        print(f"[DRY-RUN] Будет удалён файл: {form_meta_path}")
    else:
        if os.path.isdir(form_dir):
            shutil.rmtree(form_dir)
            print(f"[OK] Удалён каталог: {form_dir}")

        os.remove(form_meta_path)
        print(f"[OK] Удалён файл: {form_meta_path}")

    # --- Modify root XML ---

    root_xml_full = os.path.abspath(root_xml_path)
    parser_xml = etree.XMLParser(remove_blank_text=False)
    tree = etree.parse(root_xml_full, parser_xml)
    root = tree.getroot()

    # Remove <Form>FormName</Form> from ChildObjects
    for node in root.findall(".//md:ChildObjects/md:Form", NSMAP):
        if node.text and node.text.strip() == form_name:
            parent = node.getparent()
            prev = node.getprevious()
            if prev is not None:
                # Whitespace is in prev.tail
                if prev.tail and prev.tail.strip() == "":
                    prev.tail = ""
            else:
                # First child — whitespace is in parent.text
                if parent.text and parent.text.strip() == "":
                    parent.text = ""
            parent.remove(node)
            break

    # Clear every object-specific default form property that points to the
    # removed form. Catalogs and documents use specialized property names,
    # while processors and reports use DefaultForm.
    default_form_properties = (
        "DefaultForm",
        "DefaultObjectForm",
        "DefaultFolderForm",
        "DefaultListForm",
        "DefaultChoiceForm",
        "DefaultFolderChoiceForm",
        "DefaultRecordForm",
    )
    for property_name in default_form_properties:
        default_form = root.find(f".//md:{property_name}", NSMAP)
        if default_form is not None and default_form.text:
            if re.search(rf"Form\.{re.escape(form_name)}$", default_form.text):
                default_form.text = ""
                print(f"[OK] Очищён {property_name}")

    # Save with BOM (or show the diff in dry-run mode)
    if args.DryRun:
        import difflib

        original = Path(root_xml_full).read_bytes()
        updated = serialize_preserving(tree, read_source_style(root_xml_full))
        before = original.decode("utf-8-sig").splitlines()
        after = updated.decode("utf-8-sig").splitlines()
        print("--- Dry run: unified diff ---")
        print("\n".join(difflib.unified_diff(before, after, fromfile=root_xml_path, tofile=root_xml_path)))
        print("--- End dry run: no files changed ---")
    else:
        save_xml_with_bom(tree, root_xml_full)
        print(f"[OK] Форма {form_name} удалена из {root_xml_path}")
        unexpected = guard.changed_except(
            [root_xml_full, form_meta_path],
            allowed_prefixes=[form_dir],
        )
        if unexpected:
            print(
                "[ERROR] Unexpected file changes outside the removed form: "
                + ", ".join(unexpected[:20]),
                file=sys.stderr,
            )
            sys.exit(1)


if __name__ == "__main__":
    main()
