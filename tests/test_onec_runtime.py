import os
import sys
import tempfile
import unittest
from pathlib import Path

from common.onec_runtime import (
    RuntimeResolutionError,
    detect_version,
    mask_sensitive_arguments,
    onec_process_env,
    resolve_component,
)


class OneCRuntimeTests(unittest.TestCase):
    def make_component(self, directory: Path, name: str, executable: bool = True) -> Path:
        path = directory / name
        path.write_bytes(b"")
        path.chmod(0o755 if executable else 0o644)
        return path

    def test_explicit_file_and_directory_are_resolved(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "8.5.1.1529"
            root.mkdir()
            executable = self.make_component(root, "1cv8.exe" if os.name == "nt" else "1cv8")

            from_file = resolve_component("1cv8", executable)
            from_directory = resolve_component("1cv8", root)

            self.assertEqual(from_file.path, str(executable))
            self.assertEqual(from_directory.path, str(executable))
            self.assertEqual(from_file.bin_dir, str(root))
            self.assertEqual(from_file.version, "8.5.1.1529")

    def test_environment_value_is_used(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            executable = self.make_component(
                Path(temp_dir), "ibcmd.exe" if os.name == "nt" else "ibcmd"
            )
            resolved = resolve_component(
                "ibcmd",
                environ={"ONEC_IBCMD_PATH": str(executable)},
            )
            self.assertEqual(resolved.path, str(executable))

    def test_invalid_explicit_value_does_not_fall_back(self):
        with self.assertRaisesRegex(RuntimeResolutionError, "explicit argument"):
            resolve_component(
                "1cv8",
                "/definitely/missing/1cv8",
                environ={"ONEC_1CV8_PATH": "/also/missing/1cv8"},
            )

    def test_non_executable_linux_binary_is_rejected(self):
        if os.name == "nt":
            self.skipTest("POSIX executable permissions do not apply on Windows")
        with tempfile.TemporaryDirectory() as temp_dir:
            executable = self.make_component(Path(temp_dir), "webinst", executable=False)
            with self.assertRaisesRegex(RuntimeResolutionError, "not executable"):
                resolve_component("webinst", executable)

    def test_wsap_module_and_version_detection(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "8.5.1.1529"
            root.mkdir()
            module = self.make_component(
                root, "wsap24.dll" if os.name == "nt" else "wsap24.so", executable=False
            )
            resolved = resolve_component("wsap", root)

            self.assertEqual(resolved.path, str(module))
            self.assertEqual(detect_version(module), "8.5.1.1529")

    def test_process_environment_enables_x11_on_linux(self):
        source = {"PATH": "/usr/bin"}
        resolved = onec_process_env(environ=source)

        self.assertIsNot(resolved, source)
        self.assertNotIn("GDK_BACKEND", source)
        if sys.platform.startswith("linux"):
            self.assertEqual(resolved["GDK_BACKEND"], "x11")
        else:
            self.assertNotIn("GDK_BACKEND", resolved)

    def test_process_environment_preserves_compatible_backend(self):
        resolved = onec_process_env(environ={"GDK_BACKEND": "x11,broadway"})
        self.assertEqual(resolved["GDK_BACKEND"], "x11,broadway")

    def test_process_environment_replaces_incompatible_backend_on_linux(self):
        resolved = onec_process_env(environ={"GDK_BACKEND": "wayland"})
        expected = "x11" if sys.platform.startswith("linux") else "wayland"
        self.assertEqual(resolved["GDK_BACKEND"], expected)

    def test_sensitive_1c_arguments_are_masked(self):
        self.assertEqual(
            mask_sensitive_arguments(
                ["/NAdmin", "/Psecret", "--password", "other", "--password=value"]
            ),
            ["/NAdmin", "/P***", "--password", "***", "--password=***"],
        )


if __name__ == "__main__":
    unittest.main()
