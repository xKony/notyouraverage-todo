"""Tests for PlatformBridge, hotkey parsing, and Win32 ctypes wrappers."""

import ctypes

import pytest

from nyatodo.domain import ThemeMode
from nyatodo.platform_win32 import (
    LASTINPUTINFO,
    MOD_ALT,
    MOD_CONTROL,
    MOD_NOREPEAT,
    MOD_SHIFT,
    MOD_WIN,
    PlatformBridge,
    Win32PlatformBridge,
    parse_hotkey,
)


def test_parse_hotkey_valid_combinations() -> None:
    assert parse_hotkey("Ctrl+Alt+Space") == (MOD_CONTROL | MOD_ALT, 0x20)
    assert parse_hotkey("  ctrl + shift + a ") == (MOD_CONTROL | MOD_SHIFT, ord("A"))
    assert parse_hotkey("Win+F12") == (MOD_WIN, 0x7B)
    assert parse_hotkey("Ctrl+,") == (MOD_CONTROL, 0xBC)


@pytest.mark.parametrize(
    "invalid",
    ["", "   ", "Ctrl+Alt", "Ctrl+A+B", "Ctrl+UnknownKey", "Space"],
)
def test_parse_hotkey_rejects_invalid_strings(invalid: str) -> None:
    with pytest.raises(ValueError):
        parse_hotkey(invalid)


def test_lastinputinfo_ctypes_layout() -> None:
    info = LASTINPUTINFO()
    info.cbSize = ctypes.sizeof(LASTINPUTINFO)
    assert info.cbSize == 8


class _FakeUser32:
    def __init__(self, *, last_input_dw_time: int = 0, register_ok: bool = True) -> None:
        self.register_calls: list[tuple[int, int, int, int]] = []
        self.unregister_calls: list[tuple[int, int]] = []
        self.last_input_dw_time = last_input_dw_time
        self.register_ok = register_ok
        self.seen_cb_sizes: list[int] = []

    def RegisterHotKey(self, hwnd: int, id: int, fsModifiers: int, vk: int) -> int:
        self.register_calls.append((hwnd, id, fsModifiers, vk))
        return 1 if self.register_ok else 0

    def UnregisterHotKey(self, hwnd: int, id: int) -> int:
        self.unregister_calls.append((hwnd, id))
        return 1

    def GetLastInputInfo(self, plii: object) -> int:
        # ctypes.byref(info) wraps LASTINPUTINFO; _obj accesses the underlying struct
        struct = getattr(plii, "_obj", plii)
        assert isinstance(struct, LASTINPUTINFO)
        self.seen_cb_sizes.append(int(struct.cbSize))
        struct.dwTime = self.last_input_dw_time
        return 1


class _FakeKernel32:
    def __init__(self, tick_count: int) -> None:
        self.tick_count = tick_count

    def GetTickCount(self) -> int:
        return self.tick_count


def test_win32_bridge_register_re_register_and_unregister() -> None:
    user32 = _FakeUser32()
    kernel32 = _FakeKernel32(tick_count=10_000)
    bridge: PlatformBridge = Win32PlatformBridge(user32=user32, kernel32=kernel32, is_windows=True)

    assert bridge.register_hotkey("Ctrl+Alt+Space", hotkey_id=7, hwnd=42) is True
    assert user32.register_calls == [(42, 7, MOD_CONTROL | MOD_ALT | MOD_NOREPEAT, 0x20)]

    assert bridge.register_hotkey("Ctrl+Shift+K", hotkey_id=7, hwnd=42) is True
    assert user32.unregister_calls == [(42, 7)]
    assert user32.register_calls[-1] == (42, 7, MOD_CONTROL | MOD_SHIFT | MOD_NOREPEAT, ord("K"))

    bridge.unregister_hotkey(7, hwnd=42)
    assert user32.unregister_calls == [(42, 7), (42, 7)]


def test_win32_bridge_idle_seconds_handles_32bit_tick_wraparound() -> None:
    user32 = _FakeUser32(last_input_dw_time=0xFFFF_FFF0)
    kernel32 = _FakeKernel32(tick_count=0x0000_0100)
    bridge = Win32PlatformBridge(user32=user32, kernel32=kernel32, is_windows=True)

    idle = bridge.get_idle_seconds()
    assert user32.seen_cb_sizes == [8]
    assert idle == pytest.approx(0.272)


def test_non_windows_fallback_is_safe() -> None:
    bridge = Win32PlatformBridge(is_windows=False)
    assert bridge.register_hotkey("Ctrl+Alt+Space") is False
    bridge.unregister_hotkey(1)
    assert bridge.get_idle_seconds() == 0.0
    assert bridge.get_system_theme() == ThemeMode.DARK
