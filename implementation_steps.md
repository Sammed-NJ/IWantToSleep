# IWantToSleep Implementation Steps

This document records the step-by-step implementation of the `iwts` CLI alarm clock.

## Step 1: Initialization and Environment Setup
- Verified Python version: `3.12.10`.
- Created `requirements.txt` containing `rich` and `colorama`.
- Successfully installed dependencies via `pip`.
- Set up project files structure.

---

## Step 2: Implement Sound Player (`sound_player.py`)
- Created a background audio runner using Python's `threading` and `winsound` (on Windows).
- Supported 5 different retro beep melodies/audio patterns:
  - `classic`: Pulsing high beeps (dual-pulse).
  - `pulsing`: Sweep of frequencies from low to high.
  - `retro`: A 6-tone arcade arpeggio.
  - `siren`: Alternating sweeping pitch.
  - `system`: System exclamation WAV alerts.
- Configured thread-safe control so the client can stop playback immediately.
- Added a console beep fallback for non-Windows platforms.

---

## Step 3: Implement Alarm Manager (`alarm_manager.py`)
- Configured JSON-based state persistence (`.iwts_state.json`) inside the workspace directory.
- Created robust time string parsers:
  - Relative times: e.g. `+10s`, `5m`, `+1h30m`.
  - Absolute 24-hour format: `HH:MM` or `HH:MM:SS`.
  - Absolute 12-hour format: `HH:MM AM/PM` or `H:MM PM`.
- Created a recurring day/frequency parser supporting `daily`, `weekdays`, `weekends`, and custom list of days (e.g. `mon,wed,fri`).
- Implemented next-execution scheduling algorithm:
  - Relative alarms fire once and disable themselves.
  - Absolute alarms determine the next matching day/time and reschedule correctly upon firing or when enabled.
- Added API functions for CRUD operations: `add_alarm`, `delete_alarm`, and `set_alarm_enabled`.

---

## Step 4: Implement Daemon Runner (`daemon_runner.py`)
- Created a background checking worker thread running every 1 second:
  - Updates a JSON heartbeat timestamp (`daemon_last_seen`) and PID to declare active daemon status.
  - Automatically identifies and handles overlapping ring scenarios.
  - Controls the `SoundPlayer` thread safely.
  - Calculates relative snoozes and schedules recurrence rescheduling when dismissed.
- Implemented a complete state-based IPC handler for:
  - Ringing/Dismiss requests from CLI command clients.
  - Snooze actions targeting specific or active alarms.
  - Automatic ring timeouts (2-minute window) to prevent CPU or speaker fatigue.
- Rendered a terminal dashboard UI using `rich`'s `Live` display, showcasing:
  - Title and active daemon PID details.
  - Live local clock synchronized to standard dates.
  - A formatted active alarms table, complete with state values (ON/OFF/SNOOZE countdown).
  - A flashing red active alarm alert display.
  - A real-time running log feed tracking daemon events.

---

## Step 5: Implement CLI Entry Point (`iwts.py`)
- Created a robust CLI parser with command subparsers:
  - `daemon`: Initiates the live background scheduler dashboard.
  - `add <time>`: Schedules new alarms, supporting label (`-l`/`--label`), sound melody (`-s`/`--sound`), and recurrence pattern (`-r`/`--repeat`).
  - `list` (and alias `ls`): Displays static, colored tables of all alarms.
  - `delete` (and alias `rm`): Removes alarms by ID.
  - `enable` / `disable`: Toggles alarm states.
  - `dismiss`: Stops a ringing alarm. If ID is omitted, it auto-targets the currently ringing alarm.
  - `snooze`: Pauses ringing alarms for custom durations (`-m`/`--mins`, default 5).
  - `status`: Runs diagnostics and displays whether the daemon is online.
- Integrated automated alias preprocessing (re-mapping `ls` -> `list`, `rm` -> `delete` dynamically in `sys.argv`).
- Wrapped output formatting in elegant console blocks utilizing `rich.panel.Panel` and custom colors.

---

## Step 6: Testing, Code Refining, and Verification
- Executed diagnostics (`python iwts.py status`) and observed a `UnicodeEncodeError` due to terminal emoji rendering (`⏰`, `🚨`).
- Modified `iwts.py` and `daemon_runner.py` to replace emojis with standard ASCII representation, ensuring full compatibility on Windows CMD and PowerShell (which default to CP1252 encoding).
- Verified alarm creation:
  - Added a relative 10-second alarm (`+10s`).
  - Added a relative 1-minute alarm with a retro melody (`+1m --sound retro`).
  - Added a recurring weekdays alarm at 08:30 AM (`08:30 --repeat weekdays`).
- Verified list command output formatting and correct display of next trigger timestamps.
- Checked alarm removal command (`python iwts.py rm 1`) to ensure ID adjustment and state clearing.
- Verified alarm toggling (`python iwts.py disable 2`) to ensure correctness.
- Added a `clear` command to safely wipe all configured alarms at once. Implemented `clear_all_alarms` in `alarm_manager.py` and registered the subparser command handler in `iwts.py`.
- Added a `config` command to view and update application settings. Custom default snooze times and alarm timeouts are saved to state. The snooze client reads these settings when executing, and the daemon uses the configured timeout to stop ringing.
- App completed with all features operational.





