"""
Windows Task Scheduler setup for the SoCal AI Newsletter Agent.

Usage:
  python setup_schedule.py          # Register the weekly task
  python setup_schedule.py --remove # Remove the task
  python setup_schedule.py --status # Check current status
  python setup_schedule.py --run    # Trigger an immediate run (for testing)
"""

import argparse
import os
import subprocess
import sys

TASK_NAME = "SoCal AI Newsletter"
TASK_NAME_SYNC = "SoCal AI Newsletter - Daily Sync"
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BAT_FILE = os.path.join(SCRIPT_DIR, "run_newsletter.bat")
BAT_FILE_SYNC = os.path.join(SCRIPT_DIR, "run_sync.bat")
SCHEDULE_DAY = "TUE"
SCHEDULE_TIME = "09:00"
SYNC_TIME = "08:00"


def register_task():
    """Create (or overwrite) the weekly scheduled task."""
    if not os.path.exists(BAT_FILE):
        print(f"✗ Cannot find {BAT_FILE}")
        print("  Make sure you run this from the newsletter-agent directory.")
        sys.exit(1)

    cmd = [
        "schtasks", "/Create",
        "/TN", TASK_NAME,
        "/TR", BAT_FILE,
        "/SC", "WEEKLY",
        "/D", SCHEDULE_DAY,
        "/ST", SCHEDULE_TIME,
        "/F",           # Overwrite if task already exists
        "/RL", "LIMITED",
    ]

    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode == 0:
        print(f"✅  Task registered successfully!")
        print(f"    Name    : {TASK_NAME}")
        print(f"    Schedule: Every Tuesday at 9:00 AM")
        print(f"    Script  : {BAT_FILE}")
        print(f"    Logs    : {os.path.join(SCRIPT_DIR, 'data', 'logs', 'newsletter.log')}")
        print()
        print("💡 To verify: open Task Scheduler and look for 'SoCal AI Newsletter'")
        print("   Or run:  python setup_schedule.py --status")
    else:
        print(f"✗ Failed to register task.")
        print(f"  Error: {result.stderr.strip() or result.stdout.strip()}")
        print()
        print("  Try running this script as Administrator if you get an access error.")
        sys.exit(1)


def remove_task():
    """Delete the scheduled task."""
    cmd = ["schtasks", "/Delete", "/TN", f'"{TASK_NAME}"', "/F"]
    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode == 0:
        print(f"✅  Task '{TASK_NAME}' removed.")
    else:
        err = result.stderr.strip() or result.stdout.strip()
        if "cannot find" in err.lower() or "does not exist" in err.lower():
            print(f"   Task '{TASK_NAME}' was not found (already removed?).")
        else:
            print(f"✗ Failed to remove task: {err}")
            sys.exit(1)


def task_status():
    """Show the current state of the scheduled task."""
    cmd = ["schtasks", "/Query", "/TN", f'"{TASK_NAME}"', "/FO", "LIST", "/V"]
    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode == 0:
        # Print only the most useful lines
        useful = [
            "TaskName", "Status", "Next Run Time", "Last Run Time",
            "Last Result", "Schedule Type", "Days", "Start Time",
        ]
        for line in result.stdout.splitlines():
            if any(line.startswith(k) for k in useful):
                print(f"  {line.strip()}")
    else:
        err = result.stderr.strip() or result.stdout.strip()
        if "cannot find" in err.lower():
            print(f"  Task '{TASK_NAME}' is not registered yet.")
            print("  Run: python setup_schedule.py")
        else:
            print(f"  Error: {err}")


def run_now():
    """Trigger the newsletter task immediately via Task Scheduler."""
    cmd = ["schtasks", "/Run", "/TN", f'"{TASK_NAME}"']
    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode == 0:
        log_path = os.path.join(SCRIPT_DIR, "data", "logs", "newsletter.log")
        print(f"✅  Task triggered. Output will appear in:")
        print(f"    {log_path}")
        print()
        print("   Tip: tail the log with:  Get-Content data\\logs\\newsletter.log -Wait")
    else:
        print(f"✗ Could not trigger task: {result.stderr.strip()}")
        print("  Make sure the task is registered first: python setup_schedule.py")
        sys.exit(1)


def register_sync_task():
    """Create (or overwrite) the daily subscriber sync task."""
    if not os.path.exists(BAT_FILE_SYNC):
        print(f"✗ Cannot find {BAT_FILE_SYNC}")
        sys.exit(1)

    cmd = [
        "schtasks", "/Create",
        "/TN", TASK_NAME_SYNC,
        "/TR", BAT_FILE_SYNC,
        "/SC", "DAILY",
        "/ST", SYNC_TIME,
        "/F",
        "/RL", "LIMITED",
    ]

    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode == 0:
        print(f"✅  Daily sync task registered!")
        print(f"    Name    : {TASK_NAME_SYNC}")
        print(f"    Schedule: Every day at {SYNC_TIME} AM")
        print(f"    Script  : {BAT_FILE_SYNC}")
        print(f"    Logs    : {os.path.join(SCRIPT_DIR, 'data', 'logs', 'sync.log')}")
    else:
        print(f"✗ Failed to register sync task.")
        print(f"  Error: {result.stderr.strip() or result.stdout.strip()}")
        sys.exit(1)


def remove_sync_task():
    """Delete the daily sync scheduled task."""
    cmd = ["schtasks", "/Delete", "/TN", f'"{TASK_NAME_SYNC}"', "/F"]
    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode == 0:
        print(f"✅  Task '{TASK_NAME_SYNC}' removed.")
    else:
        err = result.stderr.strip() or result.stdout.strip()
        if "cannot find" in err.lower() or "does not exist" in err.lower():
            print(f"   Task '{TASK_NAME_SYNC}' was not found (already removed?).")
        else:
            print(f"✗ Failed to remove task: {err}")
            sys.exit(1)


def main():
    parser = argparse.ArgumentParser(description="Manage the newsletter scheduled task")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--remove", action="store_true", help="Remove the weekly newsletter task")
    group.add_argument("--status", action="store_true", help="Show current task status")
    group.add_argument("--run", action="store_true", help="Trigger an immediate newsletter run")
    group.add_argument("--add-sync", action="store_true", help="Register the daily subscriber sync task")
    group.add_argument("--remove-sync", action="store_true", help="Remove the daily subscriber sync task")
    args = parser.parse_args()

    if args.remove:
        remove_task()
    elif args.status:
        task_status()
    elif args.run:
        run_now()
    elif args.add_sync:
        register_sync_task()
    elif args.remove_sync:
        remove_sync_task()
    else:
        register_task()


if __name__ == "__main__":
    main()
