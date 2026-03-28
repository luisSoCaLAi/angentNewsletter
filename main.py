"""
SoCal AI Solutions — Weekly Newsletter Agent
============================================

Pipeline:
  1. Sync subscriber list from Netlify Forms → local cache
  2. Research top 3 AI topics this week (Claude + web_search)
  3. Write the HTML newsletter (Claude)
  4. Send to all subscribers via Resend

Usage:
  python main.py              # Full run (research + write + send)
  python main.py --test       # Send test email to TEST_EMAIL env var
  python main.py --dry-run    # Research + write, save HTML, don't send
  python main.py --add-sub    # Add a subscriber manually to local cache
"""

import argparse
import os
import sys
from datetime import datetime

from config import validate_config
from agents.research_agent import ResearchAgent
from agents.writer_agent import WriterAgent
from services.subscriber_manager import SubscriberManager
from services.email_sender import EmailSender


def banner(text: str) -> None:
    width = 60
    # Print a run-start marker so each scheduled run is easy to find in the log
    if text.startswith("SoCal AI"):
        print(f"\n{'#' * width}")
        print(f"# RUN START — {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"{'#' * width}")
    print(f"\n{'=' * width}")
    print(f"  {text}")
    print(f"{'=' * width}\n")


def step(num: int, label: str) -> None:
    print(f">> Step {num}: {label}...")


def run_full(args):
    banner("SoCal AI Solutions — Weekly Newsletter Agent")

    # Validate env before doing any work
    validate_config()

    # Trim log file if it's getting large
    _trim_log(os.path.join("data", "logs", "newsletter.log"))

    # ── Step 1: Subscribers ──────────────────────────────────────────
    step(1, "Syncing subscriber list")
    mgr = SubscriberManager()
    subscribers = mgr.sync()
    print(f"   ✓ {len(subscribers)} active subscribers\n")

    if not subscribers:
        print("WARNING: No subscribers found. Add some with: python main.py --add-sub")
        sys.exit(0)

    # ── Step 2: Research ─────────────────────────────────────────────
    step(2, "Researching hot AI topics this week")
    research_agent = ResearchAgent()
    topics = research_agent.research()
    print(f"   ✓ {len(topics)} topics identified:")
    for i, t in enumerate(topics, 1):
        print(f"      {i}. {t['title']}")
    print()

    # Brief pause so research tokens clear the per-minute rate limit window
    print("   Pausing 65s to clear API rate limit window...")
    import time; time.sleep(65)

    # ── Step 3: Write ────────────────────────────────────────────────
    step(3, "Writing newsletter")
    writer = WriterAgent()
    body_html = writer.write(topics)
    subject = writer.generate_subject(topics)
    full_html = writer.build_full_html(body_html)
    print(f"   ✓ Subject: \"{subject}\"")
    print(f"   ✓ HTML size: {len(full_html):,} bytes\n")

    # Optionally save a copy for review
    _save_preview(full_html, subject)

    if args.dry_run:
        print("Dry run -- skipping send. Preview saved to data/last_newsletter.html")
        return

    # ── Step 4: Send ─────────────────────────────────────────────────
    step(4, f"Sending to {len(subscribers)} subscriber(s)")
    sender = EmailSender()

    if args.test:
        test_email = os.getenv("TEST_EMAIL") or input("Enter test email address: ").strip()
        sender.send_test(full_html, subject, test_email)
        _archive_newsletter(full_html, subject, sent_count=1, is_test=True)
    else:
        results = sender.send_newsletter(full_html, subject, subscribers)
        print(f"\n   Sent: {results['sent']}  |  Failed: {len(results['failed'])}")
        _archive_newsletter(full_html, subject, sent_count=results["sent"], is_test=False)

    # ── Summary ──────────────────────────────────────────────────────
    banner(f"Done -- {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"Subject : {subject}")
    print(f"Topics  : {' | '.join(t['title'] for t in topics)}")
    if not args.test and not args.dry_run:
        print(f"Sent to : {len(subscribers)} subscriber(s)")
    print()


def run_sync_only():
    """Pull latest subscribers from Netlify and update local cache — no email sent."""
    banner("Sync Subscribers from Netlify")
    mgr = SubscriberManager()
    subscribers = mgr.sync()
    print(f"\n   ✓ {len(subscribers)} active subscriber(s) in local cache:")
    for s in subscribers:
        print(f"      • {s['email']}  (source: {s['source']}, since: {s['subscribed_at']})")
    print()


def run_add_subscriber():
    email = input("Email address: ").strip()
    name = input("Name (optional): ").strip()
    mgr = SubscriberManager()
    mgr.add_manual(email, name)


def _trim_log(log_path: str, keep_bytes: int = 500_000) -> None:
    """Keep the log file under keep_bytes by dropping the oldest content."""
    if not os.path.exists(log_path):
        return
    size = os.path.getsize(log_path)
    if size > keep_bytes:
        with open(log_path, "rb") as f:
            f.seek(size - keep_bytes)
            tail = f.read()
        # Find the next newline so we don't start mid-line
        newline_pos = tail.find(b"\n")
        tail = tail[newline_pos + 1 :] if newline_pos != -1 else tail
        with open(log_path, "wb") as f:
            f.write(tail)


def _save_preview(html: str, subject: str) -> None:
    """Save the rendered newsletter to data/ for local preview."""
    preview_path = os.path.join("data", "last_newsletter.html")
    os.makedirs("data", exist_ok=True)
    with open(preview_path, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"   Preview saved -> {preview_path}")


def _archive_newsletter(html: str, subject: str, sent_count: int, is_test: bool) -> None:
    """Save newsletter to dated archive and update index.json for the dashboard."""
    import json
    archive_dir = os.path.join("data", "newsletters")
    os.makedirs(archive_dir, exist_ok=True)

    date_str = datetime.now().strftime("%Y-%m-%d")
    filename = f"{date_str}.html"
    filepath = os.path.join(archive_dir, filename)
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(html)

    index_path = os.path.join(archive_dir, "index.json")
    if os.path.exists(index_path):
        with open(index_path, "r", encoding="utf-8") as f:
            index = json.load(f)
    else:
        index = []

    # Replace existing entry for today if re-run, otherwise append
    index = [e for e in index if e.get("date") != date_str]
    index.append({
        "date": date_str,
        "subject": subject,
        "sent_count": sent_count,
        "is_test": is_test,
        "filename": filename,
    })
    index.sort(key=lambda e: e["date"], reverse=True)

    with open(index_path, "w", encoding="utf-8") as f:
        json.dump(index, f, indent=2, ensure_ascii=False)


def main():
    parser = argparse.ArgumentParser(
        description="SoCal AI Solutions — Weekly Newsletter Agent"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Research and write the newsletter, save HTML preview, but don't send.",
    )
    parser.add_argument(
        "--test",
        action="store_true",
        help="Send only to TEST_EMAIL (or prompt) instead of all subscribers.",
    )
    parser.add_argument(
        "--add-sub",
        action="store_true",
        help="Add a subscriber manually to the local cache.",
    )
    parser.add_argument(
        "--sync",
        action="store_true",
        help="Pull latest subscribers from Netlify and update local cache (no email sent).",
    )
    args = parser.parse_args()

    if args.add_sub:
        run_add_subscriber()
    elif args.sync:
        run_sync_only()
    else:
        run_full(args)


if __name__ == "__main__":
    main()
