#!/usr/bin/env python3
# db-update v1.0 — Update 1C database configuration
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

def main():
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(
        description="Update 1C database configuration",
        allow_abbrev=False,
    )
    parser.add_argument("-V8Path", default="")
    parser.add_argument("-InfoBasePath", default="")
    parser.add_argument("-InfoBaseServer", default="")
    parser.add_argument("-InfoBaseRef", default="")
    parser.add_argument("-UserName", default="")
    parser.add_argument("-Password", default="")
    parser.add_argument("-Extension", default="")
    parser.add_argument("-AllExtensions", action="store_true")
    parser.add_argument("-Dynamic", default="", choices=["", "+", "-"])
    parser.add_argument("-Server", action="store_true")
    parser.add_argument("-WarningsAsErrors", action="store_true")
    args = parser.parse_args()

    v8path = resolve_v8path(args.V8Path)

    # --- Validate connection ---
    if not args.InfoBasePath and (not args.InfoBaseServer or not args.InfoBaseRef):
        print("Error: specify -InfoBasePath or -InfoBaseServer + -InfoBaseRef", file=sys.stderr)
        sys.exit(1)

    # --- Temp dir ---
    temp_dir = os.path.join(tempfile.gettempdir(), f"db_update_{random.randint(0, 999999)}")
    os.makedirs(temp_dir, exist_ok=True)

    try:
        # --- Build arguments ---
        arguments = ["DESIGNER"]

        if args.InfoBaseServer and args.InfoBaseRef:
            arguments.extend(["/S", f"{args.InfoBaseServer}/{args.InfoBaseRef}"])
        else:
            arguments.extend(["/F", args.InfoBasePath])

        if args.UserName:
            arguments.append(f"/N{args.UserName}")
        if args.Password:
            arguments.append(f"/P{args.Password}")

        arguments.append("/UpdateDBCfg")

        # --- Options ---
        if args.Dynamic:
            arguments.append(f"-Dynamic{args.Dynamic}")
        if args.Server:
            arguments.append("-Server")
        if args.WarningsAsErrors:
            arguments.append("-WarningsAsErrors")

        # --- Extensions ---
        if args.Extension:
            arguments.extend(["-Extension", args.Extension])
        elif args.AllExtensions:
            arguments.append("-AllExtensions")

        # --- Output ---
        out_file = os.path.join(temp_dir, "update_log.txt")
        arguments.extend(["/Out", out_file])
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

        # --- Result ---
        if exit_code == 0:
            print("Database configuration updated successfully")
        else:
            print(f"Error updating database configuration (code: {exit_code})", file=sys.stderr)

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
