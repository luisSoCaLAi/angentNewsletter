"""
Subscriber Manager — syncs the email list from Netlify Forms API
and maintains a local JSON cache at data/subscribers.json.

Subscriber record format:
  {
    "email": "user@example.com",
    "name": "First Last",          # optional
    "subscribed_at": "2025-01-15", # ISO date
    "source": "netlify" | "manual"
  }
"""

import json
import os
import requests
from datetime import date, datetime
from config import NETLIFY_API_TOKEN, NETLIFY_FORM_ID, NETLIFY_UNSUBSCRIBE_FORM_ID, SUBSCRIBERS_FILE


class SubscriberManager:
    def __init__(self):
        self._ensure_data_dir()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def sync(self) -> list[dict]:
        """
        Pull submissions from Netlify Forms (if configured), merge with the
        local cache, deduplicate, save, and return all active subscribers.
        """
        local = self._load_local()

        if NETLIFY_API_TOKEN and NETLIFY_FORM_ID:
            netlify = self._fetch_from_netlify()
            merged = self._merge(local, netlify)
        else:
            print(
                "   ⚠  NETLIFY_API_TOKEN or NETLIFY_FORM_ID not set. "
                "Using local subscribers.json only."
            )
            merged = local

        # Remove anyone who has submitted the unsubscribe form
        if NETLIFY_API_TOKEN and NETLIFY_UNSUBSCRIBE_FORM_ID:
            unsub_emails = self._fetch_unsubscribes()
            before = len(merged)
            merged = [s for s in merged if s["email"].lower() not in unsub_emails]
            removed = before - len(merged)
            if removed:
                print(f"   Removed {removed} unsubscribed email(s)")

        self._save_local(merged)
        return merged

    def add_manual(self, email: str, name: str = "") -> None:
        """Add a single subscriber manually (useful for testing)."""
        subscribers = self._load_local()
        if any(s["email"].lower() == email.lower() for s in subscribers):
            print(f"   {email} is already subscribed.")
            return
        subscribers.append({
            "email": email,
            "name": name,
            "subscribed_at": date.today().isoformat(),
            "source": "manual",
        })
        self._save_local(subscribers)
        print(f"   ✓ Added {email}")

    def get_all_emails(self) -> list[str]:
        return [s["email"] for s in self._load_local()]

    # ------------------------------------------------------------------
    # Netlify Forms API
    # ------------------------------------------------------------------

    def _fetch_from_netlify(self) -> list[dict]:
        """
        Fetch all form submissions from Netlify.
        Netlify Forms API: GET /api/v1/forms/{form_id}/submissions
        The form is expected to have 'email' and optionally 'name' fields.
        """
        url = f"https://api.netlify.com/api/v1/forms/{NETLIFY_FORM_ID}/submissions"
        headers = {"Authorization": f"Bearer {NETLIFY_API_TOKEN}"}

        subscribers = []
        page = 1
        per_page = 100

        while True:
            try:
                resp = requests.get(
                    url,
                    headers=headers,
                    params={"page": page, "per_page": per_page},
                    timeout=15,
                )
                resp.raise_for_status()
            except requests.RequestException as e:
                print(f"   ⚠  Netlify API error (page {page}): {e}")
                break

            data = resp.json()
            if not data:
                break

            for submission in data:
                body = submission.get("data", {})
                email = body.get("email", "").strip().lower()
                if not email or "@" not in email:
                    continue
                created = submission.get("created_at", "")
                if created:
                    try:
                        created = datetime.fromisoformat(
                            created.replace("Z", "+00:00")
                        ).date().isoformat()
                    except ValueError:
                        created = date.today().isoformat()
                else:
                    created = date.today().isoformat()

                subscribers.append({
                    "email": email,
                    "name": body.get("name", "").strip(),
                    "subscribed_at": created,
                    "source": "netlify",
                })

            if len(data) < per_page:
                break
            page += 1

        print(f"   ↳ Fetched {len(subscribers)} subscribers from Netlify Forms")
        return subscribers

    def _fetch_unsubscribes(self) -> set:
        """Return a set of lowercased emails that have submitted the unsubscribe form."""
        url = f"https://api.netlify.com/api/v1/forms/{NETLIFY_UNSUBSCRIBE_FORM_ID}/submissions"
        headers = {"Authorization": f"Bearer {NETLIFY_API_TOKEN}"}
        emails = set()
        page = 1

        while True:
            try:
                resp = requests.get(
                    url,
                    headers=headers,
                    params={"page": page, "per_page": 100},
                    timeout=15,
                )
                resp.raise_for_status()
            except requests.RequestException as e:
                print(f"   ⚠  Unsubscribe form fetch error (page {page}): {e}")
                break

            data = resp.json()
            if not data:
                break

            for submission in data:
                email = submission.get("data", {}).get("email", "").strip().lower()
                if email and "@" in email:
                    emails.add(email)

            if len(data) < 100:
                break
            page += 1

        if emails:
            print(f"   ↳ Found {len(emails)} unsubscribe request(s)")
        return emails

    # ------------------------------------------------------------------
    # Local JSON cache
    # ------------------------------------------------------------------

    def _load_local(self) -> list[dict]:
        if not os.path.exists(SUBSCRIBERS_FILE):
            return []
        try:
            with open(SUBSCRIBERS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            return []

    def _save_local(self, subscribers: list[dict]) -> None:
        with open(SUBSCRIBERS_FILE, "w", encoding="utf-8") as f:
            json.dump(subscribers, f, indent=2, ensure_ascii=False)

    def _merge(self, local: list[dict], remote: list[dict]) -> list[dict]:
        """Merge two subscriber lists, deduplicating by email (case-insensitive)."""
        seen = {}
        for s in local:
            seen[s["email"].lower()] = s
        for s in remote:
            key = s["email"].lower()
            if key not in seen:
                seen[key] = s
        return list(seen.values())

    def _ensure_data_dir(self) -> None:
        os.makedirs(os.path.dirname(SUBSCRIBERS_FILE), exist_ok=True)
