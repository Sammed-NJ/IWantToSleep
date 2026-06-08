import os
import json
import re
from datetime import datetime, timedelta

STATE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".iwts_state.json")

# Day parsing mappings
DAY_MAP = {
    "mon": 0, "monday": 0,
    "tue": 1, "tuesday": 1,
    "wed": 2, "wednesday": 2,
    "thu": 3, "thursday": 3,
    "fri": 4, "friday": 4,
    "sat": 5, "saturday": 5,
    "sun": 6, "sunday": 6
}

DEFAULT_SETTINGS = {
    "default_snooze_mins": 5,
    "alarm_timeout_secs": 120
}

def load_state():
    """Load the state from the JSON file, or return a default state."""
    default_state = {
        "alarms": [],
        "daemon_pid": None,
        "daemon_last_seen": None,
        "dismiss_requests": [],
        "snooze_requests": {},
        "settings": DEFAULT_SETTINGS.copy()
    }
    if not os.path.exists(STATE_FILE):
        return default_state
    try:
        with open(STATE_FILE, "r") as f:
            state = json.load(f)
            # Ensure all required keys exist
            for key in default_state:
                if key not in state:
                    state[key] = default_state[key]
            # Ensure nested settings keys exist
            if not isinstance(state["settings"], dict):
                state["settings"] = DEFAULT_SETTINGS.copy()
            else:
                for skey in DEFAULT_SETTINGS:
                    if skey not in state["settings"]:
                        state["settings"][skey] = DEFAULT_SETTINGS[skey]
            return state
    except (json.JSONDecodeError, IOError):
        # If file is corrupted or unreadable, return default
        return default_state

def save_state(state):
    """Save state to the JSON file safely."""
    try:
        # Write to a temp file first then rename to prevent corruption
        temp_file = STATE_FILE + ".tmp"
        with open(temp_file, "w") as f:
            json.dump(state, f, indent=2)
        if os.path.exists(STATE_FILE):
            os.remove(STATE_FILE)
        os.rename(temp_file, STATE_FILE)
    except IOError as e:
        print(f"Error saving state: {e}")

def parse_relative_time(time_str):
    """
    Parse relative time like +10s, 10m, +2h30m, 1h, +50s.
    Returns a timedelta object or None if not relative.
    """
    # Pattern: optional + sign, then hours/minutes/seconds
    pattern = r"^(\+)?(?:(\d+)h)?(?:(\d+)m)?(?:(\d+)s)?$"
    match = re.match(pattern, time_str.strip().lower())
    if not match:
        # Try if it's just raw digits, default to minutes
        if time_str.isdigit():
            return timedelta(minutes=int(time_str))
        return None
    
    # If it's just a '+' sign with nothing else, it's invalid
    groups = match.groups()
    if not any(groups[1:]):
        return None
        
    hours = int(groups[1]) if groups[1] else 0
    minutes = int(groups[2]) if groups[2] else 0
    seconds = int(groups[3]) if groups[3] else 0
    
    return timedelta(hours=hours, minutes=minutes, seconds=seconds)

def parse_absolute_time(time_str):
    """
    Parse absolute time in 24h (14:30) or 12h (2:30 PM) format.
    Returns (hour, minute) or raises ValueError.
    """
    cleaned = time_str.strip().upper()
    
    # Try 24h format HH:MM or HH:MM:SS
    match_24 = re.match(r"^(\d{1,2}):(\d{2})(?::(\d{2}))?$", cleaned)
    if match_24:
        h, m = int(match_24.group(1)), int(match_24.group(2))
        if 0 <= h < 24 and 0 <= m < 60:
            return h, m
            
    # Try 12h format H:MM AM/PM or H:MM:SS AM/PM
    match_12 = re.match(r"^(\d{1,2}):(\d{2})(?::(\d{2}))?\s*(AM|PM)$", cleaned)
    if match_12:
        h, m = int(match_12.group(1)), int(match_12.group(2))
        ampm = match_12.group(4)
        if 1 <= h <= 12 and 0 <= m < 60:
            if ampm == "PM" and h < 12:
                h += 12
            elif ampm == "AM" and h == 12:
                h = 0
            return h, m
            
    raise ValueError(f"Invalid time format: '{time_str}'. Use 14:30, 2:30 PM, or relative like +10m.")

def parse_repeat_days(repeat_str):
    """
    Parse repeat days from comma-separated string.
    Returns a list of normalized day names or preset categories.
    E.g. "mon,wed,fri" -> ["mon", "wed", "fri"]
    "weekdays" -> ["weekdays"]
    """
    if not repeat_str:
        return []
    
    cleaned = repeat_str.strip().lower()
    if cleaned in ["daily", "weekdays", "weekends"]:
        return [cleaned]
        
    parts = [p.strip() for p in cleaned.split(",")]
    resolved = []
    for part in parts:
        for day in DAY_MAP:
            if part == day or part == day[:3]:
                resolved.append(day[:3])
                break
        else:
            raise ValueError(f"Unknown day or repeat code: '{part}'")
            
    return list(sorted(set(resolved), key=lambda x: DAY_MAP[x]))

def calculate_next_trigger(hour, minute, repeat_days, from_dt=None):
    """
    Calculate the next datetime the alarm should trigger based on repeat settings.
    """
    if from_dt is None:
        from_dt = datetime.now()
        
    if not repeat_days:
        # One-time alarm
        target = from_dt.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if target <= from_dt:
            target += timedelta(days=1)
        return target
        
    # Resolve repeat days into integer weekdays (0=Mon, ..., 6=Sun)
    target_weekdays = set()
    for day in repeat_days:
        if day == "daily":
            target_weekdays.update(range(7))
        elif day == "weekdays":
            target_weekdays.update(range(5))
        elif day == "weekends":
            target_weekdays.update([5, 6])
        elif day in DAY_MAP:
            target_weekdays.add(DAY_MAP[day])
            
    # Find next matching day in the next 7 days
    for offset in range(8):
        candidate_date = from_dt + timedelta(days=offset)
        if candidate_date.weekday() in target_weekdays:
            candidate = candidate_date.replace(hour=hour, minute=minute, second=0, microsecond=0)
            if candidate > from_dt:
                return candidate
                
    # Fallback to tomorrow if nothing found (should not happen if repeat_days is valid)
    target = from_dt.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if target <= from_dt:
        target += timedelta(days=1)
    return target

def add_alarm(time_str, label="", sound="classic", repeat_str=""):
    """Parse inputs and add a new alarm to the state file."""
    state = load_state()
    now = datetime.now()
    
    # 1. Parse time
    delta = parse_relative_time(time_str)
    if delta is not None:
        # Relative alarm (always one-time)
        next_trigger = now + delta
        # Set next_trigger's microseconds to 0 for cleaner comparisons
        next_trigger = next_trigger.replace(microsecond=0)
        hour, minute = next_trigger.hour, next_trigger.minute
        repeat_days = []
        is_relative = True
    else:
        # Absolute alarm
        hour, minute = parse_absolute_time(time_str)
        repeat_days = parse_repeat_days(repeat_str)
        next_trigger = calculate_next_trigger(hour, minute, repeat_days, now)
        is_relative = False
        
    # 2. Build alarm object
    alarm_id = 1
    if state["alarms"]:
        alarm_id = max(a["id"] for a in state["alarms"]) + 1
        
    new_alarm = {
        "id": alarm_id,
        "time": time_str,
        "hour": hour,
        "minute": minute,
        "label": label or f"Alarm #{alarm_id}",
        "sound": sound,
        "repeat": repeat_days,
        "is_relative": is_relative,
        "enabled": True,
        "snoozed_until": None,
        "next_trigger": next_trigger.isoformat(),
        "last_triggered": None
    }
    
    state["alarms"].append(new_alarm)
    save_state(state)
    return new_alarm

def delete_alarm(alarm_id):
    """Delete alarm by ID."""
    state = load_state()
    original_len = len(state["alarms"])
    state["alarms"] = [a for a in state["alarms"] if a["id"] != alarm_id]
    
    # Remove any pending snooze/dismiss requests for this alarm
    if str(alarm_id) in state["snooze_requests"]:
        del state["snooze_requests"][str(alarm_id)]
    state["dismiss_requests"] = [rid for rid in state["dismiss_requests"] if rid != alarm_id]
    
    save_state(state)
    return len(state["alarms"]) < original_len

def set_alarm_enabled(alarm_id, enabled):
    """Enable or disable an alarm."""
    state = load_state()
    found = False
    for a in state["alarms"]:
        if a["id"] == alarm_id:
            a["enabled"] = enabled
            a["snoozed_until"] = None # Clear snooze
            if enabled:
                # Recalculate next trigger time from now
                if a["is_relative"]:
                    # Relative alarm cannot easily be re-enabled relative to original add time,
                    # so we interpret it relative to enabling time.
                    delta = parse_relative_time(a["time"])
                    if delta:
                        a["next_trigger"] = (datetime.now() + delta).replace(microsecond=0).isoformat()
                else:
                    a["next_trigger"] = calculate_next_trigger(a["hour"], a["minute"], a["repeat"]).isoformat()
            found = True
            break
    if found:
        save_state(state)
    return found

def clear_all_alarms():
    """Delete all configured alarms from the state file."""
    state = load_state()
    state["alarms"] = []
    state["dismiss_requests"] = []
    state["snooze_requests"] = {}
    state["active_ringing_id"] = None
    save_state(state)
    return True

def update_settings(snooze_mins=None, timeout_secs=None):
    """Update configured default values."""
    state = load_state()
    if snooze_mins is not None:
        state["settings"]["default_snooze_mins"] = snooze_mins
    if timeout_secs is not None:
        state["settings"]["alarm_timeout_secs"] = timeout_secs
    save_state(state)
    return state["settings"]
