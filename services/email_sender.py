"""
Email Sender — delivers the newsletter via the Resend API.

Sends one email per subscriber so each gets a personalized
unsubscribe link ({{unsubscribe_url}} placeholder in the HTML).
"""

import html as html_lib
import time
import resend
from config import (
    RESEND_API_KEY,
    NEWSLETTER_FROM_EMAIL,
    NEWSLETTER_FROM_NAME,
    NEWSLETTER_BCC_EMAIL,
    UNSUBSCRIBE_BASE_URL,
)

# Resend free tier: 3,000 emails/month, 100/day.
# Add a small delay between sends to stay polite on their API.
SEND_DELAY_SECONDS = 0.1


class EmailSender:
    def __init__(self):
        resend.api_key = RESEND_API_KEY
        self.from_address = f"{NEWSLETTER_FROM_NAME} <{NEWSLETTER_FROM_EMAIL}>"

    def send_newsletter(
        self,
        html_content: str,
        subject: str,
        subscribers: list[dict],
    ) -> dict:
        """
        Send the newsletter to every subscriber.
        Returns a summary dict with sent/failed counts.
        """
        sent = 0
        failed = []

        for subscriber in subscribers:
            email = subscriber["email"]
            name = subscriber.get("name", "")

            personalized_html = self._personalize(html_content, email, name)

            params = {
                "from": self.from_address,
                "to": [email],
                "subject": subject,
                "html": personalized_html,
            }
            if NEWSLETTER_BCC_EMAIL:
                params["bcc"] = [NEWSLETTER_BCC_EMAIL]

            try:
                resend.Emails.send(params)
                sent += 1
                print(f"   ✓ Sent → {email}")
            except Exception as e:
                failed.append(email)
                print(f"   ✗ Failed → {email}: {e}")

            time.sleep(SEND_DELAY_SECONDS)

        results = {"sent": sent, "failed": failed}
        if failed:
            print(f"\n   ⚠  {len(failed)} failed: {', '.join(failed)}")
        return results

    def send_test(self, html_content: str, subject: str, test_email: str) -> None:
        """Send a single test email to verify the newsletter looks right."""
        personalized_html = self._personalize(html_content, test_email, "Test Subscriber")
        params = {
            "from": self.from_address,
            "to": [test_email],
            "subject": f"[TEST] {subject}",
            "html": personalized_html,
        }
        resend.Emails.send(params)
        print(f"   ✓ Test email sent to {test_email}")

    def _personalize(self, html: str, email: str, name: str) -> str:
        """Replace placeholders with subscriber-specific values."""
        import urllib.parse

        encoded_email = urllib.parse.quote(email)
        unsubscribe_url = f"{UNSUBSCRIBE_BASE_URL}?email={encoded_email}"

        html = html.replace("{{unsubscribe_url}}", unsubscribe_url)
        html = html.replace("{{subscriber_name}}", html_lib.escape(name) if name else "there")
        html = html.replace("{{subscriber_email}}", html_lib.escape(email))
        return html
