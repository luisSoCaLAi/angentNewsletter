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
  python main.py --welcome    # Send most recent newsletter to new subscribers
"""

import argparse
import os
import sys
import traceback
from datetime import datetime

from config import validate_config, validate_linkedin_config
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
        print("Dry run -- skipping send, publish, and LinkedIn post.")
        print("Preview saved to data/last_newsletter.html")
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

    # ── Step 5: Publish to web ────────────────────────────────────────
    date_str = datetime.now().strftime("%Y-%m-%d")
    newsletter_url = f"https://socalaisolutions.com/newsletters/{date_str}"
    try:
        step(5, "Publishing newsletter to socalaisolutions.com")
        from services.newsletter_publisher import NewsletterPublisher
        publisher = NewsletterPublisher()
        publisher.publish(full_html, date_str)
        print(f"   ✓ Live at {newsletter_url}\n")
    except Exception as e:
        print(f"   WARNING: Newsletter publish failed — {e}")
        print("   LinkedIn will still post; deploy locally to activate the URL.\n")

    # ── Step 6: Post to LinkedIn ──────────────────────────────────────
    skip_li = args.skip_linkedin or args.test
    if not skip_li:
        try:
            step(6, "Posting to LinkedIn company page")
            validate_linkedin_config()
            from services.linkedin_poster import LinkedInPoster
            poster = LinkedInPoster()
            post_urn = poster.post_newsletter(topics, subject, newsletter_url)
            print(f"   Posted (URN: {post_urn})\n")
        except Exception as e:
            print(f"   WARNING: LinkedIn post failed — {type(e).__name__}: {e}")
            traceback.print_exc()
            print()
    elif args.test:
        print(">> Step 6: LinkedIn post skipped (--test mode)\n")
    elif args.skip_linkedin:
        print(">> Step 6: LinkedIn post skipped (--skip-linkedin)\n")

    # ── Summary ──────────────────────────────────────────────────────
    banner(f"Done -- {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"Subject : {subject}")
    print(f"Topics  : {' | '.join(t['title'] for t in topics)}")
    if not args.test and not args.dry_run:
        print(f"Sent to : {len(subscribers)} subscriber(s)")
    if newsletter_url:
        print(f"Web URL : {newsletter_url}")
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
        with open(index_path, "r", encoding="utf-8-sig") as f:
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


def run_welcome():
    """Send the most recent newsletter to any subscribers who haven't received it yet."""
    import json

    banner("Welcome Newsletter — New Subscriber Check")
    validate_config()

    # Load last newsletter
    preview_path = os.path.join("data", "last_newsletter.html")
    if not os.path.exists(preview_path):
        print("   No newsletter found at data/last_newsletter.html — skipping.")
        return

    # Load newsletter subject from index
    index_path = os.path.join("data", "newsletters", "index.json")
    subject = "Welcome — Your first AI Insider newsletter"
    if os.path.exists(index_path):
        with open(index_path, "r", encoding="utf-8") as f:
            index = json.load(f)
        real = [e for e in index if not e.get("is_test")]
        if real:
            subject = f"Welcome! {real[0]['subject']}"

    with open(preview_path, "r", encoding="utf-8") as f:
        full_html = f.read()

    # Load welcomed list
    welcomed_path = os.path.join("data", "welcomed.json")
    if os.path.exists(welcomed_path):
        with open(welcomed_path, "r", encoding="utf-8") as f:
            welcomed = set(json.load(f))
    else:
        welcomed = set()

    # Get current subscribers
    mgr = SubscriberManager()
    subscribers = mgr.sync()
    new_subscribers = [s for s in subscribers if s["email"].lower() not in welcomed]

    if not new_subscribers:
        print("   No new subscribers to welcome.")
        return

    print(f"   Found {len(new_subscribers)} new subscriber(s) to welcome:")
    for s in new_subscribers:
        print(f"      - {s['email']}")
    print()

    sender = EmailSender()
    for subscriber in new_subscribers:
        try:
            sender.send_newsletter(full_html, subject, [subscriber])
            welcomed.add(subscriber["email"].lower())
        except Exception as e:
            print(f"   Failed to welcome {subscriber['email']}: {e}")

    # Save updated welcomed list
    os.makedirs("data", exist_ok=True)
    with open(welcomed_path, "w", encoding="utf-8") as f:
        json.dump(sorted(welcomed), f, indent=2)
    print(f"\n   welcomed.json updated — {len(welcomed)} total welcomed.")


def run_post_linkedin(date_str: str | None = None):
    """Post the most recent newsletter to LinkedIn without resending any emails."""
    import json
    import re as _re

    banner("Post to LinkedIn — No Resend")
    validate_config()

    # Resolve date and URL
    if not date_str:
        date_str = datetime.now().strftime("%Y-%m-%d")
    newsletter_url = f"https://socalaisolutions.com/newsletters/{date_str}"

    # Load newsletter HTML: dated archive → live URL (GitHub Actions runs don't save locally)
    archive_path = os.path.join("data", "newsletters", f"{date_str}.html")
    html_path: str | None = archive_path if os.path.exists(archive_path) else None

    if html_path:
        with open(html_path, "r", encoding="utf-8") as f:
            html = f.read()
    else:
        # Not in local archive — fetch from the live site
        import requests as _req
        print(f"   Fetching newsletter HTML from {newsletter_url} ...")
        try:
            resp = _req.get(newsletter_url, timeout=15)
            resp.raise_for_status()
            html = resp.text
        except Exception as e:
            print(f"   ERROR: Could not fetch newsletter from web — {e}")
            sys.exit(1)

    # Extract topic titles from H2 headings inside article sections
    h2_titles = _re.findall(
        r'<h2[^>]*style="[^"]*color:#1a1a2e[^"]*"[^>]*>(.*?)</h2>',
        html,
        flags=_re.IGNORECASE | _re.DOTALL,
    )
    # Strip any inline tags (e.g. <strong>)
    topics = [
        {"title": _re.sub(r'<[^>]+>', '', t).strip()}
        for t in h2_titles[:3]
    ]

    # Load subject from index if available
    subject = "AI Insider — Weekly Newsletter"
    index_path = os.path.join("data", "newsletters", "index.json")
    if os.path.exists(index_path):
        with open(index_path, "r", encoding="utf-8") as f:
            index = json.load(f)
        match = next((e for e in index if e.get("date") == date_str), None)
        if match:
            subject = match.get("subject", subject)

    print(f"   Date      : {date_str}")
    print(f"   URL       : {newsletter_url}")
    print(f"   Subject   : {subject}")
    print(f"   Topics    : {[t['title'] for t in topics]}\n")

    validate_linkedin_config()
    from services.linkedin_poster import LinkedInPoster
    step(6, "Posting to LinkedIn")
    poster = LinkedInPoster()
    try:
        post_urn = poster.post_newsletter(topics, subject, newsletter_url)
        print(f"   Posted (URN: {post_urn})\n")
    except Exception as e:
        print(f"   ERROR: LinkedIn post failed — {type(e).__name__}: {e}")
        traceback.print_exc()
        sys.exit(1)


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
    parser.add_argument(
        "--welcome",
        action="store_true",
        help="Send the most recent newsletter to any subscribers not yet welcomed.",
    )
    parser.add_argument(
        "--skip-linkedin",
        action="store_true",
        help="Send emails and publish to web, but skip the LinkedIn post.",
    )
    parser.add_argument(
        "--post-linkedin",
        metavar="DATE",
        nargs="?",
        const="today",
        help="Post today's (or DATE's) newsletter to LinkedIn only — no emails sent. "
             "DATE format: YYYY-MM-DD (default: today).",
    )
    args = parser.parse_args()

    if args.add_sub:
        run_add_subscriber()
    elif args.sync:
        run_sync_only()
    elif args.welcome:
        run_welcome()
    elif args.post_linkedin is not None:
        date = None if args.post_linkedin == "today" else args.post_linkedin
        run_post_linkedin(date)
    else:
        run_full(args)


if __name__ == "__main__":
    main()
