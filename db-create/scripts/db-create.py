#!/usr/bin/env python3
# db-create v1.0 — Create 1C information base
# Source: https://github.com/Desko77/claude-code-skills-1c

import argparse
import os
import random
import shutil
import subprocess
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from common.onec_runtime import onec_process_env, resolve_1cv8_cli as resolve_v8path

def quote_cmd_arg(value):
    return '"' + value.replace('"', '\\"') + '"'


def format_cmd_arg(value):
    if value.startswith(("File=", "Srvr=")):
        return value
    if any(ch.isspace() for ch in value):
        return quote_cmd_arg(value)
    return value


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(
        description="Create 1C information base",
        allow_abbrev=False,
    )
    parser.add_argument("-V8Path", default="")
    parser.add_argument("-InfoBasePath", default="")
    parser.add_argument("-InfoBaseServer", default="")
    parser.add_argument("-InfoBaseRef", default="")
    parser.add_argument("-UseTemplate", default="")
    parser.add_argument("-AddToList", action="store_true")
    parser.add_argument("-ListName", default="")
    args = parser.parse_args()

    v8path = resolve_v8path(args.V8Path)

    # --- Validate connection ---
    if not args.InfoBasePath and (not args.InfoBaseServer or not args.InfoBaseRef):
        print("Error: specify -InfoBasePath or -InfoBaseServer + -InfoBaseRef", file=sys.stderr)
        sys.exit(1)

    # --- Validate template ---
    if args.UseTemplate and not os.path.exists(args.UseTemplate):
        print(f"Error: template file not found: {args.UseTemplate}", file=sys.stderr)
        sys.exit(1)

    # --- Temp dir ---
    temp_dir = os.path.join(tempfile.gettempdir(), f"db_create_{random.randint(0, 999999)}")
    os.makedirs(temp_dir, exist_ok=True)

    try:
        # --- Build arguments ---
        arguments = ["CREATEINFOBASE"]

        if args.InfoBaseServer and args.InfoBaseRef:
            arguments.append(f'Srvr="{args.InfoBaseServer}";Ref="{args.InfoBaseRef}";')
        else:
            arguments.append(f'File="{args.InfoBasePath}";')

        # --- Template ---
        if args.UseTemplate:
            arguments.extend(["/UseTemplate", args.UseTemplate])

        # --- Add to list ---
        if args.AddToList:
            if args.ListName:
                arguments.extend(["/AddToList", args.ListName])
            else:
                arguments.append("/AddToList")

        # --- Output ---
        out_file = os.path.join(temp_dir, "create_log.txt")
        arguments.extend(["/Out", out_file])
        arguments.append("/DisableStartupDialogs")

        # --- Execute ---
        print(f"Running: {os.path.basename(v8path)} {' '.join(arguments)}")
        if os.name == "nt":
            command_line = " ".join([quote_cmd_arg(v8path)] + [format_cmd_arg(arg) for arg in arguments])
            result = subprocess.run(
                command_line, capture_output=True, text=True, env=onec_process_env()
            )
        else:
            result = subprocess.run(
                [v8path] + arguments, capture_output=True, text=True, env=onec_process_env()
            )
        exit_code = result.returncode

        # --- Result ---
        if exit_code == 0:
            if args.InfoBaseServer and args.InfoBaseRef:
                print(f"Information base created successfully: {args.InfoBaseServer}/{args.InfoBaseRef}")
            else:
                print(f"Information base created successfully: {args.InfoBasePath}")
        else:
            print(f"Error creating information base (code: {exit_code})", file=sys.stderr)

        if os.path.isfile(out_file):
            try:
                with open(out_file, "r", encoding="utf-8-sig") as f:
                    log_content = f.read()
                if log_content:
                    print("--- Log ---")
                    print(log_content)
                    print("--- End ---")
            except Exception:
                pass

        sys.exit(exit_code)

    finally:
        if os.path.isdir(temp_dir):
            shutil.rmtree(temp_dir, ignore_errors=True)


if __name__ == "__main__":
    main()
