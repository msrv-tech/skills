#!/usr/bin/env python3
"""Install a CFE using a short-lived infobase administrator created by the bridge."""

from __future__ import annotations

import argparse
import base64
import json
import os
import ssl
import subprocess
import sys
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def bridge_execute(base_url: str, code: str, username: str, password: str, marker: str) -> None:
    payload = json.dumps({"command": "ExecuteBSL", "code": code, "params": []}, ensure_ascii=True).encode("ascii")
    headers = {"Content-Type": "application/json"}
    if username:
        token = base64.b64encode(f"{username}:{password}".encode("utf-8")).decode("ascii")
        headers["Authorization"] = f"Basic {token}"
    opener = urllib.request.build_opener(
        urllib.request.ProxyHandler({}),
        urllib.request.HTTPSHandler(context=ssl._create_unverified_context()),
    )
    request = urllib.request.Request(base_url.rstrip("/") + "/command", data=payload, headers=headers)
    try:
        with opener.open(request, timeout=30) as response:
            body = response.read().decode("utf-8-sig", errors="replace")
    except urllib.error.HTTPError as error:
        body = error.read().decode("utf-8-sig", errors="replace")
    if marker not in body:
        raise RuntimeError("Bridge bootstrap command did not return its completion marker")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--allow-bootstrap-user", action="store_true", required=True)
    parser.add_argument("--bridge-base-url", required=True)
    parser.add_argument("--bridge-user", default="")
    parser.add_argument("--bridge-password-env", default="CODEX_1C_BRIDGE_PASSWORD")
    parser.add_argument("--platform", required=True)
    parser.add_argument("--server", required=True)
    parser.add_argument("--database", required=True)
    parser.add_argument("--cfe", required=True)
    parser.add_argument("--extension", default="CodexTestBridge")
    parser.add_argument("--log", required=True)
    parser.add_argument("--timeout", type=float, default=900)
    args = parser.parse_args()

    bridge_password = os.environ.get(args.bridge_password_env, "")
    temporary_user = "ctb_bootstrap_" + uuid.uuid4().hex
    create_marker = "CODEX_BOOTSTRAP_CREATED_" + uuid.uuid4().hex
    delete_marker = "CODEX_BOOTSTRAP_DELETED_" + uuid.uuid4().hex
    quoted_user = temporary_user.replace('"', '""')
    create_code = (
        "u=InfoBaseUsers.CreateUser();"
        f'u.Name="{quoted_user}";'
        'u.FullName="Codex temporary bridge installer";'
        "u.StandardAuthentication=True;u.ShowInList=False;"
        "For Each role In Metadata.Roles Do u.Roles.Add(role); EndDo;"
        f'u.Write();Raise "{create_marker}";'
    )
    delete_code = (
        f'u=InfoBaseUsers.FindByName("{quoted_user}");'
        "If u<>Undefined Then u.Delete(); EndIf;"
        f'Raise "{delete_marker}";'
    )

    created = False
    try:
        bridge_execute(args.bridge_base_url, create_code, args.bridge_user, bridge_password, create_marker)
        created = True
        command = [
            sys.executable,
            str(ROOT / "scripts" / "install_cfe_designer_hidden.py"),
            "--platform", args.platform,
            "--server", args.server,
            "--database", args.database,
            "--user", temporary_user,
            "--empty-password",
            "--extension", args.extension,
            "--cfe", args.cfe,
            "--log", args.log,
            "--timeout", str(args.timeout),
        ]
        install = subprocess.run(
            command,
            cwd=ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        if install.returncode != 0:
            raise RuntimeError("Hidden Designer installation failed; inspect the configured Designer log")
    finally:
        if created:
            last_error: Exception | None = None
            for _ in range(5):
                try:
                    bridge_execute(args.bridge_base_url, delete_code, args.bridge_user, bridge_password, delete_marker)
                    last_error = None
                    break
                except Exception as error:  # extension update can briefly restart the publication
                    last_error = error
                    time.sleep(1)
            if last_error is not None:
                raise RuntimeError("CFE operation finished, but the temporary bootstrap user was not removed") from last_error

    print("CFE installed; temporary bootstrap user removed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
