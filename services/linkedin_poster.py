"""
LinkedIn Poster — posts the weekly newsletter to the SoCal AI Solutions company page.

Flow:
  1. Check access token freshness (auto-refresh if expiring within 7 days)
  2. Generate varied post copy using Claude Haiku
  3. POST to LinkedIn ugcPosts API as the organization
"""

import os
import time
import json
import requests
import anthropic
from dotenv import load_dotenv, set_key

# Path to .env for token write-back
_ENV_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env")

LINKEDIN_API_BASE = "https://api.linkedin.com/v2"

# Rotate through these tones so the opener never feels repetitive
_TONE_ROTATION = [
    "energetic and punchy — one bold statement",
    "direct and data-driven — lead with a specific insight or number",
    "conversational and curious — pose a quick question to the reader",
    "authoritative and confident — state a trend as fact",
    "friendly and inclusive — speak directly to the SMB owner's daily reality",
]

_SYSTEM_PROMPT = """\
You write short LinkedIn posts for SoCal A.I. Solutions, an AI consulting firm for California small businesses.
Brand voice: trusted advisor, practical, no hype, speaks to real business owners (contractors, consultants, retailers).
You write ONLY the post text — no quotes, no explanations, no markdown beyond newlines and → arrows.
The post must stay under 700 characters total (LinkedIn limit).
Never start with "I" or "We". Never use em-dashes. No hashtags — those are added separately.
"""


class LinkedInPoster:
    def __init__(self):
        load_dotenv(_ENV_PATH, override=True)
        self.client_id = os.getenv("LINKEDIN_CLIENT_ID", "")
        self.client_secret = os.getenv("LINKEDIN_CLIENT_SECRET", "")
        self.org_id = os.getenv("LINKEDIN_ORGANIZATION_ID", "")
        self.member_urn = os.getenv("LINKEDIN_MEMBER_URN", "")
        self.anthropic = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

    # ── Public interface ────────────────────────────────────────────────────

    def post_newsletter(self, topics: list, subject: str, newsletter_url: str) -> str:
        """Generate post copy and publish to LinkedIn. Returns the post URN."""
        token = self._get_valid_token()
        post_text = self._generate_post_copy(topics, newsletter_url)
        post_urn = self._post_to_linkedin(token, post_text)
        print(f"   Copy preview:\n{self._indent(post_text)}")
        return post_urn

    # ── Copy generation ─────────────────────────────────────────────────────

    def _generate_post_copy(self, topics: list, newsletter_url: str) -> str:
        topic_lines = "\n".join(f"→ {t['title']}" for t in topics)

        # Rotate tone based on week number so it varies predictably
        week_num = int(time.strftime("%W"))
        tone = _TONE_ROTATION[week_num % len(_TONE_ROTATION)]

        user_prompt = f"""\
Write a LinkedIn post announcing this week's AI Insider newsletter.

Tone this week: {tone}

Newsletter topics:
{topic_lines}

Newsletter URL: {newsletter_url}

Required structure (use this exact layout, fill in the bracketed parts):
[1-2 sentence opener matching the tone above]

This week's AI Insider covers:
→ [Topic 1 title]
→ [Topic 2 title]
→ [Topic 3 title]

[1 sentence subscribe CTA — vary the wording, e.g. "Free in your inbox every Tuesday." or "Join CA business owners getting this every week."]
👉 {newsletter_url}

Do NOT add hashtags — those are added automatically.
Do NOT exceed 650 characters for the parts you write (the URL line is added separately).\
"""

        response = self.anthropic.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=400,
            system=_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_prompt}],
        )

        post_body = response.content[0].text.strip()

        hashtags = "#AIAutomation #SmallBusiness #CaliforniaAI #AIInsider #SoCal"
        return f"{post_body}\n\n{hashtags}"

    # ── LinkedIn API ────────────────────────────────────────────────────────

    def _post_to_linkedin(self, token: str, text: str) -> str:
        """Post text to LinkedIn using the Posts API. Uses org page if org_id is set."""
        if self.org_id:
            author = f"urn:li:organization:{self.org_id}"
        elif self.member_urn:
            author = self.member_urn
        else:
            raise ValueError(
                "Neither LINKEDIN_ORGANIZATION_ID nor LINKEDIN_MEMBER_URN is set in .env. "
                "Run: python setup_linkedin.py --auth"
            )

        # LinkedIn Posts API (replaces deprecated ugcPosts)
        url = "https://api.linkedin.com/rest/posts"
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "X-Restli-Protocol-Version": "2.0.0",
            "LinkedIn-Version": "202506",
        }
        payload = {
            "author": author,
            "commentary": text,
            "visibility": "PUBLIC",
            "distribution": {
                "feedDistribution": "MAIN_FEED",
                "targetEntities": [],
                "thirdPartyDistributionChannels": [],
            },
            "lifecycleState": "PUBLISHED",
            "isReshareDisabledByAuthor": False,
        }

        resp = requests.post(url, headers=headers, json=payload, timeout=15)

        if resp.status_code == 201:
            post_urn = resp.headers.get("X-RestLi-Id", "unknown")
            return post_urn
        else:
            raise RuntimeError(
                f"LinkedIn post failed [{resp.status_code}]: {resp.text}"
            )

    # ── Token management ────────────────────────────────────────────────────

    def _get_valid_token(self) -> str:
        load_dotenv(_ENV_PATH, override=True)
        access_token = os.getenv("LINKEDIN_ACCESS_TOKEN", "")
        expiry_str = os.getenv("LINKEDIN_TOKEN_EXPIRY", "0")

        if not access_token:
            raise EnvironmentError(
                "LINKEDIN_ACCESS_TOKEN not set. Run: python setup_linkedin.py --auth"
            )

        expiry = float(expiry_str)
        if expiry == 0.0:
            # Expiry not recorded — assume token is valid and skip refresh check
            return access_token
        seven_days = 7 * 24 * 3600
        if time.time() > (expiry - seven_days):
            print("   Access token expiring soon — refreshing...")
            access_token = self._refresh_access_token()

        return access_token

    def _refresh_access_token(self) -> str:
        refresh_token = os.getenv("LINKEDIN_REFRESH_TOKEN", "")
        if not refresh_token:
            raise EnvironmentError(
                "LINKEDIN_REFRESH_TOKEN not set. Re-run: python setup_linkedin.py --auth"
            )

        resp = requests.post(
            "https://www.linkedin.com/oauth/v2/accessToken",
            data={
                "grant_type": "refresh_token",
                "refresh_token": refresh_token,
                "client_id": self.client_id,
                "client_secret": self.client_secret,
            },
            timeout=15,
        )

        if resp.status_code != 200:
            raise RuntimeError(
                f"Token refresh failed [{resp.status_code}]: {resp.text}\n"
                "Re-run: python setup_linkedin.py --auth"
            )

        data = resp.json()
        new_access = data["access_token"]
        new_expiry = str(time.time() + data.get("expires_in", 5184000))  # default 60 days
        new_refresh = data.get("refresh_token", refresh_token)

        # Write back to .env
        set_key(_ENV_PATH, "LINKEDIN_ACCESS_TOKEN", new_access)
        set_key(_ENV_PATH, "LINKEDIN_TOKEN_EXPIRY", new_expiry)
        set_key(_ENV_PATH, "LINKEDIN_REFRESH_TOKEN", new_refresh)

        print("   ✓ Tokens refreshed and saved to .env")
        return new_access

    # ── Util ────────────────────────────────────────────────────────────────

    @staticmethod
    def _indent(text: str) -> str:
        return "\n".join(f"      {line}" for line in text.splitlines())
