import sys
import os
import argparse
from datetime import datetime
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.text import Text

import alarm_manager
from daemon_runner import DaemonRunner
from sound_player import SoundPlayer

console = Console()

def is_daemon_active():
    """Helper to check if the daemon process is running."""
    runner = DaemonRunner()
    return runner.is_daemon_running()

def print_banner():
    """Prints a premium retro alarm clock banner."""
    banner = """
  [bold cyan](o) I Want To Sleep (iwts)[/] [dim]v1.0.0[/]
  [dim]The Ultimate Terminal Alarm Clock & Scheduler[/]
    """
    console.print(banner)

def handle_daemon(args):
    """Start the background daemon process."""
    print_banner()
    console.print("[bold yellow]Starting daemon mode...[/]")
    runner = DaemonRunner()
    runner.run()

def handle_add(args):
    """Add a new alarm."""
    try:
        new_alarm = alarm_manager.add_alarm(
            time_str=args.time,
            label=args.label,
            sound=args.sound,
            repeat_str=args.repeat
        )
        
        # Format the trigger time nicely
        next_dt = datetime.fromisoformat(new_alarm["next_trigger"])
        trigger_str = next_dt.strftime("%Y-%m-%d %H:%M:%S")
        
        console.print(f"[bold green]Success![/] Alarm #{new_alarm['id']} added.")
        console.print(f"[ALARM] [bold cyan]{new_alarm['label']}[/] scheduled for [bold yellow]{trigger_str}[/].")
        
        if not is_daemon_active():
            console.print("\n[bold orange1]Warning:[/] The alarm daemon is not currently running.")
            console.print("To trigger this alarm, please start the daemon in another terminal using:")
            console.print("  [bold white]python iwts.py daemon[/]")
            
    except ValueError as e:
        console.print(f"[bold red]Error:[/] {e}")

def handle_list(args):
    """List all alarms in a beautiful table."""
    state = alarm_manager.load_state()
    alarms = state.get("alarms", [])
    
    if not alarms:
        console.print("[yellow]No alarms configured. Add one with: [bold white]python iwts.py add <time>[/]")
        return
        
    print_banner()
    
    # Check daemon status
    daemon_running = is_daemon_active()
    status_color = "green" if daemon_running else "red"
    status_text = "Running" if daemon_running else "Stopped"
    console.print(f"Daemon Status: [bold {status_color}]{status_text}[/]\n")

    table = Table(expand=True)
    table.add_column("ID", style="cyan", justify="center", width=5)
    table.add_column("Label", style="white")
    table.add_column("Time", style="green", justify="center")
    table.add_column("Repeat", style="yellow")
    table.add_column("Sound", style="blue")
    table.add_column("Status", style="bold")
    table.add_column("Next Trigger", style="magenta")

    now = datetime.now()
    for a in alarms:
        status_str = ""
        status_style = ""
        if not a["enabled"]:
            status_str = "Disabled"
            status_style = "dim red"
        elif a.get("snoozed_until"):
            snoozed_dt = datetime.fromisoformat(a["snoozed_until"])
            remaining = int((snoozed_dt - now).total_seconds())
            status_str = f"Snoozed ({remaining}s)" if remaining > 0 else "Snoozed"
            status_style = "orange1"
        else:
            status_str = "Active"
            status_style = "green"
            
        repeat_display = ", ".join(a["repeat"]) if a["repeat"] else "One-Time"
        
        next_trig_val = "-"
        if a["enabled"]:
            if a.get("snoozed_until"):
                next_trig_val = datetime.fromisoformat(a["snoozed_until"]).strftime("%Y-%m-%d %H:%M:%S")
            elif a.get("next_trigger"):
                next_trig_val = datetime.fromisoformat(a["next_trigger"]).strftime("%Y-%m-%d %H:%M:%S")
                
        table.add_row(
            str(a["id"]),
            a["label"],
            a["time"],
            repeat_display,
            a.get("sound", "classic"),
            Text(status_str, style=status_style),
            next_trig_val
        )

    console.print(table)

def handle_delete(args):
    """Delete an alarm."""
    if alarm_manager.delete_alarm(args.id):
        console.print(f"[bold green]Success![/] Alarm #{args.id} has been deleted.")
    else:
        console.print(f"[bold red]Error:[/] Alarm #{args.id} not found.")

def handle_enable(args):
    """Enable an alarm."""
    if alarm_manager.set_alarm_enabled(args.id, True):
        console.print(f"[bold green]Success![/] Alarm #{args.id} has been enabled.")
    else:
        console.print(f"[bold red]Error:[/] Alarm #{args.id} not found.")

def handle_disable(args):
    """Disable an alarm."""
    if alarm_manager.set_alarm_enabled(args.id, False):
        console.print(f"[bold green]Success![/] Alarm #{args.id} has been disabled.")
    else:
        console.print(f"[bold red]Error:[/] Alarm #{args.id} not found.")

def handle_dismiss(args):
    """Dismiss a ringing alarm."""
    state = alarm_manager.load_state()
    alarm_id = args.id
    
    if alarm_id is None:
        # Check if daemon has an active ringing ID
        alarm_id = state.get("active_ringing_id")
        if alarm_id is None:
            console.print("[bold red]Error:[/] No alarm is currently ringing.")
            return

    # Add to dismiss requests
    if alarm_id not in state["dismiss_requests"]:
        state["dismiss_requests"].append(alarm_id)
        alarm_manager.save_state(state)
        console.print(f"[bold green]Requested dismissal[/] for alarm #{alarm_id}.")
        if not is_daemon_active():
            console.print("[dim]Note: Daemon is not running. Dismissal will apply once daemon starts.[/]")
    else:
        console.print(f"Dismissal request for alarm #{alarm_id} is already pending.")

def handle_snooze(args):
    """Snooze a ringing alarm."""
    state = alarm_manager.load_state()
    alarm_id = args.id
    
    if alarm_id is None:
        # Check if daemon has an active ringing ID
        alarm_id = state.get("active_ringing_id")
        if alarm_id is None:
            console.print("[bold red]Error:[/] No alarm is currently ringing.")
            return

    alarm_id_str = str(alarm_id)
    # Add to snooze requests
    state["snooze_requests"][alarm_id_str] = args.mins
    alarm_manager.save_state(state)
    console.print(f"[bold green]Requested snooze[/] of {args.mins} minutes for alarm #{alarm_id}.")
    if not is_daemon_active():
        console.print("[dim]Note: Daemon is not running. Snooze will apply once daemon starts.[/]")

def handle_status(args):
    """Print the current running status of the daemon and pending alarms."""
    print_banner()
    daemon_running = is_daemon_active()
    state = alarm_manager.load_state()
    
    # Daemon Status Panel
    status_color = "green" if daemon_running else "red"
    status_text = "Running" if daemon_running else "Stopped"
    pid_text = f" (PID: {state['daemon_pid']})" if daemon_running and state.get('daemon_pid') else ""
    
    console.print(Panel(
        f"Daemon: [bold {status_color}]{status_text}{pid_text}[/]\n"
        f"Active Alarms: [bold]{len([a for a in state['alarms'] if a['enabled']])}[/]\n"
        f"Currently Ringing: [bold red]{state.get('active_ringing_id') or 'None'}[/]",
        title="System Status",
        border_style=status_color
    ))

def main():
    # Preprocess command line to map common aliases
    if len(sys.argv) > 1:
        cmd = sys.argv[1].lower()
        if cmd == "ls":
            sys.argv[1] = "list"
        elif cmd == "rm":
            sys.argv[1] = "delete"

    parser = argparse.ArgumentParser(
        description="I Want To Sleep (iwts) - Command Line Alarm Clock Manager"
    )
    subparsers = parser.add_subparsers(dest="command", required=True, help="CLI Command to execute")

    # Daemon command
    subparsers.add_parser("daemon", help="Start the background alarm daemon and dashboard")

    # Add command
    parser_add = subparsers.add_parser("add", help="Schedule a new alarm")
    parser_add.add_argument("time", type=str, help="Alarm time (e.g. 14:30, 2:30 PM, or relative like +10m, +30s)")
    parser_add.add_argument("-l", "--label", type=str, default="", help="Label or name for the alarm")
    parser_add.add_argument("-s", "--sound", type=str, default="classic", 
                            choices=SoundPlayer.get_available_sounds(), 
                            help="Audio alert type (default: classic)")
    parser_add.add_argument("-r", "--repeat", type=str, default="",
                            help="Days to repeat, comma separated (e.g. mon,wed,fri) or categories (daily, weekdays, weekends)")

    # List command
    subparsers.add_parser("list", help="List all configured alarms")

    # Delete command
    parser_del = subparsers.add_parser("delete", help="Delete a specific alarm")
    parser_del.add_argument("id", type=int, help="Alarm ID to delete")

    # Enable command
    parser_en = subparsers.add_parser("enable", help="Enable an alarm")
    parser_en.add_argument("id", type=int, help="Alarm ID to enable")

    # Disable command
    parser_dis = subparsers.add_parser("disable", help="Disable an alarm")
    parser_dis.add_argument("id", type=int, help="Alarm ID to disable")

    # Dismiss command
    parser_dism = subparsers.add_parser("dismiss", help="Dismiss a currently ringing alarm")
    parser_dism.add_argument("id", type=int, nargs="?", default=None, help="Specific alarm ID to dismiss (optional)")

    # Snooze command
    parser_snooze = subparsers.add_parser("snooze", help="Snooze a currently ringing alarm")
    parser_snooze.add_argument("id", type=int, nargs="?", default=None, help="Specific alarm ID to snooze (optional)")
    parser_snooze.add_argument("-m", "--mins", type=int, default=5, help="Snooze duration in minutes (default: 5)")

    # Status command
    subparsers.add_parser("status", help="Show daemon status and quick diagnostics")

    args = parser.parse_args()

    # Routing commands
    command_map = {
        "daemon": handle_daemon,
        "add": handle_add,
        "list": handle_list,
        "delete": handle_delete,
        "enable": handle_enable,
        "disable": handle_disable,
        "dismiss": handle_dismiss,
        "snooze": handle_snooze,
        "status": handle_status
    }

    if args.command in command_map:
        command_map[args.command](args)

if __name__ == "__main__":
    main()
