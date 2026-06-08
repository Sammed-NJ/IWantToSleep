import os
import time
import sys
import threading
from datetime import datetime, timedelta
from rich.live import Live
from rich.layout import Layout
from rich.panel import Panel
from rich.table import Table
from rich.console import Console
from rich.text import Text
from rich.align import Align

import alarm_manager
from sound_player import SoundPlayer

console = Console()

class DaemonRunner:
    def __init__(self):
        self.player = SoundPlayer()
        self.ringing_alarm = None
        self.ringing_start_time = None
        self.logs = []
        self.is_running = True
        self.lock = threading.Lock()

    def log(self, message):
        """Add log entry with timestamp."""
        timestamp = datetime.now().strftime("%H:%M:%S")
        with self.lock:
            self.logs.append(f"[{timestamp}] {message}")
            if len(self.logs) > 8:
                self.logs.pop(0)

    def is_process_running(self, pid):
        """Check if process with PID exists."""
        if pid is None:
            return False
        try:
            if sys.platform.startswith("win"):
                # Windows process check using tasklist/psutil isn't strictly needed
                # if we trust the heartbeat, but we can do a simple check
                import ctypes
                PROCESS_QUERY_INFORMATION = 0x0400
                PROCESS_VM_READ = 0x0010
                handle = ctypes.windll.kernel32.OpenProcess(
                    PROCESS_QUERY_INFORMATION | PROCESS_VM_READ, False, pid
                )
                if handle:
                    ctypes.windll.kernel32.CloseHandle(handle)
                    return True
                return False
            else:
                os.kill(pid, 0)
                return True
        except Exception:
            return False

    def is_daemon_running(self):
        """Check if another daemon is already running using heartbeat and PID."""
        state = alarm_manager.load_state()
        pid = state.get("daemon_pid")
        last_seen_str = state.get("daemon_last_seen")
        if pid is None or last_seen_str is None:
            return False
            
        try:
            last_seen = datetime.fromisoformat(last_seen_str)
            time_diff = (datetime.now() - last_seen).total_seconds()
            # If last heartbeat was < 5s ago and process is running, daemon is active
            if time_diff < 5 and self.is_process_running(pid):
                return True
        except Exception:
            pass
        return False

    def update_heartbeat(self):
        """Write current PID and time to show daemon is alive."""
        state = alarm_manager.load_state()
        state["daemon_pid"] = os.getpid()
        state["daemon_last_seen"] = datetime.now().isoformat()
        alarm_manager.save_state(state)

    def check_alarms_worker(self):
        """Background worker that evaluates alarm conditions and controls sound player."""
        self.log("Background alarm checker started.")
        while self.is_running:
            try:
                # 1. Update heartbeat
                self.update_heartbeat()
                
                # 2. Load latest state
                state = alarm_manager.load_state()
                now = datetime.now()
                
                # 3. Handle active ringing alarm state machine
                if self.ringing_alarm:
                    alarm_id = self.ringing_alarm["id"]
                    alarm_id_str = str(alarm_id)
                    
                    # Check for dismiss request
                    dismissed = alarm_id in state.get("dismiss_requests", [])
                    
                    # Check for snooze request
                    snoozed = alarm_id_str in state.get("snooze_requests", {})
                    
                    # Check for timeout (based on configured alarm_timeout_secs)
                    timeout_limit = state.get("settings", {}).get("alarm_timeout_secs", 120)
                    timeout = (now - self.ringing_start_time).total_seconds() > timeout_limit
                    
                    if dismissed or timeout:
                        reason = "timeout" if timeout else "dismissed"
                        self.log(f"Alarm {alarm_id} ('{self.ringing_alarm['label']}') {reason}.")
                        self.player.stop()
                        
                        # Remove from dismiss list
                        if dismissed:
                            state["dismiss_requests"] = [rid for rid in state["dismiss_requests"] if rid != alarm_id]
                            
                        # Reschedule or disable the alarm
                        for a in state["alarms"]:
                            if a["id"] == alarm_id:
                                if a["is_relative"] or not a["repeat"]:
                                    a["enabled"] = False
                                    a["next_trigger"] = None
                                    self.log(f"Alarm {alarm_id} (one-time) disabled.")
                                else:
                                    # Recalculate next trigger time for recurring alarm
                                    next_t = alarm_manager.calculate_next_trigger(a["hour"], a["minute"], a["repeat"], now)
                                    a["next_trigger"] = next_t.isoformat()
                                    self.log(f"Alarm {alarm_id} rescheduled to {next_t.strftime('%Y-%m-%d %H:%M')}.")
                                a["snoozed_until"] = None
                                break
                                
                        self.ringing_alarm = None
                        self.ringing_start_time = None
                        state["active_ringing_id"] = None
                        alarm_manager.save_state(state)
                        
                    elif snoozed:
                        snooze_mins = state["snooze_requests"][alarm_id_str]
                        snooze_until = now + timedelta(minutes=snooze_mins)
                        self.log(f"Alarm {alarm_id} ('{self.ringing_alarm['label']}') snoozed for {snooze_mins}m.")
                        self.player.stop()
                        
                        # Apply snooze to state
                        for a in state["alarms"]:
                            if a["id"] == alarm_id:
                                a["snoozed_until"] = snooze_until.replace(microsecond=0).isoformat()
                                break
                                
                        # Clear snooze request
                        del state["snooze_requests"][alarm_id_str]
                        
                        self.ringing_alarm = None
                        self.ringing_start_time = None
                        state["active_ringing_id"] = None
                        alarm_manager.save_state(state)
                        
                else:
                    # Not currently ringing. Check if any alarm should fire.
                    for a in state["alarms"]:
                        if not a["enabled"]:
                            continue
                            
                        should_fire = False
                        
                        # Case A: Snoozed alarm
                        if a.get("snoozed_until"):
                            snoozed_dt = datetime.fromisoformat(a["snoozed_until"])
                            if now >= snoozed_dt:
                                should_fire = True
                                
                        # Case B: Standard alarm (only if not currently snoozed)
                        elif a.get("next_trigger"):
                            trigger_dt = datetime.fromisoformat(a["next_trigger"])
                            if now >= trigger_dt:
                                should_fire = True
                                
                        if should_fire:
                            self.ringing_alarm = a
                            self.ringing_start_time = now
                            self.log(f"Alarm {a['id']} ('{a['label']}') is ringing!")
                            state["active_ringing_id"] = a["id"]
                            alarm_manager.save_state(state)
                            
                            # Start playing the sound thread
                            self.player.start(a.get("sound", "classic"))
                            break
                            
            except Exception as e:
                self.log(f"Worker Error: {e}")
                
            time.sleep(1.0)

    def make_dashboard_layout(self):
        """Create the rich layout containing time, alarms table, logs, and ringing banner."""
        layout = Layout()
        layout.split(
            Layout(name="header", size=3),
            Layout(name="body", ratio=1),
            Layout(name="ringing", size=3),
            Layout(name="footer", size=10)
        )
        return layout

    def render_dashboard(self, layout):
        """Render components into the layout panels."""
        now = datetime.now()
        time_str = now.strftime("%Y-%m-%d %H:%M:%S")
        day_str = now.strftime("%A")
        
        # 1. Header
        header_text = Text()
        header_text.append("(o) I Want To Sleep Daemon ", style="bold cyan")
        header_text.append(f"[PID: {os.getpid()}]", style="dim white")
        layout["header"].update(
            Panel(Align.center(header_text), border_style="cyan")
        )
        
        # 2. Body: Digital clock + active alarms list
        state = alarm_manager.load_state()
        
        body_layout = Layout()
        body_layout.split_row(
            Layout(name="clock", ratio=1),
            Layout(name="alarms", ratio=2)
        )
        
        # Clock panel
        clock_text = Text()
        clock_text.append(f"\n{time_str}\n", style="bold green fs_16")
        clock_text.append(f"{day_str}", style="yellow italic")
        body_layout["clock"].update(
            Panel(Align.center(clock_text), title="Current Time", border_style="green")
        )
        
        # Alarms Table
        table = Table(title="Scheduled Alarms", title_style="bold magenta", expand=True)
        table.add_column("ID", style="cyan", justify="center")
        table.add_column("Label", style="white")
        table.add_column("Time", style="green", justify="center")
        table.add_column("Repeat", style="yellow")
        table.add_column("Status", style="bold")
        table.add_column("Next Trigger", style="blue")
        
        for a in state["alarms"]:
            status_text = ""
            status_style = ""
            if not a["enabled"]:
                status_text = "OFF"
                status_style = "dim red"
            elif a.get("snoozed_until"):
                snoozed_dt = datetime.fromisoformat(a["snoozed_until"])
                remaining = int((snoozed_dt - now).total_seconds())
                status_text = f"SNOOZE ({remaining}s)" if remaining > 0 else "SNOOZED"
                status_style = "orange1"
            else:
                status_text = "ON"
                status_style = "green"
                
            repeat_display = ", ".join(a["repeat"]) if a["repeat"] else "One-Time"
            
            next_trig_val = "-"
            if a["enabled"]:
                if a.get("snoozed_until"):
                    next_trig_val = datetime.fromisoformat(a["snoozed_until"]).strftime("%H:%M:%S")
                elif a.get("next_trigger"):
                    next_trig_val = datetime.fromisoformat(a["next_trigger"]).strftime("%m-%d %H:%M:%S")
            
            table.add_row(
                str(a["id"]),
                a["label"],
                a["time"],
                repeat_display,
                Text(status_text, style=status_style),
                next_trig_val
            )
            
        body_layout["alarms"].update(table)
        layout["body"].update(body_layout)
        
        # 3. Ringing Banner
        if self.ringing_alarm:
            banner_text = Text()
            banner_text.append("!!! RINGING !!! ", style="bold red blink")
            banner_text.append(f"'{self.ringing_alarm['label']}'", style="bold white")
            banner_text.append(" | Sound: ", style="dim")
            banner_text.append(f"{self.ringing_alarm.get('sound', 'classic')}", style="cyan")
            banner_text.append("  [To dismiss/snooze, run: ", style="yellow")
            banner_text.append(f"iwts dismiss {self.ringing_alarm['id']} ", style="bold white")
            banner_text.append("or ", style="yellow")
            banner_text.append(f"iwts snooze {self.ringing_alarm['id']}", style="bold white")
            banner_text.append("]", style="yellow")
            layout["ringing"].update(Panel(Align.center(banner_text), border_style="red"))
        else:
            layout["ringing"].update(Panel(Align.center(Text("No alarms active", style="dim green")), border_style="green"))
            
        # 4. Activity Logs
        log_content = "\n".join(self.logs)
        layout["footer"].update(
            Panel(log_content, title="Activity Logs", border_style="blue")
        )

    def run(self):
        """Main entry point for starting the daemon."""
        if self.is_daemon_running():
            console.print("[bold red]Error:[/] Another alarm daemon is already running! Check your processes.")
            sys.exit(1)
            
        self.log("Starting IWantToSleep Alarm Daemon...")
        self.update_heartbeat()
        
        # Start background worker thread
        worker_thread = threading.Thread(target=self.check_alarms_worker, daemon=True)
        worker_thread.start()
        
        layout = self.make_dashboard_layout()
        
        try:
            with Live(layout, refresh_per_second=2, screen=True) as live:
                while self.is_running:
                    self.render_dashboard(layout)
                    time.sleep(0.5)
        except (KeyboardInterrupt, SystemExit):
            self.is_running = False
            self.log("Stopping daemon service...")
            self.player.stop()
            
            # Clear PID and heartbeat on clean shutdown
            state = alarm_manager.load_state()
            state["daemon_pid"] = None
            state["daemon_last_seen"] = None
            alarm_manager.save_state(state)
            
            console.print("\n[bold yellow]Daemon shut down successfully.[/]")
