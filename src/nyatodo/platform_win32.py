"""Platform abstraction and Win32 ctypes integration for global hotkeys, idle time, and theme."""

import ctypes
import sys
from ctypes import wintypes
from typing import Protocol, SupportsIndex, SupportsInt

from nyatodo.domain import ThemeMode

MOD_ALT = 0x0001
MOD_CONTROL = 0x0002
MOD_SHIFT = 0x0004
MOD_WIN = 0x0008
MOD_NOREPEAT = 0x4000

WM_HOTKEY = 0x0312

_MODIFIER_MAP: dict[str, int] = {
    "alt": MOD_ALT,
    "ctrl": MOD_CONTROL,
    "control": MOD_CONTROL,
    "shift": MOD_SHIFT,
    "win": MOD_WIN,
    "super": MOD_WIN,
    "meta": MOD_WIN,
}

_KEY_MAP: dict[str, int] = {
    "space": 0x20,
    "enter": 0x0D,
    "return": 0x0D,
    "esc": 0x1B,
    "escape": 0x1B,
    "tab": 0x09,
    "backspace": 0x08,
    "delete": 0x2E,
    "del": 0x2E,
    "insert": 0x2D,
    "home": 0x24,
    "end": 0x23,
    "pageup": 0x21,
    "pagedown": 0x22,
    "up": 0x26,
    "down": 0x28,
    "left": 0x25,
    "right": 0x27,
    ",": 0xBC,
    "comma": 0xBC,
    ".": 0xBE,
    "period": 0xBE,
    "/": 0xBF,
    "slash": 0xBF,
    ";": 0xBA,
    "semicolon": 0xBA,
    "-": 0xBD,
    "minus": 0xBD,
    "=": 0xBB,
    "equal": 0xBB,
    "[": 0xDB,
    "]": 0xDD,
    "\\": 0xDC,
    "`": 0xC0,
}

for _fn_index in range(1, 13):
    _KEY_MAP[f"f{_fn_index}"] = 0x70 + (_fn_index - 1)


class LASTINPUTINFO(ctypes.Structure):
    """Win32 LASTINPUTINFO structure for GetLastInputInfo."""

    _fields_ = (
        ("cbSize", wintypes.UINT),
        ("dwTime", wintypes.DWORD),
    )


class PlatformBridge(Protocol):
    """Unified platform boundary injected into TodoService and UI."""

    def register_hotkey(self, shortcut: str, *, hotkey_id: int = 1, hwnd: int = 0) -> bool:
        """Register a global shortcut string; return True on success."""
        ...

    def unregister_hotkey(self, hotkey_id: int, *, hwnd: int = 0) -> None:
        """Unregister a previously registered hotkey ID."""
        ...

    def get_idle_seconds(self) -> float:
        """Return elapsed seconds since last keyboard or mouse input."""
        ...

    def get_system_theme(self) -> ThemeMode:
        """Return the OS-configured light or dark theme preference."""
        ...


def extract_hotkey_id_from_native_message(message: object) -> int | None:
    """Extract the Win32 WM_HOTKEY identifier from a native Qt MSG pointer or struct."""
    if isinstance(message, wintypes.MSG):
        msg = message
    else:
        if isinstance(message, bool | str | bytes | bytearray) or not isinstance(
            message, SupportsInt | SupportsIndex
        ):
            return None
        try:
            address = int(message)
        except (ValueError, TypeError, OverflowError):
            return None
        if address <= 0:
            return None
        try:
            msg = wintypes.MSG.from_address(address)
        except (ValueError, TypeError, OSError):
            return None

    if int(msg.message) != WM_HOTKEY:
        return None
    return int(msg.wParam)


class _User32API(Protocol):
    """Minimal typed boundary over Win32 user32 functions."""

    def RegisterHotKey(self, hwnd: int, id: int, fsModifiers: int, vk: int) -> int: ...

    def UnregisterHotKey(self, hwnd: int, id: int) -> int: ...

    def GetLastInputInfo(self, plii: object) -> int: ...


class _Kernel32API(Protocol):
    """Minimal typed boundary over Win32 kernel32 functions."""

    def GetTickCount(self) -> int: ...


def parse_hotkey(shortcut: str) -> tuple[int, int]:
    """Parse a shortcut string like 'Ctrl+Alt+Space' into (modifiers, vk_code)."""
    parts = [part.strip().lower() for part in shortcut.split("+") if part.strip()]
    if not parts:
        raise ValueError(f"Empty hotkey shortcut: {shortcut!r}")

    modifiers = 0
    vk_code: int | None = None

    for part in parts:
        if part in _MODIFIER_MAP:
            modifiers |= _MODIFIER_MAP[part]
            continue

        resolved_vk = _resolve_virtual_key(part)
        if resolved_vk is None:
            raise ValueError(f"Unsupported key token {part!r} in shortcut {shortcut!r}")
        if vk_code is not None:
            raise ValueError(f"Multiple non-modifier keys in shortcut {shortcut!r}")
        vk_code = resolved_vk

    if modifiers == 0:
        raise ValueError(f"Global hotkey requires at least one modifier: {shortcut!r}")
    if vk_code is None:
        raise ValueError(f"Global hotkey requires a non-modifier key: {shortcut!r}")
    return modifiers, vk_code


def _resolve_virtual_key(token: str) -> int | None:
    if token in _KEY_MAP:
        return _KEY_MAP[token]
    if len(token) == 1 and ("a" <= token <= "z" or "0" <= token <= "9"):
        return ord(token.upper())
    return None


class Win32PlatformBridge:
    """Win32 ctypes implementation of PlatformBridge with safe non-Windows fallback."""

    def __init__(
        self,
        *,
        user32: _User32API | None = None,
        kernel32: _Kernel32API | None = None,
        is_windows: bool | None = None,
    ) -> None:
        self._is_windows = (sys.platform == "win32") if is_windows is None else is_windows
        self._user32 = user32
        self._kernel32 = kernel32
        self._registered_ids: set[tuple[int, int]] = set()

    def _get_user32(self) -> _User32API | None:
        if self._user32 is not None:
            return self._user32
        if not self._is_windows:
            return None
        windll = getattr(ctypes, "windll", None)
        if windll is None:
            return None
        lib: _User32API = windll.user32
        self._user32 = lib
        return lib

    def _get_kernel32(self) -> _Kernel32API | None:
        if self._kernel32 is not None:
            return self._kernel32
        if not self._is_windows:
            return None
        windll = getattr(ctypes, "windll", None)
        if windll is None:
            return None
        lib: _Kernel32API = windll.kernel32
        self._kernel32 = lib
        return lib

    def register_hotkey(self, shortcut: str, *, hotkey_id: int = 1, hwnd: int = 0) -> bool:
        """Validate and register a Win32 global hotkey via RegisterHotKey."""
        modifiers, vk_code = parse_hotkey(shortcut)
        user32 = self._get_user32()
        if user32 is None:
            return False

        key = (hwnd, hotkey_id)
        if key in self._registered_ids:
            self.unregister_hotkey(hotkey_id, hwnd=hwnd)

        ok = bool(user32.RegisterHotKey(hwnd, hotkey_id, modifiers | MOD_NOREPEAT, vk_code))
        if ok:
            self._registered_ids.add(key)
        return ok

    def unregister_hotkey(self, hotkey_id: int, *, hwnd: int = 0) -> None:
        """Unregister a registered Win32 global hotkey."""
        user32 = self._get_user32()
        if user32 is None:
            return
        user32.UnregisterHotKey(hwnd, hotkey_id)
        self._registered_ids.discard((hwnd, hotkey_id))

    def get_idle_seconds(self) -> float:
        """Query Win32 GetLastInputInfo and return idle duration in seconds."""
        user32 = self._get_user32()
        kernel32 = self._get_kernel32()
        if user32 is None or kernel32 is None:
            return 0.0

        info = LASTINPUTINFO()
        info.cbSize = ctypes.sizeof(LASTINPUTINFO)
        if not user32.GetLastInputInfo(ctypes.byref(info)):
            return 0.0

        tick_count = int(kernel32.GetTickCount()) & 0xFFFFFFFF
        elapsed_ms = (tick_count - int(info.dwTime)) & 0xFFFFFFFF
        return elapsed_ms / 1000.0

    def get_system_theme(self) -> ThemeMode:
        """Read Windows AppsUseLightTheme registry preference, defaulting to Dark."""
        if not self._is_windows:
            return ThemeMode.DARK
        try:
            import winreg

            key_path = r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize"
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path) as key:
                value, _ = winreg.QueryValueEx(key, "AppsUseLightTheme")
                return ThemeMode.LIGHT if int(value) == 1 else ThemeMode.DARK
        except OSError:
            return ThemeMode.DARK
