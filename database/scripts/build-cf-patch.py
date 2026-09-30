#!/usr/bin/env python3
"""Build a minimal 1C CF patch over a binary base and verify its XML diff."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path, PurePosixPath
from typing import Callable, Iterable

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from common.onec_runtime import detect_version, onec_process_env, resolve_1cv8_cli  # noqa: E402


IGNORED_NAMES = {"configdumpinfo.xml"}
TEXT_SUFFIXES = {".bsl", ".json", ".md", ".mxl", ".txt", ".xml"}


class BuildPatchError(RuntimeError):
    pass


def normalize_relative_path(value: str) -> str:
    normalized = value.strip().replace("\\", "/")
    path = PurePosixPath(normalized)
    if not normalized or path.is_absolute() or ".." in path.parts:
        raise BuildPatchError(f"Allowlist path must be relative and stay inside ConfigDir: {value}")
    normalized = path.as_posix()
    if path.name.casefold() in IGNORED_NAMES:
        raise BuildPatchError("ConfigDumpInfo.xml cannot be included in the patch allowlist")
    return normalized


def read_allowlist(files: str, list_file: str) -> list[str]:
    if bool(files) == bool(list_file):
        raise BuildPatchError("Specify exactly one of -Files or -ListFile")
    if list_file:
        source = Path(list_file).resolve()
        if not source.is_file():
            raise BuildPatchError(f"Allowlist file not found: {source}")
        values = source.read_text(encoding="utf-8-sig").splitlines()
    else:
        values = files.split(",")
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        if not value.strip():
            continue
        relative = normalize_relative_path(value)
        folded = relative.casefold()
        if folded in seen:
            raise BuildPatchError(f"Duplicate allowlist path: {relative}")
        seen.add(folded)
        result.append(relative)
    if not result:
        raise BuildPatchError("Patch allowlist is empty")
    return result


def iter_files(root: Path, *, include_ignored: bool = False) -> Iterable[tuple[str, Path]]:
    for path in sorted(root.rglob("*")):
        if not path.is_file() or (not include_ignored and path.name.casefold() in IGNORED_NAMES):
            continue
        yield path.relative_to(root).as_posix(), path


def comparable_content(path: Path) -> bytes:
    data = path.read_bytes()
    if path.suffix.casefold() not in TEXT_SUFFIXES:
        return data
    for encoding in ("utf-8-sig", "utf-16", "cp1251"):
        try:
            text = data.decode(encoding)
            return text.replace("\r\n", "\n").replace("\r", "\n").encode("utf-8")
        except UnicodeDecodeError:
            continue
    return data


def tree_snapshot(root: Path) -> dict[str, str]:
    return {
        relative: hashlib.sha256(path.read_bytes()).hexdigest()
        for relative, path in iter_files(root, include_ignored=True)
    }


def diff_trees(left: Path, right: Path) -> list[str]:
    left_files = dict(iter_files(left))
    right_files = dict(iter_files(right))
    changed: list[str] = []
    for relative in sorted(set(left_files) | set(right_files)):
        if relative not in left_files or relative not in right_files:
            changed.append(relative)
        elif comparable_content(left_files[relative]) != comparable_content(right_files[relative]):
            changed.append(relative)
    return changed


def assert_exact_diff(actual: Iterable[str], expected: Iterable[str], phase: str) -> None:
    actual_set = {item.casefold(): item for item in actual}
    expected_set = {item.casefold(): item for item in expected}
    if actual_set.keys() == expected_set.keys():
        return
    unexpected = [actual_set[key] for key in sorted(actual_set.keys() - expected_set.keys())]
    missing = [expected_set[key] for key in sorted(expected_set.keys() - actual_set.keys())]
    details: list[str] = []
    if unexpected:
        details.append("unexpected: " + ", ".join(unexpected))
    if missing:
        details.append("missing: " + ", ".join(missing))
    raise BuildPatchError(f"{phase} differs from the allowlist ({'; '.join(details)})")


def read_log(path: Path) -> str:
    if not path.is_file():
        return ""
    data = path.read_bytes()
    for encoding in ("utf-8-sig", "utf-16", "cp1251"):
        try:
            return data.decode(encoding).strip()
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", errors="replace").strip()


def windows_command_line(executable: str, arguments: list[str]) -> str:
    """Render argv while preserving 1C connection strings with embedded quotes."""
    rendered = [subprocess.list2cmdline([executable])]
    rendered.extend(
        argument if argument.startswith(("File=", "Srvr=")) else subprocess.list2cmdline([argument])
        for argument in arguments
    )
    return " ".join(rendered)


def run_onec(v8path: str, arguments: list[str], log_path: Path) -> None:
    command = [v8path, *arguments, "/Out", str(log_path), "/DisableStartupDialogs"]
    process_command: str | list[str]
    if os.name == "nt":
        process_command = windows_command_line(command[0], command[1:])
    else:
        process_command = command
    result = subprocess.run(
        process_command,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=onec_process_env(),
    )
    if result.returncode != 0:
        details = read_log(log_path)
        suffix = f": {details}" if details else ""
        raise BuildPatchError(f"1C Designer exited with code {result.returncode}{suffix}")


def create_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Build a verified minimal CF patch over a binary base",
        allow_abbrev=False,
    )
    parser.add_argument("-V8Path", default="", help="Path to 1cv8 or its version directory")
    parser.add_argument(
        "-BaseCf", required=True, help="Unmodified production CF used as binary base",
    )
    parser.add_argument("-BaseConfigDir", required=True, help="Fresh XML dump matching BaseCf")
    parser.add_argument(
        "-ConfigDir", required=True, help="XML sources containing the intended changes",
    )
    parser.add_argument("-Files", default="", help="Comma-separated allowlist of changed files")
    parser.add_argument(
        "-ListFile", default="", help="UTF-8 allowlist file, one relative path per line",
    )
    parser.add_argument(
        "-OutputFile", required=True, help="Destination CF; replaced only after verification",
    )
    parser.add_argument("-ReportFile", default="", help="Optional JSON verification report")
    return parser


def write_json_atomic(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_value = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent,
    )
    os.close(descriptor)
    temporary = Path(temporary_value)
    try:
        temporary.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8",
        )
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def validate_artifact_paths(
    output: Path,
    report: Path | None,
    base_cf: Path,
    source_directories: Iterable[Path],
) -> None:
    artifacts = [output, *([report] if report else [])]
    for artifact in artifacts:
        if artifact == base_cf:
            raise BuildPatchError(f"Artifact path would overwrite BaseCf: {artifact}")
        for source in source_directories:
            if artifact.is_relative_to(source):
                raise BuildPatchError(
                    f"Artifact path must be outside XML source directories: {artifact}"
                )
    if report and report == output:
        raise BuildPatchError("ReportFile and OutputFile must be different paths")


def main(
    argv: list[str] | None = None,
    *,
    runner: Callable[[str, list[str], Path], None] = run_onec,
) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    args = create_parser().parse_args(argv)
    try:
        v8path = resolve_1cv8_cli(args.V8Path)
        base_cf = Path(args.BaseCf).resolve()
        base_config = Path(args.BaseConfigDir).resolve()
        config = Path(args.ConfigDir).resolve()
        output = Path(args.OutputFile).resolve()
        report = Path(args.ReportFile).resolve() if args.ReportFile else None
        if not base_cf.is_file():
            raise BuildPatchError(f"Base CF not found: {base_cf}")
        if not base_config.is_dir():
            raise BuildPatchError(f"Baseline XML directory not found: {base_config}")
        if not config.is_dir():
            raise BuildPatchError(f"Changed XML directory not found: {config}")
        if base_config == config:
            raise BuildPatchError("BaseConfigDir and ConfigDir must be different directories")
        validate_artifact_paths(output, report, base_cf, (base_config, config))
        allowlist = read_allowlist(args.Files, args.ListFile)
        for relative in allowlist:
            if not (config / Path(relative)).is_file():
                raise BuildPatchError(f"Allowlisted source file not found: {relative}")

        source_snapshot = tree_snapshot(config)
        baseline_snapshot = tree_snapshot(base_config)
        source_diff = diff_trees(base_config, config)
        assert_exact_diff(source_diff, allowlist, "Source XML diff")

        output.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="db_build_cf_patch_") as temporary_value:
            work = Path(temporary_value)
            infobase = work / "ib"
            working_source = work / "source"
            base_verification_dump = work / "base-verification"
            verification_dump = work / "verification"
            list_file = work / "allowlist.txt"
            shutil.copytree(config, working_source)
            list_file.write_text("\n".join(allowlist) + "\n", encoding="utf-8-sig")
            base_verification_dump.mkdir()
            verification_dump.mkdir()

            print("[1/6] Creating disposable file infobase")
            runner(v8path, ["CREATEINFOBASE", f'File="{infobase}";'], work / "01-create.log")
            print("[2/6] Loading the binary base CF without UpdateDBCfg")
            runner(
                v8path,
                ["DESIGNER", "/F", str(infobase), "/LoadCfg", str(base_cf)],
                work / "02-load-base.log",
            )
            print("[3/6] Verifying that BaseCf matches the baseline XML")
            runner(
                v8path,
                [
                    "DESIGNER", "/F", str(infobase),
                    "/DumpConfigToFiles", str(base_verification_dump),
                    "-Format", "Hierarchical",
                ],
                work / "03-dump-base.log",
            )
            assert_exact_diff(
                diff_trees(base_config, base_verification_dump), [], "Binary base XML diff",
            )
            print(f"[4/6] Applying {len(allowlist)} allowlisted XML file(s) with partial load")
            runner(
                v8path,
                [
                    "DESIGNER", "/F", str(infobase),
                    "/LoadConfigFromFiles", str(working_source),
                    "-listFile", str(list_file), "-partial", "-updateConfigDumpInfo",
                    "-Format", "Hierarchical",
                ],
                work / "04-load-patch.log",
            )
            print("[5/6] Dumping full XML and verifying the exact diff")
            runner(
                v8path,
                [
                    "DESIGNER", "/F", str(infobase),
                    "/DumpConfigToFiles", str(verification_dump),
                    "-Format", "Hierarchical",
                ],
                work / "05-dump-verify.log",
            )
            verified_diff = diff_trees(base_config, verification_dump)
            assert_exact_diff(verified_diff, allowlist, "Control XML diff")
            for relative in allowlist:
                dumped = verification_dump / Path(relative)
                intended = config / Path(relative)
                if (
                    not dumped.is_file()
                    or comparable_content(dumped) != comparable_content(intended)
                ):
                    raise BuildPatchError(
                        f"Control dump does not contain the intended content: {relative}"
                    )
            if (
                tree_snapshot(config) != source_snapshot
                or tree_snapshot(base_config) != baseline_snapshot
            ):
                raise BuildPatchError("Source XML directories changed during the build")

            print("[6/6] Dumping verified CF")
            descriptor, staged_value = tempfile.mkstemp(
                prefix=f".{output.name}.", suffix=".tmp", dir=output.parent,
            )
            os.close(descriptor)
            staged_cf = Path(staged_value)
            staged_cf.unlink()
            try:
                runner(
                    v8path,
                    ["DESIGNER", "/F", str(infobase), "/DumpCfg", str(staged_cf)],
                    work / "06-dump-cf.log",
                )
                if not staged_cf.is_file() or staged_cf.stat().st_size == 0:
                    raise BuildPatchError("Designer did not produce a non-empty CF")
                os.replace(staged_cf, output)
            finally:
                staged_cf.unlink(missing_ok=True)

        payload = {
            "ok": True,
            "outputFile": str(output),
            "baseCf": str(base_cf),
            "platformVersion": detect_version(v8path),
            "allowlist": allowlist,
            "verifiedDiff": allowlist,
            "sourceDirectoriesUnchanged": True,
        }
        if report:
            write_json_atomic(report, payload)
        print(f"Verified patch CF created: {output}")
        return 0
    except BuildPatchError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
