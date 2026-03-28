"""
Newsletter Dashboard — generates a self-contained HTML report and opens it in the browser.

Usage:
  python dashboard.py
"""

import json
import os
import webbrowser
from datetime import datetime

import requests
from config import NETLIFY_API_TOKEN, NETLIFY_FORM_ID, NETLIFY_UNSUBSCRIBE_FORM_ID, SUBSCRIBERS_FILE


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

def load_subscribers() -> list[dict]:
    if not os.path.exists(SUBSCRIBERS_FILE):
        return []
    with open(SUBSCRIBERS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def load_newsletter_index() -> list[dict]:
    index_path = os.path.join("data", "newsletters", "index.json")
    if not os.path.exists(index_path):
        return []
    with open(index_path, "r", encoding="utf-8") as f:
        return json.load(f)


def fetch_unsubscribe_count() -> int:
    if not NETLIFY_API_TOKEN or not NETLIFY_UNSUBSCRIBE_FORM_ID:
        return 0
    url = f"https://api.netlify.com/api/v1/forms/{NETLIFY_UNSUBSCRIBE_FORM_ID}/submissions"
    headers = {"Authorization": f"Bearer {NETLIFY_API_TOKEN}"}
    emails = set()
    page = 1
    while True:
        try:
            resp = requests.get(url, headers=headers, params={"page": page, "per_page": 100}, timeout=10)
            resp.raise_for_status()
            data = resp.json()
            if not data:
                break
            for sub in data:
                email = sub.get("data", {}).get("email", "").strip().lower()
                if email:
                    emails.add(email)
            if len(data) < 100:
                break
            page += 1
        except Exception:
            break
    return len(emails)


def fetch_total_signups() -> int:
    """Total raw form submissions to the newsletter form (before dedup/unsub)."""
    if not NETLIFY_API_TOKEN or not NETLIFY_FORM_ID:
        return 0
    url = f"https://api.netlify.com/api/v1/forms/{NETLIFY_FORM_ID}/submissions"
    headers = {"Authorization": f"Bearer {NETLIFY_API_TOKEN}"}
    count = 0
    page = 1
    while True:
        try:
            resp = requests.get(url, headers=headers, params={"page": page, "per_page": 100}, timeout=10)
            resp.raise_for_status()
            data = resp.json()
            if not data:
                break
            count += len(data)
            if len(data) < 100:
                break
            page += 1
        except Exception:
            break
    return count


# ---------------------------------------------------------------------------
# HTML generation
# ---------------------------------------------------------------------------

def newsletter_rows(index: list[dict]) -> str:
    if not index:
        return '<tr><td colspan="4" style="text-align:center;color:#888;padding:32px;">No newsletters sent yet.</td></tr>'

    rows = []
    for entry in index:
        date = entry.get("date", "")
        subject = entry.get("subject", "—")
        sent = entry.get("sent_count", 0)
        is_test = entry.get("is_test", False)
        filename = entry.get("filename", "")

        badge = '<span style="background:#fef3c7;color:#92400e;padding:2px 8px;border-radius:12px;font-size:11px;font-weight:600;">TEST</span> ' if is_test else ""
        download = f'<a href="data/newsletters/{filename}" download="{filename}" style="color:#6d28d9;text-decoration:none;font-weight:500;">Download</a>' if filename else "—"

        rows.append(f"""
        <tr>
          <td style="padding:14px 16px;color:#374151;">{date}</td>
          <td style="padding:14px 16px;color:#111827;">{badge}{subject}</td>
          <td style="padding:14px 16px;color:#374151;text-align:center;">{sent}</td>
          <td style="padding:14px 16px;text-align:center;">{download}</td>
        </tr>""")
    return "".join(rows)


def subscriber_rows(subscribers: list[dict]) -> str:
    if not subscribers:
        return '<tr><td colspan="3" style="text-align:center;color:#888;padding:32px;">No subscribers yet.</td></tr>'

    rows = []
    for s in sorted(subscribers, key=lambda x: x.get("subscribed_at", ""), reverse=True):
        email = s.get("email", "")
        name = s.get("name", "") or "—"
        since = s.get("subscribed_at", "")
        source = s.get("source", "")
        source_badge = f'<span style="background:#ede9fe;color:#5b21b6;padding:2px 8px;border-radius:12px;font-size:11px;">{source}</span>'
        rows.append(f"""
        <tr>
          <td style="padding:12px 16px;color:#111827;">{email}</td>
          <td style="padding:12px 16px;color:#374151;">{name}</td>
          <td style="padding:12px 16px;color:#374151;">{since} {source_badge}</td>
        </tr>""")
    return "".join(rows)


def build_dashboard(subscribers, index, unsub_count, total_signups) -> str:
    active = len(subscribers)
    newsletters_sent = sum(1 for e in index if not e.get("is_test"))
    generated = datetime.now().strftime("%B %d, %Y at %I:%M %p")

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Newsletter Dashboard — SoCal AI Solutions</title>
  <style>
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{ font-family: Arial, sans-serif; background: #f3f4f6; color: #111827; }}
    header {{ background: #1a1a2e; color: #fff; padding: 24px 40px; display: flex; align-items: center; gap: 16px; }}
    header img {{ height: 40px; width: auto; }}
    header h1 {{ font-size: 1.4rem; font-weight: 700; }}
    header p {{ font-size: 0.85rem; color: #a5b4fc; margin-top: 2px; }}
    .container {{ max-width: 1100px; margin: 0 auto; padding: 32px 24px; }}
    .stats {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 16px; margin-bottom: 36px; }}
    .stat-card {{ background: #fff; border-radius: 12px; padding: 24px; box-shadow: 0 1px 4px rgba(0,0,0,0.08); }}
    .stat-card .label {{ font-size: 0.8rem; color: #6b7280; font-weight: 600; text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 8px; }}
    .stat-card .value {{ font-size: 2.2rem; font-weight: 700; color: #4f46e5; }}
    .stat-card .sub {{ font-size: 0.8rem; color: #9ca3af; margin-top: 4px; }}
    .card {{ background: #fff; border-radius: 12px; box-shadow: 0 1px 4px rgba(0,0,0,0.08); margin-bottom: 28px; overflow: hidden; }}
    .card-header {{ padding: 20px 24px; border-bottom: 1px solid #f3f4f6; }}
    .card-header h2 {{ font-size: 1rem; font-weight: 700; color: #111827; }}
    table {{ width: 100%; border-collapse: collapse; }}
    thead th {{ padding: 12px 16px; background: #f9fafb; color: #6b7280; font-size: 0.75rem; font-weight: 700; text-transform: uppercase; letter-spacing: 0.05em; text-align: left; }}
    tbody tr {{ border-top: 1px solid #f3f4f6; }}
    tbody tr:hover {{ background: #f9fafb; }}
    footer {{ text-align: center; color: #9ca3af; font-size: 0.8rem; padding: 24px; }}
  </style>
</head>
<body>

<header>
  <img src="https://socalaisolutions.org/assets/logo-dark.png" alt="SoCal AI Solutions" />
  <div>
    <h1>Newsletter Dashboard</h1>
    <p>Generated {generated}</p>
  </div>
</header>

<div class="container">

  <!-- Stats -->
  <div class="stats">
    <div class="stat-card">
      <div class="label">Active Subscribers</div>
      <div class="value">{active}</div>
      <div class="sub">{total_signups} total sign-ups</div>
    </div>
    <div class="stat-card">
      <div class="label">Unsubscribes</div>
      <div class="value">{unsub_count}</div>
      <div class="sub">all time</div>
    </div>
    <div class="stat-card">
      <div class="label">Newsletters Sent</div>
      <div class="value">{newsletters_sent}</div>
      <div class="sub">excluding test sends</div>
    </div>
    <div class="stat-card">
      <div class="label">Retention Rate</div>
      <div class="value">{"N/A" if total_signups == 0 else f"{round((active / total_signups) * 100)}%"}</div>
      <div class="sub">active / total sign-ups</div>
    </div>
  </div>

  <!-- Newsletter history -->
  <div class="card">
    <div class="card-header"><h2>Newsletter History</h2></div>
    <table>
      <thead>
        <tr>
          <th>Date</th>
          <th>Subject</th>
          <th style="text-align:center;">Recipients</th>
          <th style="text-align:center;">HTML</th>
        </tr>
      </thead>
      <tbody>
        {newsletter_rows(index)}
      </tbody>
    </table>
  </div>

  <!-- Subscriber list -->
  <div class="card">
    <div class="card-header"><h2>Active Subscribers</h2></div>
    <table>
      <thead>
        <tr>
          <th>Email</th>
          <th>Name</th>
          <th>Subscribed</th>
        </tr>
      </thead>
      <tbody>
        {subscriber_rows(subscribers)}
      </tbody>
    </table>
  </div>

</div>

<footer>SoCal AI Solutions &mdash; Newsletter Agent Dashboard</footer>
</body>
</html>"""


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    print("Loading data...")
    subscribers = load_subscribers()
    index = load_newsletter_index()

    print("Fetching Netlify stats...")
    unsub_count = fetch_unsubscribe_count()
    total_signups = fetch_total_signups()

    print("Generating dashboard...")
    html = build_dashboard(subscribers, index, unsub_count, total_signups)

    out_path = os.path.join("data", "dashboard.html")
    os.makedirs("data", exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(html)

    abs_path = os.path.abspath(out_path)
    print(f"Dashboard saved -> {abs_path}")
    webbrowser.open(f"file:///{abs_path}")


if __name__ == "__main__":
    main()
