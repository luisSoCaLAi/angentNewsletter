"""
Writer Agent — uses Claude Opus 4.6 to write a polished HTML newsletter
from the research topics, branded for SoCal AI Solutions.
"""

import time
from datetime import datetime
import anthropic
import httpx
from config import ANTHROPIC_API_KEY, NEWSLETTER_FROM_NAME

SYSTEM_PROMPT = f"""You are a senior content writer for {NEWSLETTER_FROM_NAME}, \
an AI consulting firm helping small and medium businesses across the US adopt AI.

You write the weekly "AI Insider" newsletter. Your writing style is:
- Conversational yet professional (think trusted advisor, not robot)
- Action-oriented: every topic ends with a practical takeaway SMBs can use
- Enthusiastic about AI but grounded in real business value
- Inclusive: speaks to business owners nationwide, not tied to any region

You output ONLY valid HTML — no markdown, no explanations, just the HTML body content \
(no <html>, <head>, or <body> tags — just the inner content)."""


HTML_TEMPLATE_PROMPT = """Write the HTML body for this week's "AI Insider" newsletter.

Use this responsive email-safe HTML structure:

---
REQUIRED SECTIONS (in order):
1. Header banner with newsletter name and issue date
2. Brief intro paragraph (2-3 sentences, warm and welcoming)
3. Three article sections — one per topic below
4. "Until Next Week" sign-off section with CTA to visit the website
5. Footer with unsubscribe link — MUST include this exact HTML verbatim, do not change the placeholder text:
   <p style="margin:0;font-size:12px;color:#999;">Don't want these emails? <a href="%%UNSUBSCRIBE_URL%%" style="color:#999;">Unsubscribe</a></p>

---
STYLING REQUIREMENTS:
- Inline CSS only (email clients strip stylesheets)
- Max width: 600px, centered, white background
- Header: dark background (#1a1a2e), use this exact logo img tag followed by the newsletter name and date:
  <img src="https://socalaisolutions.org/assets/logo-dark.png" alt="SoCal A.I. Solutions" style="height:48px;width:auto;display:block;margin:0 auto 12px;">
  Do NOT use any emoji or placeholder — use the img tag above.
- Topic sections: alternating slightly warm background (#f9f9f9 / white), left border accent (#4f46e5)
- "Business Impact" callout box: light purple background (#ede9fe), border-radius
- Body font: Arial/sans-serif, 16px, #333 color, 1.6 line-height
- Links: #4f46e5 (indigo)
- CTA button: #4f46e5 background, white text, border-radius: 6px
- Mobile: works at 320px minimum width

---
TOPICS TO COVER:
{topics_json}

---
WEBSITE URL: https://www.socalaisolutions.com

Output ONLY the HTML. No preamble, no markdown code fences."""


SUBJECT_PROMPT = """Based on these 3 AI topics for this week's newsletter, \
write ONE compelling email subject line.

Rules:
- Max 55 characters
- No clickbait or ALL CAPS
- Should convey real value, not hype
- Can reference "this week" or be timely
- Examples of good format: "3 AI tools SMBs are using right now" or \
"This week in AI: What matters for your business"

Topics:
{topic_titles}

Return ONLY the subject line text, nothing else."""


class WriterAgent:
    def __init__(self):
        self.client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

    def _with_retry(self, fn, retries=3, wait=65):
        """Call fn(), retrying on rate-limit or transient network errors."""
        for attempt in range(retries):
            try:
                return fn()
            except anthropic.RateLimitError:
                if attempt == retries - 1:
                    raise
                print(f"   Rate limit hit — waiting {wait}s before retry ({attempt + 1}/{retries - 1})...")
                time.sleep(wait)
            except (httpx.ReadError, httpx.RemoteProtocolError, anthropic.APIConnectionError):
                if attempt == retries - 1:
                    raise
                print(f"   Network error — retrying in 10s ({attempt + 1}/{retries - 1})...")
                time.sleep(10)

    def write(self, topics: list[dict]) -> str:
        """Generate the full HTML newsletter body from research topics."""
        import json

        topics_json = json.dumps(topics, indent=2)
        user_prompt = HTML_TEMPLATE_PROMPT.format(topics_json=topics_json)

        def _call():
            response = self.client.messages.create(
                model="claude-sonnet-4-6",
                max_tokens=4096,
                system=SYSTEM_PROMPT,
                messages=[{"role": "user", "content": user_prompt}],
            )
            return response.content[0].text

        html = self._with_retry(_call)

        # Strip any accidental markdown fences
        html = html.strip()
        if html.startswith("```"):
            html = html.split("\n", 1)[1]
            if html.endswith("```"):
                html = html.rsplit("```", 1)[0]

        return html.strip()

    def generate_subject(self, topics: list[dict]) -> str:
        """Generate the email subject line from the topic titles."""
        topic_titles = "\n".join(f"- {t['title']}" for t in topics)
        user_prompt = SUBJECT_PROMPT.format(topic_titles=topic_titles)

        def _call():
            return self.client.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=128,
                messages=[{"role": "user", "content": user_prompt}],
            )

        response = self._with_retry(_call)
        return response.content[0].text.strip().strip('"').strip("'")

    def build_full_html(self, body_html: str) -> str:
        """Wrap the body HTML in a complete, email-safe HTML document."""
        today = datetime.now().strftime("%B %d, %Y")
        return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>AI Insider — {today}</title>
</head>
<body style="margin:0;padding:0;background-color:#f4f4f4;font-family:Arial,sans-serif;">
{body_html}
</body>
</html>"""
