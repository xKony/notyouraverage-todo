# nyatodo Specification

`nyatodo` is a personal, keyboard-first desktop workspace for low-friction **Task** capture, thought structuring in a **Thinking Space**, and concurrent time tracking via **Task Timers** and **Work Sessions**.

---

## 1. Runtime & Architecture

- **Runtime**: Python 3.13+ desktop application using `PySide6` (Qt 6), per [ADR 0001](adr/0001-python-desktop-app.md) and [ADR 0002](adr/0002-pyside6-and-win32-hotkey.md).
- **Storage**: Local SQLite database defaulting to `%LOCALAPPDATA%\nyatodo\nyatodo.db`. The database path is configurable and injectable for isolated testing.
- **Windows Integration**: Native Win32 `RegisterHotKey` and `GetLastInputInfo` invoked through Python's built-in `ctypes` (`user32.dll` / `kernel32.dll`). No custom `.exe` compilation and no third-party global keyboard hook libraries (`keyboard`, `pynput`).
- **Layering**:
  - `nyatodo.domain`: Pure dataclasses, enums, input parsing, and time/wall-clock math.
  - `nyatodo.storage`: SQLite schema, migrations, and `SQLiteRepository`.
  - `nyatodo.service`: Application use cases (`TodoService`).
  - `nyatodo.platform_win32`: Win32 `ctypes` integration behind `PlatformBridge`.
  - `nyatodo.ui`: PySide6 spotlight window, tray icon, widgets, and QSS themes (zero raw SQL or domain/business logic).

---

## 2. Window, System Tray & Global Hotkey

- **Spotlight Window**: Compact, always-on-top, frameless-styled floating window (~`540x640` logical pixels) centered on the active screen.
- **System Tray Icon**: Persistent tray presence with context menu actions:
  - **Show / Hide**
  - **Settings...**
  - **Quit** (cleanly stops and persists any running **Task Timers** before exiting)
- **Global Hotkey**: Defaults to `Ctrl+Alt+Space` (configurable in Settings). Pressing it toggles visibility and brings the spotlight window to the foreground with the Quick Bar focused.
- **Layered `Esc` Behavior**:
  1. Inside an open modal (**Settings**, **Activity Summary** period modal) or filter popover: `Esc` cancels/closes the overlay.
  2. Inside an open editor or **Thinking Space** field (title edit, **Requester** edit, notes, **Sub-step** input, or manual **Work Session** entry): `Esc` auto-saves and exits/collapses the field back to **Task List** navigation.
  3. When the Quick Bar has non-empty text or active filter query: `Esc` clears the Quick Bar and returns to the unfiltered **Task List**.
  4. At the top level (**Task List** with no open inline editor, or empty Quick Bar): `Esc` hides the window to the system tray.

---

## 3. Quick Bar & Live Match / Filter

- **Auto-focus**: Opening or summoning the window places keyboard focus in the Quick Bar.
- **Instant Task Creation**: Pressing `Enter` in standard capture mode immediately creates a new **Task** with **Task Status** `Todo` and clears the bar.
- **`@name` Requester Parsing**:
  - Any `@name` token (e.g., `@alice`) sets the optional **Requester** on the created **Task** and is stripped from the **Task** title.
  - All other symbols (`#`, `!`, `/`, `:`, punctuation, URLs, etc.) remain literal text in the title.
  - Only the first valid `@name` token sets `Requester` (or whitespace-normalized trailing/embedded `@name`); if no `@name` token is present, `Requester` is `None`.
- **Live Match Preview**: As the user types in capture mode, matching existing **Tasks** (by title or **Requester**) preview dynamically in the **Task List** below. Pressing `Down` moves focus directly into the matching **Task** list instead of creating a new **Task**.
- **Filter / Search Mode (`/`)**: Starting input with `/` enters pure filter/search mode across the **Task List** without creating a **Task** on `Enter`.

---

## 4. Views & Task Status Lifecycle

Top-level view switcher (`1`, `2`, `3` when not typing in an input):

1. **`1` — Active**:
   - Displays `Doing` **Tasks** pinned at the top, followed by `Todo` **Tasks** below.
   - Starting a **Task Timer** on a `Todo` **Task** automatically promotes its **Task Status** from `Todo` to `Doing`.
   - Pausing/stopping a **Task Timer** keeps the **Task** in `Doing` (explicit status transition is required to move to `Waiting`, `Done`, or back to `Todo`).
   - Recently completed (`Done`) **Tasks** may be hidden from `Active` (visible in **Activity Summary** or via filter) or shown only when toggled/reopened.
2. **`2` — Waiting**:
   - Displays **Tasks** with **Task Status** `Waiting` (paused on a **Requester** or external dependency).
3. **`3` — Activity Summary**:
   - Displays a local chronological **Activity Summary** over a calendar day, **Work Week** (Monday through Sunday), or custom inclusive `From`–`To` date range.
   - Each period shows:
     - Per-**Task** accumulated **Work Session** durations and completed **Tasks** for that period.
     - **Merged non-overlapping wall-clock active total**: When multiple **Task Timers** overlap in time, overlapping intervals are merged (interval union) so the active total reflects real elapsed wall-clock work rather than double-counted parallel minutes.
     - **Daily Breakdown Strip** (for **Work Week** and 2–14 day custom ranges): Shows per-day activity bars and lets the user click any day to drill down into that day's **Activity Summary**.

- **Task List Filtering & Sorting**:
  - **Sort** (`Manual`, `Newest`, `Oldest`): `Doing` **Tasks** always remain pinned above `Todo` **Tasks**. Within each status group, `Manual` preserves `(sort_order, created_at, id)`, while `Newest`/`Oldest` order by `created_at` (with `id` tie-breaker).
  - **Added Date Filter** (`Any`, `Today`, `This Week`, `Last Week`, `Custom` inclusive `From`–`To`): Filters `Active` and `Waiting` **Tasks** by local creation date.
- **Reordering**: `Alt+Up` / `Alt+Down` reorders **Tasks** within their current status group (`Doing`, `Todo`, or `Waiting`) when `Sort` is `Manual`, persisted in SQLite.

---

## 5. Keyboard Shortcuts

When focus is in the **Task List** (not inside a text input):

| Key | Action |
|---|---|
| `Up` / `Down` (or `j` / `k`) | Navigate between **Tasks** |
| `t` | Toggle **Task Timer** (start or pause/stop) |
| `Enter` | Expand or collapse **Thinking Space** for selected **Task** |
| `n` | Expand **Thinking Space** (if collapsed) and focus Notes with cursor at end |
| `s` | Expand **Thinking Space** (if collapsed) and focus **Sub-step** quick-add input |
| `r` | Expand **Thinking Space** (if collapsed) and focus **Requester** input with text selected |
| `e` | Expand **Thinking Space** (if collapsed) and focus **Task** title input with text selected |
| `w` | Toggle **Task Status** to/from `Waiting` |
| `d` | Mark **Task** `Done` (or reopen a `Done` **Task** to `Todo`) |
| `+` | Open quick time adjustment (`+15m` / manual **Work Session**) |
| `Alt+Up` / `Alt+Down` | Move **Task** up or down within its status group (in `Manual` sort) |
| `1` / `2` / `3` | Switch view (`Active` · `Waiting` · `Activity Summary`) |
| `Ctrl+,` | Open Settings modal |
| `Esc` | Layered escape (close modal/popover -> collapse inline editor -> clear bar -> hide to tray) |

- **Show Shortcut Hints**: A toggleable setting (`On` / `Off`) displays subtle keycap hints in the footer and row actions to aid shortcut discovery.

---

## 6. Thinking Space & Work Sessions

Expanding a **Task** opens its inline **Thinking Space** containing:

- **Inline Title & Requester Edit**: Click or use direct-edit shortcuts (`e` for **Task** title, `r` for **Requester**, both selecting existing text) to edit the **Task** title and optional **Requester** (`@name` or plain text). Pressing `Enter` saves and collapses the **Thinking Space** back to **Task List** navigation; edits also auto-save on blur or `Esc`.
- **Freeform Notes**: Auto-saved plain-text notes area (`n` shortcut focuses with cursor at the end) where `Enter` inserts a newline, with debounced persistence and immediate flush on `Ctrl+Enter`, `Esc`, or window hide.
- **Sub-steps**: Ordered, checkable action items inside the **Thinking Space** with inline add (`s` shortcut focuses `+ Add sub-step...`; `Enter` adds the **Sub-step** and keeps focus in the input for rapid multi-step entry), toggle complete, and remove.
- **Work Sessions**: List of recorded **Work Sessions** for the **Task**, supporting:
  - Quick adjustments (`+15m`, `-10m`)
  - Manual **Work Session** entry (duration or start/end time)
  - Deleting an individual **Work Session**

---

## 7. Concurrent Timers, Idle Detection & Clean Exit

- **Concurrent Timers**: Multiple **Task Timers** may run simultaneously. Each running **Task Timer** tracks an open `started_at` timestamp persisted in SQLite so timer state survives crashes or restarts.
- **Idle Check Threshold**:
  - Configurable in Settings: `15 min`, `30 min`, or `Off`.
  - Polled periodically using Win32 `GetLastInputInfo` via `PlatformBridge` while at least one **Task Timer** is active.
  - When user input resumes after an idle gap exceeding the configured threshold, `nyatodo` surfaces a non-intrusive prompt offering **Keep full time** or **Trim idle time** (adjusting affected active timers / **Work Sessions** back to the idle onset timestamp).
- **Clean Exit**: Quitting the application stops all active **Task Timers**, records their **Work Sessions** up to exit time, unregisters the Win32 global hotkey, and closes SQLite cleanly.

---

## 8. Settings Modal (`Ctrl+,`)

Configurable preferences persisted locally:

- **Theme**: `Dark` | `Light` | `System` (follows Windows dark/light preference)
- **Global Shortcut**: Key combination string (default `Ctrl+Alt+Space`), validated and re-registered immediately via `PlatformBridge`
- **Show Shortcut Hints**: `On` | `Off`
- **Idle Check Threshold**: `15 min` | `30 min` | `Off`

---

## 9. Explicit TDD Seams

All core logic is built test-first against four explicit, Qt-free seams before UI integration:

1. **`QuickBarParser` (`parse_quick_input`)** in `nyatodo.domain`:
   - Parses raw Quick Bar text into structured intent: capture vs. filter mode (`/`), clean **Task** title, optional **Requester** from `@name`, while preserving all other symbols literally.
2. **`SQLiteRepository`** in `nyatodo.storage`:
   - Owns SQLite connection, schema initialization, and CRUD/query operations for **Tasks**, **Sub-steps**, **Work Sessions**, active **Task Timers**, ordering, and settings, parameterized by an injectable database path (`:memory:` or temp path in tests).
3. **`TodoService`** in `nyatodo.service`:
   - Orchestrates **Task** lifecycle (`Todo` -> `Doing` auto-promotion on timer start, staying `Doing` on pause, `Waiting`, `Done`/reopen), within-group reordering, creation-date filtering/sorting, **Thinking Space** updates, concurrent **Task Timers**, **Activity Summary** interval-union wall-clock math across days/**Work Weeks**/custom ranges, idle trim calculations, and clean shutdown timer persistence with an injectable clock.
4. **`PlatformBridge`** in `nyatodo.platform_win32`:
   - Defines a clean interface (`Protocol` / abstract boundary) for global hotkey registration/unregistration, idle-duration queries (`GetLastInputInfo`), and system theme detection, with Win32 `ctypes` implementation isolated behind it so service and UI tests can use deterministic fakes.
