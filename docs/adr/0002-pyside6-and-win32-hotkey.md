# PySide6 UI with Win32 RegisterHotKey via ctypes

- Status: accepted

`nyatodo` uses `PySide6` (Qt 6) for its desktop window, QSS dark/light theming, and system tray icon, paired with Windows' native `RegisterHotKey` API called through Python's built-in `ctypes` rather than a third-party global hook library.

## Considered Options

- **`tkinter`**: Built into Python with zero extra dependencies, but severely limited for clean modern typography, custom dark/light surfaces, and subtle animations.
- **`pywebview` (Edge WebView2)**: Tiny Python dependency with full HTML/CSS styling flexibility, but spawns Edge WebView2 processes (~120–220 MB RAM) and needs a separate tray library.
- **`PySide6` + Win32 `RegisterHotKey`**: Higher visual polish than `tkinter`, noticeably lower RAM than WebView2 (~50–90 MB), built-in `QSystemTrayIcon`, and `RegisterHotKey` via `ctypes` avoids installing low-level keyboard hook libraries (`keyboard`/`pynput`) that corporate security tools often flag.
