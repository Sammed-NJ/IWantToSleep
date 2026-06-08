# I Want To Sleep (iwts) ⏰

A premium, highly interactive, and robust Python CLI alarm clock. 

This application was engineered during a 30-minute coding exercise to showcase senior-level architectural design, decoupled system communication, problem definition, and iterative validation.

---

## 🌟 Key Features

- **Decoupled Daemon/Client Architecture:** Start the clock daemon in one terminal pane and manage alarms (add, list, delete, disable) from any other pane or script.
- **Live Terminal Dashboard:** A beautiful interactive panel displaying a live synchronized clock, structured tables of active alarms (with real-time countdowns for snoozes), a flashing alert banner when alarms trigger, and running logs.
- **Robust Scheduling Options:** Supports relative timers (e.g. `+10s`, `+1h30m`), 12h/24h absolute times (`07:30`, `2:30 PM`), and recurring schedules (`daily`, `weekdays`, `weekends`, or specific days like `mon,wed,fri`).
- **Retro Tone Engine:** Custom-threaded melodies (Classic beep, Siren wail, Pulsing frequency, System alarms, and Retro chiptunes) utilizing native Windows APIs with standard terminal fallbacks.
- **Advanced State Synchrony (IPC):** Control ringing alarms remotely with immediate `snooze` and `dismiss` commands.

---

## 🏗️ Engineering & Design Decisions

### 1. The Daemon-Client Architecture
Instead of building a simple foreground script that locks the terminal, `iwts` implements a decoupled pattern:
- **Daemon (`python iwts.py daemon`)**: Runs a lightweight background thread evaluating schedules and controlling the audio engine. The main thread runs a high-frequency UI cycle updating the CLI dashboard.
- **Client (`python iwts.py <cmd>`)**: A stateless wrapper executing instant CLI actions (adding, deleting, toggling alarms, or dispatching dismiss signals).

### 2. State-File IPC (No Database)
To fulfill the *"no database"* and *"CLI only"* constraint while retaining decoupled execution, we designed a shared-state protocol via a local JSON file (`.iwts_state.json`). 
- **Heartbeat Check:** The daemon writes its PID and a heartbeat timestamp (`daemon_last_seen`) to the state file every second. The client checks this before adding alarms, printing clear user warnings if the daemon is offline.
- **Ringing Handshake:** When an alarm triggers, the daemon marks its ID under `active_ringing_id`. When a user runs `python iwts.py dismiss`, the client appends the request to a queue in the state file. The daemon reads, terminates audio playback, reschedules the alarm, and clears the queue.

### 3. Scheduling Edge Cases
- **Overlapping Alarms:** The scheduler computes the next trigger times immediately upon a dismissal or snooze. If multiple alarms are scheduled for the exact same minute, they will trigger sequentially (as soon as the active one is dismissed).
- **One-time Alarms:** Relative alarms (`+10s`, `+5m`) and absolute alarms without recurrence are auto-disabled after firing to prevent infinite loops.

### 4. Windows Compatibility & Robustness
During local testing, standard Unicode emojis caused `UnicodeEncodeError` crashes on default Windows PowerShell/CMD environments (which use CP1252 encoding). Emojis were replaced with standard ASCII indicators to ensure 100% crash-free out-of-the-box performance on Windows machines.

---

## ⚙️ Setup & Installation

### Prerequisites
- Python 3.10+
- Windows OS (prioritized for native `winsound` support, safe terminal buzzer fallbacks are executed on macOS/Linux).

### Install Dependencies
```bash
pip install -r requirements.txt
```

---

## 🚀 Usage Guide

### Step 1: Spin up the Daemon Dashboard
Run this in a dedicated terminal pane:
```bash
python iwts.py daemon
```

### Step 2: Manage Alarms (from another pane)

#### Add Alarms
- Relative timer:
  ```bash
  python iwts.py add +10s --label "Quick stretch"
  ```
- Specific 12-hour/24-hour time with custom melody:
  ```bash
  python iwts.py add "2:30 PM" --label "Standup Meeting" --sound retro
  ```
- Recurring weekday alarm:
  ```bash
  python iwts.py add 07:30 --label "Wake Up!" --repeat weekdays
  ```

#### List Alarms
```bash
python iwts.py list
# or using the quick alias
python iwts.py ls
```

#### Disable, Enable, or Delete Alarms
```bash
python iwts.py disable <alarm_id>
python iwts.py enable <alarm_id>
python iwts.py delete <alarm_id>   # or: python iwts.py rm <alarm_id>
python iwts.py clear               # Deletes all alarms at once
```

#### Dismiss or Snooze a Ringing Alarm
When an alarm is ringing, run:
```bash
python iwts.py dismiss     # Silences the alarm immediately
python iwts.py snooze      # Delays the alarm by default duration (or custom: --mins 10)
```

#### Application Settings Configuration
To view or customize application defaults:
```bash
# View current default settings
python iwts.py config

# Update defaults (e.g. 10m snooze, 60s ring timeout)
python iwts.py config --snooze 10 --timeout 60
```

---

## 🤖 AI Collaboration Process & Review

1. **Requirements Refinement:** Defined constraints (CLI, Python standard libraries, Windows native audio) and mapped out the client-daemon state synchronization model.
2. **Step-by-Step Logging:** Tracked implementation progress sequentially in `implementation_steps.md`.
3. **Validation & Iteration:** Detected Unicode crashes on command console execution and corrected formatting back to safe standard outputs.
