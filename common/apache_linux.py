"""Strict Ubuntu Apache management for 1C web publications."""

from __future__ import annotations

import argparse
import html
import os
import re
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Sequence

from common.onec_runtime import RuntimeResolutionError, resolve_wsap_module


GLOBAL_CONF = "1c-skills-ws.conf"
PUBLICATION_PREFIX = "1c-skills-publication-"
APP_RE = re.compile(r"^[a-z0-9][a-z0-9._-]*$")


class ApacheLinuxError(RuntimeError):
    """Raised when a Linux Apache operation cannot be completed safely."""


@dataclass(frozen=True)
class ApacheLayout:
    available: Path
    enabled: Path
    publish_root: Path
    apachectl: str
    systemctl: str


def validate_app_name(value: str) -> str:
    app_name = value.strip().lower()
    if not APP_RE.fullmatch(app_name):
        raise ApacheLinuxError(
            "publication name must match [a-z0-9][a-z0-9._-]*"
        )
    return app_name


def derive_app_name(explicit: str, file_path: str, reference: str) -> str:
    if explicit:
        return validate_app_name(explicit)
    source = Path(file_path).name if file_path else reference
    candidate = re.sub(r"[^a-zA-Z0-9._-]", "", source).lower()
    if not candidate:
        raise ApacheLinuxError("cannot derive publication name; specify -AppName")
    return validate_app_name(candidate)


def _connection_value(value: str) -> str:
    if "\x00" in value or "\n" in value or "\r" in value:
        raise ApacheLinuxError("connection values must not contain NUL or newlines")
    return value.replace('"', '""')


def build_connection_string(
    *,
    file_path: str = "",
    server: str = "",
    reference: str = "",
    username: str = "",
    password: str = "",
) -> str:
    if bool(server) != bool(reference):
        raise ApacheLinuxError("-InfoBaseServer and -InfoBaseRef must be specified together")
    if bool(file_path) == bool(server):
        raise ApacheLinuxError(
            "specify exactly one of -InfoBasePath or -InfoBaseServer + -InfoBaseRef"
        )
    parts = (
        [f'File="{_connection_value(file_path)}"']
        if file_path
        else [
            f'Srvr="{_connection_value(server)}"',
            f'Ref="{_connection_value(reference)}"',
        ]
    )
    if username:
        parts.append(f'Usr="{_connection_value(username)}"')
    if password:
        parts.append(f'Pwd="{_connection_value(password)}"')
    return ";".join(parts) + ";"


def build_vrd(app_name: str, connection_string: str) -> str:
    app_name = validate_app_name(app_name)
    escaped = html.escape(connection_string, quote=True)
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<point xmlns="http://v8.1c.ru/8.2/virtual-resource-system"\n'
        '       xmlns:xs="http://www.w3.org/2001/XMLSchema"\n'
        '       xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"\n'
        f'       base="/{app_name}"\n'
        f'       ib="{escaped}"\n'
        '       enableStandardOdata="true">\n'
        '    <ws pointEnableCommon="true"/>\n'
        '    <httpServices publishByDefault="true"/>\n'
        '</point>\n'
    )


def _apache_quote(path: Path | str) -> str:
    value = os.fspath(path)
    if any(char in value for char in ('"', "\r", "\n", "\x00")):
        raise ApacheLinuxError(f"unsafe Apache path: {value!r}")
    return f'"{value}"'


def build_global_config(wsap_module: Path | str) -> str:
    return (
        "# Managed by bsl-skills; do not add foreign publications here.\n"
        f"LoadModule _1cws_module {_apache_quote(wsap_module)}\n"
    )


def build_publication_config(
    app_name: str, publish_dir: Path | str, vrd_path: Path | str
) -> str:
    app_name = validate_app_name(app_name)
    return (
        "# Managed by bsl-skills; this file owns one publication only.\n"
        f"Alias /{app_name} {_apache_quote(publish_dir)}\n"
        f"<Directory {_apache_quote(publish_dir)}>\n"
        "    AllowOverride None\n"
        "    Options None\n"
        "    Require all granted\n"
        "    SetHandler 1c-application\n"
        f"    ManagedApplicationDescriptor {_apache_quote(vrd_path)}\n"
        "</Directory>\n"
    )


def configtest_command(apachectl: str) -> list[str]:
    return [apachectl, "configtest"]


def systemctl_command(action: str, systemctl: str = "systemctl") -> list[str]:
    if action not in {"reload", "is-active"}:
        raise ValueError(f"unsupported systemctl action: {action}")
    return [systemctl, action, "apache2"]


def _run_checked(command: Sequence[str], description: str) -> subprocess.CompletedProcess[str]:
    try:
        result = subprocess.run(command, text=True, capture_output=True, check=False)
    except OSError as exc:
        raise ApacheLinuxError(f"{description} failed: {exc}") from exc
    if result.returncode:
        output = "\n".join(part.strip() for part in (result.stdout, result.stderr) if part.strip())
        raise ApacheLinuxError(
            f"{description} failed (exit {result.returncode})"
            + (f":\n{output}" if output else "")
        )
    return result


def _atomic_write(path: Path, content: str, mode: int = 0o644) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as stream:
            stream.write(content)
        os.chmod(temporary, mode)
        os.replace(temporary, path)
    except Exception:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass
        raise


def _enable(layout: ApacheLayout, name: str) -> None:
    source = layout.available / name
    destination = layout.enabled / name
    if destination.is_symlink() and destination.resolve() == source.resolve():
        return
    if destination.exists() or destination.is_symlink():
        raise ApacheLinuxError(f"refusing to replace non-owned Apache entry: {destination}")
    destination.symlink_to(source)


def _owned_publication_names(directory: Path) -> list[str]:
    result = []
    for path in directory.glob(f"{PUBLICATION_PREFIX}*.conf"):
        suffix = path.name[len(PUBLICATION_PREFIX) : -len(".conf")]
        if APP_RE.fullmatch(suffix):
            result.append(suffix)
    return sorted(result)


def _snapshot(paths: Iterable[Path]) -> dict[Path, tuple[str, bytes | str] | None]:
    result: dict[Path, tuple[str, bytes | str] | None] = {}
    for path in paths:
        if path.is_symlink():
            result[path] = ("symlink", os.readlink(path))
        elif path.exists():
            result[path] = ("file", path.read_bytes())
        else:
            result[path] = None
    return result


def _restore(snapshot: dict[Path, tuple[str, bytes | str] | None]) -> None:
    for path, state in snapshot.items():
        if path.exists() or path.is_symlink():
            if path.is_dir() and not path.is_symlink():
                shutil.rmtree(path)
            else:
                path.unlink()
        if state is None:
            continue
        kind, value = state
        path.parent.mkdir(parents=True, exist_ok=True)
        if kind == "symlink":
            path.symlink_to(str(value))
        else:
            path.write_bytes(bytes(value))


def _apply_and_reload(layout: ApacheLayout, snapshots: dict[Path, tuple[str, bytes | str] | None]) -> None:
    try:
        _run_checked(configtest_command(layout.apachectl), "apache2 configuration test")
        _run_checked(systemctl_command("reload", layout.systemctl), "apache2 reload")
    except Exception as exc:
        _restore(snapshots)
        try:
            _run_checked(configtest_command(layout.apachectl), "restored apache2 configuration test")
            _run_checked(systemctl_command("reload", layout.systemctl), "restored apache2 reload")
        except ApacheLinuxError as rollback_exc:
            raise ApacheLinuxError(f"{exc}; rollback also failed: {rollback_exc}") from exc
        raise


def default_layout(args: argparse.Namespace) -> ApacheLayout:
    return ApacheLayout(
        available=Path(args.ApacheConfigDir).resolve(),
        enabled=Path(args.ApacheEnabledDir).resolve(),
        publish_root=Path(args.PublishRoot).resolve(),
        apachectl=args.ApacheCtl,
        systemctl=args.Systemctl,
    )


def _add_layout_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("-ApacheConfigDir", default="/etc/apache2/conf-available")
    parser.add_argument("-ApacheEnabledDir", default="/etc/apache2/conf-enabled")
    parser.add_argument("-PublishRoot", default="/var/www/1c-publications")
    parser.add_argument("-ApacheCtl", default="apache2ctl")
    parser.add_argument("-Systemctl", default="systemctl")


def publish_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Publish 1C infobase via system Apache", allow_abbrev=False)
    parser.add_argument("-V8Path", default="", help="1C directory or wsap24.so path")
    parser.add_argument("-WsModule", default="", help="explicit official wsap24.so path")
    parser.add_argument("-InfoBasePath", default="")
    parser.add_argument("-InfoBaseServer", default="")
    parser.add_argument("-InfoBaseRef", default="")
    parser.add_argument("-UserName", default="")
    parser.add_argument("-Password", default="")
    parser.add_argument("-AppName", default="")
    parser.add_argument("-ApachePath", default="", help=argparse.SUPPRESS)
    parser.add_argument("-Port", type=int, default=80, help=argparse.SUPPRESS)
    parser.add_argument("-Manual", action="store_true", help=argparse.SUPPRESS)
    _add_layout_arguments(parser)
    return parser


def linux_publish(argv: Sequence[str] | None = None) -> int:
    args = publish_parser().parse_args(argv)
    if args.ApachePath:
        raise ApacheLinuxError("-ApachePath is Windows-only; use -ApacheConfigDir on Linux")
    if args.Port != 80:
        raise ApacheLinuxError("-Port is unsupported for system Apache; configure its VirtualHost explicitly")
    if args.Manual:
        raise ApacheLinuxError("-Manual is Windows-only and is not a Linux publication mode")
    connection = build_connection_string(
        file_path=args.InfoBasePath,
        server=args.InfoBaseServer,
        reference=args.InfoBaseRef,
        username=args.UserName,
        password=args.Password,
    )
    app_name = derive_app_name(args.AppName, args.InfoBasePath, args.InfoBaseRef)
    explicit_module = args.WsModule or args.V8Path or None
    try:
        wsap_module = Path(resolve_wsap_module(explicit_module)).resolve()
    except RuntimeResolutionError as exc:
        raise ApacheLinuxError(str(exc)) from exc
    layout = default_layout(args)
    if not layout.available.is_dir() or not layout.enabled.is_dir():
        raise ApacheLinuxError("Ubuntu Apache conf-available/conf-enabled directories are missing")

    publish_dir = layout.publish_root / app_name
    vrd_path = publish_dir / "default.vrd"
    global_available = layout.available / GLOBAL_CONF
    global_enabled = layout.enabled / GLOBAL_CONF
    pub_name = f"{PUBLICATION_PREFIX}{app_name}.conf"
    pub_available = layout.available / pub_name
    pub_enabled = layout.enabled / pub_name
    enable_paths = [global_enabled]
    enable_paths.extend(
        layout.enabled / f"{PUBLICATION_PREFIX}{name}.conf"
        for name in set(_owned_publication_names(layout.available)) | {app_name}
    )
    changed = [vrd_path, global_available, pub_available, *enable_paths]
    snapshots = _snapshot(changed)
    try:
        # Apache must be able to read the descriptor even when publication is
        # created by root and the file therefore belongs to root:root.
        _atomic_write(vrd_path, build_vrd(app_name, connection), 0o644)
        _atomic_write(global_available, build_global_config(wsap_module))
        _atomic_write(pub_available, build_publication_config(app_name, publish_dir, vrd_path))
        _enable(layout, GLOBAL_CONF)
        for name in set(_owned_publication_names(layout.available)):
            _enable(layout, f"{PUBLICATION_PREFIX}{name}.conf")
        _apply_and_reload(layout, snapshots)
    except Exception:
        _restore(snapshots)
        raise
    print(f"Публикация готова: http://localhost/{app_name}")
    print(f"VRD: {vrd_path}")
    return 0


def info_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="System Apache & 1C publication status", allow_abbrev=False)
    parser.add_argument("-ApachePath", default="", help=argparse.SUPPRESS)
    _add_layout_arguments(parser)
    return parser


def linux_info(argv: Sequence[str] | None = None) -> int:
    args = info_parser().parse_args(argv)
    if args.ApachePath:
        raise ApacheLinuxError("-ApachePath is Windows-only on Linux")
    layout = default_layout(args)
    if not layout.available.is_dir() or not layout.enabled.is_dir():
        raise ApacheLinuxError("Ubuntu Apache conf-available/conf-enabled directories are missing")
    try:
        active = subprocess.run(
            systemctl_command("is-active", layout.systemctl),
            text=True,
            capture_output=True,
            check=False,
        )
    except OSError as exc:
        raise ApacheLinuxError(f"cannot query apache2 status: {exc}") from exc
    status = active.stdout.strip() or active.stderr.strip() or f"exit {active.returncode}"
    print("=== Apache Web Server ===")
    print(f"Status: {status}")
    print(f"Config: {layout.available}")
    print("\n=== Управляемые публикации 1С ===")
    names = _owned_publication_names(layout.available)
    if not names:
        print("(нет публикаций)")
    for name in names:
        enabled = (layout.enabled / f"{PUBLICATION_PREFIX}{name}.conf").is_symlink()
        state = "включена" if enabled else "остановлена"
        print(f"  {name}  http://localhost/{name}  [{state}]")
    try:
        test = subprocess.run(
            configtest_command(layout.apachectl),
            text=True,
            capture_output=True,
            check=False,
        )
    except OSError as exc:
        raise ApacheLinuxError(f"cannot test apache2 configuration: {exc}") from exc
    output = "\n".join(part.strip() for part in (test.stdout, test.stderr) if part.strip())
    print(f"\nConfigtest: {'OK' if test.returncode == 0 else 'ERROR'}")
    if output:
        print(output)
    return 0 if active.returncode == 0 and test.returncode == 0 else 1


def stop_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Disable managed 1C publications", allow_abbrev=False)
    parser.add_argument("-ApachePath", default="", help=argparse.SUPPRESS)
    _add_layout_arguments(parser)
    return parser


def linux_stop(argv: Sequence[str] | None = None) -> int:
    args = stop_parser().parse_args(argv)
    if args.ApachePath:
        raise ApacheLinuxError("-ApachePath is Windows-only on Linux")
    layout = default_layout(args)
    names = _owned_publication_names(layout.available)
    enabled = [layout.enabled / GLOBAL_CONF]
    enabled.extend(layout.enabled / f"{PUBLICATION_PREFIX}{name}.conf" for name in names)
    snapshots = _snapshot(enabled)
    try:
        for path in enabled:
            if path.is_symlink():
                path.unlink()
            elif path.exists():
                raise ApacheLinuxError(f"refusing to remove non-symlink Apache entry: {path}")
        _apply_and_reload(layout, snapshots)
    except Exception:
        _restore(snapshots)
        raise
    print(f"Отключены управляемые публикации 1С: {len(names)}")
    print("Системный Apache и чужие публикации не остановлены")
    return 0


def unpublish_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Remove managed 1C publication", allow_abbrev=False)
    parser.add_argument("-AppName", default="")
    parser.add_argument("-All", action="store_true")
    parser.add_argument("-ApachePath", default="", help=argparse.SUPPRESS)
    _add_layout_arguments(parser)
    return parser


def linux_unpublish(argv: Sequence[str] | None = None) -> int:
    args = unpublish_parser().parse_args(argv)
    if args.ApachePath:
        raise ApacheLinuxError("-ApachePath is Windows-only on Linux")
    if args.All == bool(args.AppName):
        raise ApacheLinuxError("specify exactly one of -AppName or -All")
    layout = default_layout(args)
    names = _owned_publication_names(layout.available) if args.All else [validate_app_name(args.AppName)]
    if not names:
        print("Нет управляемых публикаций для удаления")
        return 0
    if not args.All and names[0] not in _owned_publication_names(layout.available):
        raise ApacheLinuxError(f"managed publication not found: {names[0]}")

    remaining = set(_owned_publication_names(layout.available)) - set(names)
    config_paths: list[Path] = []
    for name in names:
        conf = f"{PUBLICATION_PREFIX}{name}.conf"
        config_paths.extend((layout.available / conf, layout.enabled / conf))
    if not remaining:
        config_paths.extend((layout.available / GLOBAL_CONF, layout.enabled / GLOBAL_CONF))
    snapshots = _snapshot(config_paths)
    try:
        for path in config_paths:
            if path.is_symlink() or path.is_file():
                path.unlink()
            elif path.exists():
                raise ApacheLinuxError(f"refusing to remove unexpected Apache entry: {path}")
        _apply_and_reload(layout, snapshots)
    except Exception:
        _restore(snapshots)
        raise
    for name in names:
        publish_dir = layout.publish_root / name
        if publish_dir.exists():
            shutil.rmtree(publish_dir)
    print(f"Удалены управляемые публикации: {', '.join(names)}")
    return 0


def cli(function, argv: Sequence[str] | None = None) -> None:
    try:
        raise SystemExit(function(argv))
    except (ApacheLinuxError, OSError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
