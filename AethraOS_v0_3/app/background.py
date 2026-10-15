"""Lightweight loop for reminders, folder watch, and inbox. No window required."""

import time

from app.tools.inbox_watch import poll_inbox
from app.tools.scheduler import check_due_reminders
from app.tools.watcher import poll_watch


def main():
    print("Aethra background agent running. Close this window to stop it.")
    while True:
        try:
            due = check_due_reminders()
            for item in due.get("items") or []:
                print("DUE:", item.get("message"))
        except Exception as exc:
            print("reminder check failed:", exc)
        try:
            found = poll_watch()
            for name in found.get("new_files") or []:
                print("NEW FILE:", name, "workflow:", found.get("workflow"))
        except Exception as exc:
            print("watch failed:", exc)
        try:
            mail = poll_inbox()
            for plan in mail.get("plans") or []:
                print("MAIL:", plan)
        except Exception as exc:
            print("inbox check failed:", exc)
        time.sleep(20)


if __name__ == "__main__":
    main()