#!/usr/bin/env python3
# db-load-xml v1.3 — Load 1C configuration from XML files
# Source: https://github.com/Desko77/claude-code-skills-1c

import argparse
import os
import random
import shutil
import subprocess
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from common.onec_runtime import mask_sensitive_arguments, onec_process_env, resolve_1cv8_cli as resolve_v8path

def onec_path_argument(path):
    """Return a relative path: 1C for Linux treats "/s..." inside an absolute
    path as another /S option and fails with "server_addr=..."."""
    try:
        return os.path.relpath(os.path.abspath(path))
    except ValueError:
        return path


SOURCE_GUARD_FILES = ("Configuration.xml", "ConfigDumpInfo.xml")


def snapshot_source_files(config_dir):
    """Remember the two tracked root files that Partial load must not touch."""
    snapshot = {}
    for name in SOURCE_GUARD_FILES:
        path = os.path.join(config_dir, name)
        if os.path.isfile(path):
            with open(path, "rb") as source:
                snapshot[name] = source.read()
    return snapshot


def restore_changed_source_files(config_dir, snapshot):
    """Restore any root file changed by the platform and return their names."""
    changed = []
    for name, expected in snapshot.items():
        path = os.path.join(config_dir, name)
        try:
            with open(path, "rb") as source:
                actual = source.read()
        except OSError:
            actual = None
        if actual != expected:
            with open(path, "wb") as target:
                target.write(expected)
            changed.append(name)
    return changed


def build_partial_workspace(config_dir, target_dir):
    """Mirror ConfigDir into a throwaway tree for Partial load.

    The platform still reads Configuration.xml and the whole object tree during a
    partial load, so a genuinely sparse tree is rejected with "file does not
    exist". Instead, hard-link every immutable file (cheap on the same filesystem)
    and copy the two files the platform may rewrite: Configuration.xml and
    ConfigDumpInfo.xml. The tracked source tree is never modified.
    """
    os.makedirs(target_dir, exist_ok=True)
    mutable = {"Configuration.xml", "ConfigDumpInfo.xml"}
    linked = 0
    copied = 0
    for current, _directories, files in os.walk(config_dir):
        relative_dir = os.path.relpath(current, config_dir)
        destination_dir = target_dir if relative_dir == "." else os.path.join(target_dir, relative_dir)
        os.makedirs(destination_dir, exist_ok=True)
        for name in files:
            source = os.path.join(current, name)
            destination = os.path.join(destination_dir, name)
            if name in mutable and relative_dir == ".":
                shutil.copy2(source, destination)
                copied += 1
                continue
            try:
                os.link(source, destination)
                linked += 1
            except OSError:
                shutil.copy2(source, destination)
                copied += 1
    for name in mutable:
        source = os.path.join(config_dir, name)
        destination = os.path.join(target_dir, name)
        if os.path.isfile(source) and not os.path.exists(destination):
            shutil.copy2(source, destination)
            copied += 1
    return target_dir, linked, copied


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(
        description="Load 1C configuration from XML files",
        allow_abbrev=False,
    )
    parser.add_argument("-V8Path", default="", help="Path to 1cv8.exe or its bin directory")
    parser.add_argument("-InfoBasePath", default="", help="Path to file infobase")
    parser.add_argument("-InfoBaseServer", default="", help="1C server (for server infobase)")
    parser.add_argument("-InfoBaseRef", default="", help="Infobase name on server")
    parser.add_argument("-UserName", default="", help="1C user name")
    parser.add_argument("-Password", default="", help="1C user password")
    parser.add_argument("-ConfigDir", required=True, help="Directory with XML configuration sources")
    parser.add_argument(
        "-Mode",
        default="Full",
        choices=["Full", "Partial"],
        help="Load mode (default: Full)",
    )
    parser.add_argument("-Files", default="", help="Comma-separated relative file paths (for Partial mode)")
    parser.add_argument("-ListFile", default="", help="Path to file list (alternative to -Files, for Partial mode)")
    parser.add_argument(
        "-PartialFullTree",
        action="store_true",
        help="Load Partial mode from the full ConfigDir (legacy; may update ConfigDumpInfo.xml in the source tree)",
    )
    parser.add_argument(
        "-NoUpdateConfigDumpInfo",
        action="store_true",
        help="Do not pass -updateConfigDumpInfo in Partial mode",
    )
    parser.add_argument("-Extension", default="", help="Extension name to load")
    parser.add_argument("-AllExtensions", action="store_true", help="Load all extensions")
    parser.add_argument(
        "-Format",
        default="Hierarchical",
        choices=["Hierarchical", "Plain"],
        help="File format (default: Hierarchical)",
    )
    parser.add_argument("-UpdateDB", action="store_true", help="Also update database configuration after load")
    parser.add_argument(
        "-StrictLog",
        action="store_true",
        help="Treat silent rejection warnings in the log as errors (elevate exit code to 1)",
    )
    args = parser.parse_args()

    # --- Resolve V8Path ---
    v8path = resolve_v8path(args.V8Path)

    # --- Validate connection ---
    if not args.InfoBasePath and (not args.InfoBaseServer or not args.InfoBaseRef):
        print("Error: specify -InfoBasePath or -InfoBaseServer + -InfoBaseRef", file=sys.stderr)
        sys.exit(1)

    # --- Validate config dir ---
    if not os.path.exists(args.ConfigDir):
        print(f"Error: config directory not found: {args.ConfigDir}", file=sys.stderr)
        sys.exit(1)

    # --- Validate Partial mode ---
    if args.Mode == "Partial" and not args.Files and not args.ListFile:
        print("Error: -Files or -ListFile required for Partial mode", file=sys.stderr)
        sys.exit(1)

    # --- Temp dir ---
    temp_dir = os.path.join(tempfile.gettempdir(), f"db_load_xml_{random.randint(0, 999999)}")
    os.makedirs(temp_dir, exist_ok=True)

    try:
        # --- Build arguments ---
        arguments = ["DESIGNER"]

        if args.InfoBaseServer and args.InfoBaseRef:
            arguments += ["/S", f"{args.InfoBaseServer}/{args.InfoBaseRef}"]
        else:
            arguments += ["/F", args.InfoBasePath]

        if args.UserName:
            arguments.append(f"/N{args.UserName}")
        if args.Password:
            arguments.append(f"/P{args.Password}")

        load_dir = args.ConfigDir
        source_snapshot = None

        if args.Mode == "Full":
            print("Executing full configuration load...")
        else:
            print("Executing partial configuration load...")

            # Build list file
            generated_list_file = None
            if args.ListFile:
                # Use provided list file
                if not os.path.isfile(args.ListFile):
                    print(f"Error: list file not found: {args.ListFile}", file=sys.stderr)
                    sys.exit(1)
                generated_list_file = args.ListFile
                with open(args.ListFile, "r", encoding="utf-8-sig") as f:
                    file_list = [line.strip() for line in f if line.strip()]
            else:
                # Generate from -Files parameter
                file_list = [f.strip() for f in args.Files.split(",") if f.strip()]
                generated_list_file = os.path.join(temp_dir, "load_list.txt")
                with open(generated_list_file, "w", encoding="utf-8-sig") as f:
                    f.write("\n".join(file_list))

            print(f"Files to load: {len(file_list)}")
            for fl in file_list:
                print(f"  {fl}")

            for relative in file_list:
                normalized = relative.replace("\\", "/").lstrip("/")
                if not os.path.isfile(os.path.join(args.ConfigDir, *normalized.split("/"))):
                    print(f"Error: file not found in ConfigDir: {relative}", file=sys.stderr)
                    sys.exit(1)

            if args.PartialFullTree:
                print("Partial mode: using the full ConfigDir (legacy)")
            else:
                source_snapshot = snapshot_source_files(args.ConfigDir)
                load_dir, linked, copied = build_partial_workspace(
                    args.ConfigDir, os.path.join(temp_dir, "config")
                )
                print(
                    f"Partial mode: temporary workspace ({linked} hard-linked, {copied} copied file(s)); "
                    "the source ConfigDumpInfo.xml is not modified"
                )

            arguments += ["-listFile", onec_path_argument(generated_list_file)]
            arguments.append("-partial")
            if not args.NoUpdateConfigDumpInfo:
                arguments.append("-updateConfigDumpInfo")

        # On Linux 1C parses an absolute argument beginning with "/" as another
        # slash-option; pass a relative path to keep it a value of
        # /LoadConfigFromFiles.
        arguments += ["/LoadConfigFromFiles", onec_path_argument(load_dir)]
        arguments += ["-Format", args.Format]

        # --- Extensions ---
        if args.Extension:
            arguments += ["-Extension", args.Extension]
        elif args.AllExtensions:
            arguments.append("-AllExtensions")

        # --- UpdateDB ---
        if args.UpdateDB:
            arguments.append("/UpdateDBCfg")

        # --- Output ---
        out_file = os.path.join(temp_dir, "load_log.txt")
        arguments += ["/Out", onec_path_argument(out_file)]
        arguments.append("/DisableStartupDialogs")

        # --- Execute ---
        print(f"Running: {os.path.basename(v8path)} {' '.join(mask_sensitive_arguments(arguments))}")
        result = subprocess.run(
            [v8path] + arguments,
            capture_output=True,
            text=True,
            env=onec_process_env(),
        )
        exit_code = result.returncode

        if source_snapshot is not None:
            restored = restore_changed_source_files(args.ConfigDir, source_snapshot)
            if restored:
                print(
                    "[warning] partial load changed tracked source file(s): "
                    + ", ".join(restored)
                    + "; original bytes were restored",
                    file=sys.stderr,
                )
                exit_code = 1

        # --- Read log ---
        log_content = ""
        if os.path.isfile(out_file):
            try:
                with open(out_file, "r", encoding="utf-8-sig") as f:
                    log_content = f.read()
            except Exception:
                log_content = ""

        # --- Scan log for silent rejections ---
        # Platform often writes load-time rejections into /Out but exits with code 0.
        # These patterns flag cases where metadata was dropped or rejected silently.
        fatal_log_patterns = [
            "Неверное свойство объекта метаданных",
            "не входит в состав объекта метаданных",
            "Неизвестное имя типа",
            "Неизвестный объект метаданных",
            "Ни один из документов не является регистратором для регистра",
            "Неверное значение перечисления",
            "не может быть приведен к типу",
        ]
        silent_failures = []
        if log_content:
            for line in log_content.splitlines():
                for pat in fatal_log_patterns:
                    if pat in line:
                        silent_failures.append(line.strip())
                        break

        # --- Result ---
        # Default: mirror platform's verdict via exit code. Log content (including any
        # rejection warnings) is always printed to stdout for visibility. With -StrictLog,
        # elevate exit code to 1 when rejection patterns are found even if platform said 0.
        if exit_code == 0:
            print("Load completed successfully")
        else:
            print(f"Error loading configuration (code: {exit_code})", file=sys.stderr)

        if log_content:
            print("--- Log ---")
            print(log_content)
            print("--- End ---")

        if silent_failures:
            suffix = "" if args.StrictLog else " (pass -StrictLog to treat as error)"
            print(
                f"[warning] log contains {len(silent_failures)} rejection(s) — "
                f"platform loaded config but dropped properties/refs{suffix}",
                file=sys.stderr,
            )
            for f in silent_failures:
                print(f"  {f}", file=sys.stderr)
            if args.StrictLog and exit_code == 0:
                exit_code = 1

        sys.exit(exit_code)

    finally:
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir, ignore_errors=True)


if __name__ == "__main__":
    main()
