import os
from dotenv import load_dotenv

load_dotenv()

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
RESEND_API_KEY = os.getenv("RESEND_API_KEY")
NETLIFY_API_TOKEN = os.getenv("NETLIFY_API_TOKEN")
NETLIFY_FORM_ID = os.getenv("NETLIFY_FORM_ID")
NETLIFY_UNSUBSCRIBE_FORM_ID = os.getenv("NETLIFY_UNSUBSCRIBE_FORM_ID", "")
NEWSLETTER_FROM_EMAIL = os.getenv("NEWSLETTER_FROM_EMAIL", "newsletter@socalaisolutions.com")
NEWSLETTER_FROM_NAME = os.getenv("NEWSLETTER_FROM_NAME", "SoCal AI Solutions")
NEWSLETTER_BCC_EMAIL = os.getenv("NEWSLETTER_BCC_EMAIL", "")

UNSUBSCRIBE_BASE_URL = os.getenv("UNSUBSCRIBE_BASE_URL", "https://socalaisolutions.org/unsubscribe")
SUBSCRIBERS_FILE = os.path.join(os.path.dirname(__file__), "data", "subscribers.json")


def validate_config():
    missing = []
    if not ANTHROPIC_API_KEY:
        missing.append("ANTHROPIC_API_KEY")
    if not RESEND_API_KEY:
        missing.append("RESEND_API_KEY")
    if not NEWSLETTER_FROM_EMAIL or NEWSLETTER_FROM_EMAIL == "newsletter@yourdomain.com":
        missing.append("NEWSLETTER_FROM_EMAIL (must be a verified Resend sender)")
    if missing:
        raise EnvironmentError(
            f"Missing required environment variables: {', '.join(missing)}\n"
            f"Copy .env.example to .env and fill in your values."
        )
