import importlib.util
import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "database" / "scripts" / "build-cf-patch.py"
SPEC = importlib.util.spec_from_file_location("build_cf_patch", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


class BuildCfPatchTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.base = self.root / "base"
        self.changed = self.root / "changed"
        for directory in (self.base, self.changed):
            (directory / "CommonModules" / "Exchange" / "Ext").mkdir(parents=True)
            (directory / "Forms").mkdir()
            (directory / "Configuration.xml").write_text("<Configuration/>\n", encoding="utf-8")
            (directory / "Forms" / "Main.xml").write_text("<Form mode='Auto'/>\n", encoding="utf-8")
            (directory / "ConfigDumpInfo.xml").write_text("generated\n", encoding="utf-8")
        self.relative = "CommonModules/Exchange/Ext/Module.bsl"
        (self.base / self.relative).write_text("old\n", encoding="utf-8")
        (self.changed / self.relative).write_text("new\n", encoding="utf-8")
        self.base_cf = self.root / "production.cf"
        self.base_cf.write_bytes(b"base-cf")
        self.v8 = self.root / "1cv8"
        self.v8.write_text("stub", encoding="utf-8")
        self.v8.chmod(0o755)
        self.output = self.root / "patch.cf"
        self.report = self.root / "report.json"
        self.commands = []
        self.dump_count = 0

    def tearDown(self):
        self.temporary.cleanup()

    def fake_runner(self, _v8path, arguments, _log_path, *, extra_control_change=False):
        self.commands.append(arguments)
        if "/LoadConfigFromFiles" in arguments:
            source = Path(arguments[arguments.index("/LoadConfigFromFiles") + 1])
            (source / "ConfigDumpInfo.xml").write_text(
                "platform-mutated-copy\n", encoding="utf-8",
            )
        elif "/DumpConfigToFiles" in arguments:
            self.dump_count += 1
            target = Path(arguments[arguments.index("/DumpConfigToFiles") + 1])
            shutil.copytree(self.base, target, dirs_exist_ok=True)
            if self.dump_count > 1:
                target_file = target / self.relative
                target_file.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(self.changed / self.relative, target_file)
            (target / "ConfigDumpInfo.xml").write_text(
                "different-generated-value\n", encoding="utf-8",
            )
            if extra_control_change and self.dump_count > 1:
                (target / "Forms" / "Main.xml").write_text(
                    "<Form mode='Usual'/>\n", encoding="utf-8",
                )
        elif "/DumpCfg" in arguments:
            Path(arguments[arguments.index("/DumpCfg") + 1]).write_bytes(b"verified-cf")

    def arguments(self):
        return [
            "-V8Path", str(self.v8),
            "-BaseCf", str(self.base_cf),
            "-BaseConfigDir", str(self.base),
            "-ConfigDir", str(self.changed),
            "-Files", self.relative,
            "-OutputFile", str(self.output),
            "-ReportFile", str(self.report),
        ]

    def test_verified_workflow_preserves_sources_and_atomically_replaces_output(self):
        self.output.write_bytes(b"previous-cf")
        before_base = MODULE.tree_snapshot(self.base)
        before_changed = MODULE.tree_snapshot(self.changed)

        def runner(v8path, arguments, log_path):
            if arguments[0] == "CREATEINFOBASE":
                infobase = Path(arguments[1].removeprefix('File="').removesuffix('";'))
                self.assertFalse(infobase.exists())
            self.fake_runner(v8path, arguments, log_path)

        exit_code = MODULE.main(self.arguments(), runner=runner)

        self.assertEqual(0, exit_code)
        self.assertEqual(b"verified-cf", self.output.read_bytes())
        self.assertEqual(before_base, MODULE.tree_snapshot(self.base))
        self.assertEqual(before_changed, MODULE.tree_snapshot(self.changed))
        payload = json.loads(self.report.read_text(encoding="utf-8"))
        self.assertEqual([self.relative], payload["verifiedDiff"])
        flattened = [argument for command in self.commands for argument in command]
        self.assertIn("-partial", flattened)
        self.assertIn("-updateConfigDumpInfo", flattened)
        self.assertNotIn("/UpdateDBCfg", flattened)
        self.assertEqual(6, len(self.commands))

    def test_unexpected_control_diff_keeps_existing_output(self):
        self.output.write_bytes(b"previous-cf")

        def runner(v8path, arguments, log_path):
            self.fake_runner(v8path, arguments, log_path, extra_control_change=True)

        exit_code = MODULE.main(self.arguments(), runner=runner)

        self.assertEqual(1, exit_code)
        self.assertEqual(b"previous-cf", self.output.read_bytes())
        self.assertFalse(self.report.exists())
        self.assertFalse(any("/DumpCfg" in command for command in self.commands))

    def test_binary_base_must_match_baseline_before_partial_load(self):
        self.output.write_bytes(b"previous-cf")

        def runner(v8path, arguments, log_path):
            self.fake_runner(v8path, arguments, log_path)
            if "/DumpConfigToFiles" in arguments and self.dump_count == 1:
                target = Path(arguments[arguments.index("/DumpConfigToFiles") + 1])
                (target / "Forms" / "Main.xml").write_text(
                    "binary base mismatch\n", encoding="utf-8",
                )

        exit_code = MODULE.main(self.arguments(), runner=runner)

        self.assertEqual(1, exit_code)
        self.assertEqual(b"previous-cf", self.output.read_bytes())
        self.assertFalse(any("/LoadConfigFromFiles" in command for command in self.commands))

    def test_source_diff_must_match_allowlist_before_platform_start(self):
        (self.changed / "Forms" / "Main.xml").write_text("unexpected\n", encoding="utf-8")

        exit_code = MODULE.main(self.arguments(), runner=self.fake_runner)

        self.assertEqual(1, exit_code)
        self.assertEqual([], self.commands)
        self.assertFalse(self.output.exists())

    def test_allowlist_rejects_unsafe_and_generated_paths(self):
        for value in ("../outside.bsl", "/absolute.bsl", "ConfigDumpInfo.xml"):
            with self.subTest(value=value):
                with self.assertRaises(MODULE.BuildPatchError):
                    MODULE.read_allowlist(value, "")
        with self.assertRaises(MODULE.BuildPatchError):
            MODULE.read_allowlist(f"{self.relative},{self.relative}", "")

    def test_text_comparison_normalizes_bom_and_line_endings_only(self):
        left = self.root / "left.bsl"
        right = self.root / "right.bsl"
        left.write_bytes(b"\xef\xbb\xbfline1\r\nline2\r\n")
        right.write_text("line1\nline2\n", encoding="utf-8")
        self.assertEqual(MODULE.comparable_content(left), MODULE.comparable_content(right))
        right.write_text("line1\nline 2\n", encoding="utf-8")
        self.assertNotEqual(MODULE.comparable_content(left), MODULE.comparable_content(right))

    def test_windows_command_line_preserves_1c_file_connection_quotes(self):
        rendered = MODULE.windows_command_line(
            r"C:\Program Files\1cv8\bin\1cv8.exe",
            ["CREATEINFOBASE", 'File="C:\\Temp Folder\\ib";', "/DisableStartupDialogs"],
        )
        self.assertEqual(
            '"C:\\Program Files\\1cv8\\bin\\1cv8.exe" '
            'CREATEINFOBASE File="C:\\Temp Folder\\ib"; /DisableStartupDialogs',
            rendered,
        )

    def test_artifacts_cannot_overwrite_inputs_or_enter_source_trees(self):
        invalid_pairs = (
            (self.base_cf, self.report),
            (self.base / "patch.cf", self.report),
            (self.output, self.changed / "report.json"),
            (self.output, self.output),
        )
        for output, report in invalid_pairs:
            with self.subTest(output=output, report=report):
                with self.assertRaises(MODULE.BuildPatchError):
                    MODULE.validate_artifact_paths(
                        output.resolve(), report.resolve(), self.base_cf.resolve(),
                        (self.base.resolve(), self.changed.resolve()),
                    )


if __name__ == "__main__":
    unittest.main()
