# Native Python Desktop App Over Rust Binary or Local Web UI

- Status: accepted

Because the target work environment likely restricts executing custom compiled `.exe` binaries (ruling out a Rust build) and a browser-hosted web UI gets lost amid constant work browser usage, `nyatodo` is built as a standalone Python desktop application with a system tray icon and a global-shortcut floating popup.

## Considered Options

- **Rust native binary / TUI**: Ideal memory footprint and keyboard speed, but compiling custom `.exe` binaries risks being blocked by corporate endpoint controls.
- **Local Web UI in browser**: Easy visual polish, but blends into heavy daily browser usage instead of behaving as an instant distraction-free popup.
- **Python desktop application**: Executes under an already-permitted Python runtime while providing native tray presence and global-hotkey activation, trading some RAM overhead compared to Rust for reliable execution at work.
