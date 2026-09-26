import sys
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from atspi_runner import (
    AtspiRunnerError,
    expand_accessible_element,
    find_accessible_element,
    focus_application_window,
    invoke_accessible_element,
    normalize_accessible_text,
    run_atspi_bridge_request,
)


class FakeComponent:
    def __init__(self, focused=True):
        self.focused = focused

    def grab_focus(self):
        return self.focused


class FakeAccessible:
    def __init__(
        self,
        name="",
        *,
        description="",
        role="label",
        attributes=None,
        actions=None,
        children=None,
        action_result=True,
        focused=True,
    ):
        self.name = name
        self.description = description
        self.role = role
        self.attributes = attributes or {}
        self.actions = actions or []
        self.children = children or []
        self.action_result = action_result
        self.component = FakeComponent(focused)
        self.invoked = []

    def get_name(self):
        return self.name

    def get_description(self):
        return self.description

    def get_role_name(self):
        return self.role

    def get_attributes(self):
        return self.attributes

    def get_child_count(self):
        return len(self.children)

    def get_child_at_index(self, index):
        return self.children[index]

    def get_n_actions(self):
        return len(self.actions)

    def get_action_name(self, index):
        return self.actions[index]

    def do_action(self, index):
        self.invoked.append(index)
        return self.action_result

    def get_component_iface(self):
        return self.component


class FakeAtspi:
    class KeySynthType:
        PRESSRELEASE = "press-release"

    def __init__(self, keyboard_result=True):
        self.keyboard_result = keyboard_result
        self.keys = []

    def generate_keyboard_event(self, keysym, text, mode):
        self.keys.append((keysym, text, mode))
        return self.keyboard_result


class AtspiRunnerTests(unittest.TestCase):
    def test_normalization_ignores_mnemonic_markers_and_spacing(self):
        self.assertEqual(normalize_accessible_text("  &Open__ form  "), "open form")

    def test_find_element_uses_name_description_and_attributes(self):
        expected = FakeAccessible(attributes={"automation-id": "ClickableDecoration"})
        root = FakeAccessible("1C", children=[FakeAccessible("Other"), expected])
        self.assertIs(find_accessible_element([root], ["ClickableDecoration"]), expected)

    def test_default_action_is_preferred_over_keyboard_fallback(self):
        accessible = FakeAccessible("Open", actions=["show-menu", "click"])
        result = invoke_accessible_element(accessible, FakeAtspi())
        self.assertEqual(result["method"], "atspiAction")
        self.assertEqual(result["action"], "click")
        self.assertEqual(accessible.invoked, [1])

    def test_focus_enter_is_used_when_no_default_action_exists(self):
        atspi = FakeAtspi()
        result = invoke_accessible_element(FakeAccessible("Open"), atspi)
        self.assertEqual(result["method"], "atspiFocusEnter")
        self.assertEqual(atspi.keys[0][0], 0xFF0D)

    def test_expand_action_is_preferred_for_tree_row(self):
        accessible = FakeAccessible("Fixture tree parent", actions=["click", "expand or collapse"])
        result = expand_accessible_element(accessible, FakeAtspi())
        self.assertEqual(result["method"], "atspiExpandAction")
        self.assertEqual(result["action"], "expand or collapse")
        self.assertEqual(accessible.invoked, [1])

    def test_expand_falls_back_to_focused_right_key(self):
        atspi = FakeAtspi()
        result = expand_accessible_element(FakeAccessible("Fixture tree parent"), atspi)
        self.assertEqual(result["method"], "atspiFocusRight")
        self.assertEqual(atspi.keys[0][0], 0xFF53)

    def test_application_window_is_focused_before_global_key(self):
        frame = FakeAccessible("Codex UI conformance", role="frame")
        root = FakeAccessible("1cv8", role="application", children=[frame], focused=False)
        focused = focus_application_window([root])
        self.assertEqual(focused["role"], "frame")

    def test_request_returns_protocol_compatible_uia_response(self):
        accessible = FakeAccessible("Clickable decoration", actions=["click"])
        atspi = FakeAtspi()
        with patch("atspi_runner._atspi_module", return_value=atspi), patch(
            "atspi_runner.application_roots", return_value=[accessible]
        ):
            response = run_atspi_bridge_request(123, {
                "requestId": "request-1",
                "action": "invokeElement",
                "title": "Clickable decoration",
                "elementName": "ClickableDecoration",
            })
        self.assertTrue(response["ok"])
        self.assertEqual(response["status"], "uia-response")
        self.assertEqual(response["actual"]["method"], "atspiAction")

    def test_expand_request_returns_protocol_compatible_uia_response(self):
        accessible = FakeAccessible("Fixture tree parent", actions=["expand"])
        atspi = FakeAtspi()
        with patch("atspi_runner._atspi_module", return_value=atspi), patch(
            "atspi_runner.application_roots", return_value=[accessible]
        ):
            response = run_atspi_bridge_request(123, {
                "requestId": "request-2",
                "action": "expandElement",
                "title": "Fixture tree parent",
                "elementName": "",
            })
        self.assertTrue(response["ok"])
        self.assertEqual(response["status"], "uia-response")
        self.assertEqual(response["actual"]["method"], "atspiExpandAction")

    def test_press_key_focuses_owned_application_window(self):
        frame = FakeAccessible("Codex UI conformance", role="frame")
        atspi = FakeAtspi()
        with patch("atspi_runner._atspi_module", return_value=atspi), patch(
            "atspi_runner.application_roots", return_value=[frame]
        ):
            response = run_atspi_bridge_request(123, {
                "requestId": "request-3",
                "action": "pressKey",
                "key": "down",
            })
        self.assertTrue(response["ok"])
        self.assertEqual(response["actual"]["method"], "atspiFocusedKey")
        self.assertEqual(response["actual"]["focused"]["role"], "frame")

    def test_missing_element_is_a_structured_failure(self):
        with self.assertRaises(AtspiRunnerError):
            find_accessible_element([FakeAccessible("Other")], ["Missing"])


if __name__ == "__main__":
    unittest.main()
