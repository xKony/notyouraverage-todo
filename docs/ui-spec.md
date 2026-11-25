# `nyatodo` UI Design Specification

> **Authority:** Create (greenfield desktop operational surface).  
> **Primary Purpose:** **Operate** — UI disappears into the task. Keyboard-first speed, zero decorative clutter, crisp hierarchy.  
> **Domain Vocabulary:** Strictly follows [GLOSSARY.md](../GLOSSARY.md) (**Task**, **Task List**, **Requester**, **Task Status** [`Todo`, `Doing`, `Waiting`, `Done`], **Thinking Space**, **Sub-step**, **Task Timer**, **Work Session**, **Daily Summary**).

---

## 1. Anti-Slop Design Contract

`nyatodo` adopts a calm Swiss / Linear / Things-inspired desktop utility aesthetic. Every visual element must earn its pixels:

1. **Zero gradients:** Flat solid surfaces and hairline `1px` borders only. No gradient headers, buttons, or pills.
2. **Zero neon / purple-blue glow:** No colored `box-shadow` halos. Window elevation uses a single neutral drop shadow only.
3. **Zero dashboard card clutter:** No multi-card grids, sparklines, progress rings, or decorative containers. Collapsed **Task** rows share a clean unified **Task List**.
4. **Zero anime/mascot clutter or emoji in chrome:** Brand presence is limited to a single restrained `18 × 18` geometric cat-ear/whisker monogram (`1.5px` vector stroke) in the header and tray icon. No emoji anywhere in UI chrome.
5. **One grey family:** Cool slate-graphite neutrals across both **Dark** and **Light** themes. Never mix warm/sepia greys with cool greys.
6. **One accent hue, locked:** Muted Cobalt (`#5E8BFF` Dark / `#2054D6` Light) is the sole interactive accent across every surface. Semantic status colors are reserved strictly for **Task Status** (`Doing`, `Waiting`, `Done`) and destructive/trim actions (`danger`).
7. **Shape lock (Corner-Radius Scale):**
   - `12px`: Floating spotlight window outer shell
   - `10px`: Centered overlay modal (**Settings**)
   - `8px`: **Quick Bar**, expanded **Thinking Space** inset, **Idle Check** banner, **Daily Summary** hero container
   - `6px`: **Task** row hover/selection highlight, segmented tab track, action buttons, **Work Session** quick-adjust chips
   - `4px`: `@Requester` pill, shortcut keycaps, active segmented tab item
   - `999px`: Header running **Task Timer** pill, status dots
8. **Spacing grid:** Strict `4px` base unit (`4px`, `8px`, `12px`, `16px`, `20px`).

---

## 2. Window Geometry, Chrome & System Tray

| Property | Specification |
|---|---|
| **Default Size** | `540 × 660` logical px |
| **Minimum Size** | `460 × 520` logical px (resizable via bottom-right grip & window edges) |
| **Window Flags** | `Qt.FramelessWindowHint \| Qt.Window` with `Qt.WA_TranslucentBackground` outer margin (`12px`) for shadow + rounded `12px` inner frame |
| **Outer Border** | `1px solid border_subtle` |
| **Window Elevation Shadow** | Dark: `0 16px 40px rgba(0, 0, 0, 0.48)` · Light: `0 12px 32px rgba(15, 23, 42, 0.14)` |
| **Drag Handle** | Entire `44px` custom Header bar (excluding interactive timer pill and Settings button) |
| **Outer Content Padding** | `16px` horizontal, `12px` vertical |
| **Scrollbars** | Custom `6px`-wide slim trackless scrollbar, `bg_elevated` thumb (`3px` radius), appears on hover/scroll |

### System Tray (`QSystemTrayIcon`)
- **Icon:** `16 × 16` / `32 × 32` crisp vector SVG of the geometric cat-ear/whisker monogram (`1.5px` stroke, adapts foreground to Windows light/dark taskbar).
- **Active Timer Badge:** When `>= 1` **Task Timer** is running, render a `4px` solid `accent_primary` dot in the bottom-right corner of the tray icon.
- **Context Menu:**
  - `Show / Hide nyatodo` (bold default action, shows shortcut e.g. `Ctrl+Alt+Space`)
  - Disabled status item when timers run: `Running: 1 Task (00:14:22)`
  - Separator
  - `Settings…`
  - `Quit`

---

## 3. Typography & Tabular Numerals

| Role | Font Family | Size | Weight | Line Height | Notes |
|---|---|---|---|---|---|
| **Brand Wordmark** | `Segoe UI Variable Text`, `Segoe UI` | `13px` | `600` | `18px` | Tight `-0.01em` tracking |
| **Section / Day Title** | `Segoe UI Variable Text`, `Segoe UI` | `13px` | `600` | `18px` | Clean hierarchy |
| **Hero Metric Value** | `Cascadia Mono`, `Consolas` | `22px` | `600` | `28px` | Tabular digits (`04:42:10`) |
| **Task Title** | `Segoe UI Variable Text`, `Segoe UI` | `13px` | `500` (collapsed) / `600` (expanded) | `18px` | `Qt.ElideRight` when collapsed |
| **Body / Notes / Inputs** | `Segoe UI Variable Text`, `Segoe UI` | `13px` | `400` | `19px` | Readable `Notes` measure |
| **Sub-step Label** | `Segoe UI Variable Text`, `Segoe UI` | `12.5px` | `400` | `17px` | Crisp alignment with `14px` check |
| **Live Timer / Duration** | `Cascadia Mono`, `Consolas` | `12px` | `500` | `16px` | Fixed-pitch / tabular digits |
| **Metadata / Pills / Tabs** | `Segoe UI Variable Text`, `Segoe UI` | `11.5px` | `500` | `15px` | Tab labels, `@Requester`, captions |
| **Keycaps & Counts** | `Cascadia Mono`, `Consolas` | `10.5px` | `500` | `14px` | Keycaps (`Enter`, `t`), `2/4` counts |

> **PySide6 Note:** Set `QFont.setStyleHint(QFont.Monospace)` and `QFont.setFixedPitch(True)` on all timer, count, and keycap `QFont` instances so `Cascadia Mono` / `Consolas` digits never jitter horizontally as seconds tick.

---

## 4. Complete Color Token Tables

All foreground tokens are verified to achieve `>= 4.5:1` WCAG AA contrast against `bg_window`, `bg_surface`, and `bg_selected`.

### Core Tokens

| Token | Dark Theme | Light Theme | Usage |
|---|---|---|---|
| `bg_window` | `#111317` | `#F8F9FB` | Main spotlight window canvas & modal surface |
| `bg_surface` | `#171A20` | `#F1F3F7` | **Quick Bar**, segmented tab track, expanded **Thinking Space**, hero summary panel, footer |
| `bg_elevated` | `#1E222A` | `#FFFFFF` | Active tab item, `@Requester` pill, keycap fill, quick-adjust chips, buttons |
| `bg_hover` | `#1A1E26` | `#EEF1F6` | Hovered **Task** row, hovered icon button |
| `bg_selected` | `#222733` | `#E7ECF5` | Keyboard-selected **Task** row |
| `border_subtle` | `#262B35` | `#DCE1EA` | `1px` outer frame, hairlines, input borders, keycap borders, dividers |
| `border_focus` | `#5E8BFF` | `#2054D6` | Active focus border (`1.5px`) on **Quick Bar**, inputs, checkboxes |
| `text_primary` | `#ECEFF4` | `#111827` | Primary **Task** titles, hero numbers, active timer text, notes |
| `text_secondary` | `#9CA5B4` | `#4B5565` | `@Requester` pill text, inactive tab labels, **Work Session** timestamps, captions |
| `text_muted` | `#858FA1` | `#5F6B7E` | Placeholders, footer hints, `Sub-step` counts, `Done` strikethrough text |
| `accent_primary` | `#5E8BFF` | `#2054D6` | Primary focus ring, active selection left bar, active timer pill dot, summary bars |
| `status_doing` | `#5E8BFF` | `#2054D6` | `Doing` status indicator & live running **Task Timer** readout |
| `status_waiting` | `#E5A93B` | `#9A5404` | `Waiting` status icon/badge & **Idle Check** banner cue |
| `status_done` | `#38C172` | `#137338` | `Done` checkmark icon & completed indicator |
| `danger` | `#F06464` | `#C62222` | `Trim` action in **Idle Check** banner, delete **Task** / **Work Session** hover action |

### Derived Semantic Tints (Zero Extra Hues)

| Derived Token | Dark Theme | Light Theme | Usage |
|---|---|---|---|
| `tint_accent` | `rgba(94, 139, 255, 0.14)` | `rgba(32, 84, 214, 0.10)` | Header running timer pill fill, active timer button fill |
| `tint_accent_border` | `rgba(94, 139, 255, 0.35)` | `rgba(32, 84, 214, 0.28)` | Header running timer pill `1px` border |
| `tint_waiting` | `rgba(229, 169, 59, 0.12)` | `rgba(154, 84, 4, 0.09)` | **Idle Check** banner background / `Waiting` status badge |
| `tint_waiting_border` | `rgba(229, 169, 59, 0.38)` | `rgba(154, 84, 4, 0.30)` | **Idle Check** banner `1px` border |
| `tint_danger` | `rgba(240, 100, 100, 0.12)` | `rgba(198, 34, 34, 0.08)` | `Trim` button hover / destructive confirmation fill |
| `scrim_modal` | `rgba(0, 0, 0, 0.55)` | `rgba(15, 23, 42, 0.28)` | Backdrop scrim behind **Settings** modal |

---

## 5. Surface-by-Surface Visual Hierarchy

```
┌──────────────────────────────────────────────────────────┐ 12px radius
│ [cat-mark] nyatodo          [● 00:14:22]  [gear]         │ Surface 1: Header (44px)
│ [ +  Add task... (@who)                   @Maya  Enter ] │ Surface 1: Quick Bar (38px)
│ (Optional: Idle Check Banner when idle gap detected)     │ Surface 5: Banner (non-modal)
│ [ 1 Active 6 | 2 Waiting 2 | 3 Summary ]                 │ Surface 2: Segmented Tabs (32px)
├──────────────────────────────────────────────────────────┤
│                                                          │
│  ● 00:14:22  API rate limit fix          @Maya    2/4    │ Surface 3: Task Row (Doing)
│  ┌────────────────────────────────────────────────────┐  │ Surface 3: Expanded
│  │ API rate limit fix            @Maya   [Stop Timer] │  │            Thinking Space
│  │ Notes: Check retry-after header & burst window...  │  │
│  │ Sub-steps (2/4)                                    │  │
│  │ [x] Reproduce 429 locally                          │  │
│  │ [ ] Add jittered backoff                           │  │
│  │ + Add sub-step...                                  │  │
│  │ Work Sessions · 00:44:22   [-10m] [+15m] [+30m] [+]│  │
│  │ 14:10 – now (active) · Timer   10:20 – 10:50 · 30m │  │
│  └────────────────────────────────────────────────────┘  │
│  ○  Draft Q4 migration notes             @Alex    0/3    │ Surface 3: Task Row (Todo)
│  ✓  Review PR #418                       @Sam            │ Surface 3: Task Row (Done)
│                                                          │
├──────────────────────────────────────────────────────────┤
│ Enter Add · ↓ Move · t Timer · Enter Expand · w Wait     │ Surface 5: Footer (28px, optional)
└──────────────────────────────────────────────────────────┘
```

### Surface 1: Header + Quick Bar

1. **Header (`44px` height, `16px` horizontal padding):**
   - **Left cluster (`8px` gap):**
     - `18 × 18` custom SVG / `QPainter` geometric monogram: minimalist pointed cat-ear silhouette + two clean horizontal whisker ticks on each side (`1.5px` stroke in `text_primary`, rounded linecaps).
     - `"nyatodo"` wordmark (`13px` `600`, `text_primary`).
   - **Right cluster (`8px` gap):**
     - **Running Task Timer Pill** (hidden when `0` timers are running; visible when `>= 1` timer runs):
       - Height `24px`, radius `999px`, padding `0 10px`, `tint_accent` background, `1px solid tint_accent_border`.
       - Inside (`6px` gap): `6px` solid `status_doing` circle + `Cascadia Mono` `11.5px` readout (`00:14:22` if 1 timer, `2 · 00:14:22` if multiple timers running). Clicking jumps to / focuses the active **Task**.
     - **Settings Button:** `28 × 28`, `6px` radius, subtle `16 × 16` outline gear icon (`1.5px` stroke `text_secondary`, `bg_hover` + `text_primary` on hover).
2. **Quick Bar (`38px` height, `8px` bottom margin, `8px` radius):**
   - Background `bg_surface`, border `1px solid border_subtle` (transitions to `1.5px solid border_focus` when focused).
   - **Left mode glyph (`16 × 16`, `12px` left margin):** `+` icon in `text_muted` (`Add` mode), switches cleanly to magnifying glass icon in `accent_primary` when input starts with `/`.
   - **Single-line `QLineEdit` (`13px`, `text_primary`):**
     - Placeholder (`text_muted`): `"Add task... (@who)  or  / to search"`
   - **Right inline indicators (`8px` right margin, `6px` gap):**
     - Live `@Requester` pill preview: appears automatically as user types `@name` (e.g., `@Maya` in `bg_elevated`, `1px solid border_subtle`, `4px` radius, `11px` `text_secondary`, `2px 6px` padding).
     - Subtle `Enter` keycap hint (`bg_elevated`, `10.5px` `text_muted`) shown only when text is non-empty in Add mode.

### Surface 2: Segmented View Tabs

- **Container (`32px` height, `12px` bottom margin):** Full-width segmented track (`bg_surface`, `6px` radius, `1px solid border_subtle`, `3px` internal padding, `2px` gap between segments).
- **Three equal-width peer segments (`26px` height, `4px` radius):**
  1. `1 Active` + tabular count badge (e.g., `6` — all non-`Done`, non-`Waiting` **Tasks**, plus recently completed today if pinned/visible, or `Todo` + `Doing`).
  2. `2 Waiting` + tabular count badge (e.g., `2`).
  3. `3 Summary` (opens **Daily Summary**).
- **Tab States:**
  - **Active segment:** `bg_elevated` fill, `1px solid border_subtle`, `text_primary` `500` label, `text_secondary` count.
  - **Inactive segment:** Transparent fill, `text_secondary` `500` label, `text_muted` count; `bg_hover` text shift on hover.
  - **Transition:** Instant cut (`0ms`); tabs never slide.

### Surface 3: Task Row & Expanded Thinking Space

#### Collapsed **Task** Row (`40px` min-height, `6px` radius, `0 10px` padding)
Arranged left-to-right on a single `8px`-spaced horizontal row:

1. **Task Status Button (`20 × 20` hit area, `14 × 14` icon):**
   - `Todo`: Hollow `14px` circle (`1.5px` stroke `text_muted`).
   - `Doing`: `14px` `status_doing` outer ring + solid `6px` inner dot (`status_doing`).
   - `Waiting`: `14px` rounded square/circle in `status_waiting` tint with crisp `||` pause bars (`1.5px` stroke `status_waiting`).
   - `Done`: `14px` filled `status_done` circle with crisp white checkmark (`1.5px` stroke).
2. **Live / Logged Timer Slot (conditional):**
   - When `Doing` (timer active): `Cascadia Mono` `12px` `500` in `status_doing` (e.g. `00:14:22`).
   - When paused with logged time `> 0`: `Cascadia Mono` `11.5px` in `text_muted` (e.g. `01:15`).
   - When `00:00` and paused: omitted to keep scanline ultra-clean.
3. **Task Title (`13px` `500`, `stretch=1`):**
   - `text_primary`, single line with `Qt.ElideRight`.
   - When `Done`: `text_muted` with strikethrough.
4. **Right Metadata Cluster (`6px` gap, right-aligned):**
   - `@Requester` pill (if set): `11px` `500` `text_secondary`, `bg_elevated`, `1px solid border_subtle`, `4px` radius, `2px 6px` padding (max-width `108px`, elided).
   - **Sub-step** counter (if `>= 1` **Sub-step** exists): `2/4` in `Cascadia Mono` `10.5px` `text_muted`.

- **Row Interactive States:**
  - **Hover:** `bg_hover` background.
  - **Keyboard Selected (`↓`/`↑`):** `bg_selected` background + `2px`-wide `accent_primary` vertical bar inset on left edge (`6px` tall margin top/bottom).
  - **Empty State:** Centered vertically in list area — subtle `20px` geometric check/whisker glyph in `text_muted` + `"No active tasks"` (`13px` `text_secondary`) + `"Press Ctrl+L or click above to add a task."` (`12px` `text_muted`).

#### Expanded **Thinking Space** (Accordion below selected **Task** Row)
- **Container:** `bg_surface`, `8px` radius, `1px solid border_subtle` (or `border_focus` hairline on left), `12px` inner padding, `4px 0 8px 0` outer vertical margin. Internal sections separated by `12px` gaps and subtle `1px solid border_subtle` hairlines.
- **Section A — Header & Primary Controls (`8px` gap):**
  - Editable **Task** Title (`QLineEdit`, transparent background, `13.5px` `600` `text_primary`, subtle bottom `border_focus` line on focus).
  - Second compact control row (`8px` gap):
    - Editable `@Requester` chip (`bg_elevated`, `1px solid border_subtle`, `4px` radius; clicking turns into inline `QLineEdit` `@name`, placeholder `+ @requester`).
    - **Task Status** selector pill (`Todo` / `Waiting` / `Done` cycle or mini-segmented toggle).
    - Spacer + **Task Timer** button (`26px` height, `6px` radius): `"Start Timer"` (`bg_elevated`, `1px solid border_subtle`, play triangle) or `"Stop 00:14:22"` (`tint_accent`, `1px solid tint_accent_border`, `status_doing` stop square + tabular clock).
- **Section B — Freeform Notes (`Thinking Space`):**
  - Header label `"Notes"` (`11px` `600` uppercase-muted or sentence-case `text_secondary`) + right-aligned `"Saved"` status micro-text (`10.5px` `text_muted`).
  - `QPlainTextEdit` (`min-height: 64px`, `max-height: 160px`, `bg_window` background, `1px solid border_subtle`, `6px` radius, `8px` padding, `13px` `text_primary`, placeholder `"Capture context, links, or rough thoughts..."`). Auto-saves on debounce (`400ms`) and blur.
- **Section C — Sub-steps:**
  - Header `"Sub-steps · 2/4"` (`11.5px` `600` `text_secondary`).
  - Vertical list (`4px` gap) of checkable **Sub-step** rows (`26px` height): `14 × 14` square checkbox (`4px` radius, `1.5px` border `border_subtle` -> filled `accent_primary` / `status_done` when checked) + inline-editable `12.5px` label + subtle `×` delete button visible only on row hover.
  - Bottom quick-add row: `"+ Add sub-step..."` (`26px` height, borderless `QLineEdit` in `12.5px`, `Enter` adds and stays focused for rapid multi-step entry).
- **Section D — Work Sessions:**
  - Header row: `"Work Sessions · 00:44:22"` (`11.5px` `600` `text_secondary` + `Cascadia Mono` total) on left; quick-adjust chips on right (`4px` gap):
    - `-10m`, `+15m`, `+30m`, `+ Manual` (`22px` height, `6px` radius, `bg_elevated`, `1px solid border_subtle`, `Cascadia Mono` `10.5px` `text_secondary`; clicking `+ Manual` reveals compact inline input `"e.g. 25m or 1:15"` + `Add`).
  - Compact chronological session list (`max 3–4` visible with internal scroll if longer, `22px` row height):
    - e.g. `14:10 – now (running)` · `Timer` (in `status_doing`)
    - e.g. `10:20 – 10:50` · `30m` · `Timer` (with hover `×` to remove mistaken entry)
    - e.g. `Manual adjustment` · `+15m` (`text_muted`)

### Surface 4: Daily Summary View

Displayed when Tab `3 Summary` is active (replaces the **Task List** below the segmented tabs; **Quick Bar** remains accessible at top so capture is always 1 shortcut away).

1. **Day Selector Row (`32px` height, `12px` bottom margin):**
   - Centered or space-between bar: `<` button (`28 × 28`, `6px` radius, `bg_surface`, `1px solid border_subtle`) + Day Label (`"Today · Thu, Nov 25"`, `13px` `600` `text_primary`) + `>` button (disabled when viewing Today).
2. **Hero Metric Pair (`bg_surface`, `8px` radius, `1px solid border_subtle`, `14px 16px` padding):**
   - Two equal columns separated by a `1px solid border_subtle` vertical hairline:
     - **Left — Wall-Clock Active:** Label `"Wall-Clock Active"` (`11.5px` `500` `text_secondary`) above `04:42:10` (`22px` `Cascadia Mono` `600` `text_primary`) above `"Time with >=1 timer running"` (`11px` `text_muted`).
     - **Right — Total Logged:** Label `"Total Logged"` (`11.5px` `500` `text_secondary`) above `05:18:40` (`22px` `Cascadia Mono` `600` `text_primary`) above `"Sum of Work Sessions"` (`11px` `text_muted`).
   - **Concurrent Overlap Explanation Strip** (rendered inside bottom of hero box separated by `1px` top hairline *only* when `Total Logged > Wall-Clock Active`):
     - `"Includes 00:36:30 of concurrent Task Timers across overlapping sessions."` (`11.5px` `text_secondary`, `Cascadia Mono` duration).
3. **Per-Task Breakdown List (`12px` top margin):**
   - Section Header: `"Tasks Worked & Completed"` (`11.5px` `600` `text_secondary`) + right-aligned task count (`"5 tasks"` in `Cascadia Mono` `11px` `text_muted`).
   - Breakdown rows (`36px` height, `6px` radius, `0 8px` padding, separated by `1px solid border_subtle` hairlines):
     - Status indicator (`14px` `status_done` checkmark if completed that day, or `10px` `accent_primary`/`text_muted` dot if worked-on and still open).
     - **Task** Title (`12.5px` `500` `text_primary`, elided) + optional `@Requester` pill (`11px`).
     - Proportional horizontal duration bar (`4px` height, `64px` max-width, `bg_surface` track, `accent_primary` fill scaled to day's longest task) + right-aligned `Cascadia Mono` `12px` duration (`01:45:00` or `Done` if completed with `0m` logged).
   - **Empty Day State:** `"No Work Sessions or completed Tasks for this day."` (`12.5px` `text_muted`, centered).

### Surface 5: Idle Check Banner, Settings Modal & Toggleable Shortcut Hints Footer

1. **Idle Check Banner (Non-Modal Top Strip):**
   - Positioned between **Quick Bar** and **Segmented View Tabs** when OS idle time exceeds `Idle Check Threshold` while a **Task Timer** is running. Never steals typing focus.
   - Styling: `bg_surface` blended with `tint_waiting`, `1px solid tint_waiting_border`, `8px` radius, `8px 12px` padding.
   - Left (`8px` gap): `14 × 14` `status_waiting` clock/pause icon + `"Idle for 18m on 'API rate limit fix'. Keep or trim?"` (`12px` `text_primary`).
   - Right (`6px` gap):
     - `Keep` button (`24px` height, `6px` radius, `bg_elevated`, `1px solid border_subtle`, `11.5px` `500` `text_primary`).
     - `Trim 18m` button (`24px` height, `6px` radius, `tint_danger`, `1px solid danger` subtle border, `11.5px` `500` `danger`).
2. **Settings Modal (`360px` width, centered over `scrim_modal`):**
   - Container: `bg_window` (Dark) / `bg_elevated` (Light), `10px` radius, `1px solid border_subtle`, `16px` padding, neutral elevation shadow.
   - Header: `"Settings"` (`14px` `600` `text_primary`) + `×` close button (`24 × 24`, `6px` radius).
   - Rows (`42px` height, `1px solid border_subtle` dividers):
     1. **Theme:** 2-option segmented control (`Dark` | `Light`) — switches QSS palette immediately.
     2. **Global Shortcut:** Interactive keycap button (`Ctrl+Alt+Space`, `Cascadia Mono` `11.5px`, `bg_surface`, `1px solid border_subtle`, `6px` radius; clicking enters `"Press shortcut..."` state with `border_focus`).
     3. **Show Shortcut Hints:** Toggle switch (`34 × 18`, `999px` pill; `accent_primary` when On, `bg_surface` + `border_subtle` when Off).
     4. **Idle Check Threshold:** Compact dropdown/stepper (`Off`, `5m`, `10m`, `15m`, `30m`).
   - Footer: Right-aligned `Done` button (`28px` height, `6px` radius, `accent_primary` fill with `#FFFFFF` `500` text).
3. **Toggleable Shortcut Hints Footer (`28px` height):**
   - Collapses completely (`0px` height, `visible = False`) when `Show Shortcut Hints` is Off.
   - Styling: `bg_surface` (or `bg_window` with `1px solid border_subtle` top hairline), `0 16px` padding, horizontal flow with `10px` item gaps.
   - Each hint pairs a keycap (`Cascadia Mono` `10px`, `bg_elevated`, `1px solid border_subtle`, `4px` radius, `1px 5px` padding, `text_secondary`) + `11px` `text_muted` verb:
     - **Quick Bar focused:** `Enter` Add · `/` Search · `↓` List · `Esc` Hide
     - **Task List focused (Active / Waiting):** `↓↑` Move · `t` Timer · `Enter` Expand · `w` Waiting · `d` Done · `Esc` Hide
     - **Thinking Space editing:** `Esc` Collapse · `Ctrl+Enter` Done
     - **Daily Summary:** `←→` Day · `1–3` Tabs · `Esc` Hide

---

## 6. Motion, Focus & Keyboard Ergonomics (PySide6)

- **Frequency-gated motion:**
  - `0ms` instant: tab switches, `↓`/`↑` row selection, typing, `@Requester` pill parsing, timer digit updates.
  - `160ms` `QEasingCurve.OutCubic`: **Thinking Space** expand/collapse (`QPropertyAnimation`), **Idle Check** banner reveal/dismiss.
  - `100ms`: button hover/press tint; **Settings** modal fade (`opacity 0.0 -> 1.0`).
- **Focus order:** `Quick Bar` -> `Segmented Tabs` -> `Task List` -> (if expanded) `Thinking Space` controls (`Title` -> `@Requester` -> `Timer` -> `Notes` -> `Sub-steps` -> `Work Sessions`).
- **Global Spotlight Behavior:** Pressing global hotkey (`Ctrl+Alt+Space` default) toggles window visibility, centers/restores last position on current active monitor, and focuses the **Quick Bar** immediately (`selectAll()` or cursor at end). Pressing `Esc` collapses an open **Thinking Space** or modal first; pressing `Esc` from root hides the spotlight window back to the system tray.

---

## 7. Image-Generation Target Prompts

Use these straight-on orthographic prompts with an image generator to produce 1:1 visual targets before writing QSS/PySide6 layout code.

### Prompt 1 — Dark Mode Target (`540 × 660`, Active View + Expanded Thinking Space)

> Straight-on orthographic flat desktop UI screenshot of a compact vertical floating spotlight window named "nyatodo", exact portrait aspect ratio 9:11 (540x660 pixels), centered on a neutral plain dark grey studio backdrop so the crisp 12px rounded window corners and subtle 1px dark slate border (#262B35) with soft neutral drop shadow are clearly visible. No tilted device mockup, no browser chrome, no gradients, no neon glow, no anime artwork. Deep cool charcoal background (#111317), cool slate typography in Segoe UI and tabular Cascadia Mono. Top 44px header shows a tiny minimalist 1.5px geometric cat-ear and whisker line icon next to lowercase bold "nyatodo" (#ECEFF4), and on the right a flat pill badge (#1E2A44 fill, #5E8BFF dot) reading "00:14:22" beside a minimal outline gear icon. Below it, a 38px inset dark surface (#171A20) Quick Bar with 1px border (#262B35), left "+" icon, text "Add task... (@who)  or  / to search" (#858FA1). Below that, a compact segmented tab control (#171A20 track) with active elevated tab "1 Active  6" (#222733), "2 Waiting  2", and "3 Summary". Below tabs, a clean Task List: first row is selected (#222733 with thin 2px left #5E8BFF bar) showing a blue active dot (#5E8BFF), tabular blue timer "00:14:22", title "API rate limit fix", right-aligned "@Maya" chip and "2/4". Directly nested beneath that row is an expanded inset Thinking Space (#171A20, 8px radius, 1px #262B35 border) containing: editable title "API rate limit fix", "@Maya" pill, "Stop Timer" button, a clean Notes box reading "Check retry-after header and burst window config.", checkable Sub-steps list ("2/4") with two checked blue boxes ("Reproduce 429 locally", "Capture response headers") and two unchecked boxes ("Add jittered backoff", "Verify staging logs") plus "+ Add sub-step...", and a Work Sessions section reading "Work Sessions · 00:44:22" with crisp flat chips "-10m", "+15m", "+30m", "+ Manual" and two compact session lines ("14:10 – now · Timer", "10:20 – 10:50 · 30m"). Below the expanded block, two collapsed single-line Task rows ("Draft Q4 migration notes" with "@Alex" and "0/3"; "Review PR #418" with green check #38C172 and muted strikethrough). Slim 28px footer bar at bottom with tiny monospace keycaps: "Enter Add · ↓ Move · t Timer · Enter Expand · w Waiting · d Done · Esc Hide". Ultra-crisp UI typography, razor-sharp 1px hairlines, flat modern Linear/Things desktop aesthetic.

### Prompt 2 — Light Mode Target (`540 × 660`, Daily Summary View + Quick Bar)

> Straight-on orthographic flat desktop UI screenshot of a compact vertical floating spotlight window named "nyatodo", exact portrait aspect ratio 9:11 (540x660 pixels), centered on a soft neutral light grey studio backdrop so the crisp 12px rounded window corners, subtle 1px cool slate border (#DCE1EA), and soft neutral drop shadow are clearly visible. No tilted device mockup, no browser chrome, no gradients, no neon glow, no decorative cards. Crisp cool alabaster window background (#F8F9FB), dark slate ink typography (#111827) in Segoe UI and tabular Cascadia Mono. Top 44px header shows a tiny minimalist 1.5px geometric cat-ear and whisker line icon next to lowercase bold "nyatodo", and on the right a subtle running timer pill (light cobalt tint, blue dot #2054D6, "00:14:22") beside a minimal outline gear icon. Below it, a 38px inset Quick Bar (#F1F3F7, 1px #DCE1EA border) reading "Add task... (@who)  or  / to search". Below that, a segmented tab bar (#F1F3F7 track) with "1 Active  6", "2 Waiting  2", and active white elevated tab "3 Summary" (#FFFFFF, 1px #DCE1EA border). Below tabs, a clean day selector row: "<" button, "Today · Thu, Nov 25", and disabled ">" button. Below it, a unified light grey-slate hero panel (#F1F3F7, 8px radius, 1px #DCE1EA border) split by a single 1px vertical hairline into two columns: left column reads "Wall-Clock Active", large crisp tabular "04:42:10", and caption "Time with >=1 timer running"; right column reads "Total Logged", large crisp tabular "05:18:40", and caption "Sum of Work Sessions"; across the bottom of the same panel below a 1px horizontal hairline reads "Includes 00:36:30 of concurrent Task Timers across overlapping sessions.". Below the hero panel, section label "Tasks Worked & Completed" and 5 clean single-line breakdown rows separated by 1px hairlines: each row shows a green checkmark (#137338) or blue active dot (#2054D6), Task title ("API rate limit fix", "Fix auth token refresh", "Quarterly roadmap review", "Update onboarding copy", "Deploy staging hotfix"), subtle "@Maya" / "@Alex" pill, a thin 4px horizontal cobalt progress bar (#2054D6), and right-aligned tabular duration ("01:45:00", "01:22:10", "00:58:00", "00:41:30", "00:32:00"). Slim 28px footer bar at bottom with tiny monospace keycaps: "←→ Day · 1–3 Tabs · Esc Hide". Ultra-crisp Swiss operational desktop UI, sharp 1px lines, zero clutter.
