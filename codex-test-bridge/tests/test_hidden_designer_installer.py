import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from install_cfe_designer_hidden import (
    is_authentication_title, is_batch_designer_title, prepare_windows_raw_command,
    x11_keysym_name, xvfb_display_candidates,
)


class HiddenDesignerInstallerTests(unittest.TestCase):
    def test_unicode_credentials_use_x11_unicode_keysyms(self):
        self.assertEqual(x11_keysym_name("П"), "U041F")
        self.assertEqual(x11_keysym_name("a"), "U0061")
        self.assertEqual(x11_keysym_name("_"), "U005F")
        with self.assertRaises(ValueError):
            x11_keysym_name("\n")

    def test_xvfb_display_selection_skips_sockets_and_lock_files(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            sockets = root / "sockets"
            sockets.mkdir()
            (sockets / "X90").touch()
            (root / ".X91-lock").touch()
            candidates = xvfb_display_candidates(sockets, root)
        self.assertEqual(candidates[0], 92)
        self.assertNotIn(90, candidates)
        self.assertNotIn(91, candidates)

    def test_authentication_and_batch_windows_are_distinguished(self):
        self.assertTrue(is_authentication_title("Доступ к информационной базе"))
        self.assertTrue(is_authentication_title("Запуск 1С:Предприятия"))
        self.assertTrue(is_authentication_title("1С:Предприятие"))
        self.assertFalse(is_authentication_title("Загрузка конфигурационной информации..."))
        self.assertTrue(is_batch_designer_title("Конфигуратор - Бухгалтерия предприятия"))
        self.assertTrue(is_batch_designer_title("Загрузка конфигурационной информации..."))
        self.assertFalse(is_batch_designer_title("Доступ к информационной базе"))

    def test_windows_raw_command_preserves_empty_password_and_quotes_paths(self):
        command = [
            r"C:\Program Files\1cv8\bin\1cv8.exe",
            "DESIGNER",
            r"/Sserver\database",
            "/NTest User",
            '/P""',
            "/LoadCfg",
            r"C:\Temp Space\codex-test-bridge.cfe",
        ]

        prepared = prepare_windows_raw_command(command)

        self.assertEqual(prepared[0], command[0])
        self.assertEqual(prepared[4], '/P""')
        self.assertEqual(prepared[3], '"/NTest User"')
        self.assertEqual(prepared[6], '"C:\\Temp Space\\codex-test-bridge.cfe"')


if __name__ == "__main__":
    unittest.main()
