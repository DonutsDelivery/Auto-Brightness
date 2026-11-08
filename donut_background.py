"""Background and autostart permission through org.freedesktop.portal.Background.

Inside a Flatpak sandbox there is no systemd user manager to run
donut-monitord.service. The app asks the desktop portal instead. The portal
shows the permission prompt and writes the autostart entry on the host. Outside
a sandbox none of this runs: the package ships donut-monitord.service and the
user enables it with systemctl.

BackgroundPortal holds the portal protocol and takes a transport, so tests can
replace D-Bus. QtDBusTransport is the real one and uses PyQt6.QtDBus, which the
GUI already depends on.
"""

import logging
import os
import uuid
from dataclasses import dataclass
from typing import Callable, Dict, Optional, Sequence

FLATPAK_INFO = "/.flatpak-info"

PORTAL_SERVICE = "org.freedesktop.portal.Desktop"
PORTAL_PATH = "/org/freedesktop/portal/desktop"
BACKGROUND_INTERFACE = "org.freedesktop.portal.Background"
REQUEST_INTERFACE = "org.freedesktop.portal.Request"

DAEMON_COMMAND = "donut-monitord"
DEFAULT_REASON = "Adjust monitor brightness through the day, also when the window is closed"

# D-Bus errors that mean "there is no portal here", as opposed to a failed request.
_UNAVAILABLE_ERRORS = (
    "org.freedesktop.DBus.Error.ServiceUnknown",
    "org.freedesktop.DBus.Error.NameHasNoOwner",
    "org.freedesktop.DBus.Error.UnknownMethod",
    "org.freedesktop.DBus.Error.UnknownInterface",
    "org.freedesktop.DBus.Error.UnknownObject",
    "org.freedesktop.DBus.Error.NoServer",
    "org.freedesktop.DBus.Error.Disconnected",
)

_log = logging.getLogger("DonutBackground")


def in_sandbox(flatpak_info: str = FLATPAK_INFO) -> bool:
    """True inside a Flatpak sandbox, where Flatpak creates /.flatpak-info."""
    return os.path.exists(flatpak_info)


@dataclass(frozen=True)
class BackgroundResult:
    status: str  # granted, denied, failed or unavailable
    background: bool = False
    autostart: bool = False
    detail: str = ""


def request_path(unique_name: str, token: str) -> str:
    """Object path the portal gives the Request, so the signal can be matched before the call returns."""
    sender = unique_name.lstrip(":").replace(".", "_")
    return f"{PORTAL_PATH}/request/{sender}/{token}"


def build_options(reason: str, token: str, commandline: Sequence[str], autostart: bool) -> Dict[str, object]:
    return {
        "handle_token": token,
        "reason": reason,
        "autostart": autostart,
        "commandline": list(commandline),
        "dbus-activatable": False,
    }


def result_from_response(code: int, results: Dict[str, object]) -> BackgroundResult:
    """Map the Request.Response signal. 0 is success, 1 the user cancelled, 2 anything else."""
    if code == 0:
        background = bool(results.get("background", False))
        autostart = bool(results.get("autostart", False))
        if background:
            return BackgroundResult("granted", background, autostart)
        return BackgroundResult("denied", background, autostart, "background access was refused")
    if code == 1:
        return BackgroundResult("denied", detail="the request was cancelled")
    return BackgroundResult("failed", detail=f"portal response code {code}")


class BackgroundPortal:
    """Protocol side of RequestBackground, independent of any D-Bus library.

    A transport provides:
      unique_name() -> str
      subscribe_response(path, callback(code, results))  # callback fires once
      call_request_background(parent_window, options, on_reply(handle, error_name))
    """

    def __init__(self, transport, token_factory: Callable[[], str] = None):
        self._transport = transport
        self._token_factory = token_factory or (lambda: "donutmc" + uuid.uuid4().hex[:12])

    def request(
        self,
        callback: Callable[[BackgroundResult], None],
        reason: str = DEFAULT_REASON,
        commandline: Sequence[str] = (DAEMON_COMMAND,),
        autostart: bool = True,
    ) -> None:
        """Ask for background and autostart. callback runs once with the outcome."""
        done = []

        def finish(result: BackgroundResult) -> None:
            if not done:
                done.append(result)
                callback(result)

        def on_response(code, results):
            finish(result_from_response(int(code), dict(results or {})))

        token = self._token_factory()
        expected = request_path(self._transport.unique_name(), token)
        # Subscribe first: the portal can answer before the call reply arrives.
        self._transport.subscribe_response(expected, on_response)

        def on_reply(handle: Optional[str], error_name: Optional[str]) -> None:
            if error_name:
                status = "unavailable" if error_name in _UNAVAILABLE_ERRORS else "failed"
                finish(BackgroundResult(status, detail=error_name))
            elif handle and handle != expected:
                # Portals before version 0.9 ignore handle_token.
                self._transport.subscribe_response(handle, on_response)

        options = build_options(reason, token, commandline, autostart)
        self._transport.call_request_background("", options, on_reply)


class QtDBusTransport:
    """Session bus transport on PyQt6.QtDBus. Needs a running Qt event loop."""

    def __init__(self):
        from PyQt6.QtDBus import QDBusConnection

        self._bus = QDBusConnection.sessionBus()
        self._keep = []  # slots must outlive the connection

    def unique_name(self) -> str:
        return self._bus.baseService()

    def subscribe_response(self, path, callback) -> None:
        from PyQt6.QtCore import QObject, pyqtSlot
        from PyQt6.QtDBus import QDBusMessage

        bus = self._bus

        class Listener(QObject):
            @pyqtSlot(QDBusMessage)
            def on_message(self, message):
                arguments = message.arguments()
                bus.disconnect("", path, REQUEST_INTERFACE, "Response", self.on_message)
                if len(arguments) >= 2:
                    callback(arguments[0], arguments[1])
                else:
                    callback(2, {})

        listener = Listener()
        self._keep.append(listener)
        # An empty service matches the sender by path, which already holds our unique name.
        if not bus.connect("", path, REQUEST_INTERFACE, "Response", listener.on_message):
            _log.warning("Could not listen for the portal response on %s", path)

    def call_request_background(self, parent_window, options, on_reply) -> None:
        from PyQt6.QtCore import QMetaType
        from PyQt6.QtDBus import (
            QDBusArgument, QDBusMessage, QDBusPendingCallWatcher, QDBusPendingReply,
        )

        # A plain Python list would go out as an array of variants, the portal wants strings (as).
        marshalled = dict(options)
        for key, value in options.items():
            if isinstance(value, (list, tuple)):
                array = QDBusArgument()
                array.beginArray(QMetaType(QMetaType.Type.QString.value))
                for item in value:
                    array.add(str(item))
                array.endArray()
                marshalled[key] = array

        message = QDBusMessage.createMethodCall(
            PORTAL_SERVICE, PORTAL_PATH, BACKGROUND_INTERFACE, "RequestBackground")
        message.setArguments([parent_window, marshalled])
        pending = self._bus.asyncCall(message, 30000)
        watcher = QDBusPendingCallWatcher(pending)
        self._keep.append(watcher)

        def finished(_watcher):
            reply = QDBusPendingReply(pending)
            if reply.isError():
                on_reply(None, reply.error().name())
                return
            values = reply.reply().arguments()
            handle = None
            if values:
                # QtDBus hands object paths back as str or as QDBusObjectPath, depending on the build.
                handle = values[0].path() if hasattr(values[0], "path") else str(values[0])
            on_reply(handle, None)

        watcher.finished.connect(finished)
