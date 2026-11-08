import os
import subprocess
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

import donut_background as bg


class FakeTransport:
    """Stands in for the session bus. Records calls and lets a test fire replies and signals."""

    def __init__(self, unique_name=":1.42", reply=("auto", None)):
        self._unique_name = unique_name
        self.reply = reply  # (handle or "auto" for the expected path, error name)
        self.events = []
        self.subscriptions = {}
        self.calls = []

    def unique_name(self):
        return self._unique_name

    def subscribe_response(self, path, callback):
        self.events.append(("subscribe", path))
        self.subscriptions[path] = callback

    def call_request_background(self, parent_window, options, on_reply):
        self.events.append(("call", None))
        self.calls.append((parent_window, options))
        handle, error = self.reply
        if handle == "auto":
            handle = bg.request_path(self._unique_name, options["handle_token"])
        on_reply(handle, error)

    def respond(self, path, code, results):
        self.subscriptions[path](code, results)


def run_request(transport, **kwargs):
    seen = []
    portal = bg.BackgroundPortal(transport, token_factory=lambda: "tok123")
    portal.request(seen.append, **kwargs)
    return seen


class SandboxDetectionTests(unittest.TestCase):
    def test_flatpak_info_marks_a_sandbox(self):
        with tempfile.TemporaryDirectory() as directory:
            marker = os.path.join(directory, ".flatpak-info")
            self.assertFalse(bg.in_sandbox(marker))
            open(marker, "w").close()
            self.assertTrue(bg.in_sandbox(marker))

    def test_default_marker_is_the_flatpak_file(self):
        with patch("donut_background.os.path.exists", return_value=True) as exists:
            self.assertTrue(bg.in_sandbox())
        exists.assert_called_once_with("/.flatpak-info")


class ProtocolTests(unittest.TestCase):
    def test_request_path_follows_the_portal_naming_rule(self):
        self.assertEqual(
            bg.request_path(":1.42", "tok123"),
            "/org/freedesktop/portal/desktop/request/1_42/tok123",
        )

    def test_options_ask_for_background_autostart_and_the_daemon(self):
        options = bg.build_options("why", "tok123", ["donut-monitord"], True)
        self.assertEqual(options, {
            "handle_token": "tok123",
            "reason": "why",
            "autostart": True,
            "commandline": ["donut-monitord"],
            "dbus-activatable": False,
        })

    def test_subscribes_before_calling_the_portal(self):
        transport = FakeTransport()
        run_request(transport)
        self.assertEqual([name for name, _ in transport.events], ["subscribe", "call"])
        parent_window, options = transport.calls[0]
        self.assertEqual(parent_window, "")
        self.assertEqual(options["commandline"], ["donut-monitord"])
        self.assertTrue(options["autostart"])
        self.assertEqual(options["handle_token"], "tok123")
        self.assertEqual(transport.events[0][1], "/org/freedesktop/portal/desktop/request/1_42/tok123")

    def test_granted(self):
        transport = FakeTransport()
        seen = run_request(transport)
        self.assertEqual(seen, [])  # nothing until the user answers
        transport.respond(transport.events[0][1], 0, {"background": True, "autostart": True})
        self.assertEqual(seen, [bg.BackgroundResult("granted", True, True)])

    def test_background_without_autostart_is_still_granted(self):
        transport = FakeTransport()
        seen = run_request(transport)
        transport.respond(transport.events[0][1], 0, {"background": True, "autostart": False})
        self.assertEqual((seen[0].status, seen[0].autostart), ("granted", False))

    def test_user_refusal_is_denied(self):
        for code, results in ((1, {}), (0, {"background": False, "autostart": False})):
            transport = FakeTransport()
            seen = run_request(transport)
            transport.respond(transport.events[0][1], code, results)
            self.assertEqual(seen[0].status, "denied", (code, results))

    def test_other_response_code_is_failed(self):
        transport = FakeTransport()
        seen = run_request(transport)
        transport.respond(transport.events[0][1], 2, {})
        self.assertEqual(seen[0].status, "failed")

    def test_missing_portal_is_unavailable(self):
        for error in ("org.freedesktop.DBus.Error.ServiceUnknown", "org.freedesktop.DBus.Error.UnknownMethod"):
            seen = run_request(FakeTransport(reply=(None, error)))
            self.assertEqual(seen, [bg.BackgroundResult("unavailable", detail=error)], error)

    def test_other_call_error_is_failed(self):
        error = "org.freedesktop.DBus.Error.AccessDenied"
        seen = run_request(FakeTransport(reply=(None, error)))
        self.assertEqual(seen, [bg.BackgroundResult("failed", detail=error)])

    def test_callback_runs_once(self):
        transport = FakeTransport()
        seen = run_request(transport)
        path = transport.events[0][1]
        transport.respond(path, 0, {"background": True, "autostart": True})
        transport.respond(path, 1, {})
        self.assertEqual(len(seen), 1)

    def test_response_before_the_call_reply_is_not_lost(self):
        transport = FakeTransport()
        original = transport.call_request_background

        def answer_first(parent_window, options, on_reply):
            transport.respond(transport.events[0][1], 0, {"background": True, "autostart": True})
            original(parent_window, options, on_reply)

        transport.call_request_background = answer_first
        seen = run_request(transport)
        self.assertEqual([r.status for r in seen], ["granted"])

    def test_old_portal_handle_gets_its_own_subscription(self):
        transport = FakeTransport(reply=("/org/freedesktop/portal/desktop/request/1_42/other", None))
        seen = run_request(transport)
        self.assertIn("/org/freedesktop/portal/desktop/request/1_42/other", transport.subscriptions)
        transport.respond("/org/freedesktop/portal/desktop/request/1_42/other", 0,
                          {"background": True, "autostart": True})
        self.assertEqual(seen[0].status, "granted")


class ControllerPolicyTests(unittest.TestCase):
    """restart_service keeps today's systemctl call outside a sandbox and skips it inside one."""

    @classmethod
    def setUpClass(cls):
        try:
            import brightness_kirigami_qt6 as gui
        except ImportError as error:  # PyQt6 or Kirigami helpers missing on this machine
            raise unittest.SkipTest(f"GUI module not importable: {error}")
        cls.gui = gui

    def make_self(self):
        return SimpleNamespace(statusChanged=Mock(), _on_background_result=Mock())

    def test_outside_a_sandbox_the_systemd_unit_is_restarted(self):
        fake = self.make_self()
        with patch.object(self.gui, "in_sandbox", return_value=False), \
                patch.object(self.gui.subprocess, "run") as run:
            self.gui.BrightnessController.restart_service(fake)
        run.assert_called_once_with(["systemctl", "--user", "restart", "donut-monitord.service"],
                                    check=True, capture_output=True)
        fake.statusChanged.emit.assert_called_once_with("Service restarted", "success")

    def test_inside_a_sandbox_systemctl_is_not_called(self):
        fake = self.make_self()
        with patch.object(self.gui, "in_sandbox", return_value=True), \
                patch.object(self.gui.subprocess, "run") as run:
            self.gui.BrightnessController.restart_service(fake)
        run.assert_not_called()
        self.assertEqual(fake.statusChanged.emit.call_args[0][1], "success")

    def test_background_request_goes_through_the_portal_class(self):
        fake = self.make_self()
        portal = Mock()
        with patch.object(self.gui, "BackgroundPortal", return_value=portal) as portal_class, \
                patch.object(self.gui, "QtDBusTransport") as transport_class:
            self.gui.BrightnessController.request_background(fake)
        portal_class.assert_called_once_with(transport_class.return_value)
        portal.request.assert_called_once_with(fake._on_background_result)

    def test_result_messages(self):
        fake = self.make_self()
        for result, kind in (
            (bg.BackgroundResult("granted", True, True), "success"),
            (bg.BackgroundResult("denied", detail="the request was cancelled"), "error"),
            (bg.BackgroundResult("unavailable", detail="x"), "error"),
        ):
            fake.statusChanged.reset_mock()
            self.gui.BrightnessController._on_background_result(fake, result)
            self.assertEqual(fake.statusChanged.emit.call_args[0][1], kind)


if __name__ == "__main__":
    unittest.main()
