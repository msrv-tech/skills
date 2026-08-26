#!/usr/bin/env python3
"""Build CodexTestBridge.cfe with batch Designer on an isolated Windows desktop."""

from __future__ import annotations

import argparse
import os
import shutil
import sys
import time
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


def run_designer(backend: WindowsHiddenDesktopBackend, command: list[str], log: Path, timeout: float) -> None:
    if log.exists():
        log.unlink()
    process = backend.start(command + ["/Out", str(log)])
    try:
        exit_code = wait_for_process(process, timeout)
    finally:
        process.close()
    if exit_code != 0:
        details = read_log(log)
        raise RuntimeError(f"Designer exited with code {exit_code}: {details or 'no log output'}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--platform", required=True, help="Path to 1cv8.exe or its bin directory")
    parser.add_argument("--work-dir", required=True)
    parser.add_argument("--source-dir", default=str(ROOT / "src"))
    parser.add_argument("--out-file", default=str(ROOT / "codex-test-bridge.cfe"))
    parser.add_argument("--timeout", type=float, default=180)
    args = parser.parse_args()

    if os.name != "nt":
        raise RuntimeError("Hidden Designer build is supported only on Windows")

    platform = Path(args.platform).resolve()
    executable = platform / "1cv8.exe" if platform.is_dir() else platform
    if not executable.is_file():
        raise FileNotFoundError(f"1cv8.exe not found: {executable}")

    work_dir = Path(args.work_dir).resolve()
    source_dir = Path(args.source_dir).resolve()
    seed_cfe = (ROOT / "codex-test-bridge.cfe").resolve()
    out_file = Path(args.out_file).resolve()
    if not source_dir.is_dir() or not seed_cfe.is_file():
        raise FileNotFoundError("Bridge source directory or seed CFE is missing")

    work_dir.mkdir(parents=True, exist_ok=True)
    run_dir = work_dir / f"run-{time.strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:8]}"
    run_dir.mkdir()
    ib_dir = run_dir / "ib"
    staged_cfe = run_dir / "codex-test-bridge.cfe"
    common = [str(executable), "DESIGNER", "/F", str(ib_dir), "/DisableStartupDialogs", "/DisableStartupMessages"]

    desktop_name = f"CodexCfeBuild-{uuid.uuid4().hex}"
    backend = WindowsHiddenDesktopBackend({}, str(ROOT), desktop_name)
    try:
        run_designer(
            backend,
            [str(executable), "CREATEINFOBASE", f"File={ib_dir};", "/DisableStartupDialogs", "/DisableStartupMessages"],
            run_dir / "01-create.log",
            args.timeout,
        )
        run_designer(
            backend,
            common + ["/LoadCfg", str(seed_cfe), "-Extension", "CodexTestBridge"],
            run_dir / "02-seed.log",
            args.timeout,
        )
        run_designer(
            backend,
            common + ["/LoadConfigFromFiles", str(source_dir), "-Extension", "CodexTestBridge"],
            run_dir / "03-import.log",
            args.timeout,
        )
        run_designer(
            backend,
            common + [
                "/CheckConfig", "-ConfigLogIntegrity", "-HandlersExistence",
                "-EmptyHandlers", "-Server", "-ThinClient", "-Extension", "CodexTestBridge",
            ],
            run_dir / "04-check.log",
            args.timeout,
        )
        run_designer(
            backend,
            common + ["/DumpCfg", str(staged_cfe), "-Extension", "CodexTestBridge"],
            run_dir / "05-dump.log",
            args.timeout,
        )
    finally:
        backend.close()

    if not staged_cfe.is_file() or staged_cfe.stat().st_size == 0:
        raise RuntimeError("Designer did not produce a CFE file")
    out_file.parent.mkdir(parents=True, exist_ok=True)
    target_temp = out_file.with_name(f".{out_file.name}.{uuid.uuid4().hex}.tmp")
    try:
        shutil.copy2(staged_cfe, target_temp)
        os.replace(target_temp, out_file)
    finally:
        target_temp.unlink(missing_ok=True)
    print(out_file)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
