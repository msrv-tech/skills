import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from common.test_database_registry import RegistryResolutionError, resolve_registry


ROOT = Path(__file__).resolve().parents[1]
RESOLVER_SCRIPT = ROOT / "test-databases" / "scripts" / "resolve-registry.py"
REPO_UPDATE_SCRIPT = ROOT / "repo-update" / "scripts" / "repo-update.py"

spec = importlib.util.spec_from_file_location("repo_update", REPO_UPDATE_SCRIPT)
assert spec is not None and spec.loader is not None
repo_update = importlib.util.module_from_spec(spec)
spec.loader.exec_module(repo_update)


def write_json(path: Path, value: object, encoding: str = "utf-8") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False), encoding=encoding)


class RegistryResolverTests(unittest.TestCase):
    def test_explicit_path_has_priority_and_cli_prints_absolute_path(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            explicit = root / "явный.json"
            ignored = root / "ignored.json"
            write_json(explicit, {"databases": []}, encoding="utf-8-sig")
            write_json(ignored, {"databases": []})
            environment = os.environ.copy()
            environment["CODEX_1C_TEST_DATABASES"] = str(ignored)

            result = subprocess.run(
                [sys.executable, str(RESOLVER_SCRIPT), "-RegistryPath", explicit.name],
                cwd=root,
                env=environment,
                capture_output=True,
                text=True,
                encoding="utf-8",
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout.strip(), str(explicit.resolve()))
            self.assertEqual(result.stderr, "")

    def test_environment_path_is_resolved_relative_to_current_directory(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            registry = root / "config" / "databases.json"
            write_json(registry, {"databases": []})

            resolved = resolve_registry(
                environ={"CODEX_1C_TEST_DATABASES": "config/databases.json"},
                cwd=root,
            )

            self.assertEqual(resolved, registry.resolve())

    def test_local_config_registry_is_relative_to_config_file(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            local_config = root / "private" / "local.json"
            registry = root / "private" / "registry" / "databases.json"
            write_json(local_config, {"testDatabasesPath": "registry/databases.json"})
            write_json(registry, {"databases": [{"Ref": "Демо"}]})

            resolved = resolve_registry(
                local_config_path=local_config,
                environ={},
                cwd=root / "unrelated",
            )

            self.assertEqual(resolved, registry.resolve())

    def test_codex_home_and_default_home_are_supported(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            registry = root / "registry.json"
            write_json(registry, {"databases": []})

            codex_home = root / "custom-codex"
            write_json(
                codex_home / "1c" / "local.json",
                {"testDatabasesPath": str(registry)},
            )
            self.assertEqual(
                resolve_registry(environ={"CODEX_HOME": str(codex_home)}, cwd=root),
                registry.resolve(),
            )

            home = root / "home"
            write_json(
                home / ".codex" / "1c" / "local.json",
                {"testDatabasesPath": str(registry)},
            )
            self.assertEqual(
                resolve_registry(environ={}, cwd=root, home=home),
                registry.resolve(),
            )

    def test_invalid_registry_is_reported_only_on_stderr(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            registry = Path(temp_dir) / "invalid.json"
            write_json(registry, {"databases": {}})

            result = subprocess.run(
                [sys.executable, str(RESOLVER_SCRIPT), "-RegistryPath", str(registry)],
                capture_output=True,
                text=True,
                encoding="utf-8",
                check=False,
            )

            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(result.stdout, "")
            self.assertIn("has no databases array", result.stderr)

    def test_missing_local_path_and_malformed_utf8_fail_strictly(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            local_config = root / "local.json"
            write_json(local_config, {})
            with self.assertRaisesRegex(RegistryResolutionError, "no testDatabasesPath"):
                resolve_registry(local_config_path=local_config, environ={}, cwd=root)

            registry = root / "bad.json"
            registry.write_bytes(b'{"databases":[]}\xff')
            with self.assertRaisesRegex(RegistryResolutionError, "Cannot read"):
                resolve_registry(registry_path=registry, environ={}, cwd=root)


class RepoUpdateTests(unittest.TestCase):
    def setUp(self):
        self.database = {
            "path": "/workspace/project",
            "Srvr": "server.example",
            "Ref": "Demo_Base",
            "User": "user",
            "Password": "database-secret",
            "Repository": {
                "Name": "Main repository",
                "Url": "tcp://server.example/repository",
                "User": "repo-user",
                "Password": "repository-secret",
            },
        }

    def test_database_selection_matches_ps1_fields_and_nearest_parent_order(self):
        databases = [
            {"path": "/workspace", "Ref": "root"},
            self.database,
            {
                "path": "/other",
                "Ref": "other",
                "Repository": {"Name": "Special Name", "Url": "tcp://repo/other"},
            },
        ]

        by_project = repo_update.select_databases(databases, "", "/workspace/project/src")
        by_repository = repo_update.select_databases(databases, "special name", "/nowhere")

        self.assertEqual([item["Ref"] for item in by_project], ["Demo_Base", "root"])
        self.assertEqual([item["Ref"] for item in by_repository], ["other"])

    def test_complete_server_command_is_built_without_running_1c(self):
        arguments = repo_update.build_arguments(
            self.database,
            "/tmp/repo update.log",
            version=123,
            revised=True,
            force=True,
            objects="/tmp/objects.xml",
            extension="Extension Name",
            update_db=True,
        )

        self.assertEqual(
            arguments,
            [
                "DESIGNER",
                "/S",
                "server.example/Demo_Base",
                "/Nuser",
                "/Pdatabase-secret",
                "/ConfigurationRepositoryF",
                "tcp://server.example/repository",
                "/ConfigurationRepositoryN",
                "repo-user",
                "/ConfigurationRepositoryP",
                "repository-secret",
                "/ConfigurationRepositoryUpdateCfg",
                "-v",
                "123",
                "-revised",
                "-force",
                "-objects",
                "/tmp/objects.xml",
                "-Extension",
                "Extension Name",
                "/UpdateDBCfg",
                "/Out",
                "/tmp/repo update.log",
                "/DisableStartupDialogs",
            ],
        )

    def test_connection_fallback_order_and_password_masking(self):
        connection_string_database = {
            **self.database,
            "Srvr": "",
            "Ref": "",
            "IBConnectionString": 'Srvr="server";Ref="base";',
        }
        arguments = repo_update.build_arguments(connection_string_database, "/tmp/log")
        masked = repo_update.mask_arguments(arguments, connection_string_database)

        self.assertEqual(arguments[1:3], ["/IBConnectionString", 'Srvr="server";Ref="base";'])
        self.assertNotIn("database-secret", masked)
        self.assertNotIn("repository-secret", masked)
        self.assertIn("/P***", masked)
        self.assertIn("***", masked)

        file_database = {
            "path": "/data/base",
            "Repository": {"Url": "/data/repository"},
        }
        self.assertEqual(
            repo_update.build_arguments(file_database, "/tmp/log")[1:3],
            ["/F", "/data/base"],
        )

    def test_invalid_repository_and_connection_are_rejected(self):
        with self.assertRaisesRegex(repo_update.RepoUpdateError, "Repository is not configured"):
            repo_update.build_arguments({"path": "/data/base"}, "/tmp/log")
        with self.assertRaisesRegex(repo_update.RepoUpdateError, "connection is incomplete"):
            repo_update.build_arguments(
                {"Repository": {"Url": "/data/repository"}},
                "/tmp/log",
            )


if __name__ == "__main__":
    unittest.main()
