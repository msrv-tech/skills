#!/usr/bin/env python3
"""Run a UI scenario against a legacy target using a full bridge in a manager infobase."""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import uuid
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.install_cfe_with_bridge_bootstrap import bridge_execute  # noqa: E402
from ui_worker import load_worker_config, run_ui_worker  # noqa: E402
from ui_batch import run_ui_batch  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--allow-bootstrap-user", action="store_true", required=True)
    parser.add_argument("--target-bridge-base-url", required=True)
    parser.add_argument("--target-bridge-user", default="")
    parser.add_argument("--target-bridge-password-env", default="CODEX_1C_TARGET_BRIDGE_PASSWORD")
    parser.add_argument("--manager-bridge-base-url", required=True)
    parser.add_argument("--manager-bridge-user", default="")
    parser.add_argument("--manager-bridge-password-env", default="CODEX_1C_MANAGER_BRIDGE_PASSWORD")
    parser.add_argument("--worker-config", required=True)
    parser.add_argument("--scenario", action="append", required=True, help="UI scenario; repeat for one warm batch")
    parser.add_argument("--artifact-dir", required=True)
    parser.add_argument("--report", default="")
    args = parser.parse_args()

    target_bridge_password = os.environ.get(args.target_bridge_password_env, "")
    manager_bridge_password = os.environ.get(args.manager_bridge_password_env, "")
    target_user = "ctb_ui_target_" + uuid.uuid4().hex
    manager_user = "ctb_ui_manager_" + uuid.uuid4().hex

    def user_commands(user_name: str) -> tuple[str, str, str, str]:
        create_marker = "CODEX_UI_USER_CREATED_" + uuid.uuid4().hex
        delete_marker = "CODEX_UI_USER_DELETED_" + uuid.uuid4().hex
        create_code = (
        "u=InfoBaseUsers.CreateUser();"
        f'u.Name="{user_name}";'
        'u.FullName="Codex temporary UI test client";'
        "u.StandardAuthentication=True;u.ShowInList=False;"
        "For Each role In Metadata.Roles Do u.Roles.Add(role); EndDo;"
        f'u.Write();Raise "{create_marker}";'
        )
        delete_code = (
        f'u=InfoBaseUsers.FindByName("{user_name}");'
        "If u<>Undefined Then u.Delete(); EndIf;"
        f'Raise "{delete_marker}";'
        )
        return create_code, create_marker, delete_code, delete_marker

    target_create, target_created_marker, target_delete, target_deleted_marker = user_commands(target_user)
    manager_create, manager_created_marker, manager_delete, manager_deleted_marker = user_commands(manager_user)

    target_created = False
    manager_created = False
    previous_client_user = os.environ.get("CODEX_1C_CLIENT_USERNAME")
    previous_manager_user = os.environ.get("CODEX_1C_MANAGER_USERNAME")
    try:
        bridge_execute(
            args.target_bridge_base_url,
            target_create,
            args.target_bridge_user,
            target_bridge_password,
            target_created_marker,
        )
        target_created = True
        bridge_execute(
            args.manager_bridge_base_url,
            manager_create,
            args.manager_bridge_user,
            manager_bridge_password,
            manager_created_marker,
        )
        manager_created = True
        os.environ["CODEX_1C_CLIENT_USERNAME"] = target_user
        os.environ["CODEX_1C_MANAGER_USERNAME"] = manager_user
        worker_config = load_worker_config(args.worker_config)
        if len(args.scenario) == 1:
            report = run_ui_worker(worker_config, args.scenario[0], args.artifact_dir)
        else:
            report = run_ui_batch(worker_config, args.scenario, args.artifact_dir)
        if args.report:
            report_path = Path(args.report).resolve()
            report_path.parent.mkdir(parents=True, exist_ok=True)
            report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    finally:
        if previous_client_user is None:
            os.environ.pop("CODEX_1C_CLIENT_USERNAME", None)
        else:
            os.environ["CODEX_1C_CLIENT_USERNAME"] = previous_client_user
        if previous_manager_user is None:
            os.environ.pop("CODEX_1C_MANAGER_USERNAME", None)
        else:
            os.environ["CODEX_1C_MANAGER_USERNAME"] = previous_manager_user
        cleanup_operations = []
        if manager_created:
            cleanup_operations.append((
                args.manager_bridge_base_url, manager_delete, args.manager_bridge_user,
                manager_bridge_password, manager_deleted_marker,
            ))
        if target_created:
            cleanup_operations.append((
                args.target_bridge_base_url, target_delete, args.target_bridge_user,
                target_bridge_password, target_deleted_marker,
            ))
        for bridge_url, delete_code, bridge_user, bridge_password, delete_marker in cleanup_operations:
            last_error: Exception | None = None
            for _ in range(5):
                try:
                    bridge_execute(
                        bridge_url,
                        delete_code,
                        bridge_user,
                        bridge_password,
                        delete_marker,
                    )
                    last_error = None
                    break
                except Exception as error:
                    last_error = error
                    time.sleep(1)
            if last_error is not None:
                raise RuntimeError("UI run finished, but a temporary UI user was not removed") from last_error

    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
