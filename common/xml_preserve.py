"""Byte-preserving XML serialization helpers for 1C Configurator dumps.

The mutating skills historically loaded a document into a DOM, changed one node and
serialized the whole tree.  That rewrites BOM, XML declaration, line endings and
paired empty elements even when the rest of the file is untouched, producing broad
unrelated diffs.  These helpers restore the properties of the original file that a
DOM round-trip normally loses.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from lxml import etree
import xml.etree.ElementTree as ET


DEFAULT_DECLARATION = b'<?xml version="1.0" encoding="UTF-8"?>'
_UTF8_BOM = b"\xef\xbb\xbf"
_DECLARATION_RE = re.compile(rb"^<\?xml[^>]*\?>")
_PAIRED_EMPTY_RE = re.compile(rb"<([A-Za-z_][\w:.-]*)(\s[^<>]*?)?></\1>")


@dataclass(frozen=True)
class XmlSourceStyle:
    """Properties of the source file that must survive a DOM round-trip."""

    bom: bool = True
    eol: bytes = b"\n"
    declaration: bytes | None = DEFAULT_DECLARATION
    final_newline: bool = True
    paired_empty: tuple[tuple[bytes, int], ...] = ()
    root_start_tag: bytes | None = None


def _dominant_eol(body: bytes) -> bytes:
    crlf = body.count(b"\r\n")
    lf = body.count(b"\n") - crlf
    return b"\r\n" if crlf > lf else b"\n"


def _paired_empty_counts(body: bytes) -> tuple[tuple[bytes, int], ...]:
    counts: dict[bytes, int] = {}
    for match in _PAIRED_EMPTY_RE.finditer(body):
        name = match.group(1)
        counts[name] = counts.get(name, 0) + 1
    return tuple(sorted(counts.items()))


def read_source_style(path: str | os.PathLike[str]) -> XmlSourceStyle:
    """Capture BOM, EOL, declaration, final newline and paired-empty style."""

    raw = Path(path).read_bytes()
    bom = raw.startswith(_UTF8_BOM)
    body = raw[len(_UTF8_BOM):] if bom else raw
    declaration_match = _DECLARATION_RE.match(body)
    root_match = re.search(rb"<MetaDataObject[^>]*>", body)
    return XmlSourceStyle(
        bom=bom,
        eol=_dominant_eol(body),
        declaration=declaration_match.group(0) if declaration_match else None,
        final_newline=body.endswith(b"\n"),
        paired_empty=_paired_empty_counts(body),
        root_start_tag=root_match.group(0) if root_match else None,
    )


def default_source_style() -> XmlSourceStyle:
    return XmlSourceStyle()


def _restore_paired_empty(xml_bytes: bytes, counts: tuple[tuple[bytes, int], ...]) -> bytes:
    remaining = {name: count for name, count in counts}
    if not remaining:
        return xml_bytes

    def replace(match: re.Match[bytes]) -> bytes:
        name = match.group(1)
        left = remaining.get(name, 0)
        if left <= 0:
            return match.group(0)
        remaining[name] = left - 1
        return match.group(0)[:-2] + b"></" + name + b">"

    return re.sub(rb"<([A-Za-z_][\w:.-]*)(\s[^<>]*?)?/>", replace, xml_bytes)


def _restore_root_start_tag(xml_bytes: bytes, original: bytes | None) -> bytes:
    """Keep the original xmlns declarations and attribute order on the root tag."""

    if not original:
        return xml_bytes
    match = re.search(rb"<MetaDataObject[^>]*>", xml_bytes)
    if match is None:
        return xml_bytes
    serialized = match.group(0)
    version_match = re.search(rb'version="[^"]*"', serialized)
    restored = original
    if version_match is not None:
        if re.search(rb'version="[^"]*"', restored):
            restored = re.sub(rb'version="[^"]*"', version_match.group(0), restored, count=1)
        else:
            restored = restored[:-1] + b" " + version_match.group(0) + b">"
    return xml_bytes[:match.start()] + restored + xml_bytes[match.end():]


def _apply_style(
    xml_bytes: bytes,
    style: XmlSourceStyle,
    postprocess: Callable[[bytes], bytes] | None,
) -> bytes:
    if style.declaration is None:
        xml_bytes = _DECLARATION_RE.sub(b"", xml_bytes, count=1).lstrip(b"\r\n")
    else:
        xml_bytes = _DECLARATION_RE.sub(style.declaration, xml_bytes, count=1)
    xml_bytes = _restore_root_start_tag(xml_bytes, style.root_start_tag)
    xml_bytes = _restore_paired_empty(xml_bytes, style.paired_empty)

    # lxml always emits LF; restore the source line endings before writing.
    xml_bytes = xml_bytes.replace(b"\r\n", b"\n")
    if style.eol == b"\r\n":
        xml_bytes = xml_bytes.replace(b"\n", b"\r\n")

    xml_bytes = xml_bytes.rstrip(b"\r\n")
    if style.final_newline:
        xml_bytes += style.eol

    if postprocess is not None:
        xml_bytes = postprocess(xml_bytes)

    if style.bom and not xml_bytes.startswith(_UTF8_BOM):
        xml_bytes = _UTF8_BOM + xml_bytes
    elif not style.bom and xml_bytes.startswith(_UTF8_BOM):
        xml_bytes = xml_bytes[len(_UTF8_BOM):]

    return xml_bytes


def serialize_preserving(
    tree: etree._ElementTree,
    style: XmlSourceStyle,
    *,
    postprocess: Callable[[bytes], bytes] | None = None,
) -> bytes:
    """Serialize an lxml or stdlib ElementTree while restoring the source byte style."""

    if isinstance(tree, (ET.ElementTree, ET.Element)):
        return serialize_elementtree_preserving(tree, style, postprocess=postprocess)
    return _apply_style(
        etree.tostring(tree, xml_declaration=True, encoding="UTF-8"),
        style,
        postprocess,
    )


def serialize_elementtree_preserving(
    tree,
    style: XmlSourceStyle,
    *,
    postprocess: Callable[[bytes], bytes] | None = None,
) -> bytes:
    """Serialize a stdlib ElementTree while restoring the source byte style.

    ``xml.etree`` writes empty elements as ``<Tag />``.  The extra space is not
    produced by Configurator, so it is removed before the style is restored.
    """

    element = tree.getroot() if hasattr(tree, "getroot") else tree
    xml_bytes = ET.tostring(element, encoding="utf-8", xml_declaration=True)
    xml_bytes = re.sub(rb"<([A-Za-z_][\w:.-]*)(\s[^<>]*?)? />", rb"<\1\2/>", xml_bytes)
    return _apply_style(xml_bytes, style, postprocess)


def write_tree_preserving(
    tree: etree._ElementTree,
    path: str | os.PathLike[str],
    *,
    postprocess: Callable[[bytes], bytes] | None = None,
) -> None:
    """Write *tree* to *path*, preserving the existing file's byte style.

    New files get the historical defaults: UTF-8 BOM, LF, standard declaration and
    a trailing newline.
    """

    target = Path(path)
    style = read_source_style(target) if target.is_file() else default_source_style()
    target.write_bytes(serialize_preserving(tree, style, postprocess=postprocess))


def write_etree_preserving(
    tree,
    path: str | os.PathLike[str],
    *,
    postprocess: Callable[[bytes], bytes] | None = None,
) -> None:
    """Write a stdlib ElementTree, preserving the existing file's byte style."""

    target = Path(path)
    style = read_source_style(target) if target.is_file() else default_source_style()
    target.write_bytes(serialize_elementtree_preserving(tree, style, postprocess=postprocess))


def write_text_preserving(path: str | os.PathLike[str], text: str) -> None:
    """Write text while restoring BOM, EOL and final-newline style of the target."""

    target = Path(path)
    style = read_source_style(target) if target.is_file() else default_source_style()
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    if style.eol == b"\r\n":
        normalized = normalized.replace("\n", "\r\n")
    normalized = normalized.rstrip("\r\n")
    if style.final_newline:
        normalized += style.eol.decode("ascii")
    payload = normalized.encode("utf-8")
    if style.bom:
        payload = _UTF8_BOM + payload
    target.write_bytes(payload)
