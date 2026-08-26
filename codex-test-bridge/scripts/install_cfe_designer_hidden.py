#!/usr/bin/env python3
"""Install a CFE with batch Designer on an isolated Windows desktop."""

from __future__ import annotations

import argparse
import os
import sys
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from ui_worker import WindowsHiddenDesktopBackend, wait_for_process  # noqa: E402


def read_log(path: Path) -> str:
    if not path.exists():
        return ""
    data = path.read_bytes()
    for encoding in ("utf-8-sig", "utf-16", "cp1251"):
        try:
            return data.decode(encoding).strip()
        except UnicodeDecodeError:
            pass
    return data.decode("utf-8", errors="replace").strip()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--platform", required=True, help="Path to 1cv8.exe or its bin directory")
    connection = parser.add_mutually_exclusive_group(required=True)
    connection.add_argument("--server")
    connection.add_argument("--database-path")
    parser.add_argument("--database", help="Server infobase name; required with --server")
    parser.add_argument("--user", default="", help="Infobase user; omit for anonymous infobases")
    parser.add_argument("--password-env", default="CODEX_1C_PASSWORD")
    parser.add_argument("--empty-password", action="store_true", help="Use an explicitly empty infobase password")
    parser.add_argument("--extension", default="CodexTestBridge")
    parser.add_argument("--cfe", default=str(ROOT / "codex-test-bridge.cfe"))
    parser.add_argument("--log", required=True)
    parser.add_argument("--timeout", type=float, default=600)
    args = parser.parse_args()

    if os.name != "nt":
        raise RuntimeError("Hidden Designer installation is supported only on Windows")
    if args.server and not args.database:
        parser.error("--database is required with --server")

    password = os.environ.get(args.password_env)
    if args.empty_password:
        password = ""
    if args.user and password is None:
        raise RuntimeError(f"Environment variable is not set: {args.password_env}")

    platform = Path(args.platform).resolve()
    executable = platform / "1cv8.exe" if platform.is_dir() else platform
    cfe = Path(args.cfe).resolve()
    log = Path(args.log).resolve()
    if not executable.is_file():
        raise FileNotFoundError(f"1cv8.exe not found: {executable}")
    if not cfe.is_file():
        raise FileNotFoundError(f"CFE not found: {cfe}")
    log.parent.mkdir(parents=True, exist_ok=True)
    if log.exists():
        log.unlink()

    target = ["/S", f"{args.server}\\{args.database}"] if args.server else ["/F", str(Path(args.database_path).resolve())]
    authentication = ["/N", args.user, "/P", password] if args.user else []
    command = [
        str(executable), "DESIGNER", *target, *authentication,
        "/DisableStartupDialogs", "/DisableStartupMessages",
        "/LoadCfg", str(cfe), "-Extension", args.extension,
        "/UpdateDBCfg", "/Out", str(log),
    ]

    backend = WindowsHiddenDesktopBackend({}, str(ROOT), f"CodexCfeInstall-{uuid.uuid4().hex}")
    process = None
    try:
        process = backend.start(command)
        exit_code = wait_for_process(process, args.timeout)
    finally:
        if process is not None:
            process.close()
        backend.close()

    details = read_log(log)
    if exit_code != 0:
        raise RuntimeError(f"Designer exited with code {exit_code}: {details or 'no log output'}")
    print(details or "CFE installation completed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
