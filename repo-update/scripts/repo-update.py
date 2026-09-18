#!/usr/bin/env python3
"""Update a 1C configuration from its configuration repository."""

from __future__ import annotations

import argparse
import os
import shlex
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, Mapping, Sequence

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from common.onec_runtime import RuntimeResolutionError, onec_process_env, resolve_1cv8
from common.test_database_registry import (
    RegistryResolutionError,
    load_registry,
    resolve_registry,
)


class RepoUpdateError(RuntimeError):
    """Raised for invalid registry entries or command parameters."""


def _text(value: object) -> str:
    return "" if value is None else str(value)


def _repository(database: Mapping[str, Any]) -> Mapping[str, Any]:
    value = database.get("Repository")
    return value if isinstance(value, Mapping) else {}


def database_matches(database: Mapping[str, Any], query: str) -> bool:
    """Match the same fields as the PowerShell implementation."""

    if not query:
        return False
    path = _text(database.get("path"))
    path_leaf = path.replace("\\", "/").rstrip("/").rsplit("/", 1)[-1] if path else ""
    repository = _repository(database)
    server = _text(database.get("Srvr"))
    ref = _text(database.get("Ref"))
    values = (
        ref,
        path_leaf,
        path,
        server,
        f"{server}/{ref}",
        _text(database.get("IBConnectionString")),
        _text(repository.get("Name")),
        _text(repository.get("Url")),
    )
    needle = query.casefold()
    return any(value and needle in value.casefold() for value in values)


def _normalized_path(path: str | os.PathLike[str]) -> str:
    return os.path.abspath(os.fspath(path)).rstrip("\\/").casefold()


def select_databases(
    databases: Sequence[object],
    query: str,
    project_path: str | os.PathLike[str],
) -> list[Mapping[str, Any]]:
    """Select query matches, or nearest project parent matches."""

    entries = [item for item in databases if isinstance(item, Mapping)]
    if query:
        return [item for item in entries if database_matches(item, query)]

    project = _normalized_path(project_path)
    matches: list[Mapping[str, Any]] = []
    for database in entries:
        path = _text(database.get("path"))
        if not path:
            continue
        database_path = _normalized_path(path)
        if project == database_path or project.startswith(database_path + os.sep):
            matches.append(database)
    return sorted(matches, key=lambda item: len(_normalized_path(_text(item.get("path")))), reverse=True)


def build_arguments(
    database: Mapping[str, Any],
    out_file: str | os.PathLike[str],
    *,
    version: int | None = None,
    revised: bool = False,
    force: bool = False,
    objects: str = "",
    extension: str = "",
    update_db: bool = False,
) -> list[str]:
    """Build subprocess arguments without starting 1C."""

    repository = _repository(database)
    if not repository:
        raise RepoUpdateError(f"Repository is not configured for {_text(database.get('path'))}")
    repository_url = _text(repository.get("Url"))
    if not repository_url:
        raise RepoUpdateError(f"Repository.Url is empty for {_text(database.get('path'))}")

    arguments = ["DESIGNER"]
    server = _text(database.get("Srvr"))
    ref = _text(database.get("Ref"))
    connection_string = _text(database.get("IBConnectionString"))
    database_path = _text(database.get("path"))
    if server and ref:
        arguments.extend(["/S", f"{server}/{ref}"])
    elif connection_string:
        arguments.extend(["/IBConnectionString", connection_string])
    elif database_path:
        arguments.extend(["/F", database_path])
    else:
        raise RepoUpdateError("database connection is incomplete for selected entry")

    user = _text(database.get("User"))
    password = _text(database.get("Password"))
    if user:
        arguments.append(f"/N{user}")
    if password:
        arguments.append(f"/P{password}")

    arguments.extend(["/ConfigurationRepositoryF", repository_url])
    repository_user = _text(repository.get("User"))
    repository_password = _text(repository.get("Password"))
    if repository_user:
        arguments.extend(["/ConfigurationRepositoryN", repository_user])
    if repository_password:
        arguments.extend(["/ConfigurationRepositoryP", repository_password])

    arguments.append("/ConfigurationRepositoryUpdateCfg")
    if version:
        arguments.extend(["-v", str(version)])
    if revised:
        arguments.append("-revised")
    if force:
        arguments.append("-force")
    if objects:
        arguments.extend(["-objects", objects])
    if extension:
        arguments.extend(["-Extension", extension])
    if update_db:
        arguments.append("/UpdateDBCfg")
    arguments.extend(["/Out", os.fspath(out_file), "/DisableStartupDialogs"])
    return arguments


def mask_arguments(arguments: Sequence[str], database: Mapping[str, Any]) -> list[str]:
    """Mask both infobase and repository passwords for display."""

    masked = list(arguments)
    password = _text(database.get("Password"))
    if password:
        masked = ["/P***" if item == f"/P{password}" else item for item in masked]

    repository_password = _text(_repository(database).get("Password"))
    if repository_password:
        for index, item in enumerate(masked[:-1]):
            if item == "/ConfigurationRepositoryP" and masked[index + 1] == repository_password:
                masked[index + 1] = "***"
    return masked


def _display_command(executable: str, arguments: Sequence[str]) -> str:
    command = [executable, *arguments]
    return subprocess.list2cmdline(command) if os.name == "nt" else shlex.join(command)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Update 1C configuration from repository",
        allow_abbrev=False,
    )
    parser.add_argument("database", nargs="?", help=argparse.SUPPRESS)
    parser.add_argument("-Database", dest="database_option", default="")
    parser.add_argument("-ProjectPath", default=os.getcwd())
    parser.add_argument("-RegistryPath", default="")
    parser.add_argument("-V8Path", default="")
    parser.add_argument("-Version", type=int)
    parser.add_argument("-Revised", action="store_true")
    parser.add_argument("-Force", action="store_true")
    parser.add_argument("-Objects", default="")
    parser.add_argument("-Extension", default="")
    parser.add_argument("-UpdateDB", action="store_true")
    parser.add_argument("-DryRun", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    if args.database and args.database_option:
        print("Error: specify the database either positionally or with -Database, not both", file=sys.stderr)
        return 1
    database_query = args.database_option or args.database or ""

    try:
        registry_path = resolve_registry(args.RegistryPath)
        registry = load_registry(registry_path, str(registry_path))
        if not registry["databases"]:
            raise RepoUpdateError(f"registry has no databases array: {registry_path}")
        matches = select_databases(registry["databases"], database_query, args.ProjectPath)
        if not matches:
            raise RepoUpdateError(f"database not found in {registry_path}")
        if len(matches) > 1:
            print("Multiple databases matched. Specify -Database more precisely:")
            for item in matches:
                repository_url = _text(_repository(item).get("Url")) or "-"
                print(
                    f"  {_text(item.get('path'))} | "
                    f"{_text(item.get('Srvr'))}/{_text(item.get('Ref'))} | {repository_url}"
                )
            return 2

        database = matches[0]
        with tempfile.TemporaryDirectory(prefix="repo_update_") as temp_dir:
            out_file = Path(temp_dir) / "repo_update.log"
            arguments = build_arguments(
                database,
                out_file,
                version=args.Version,
                revised=args.Revised,
                force=args.Force,
                objects=args.Objects,
                extension=args.Extension,
                update_db=args.UpdateDB,
            )
            executable = "1cv8.exe" if os.name == "nt" else "1cv8"
            if not args.DryRun:
                executable = resolve_1cv8(args.V8Path)
            print(
                f"Database: {_text(database.get('path'))} | "
                f"{_text(database.get('Srvr'))}/{_text(database.get('Ref'))}"
            )
            repository = _repository(database)
            print(f"Repository: {_text(repository.get('Name'))} | {_text(repository.get('Url'))}")
            print(f"Running: {_display_command(executable, mask_arguments(arguments, database))}")
            if args.DryRun:
                print("Dry run: 1C was not started")
                return 0

            result = subprocess.run(
                [executable, *arguments],
                check=False,
                env=onec_process_env(),
            )
            if out_file.is_file():
                with out_file.open("r", encoding="utf-8-sig") as stream:
                    log_content = stream.read()
                if log_content:
                    print("--- Log ---")
                    print(log_content)
                    print("--- End ---")

            if result.returncode == 0:
                print("Configuration updated from repository successfully")
            else:
                print(
                    f"Repository update failed (code: {result.returncode})",
                    file=sys.stderr,
                )
            return result.returncode
    except (RegistryResolutionError, RuntimeResolutionError, RepoUpdateError, OSError, UnicodeError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
