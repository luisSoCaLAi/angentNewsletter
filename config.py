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

UNSUBSCRIBE_BASE_URL = os.getenv("UNSUBSCRIBE_BASE_URL") or "https://socalaisolutions.com/unsubscribe"
SUBSCRIBERS_FILE = os.path.join(os.path.dirname(__file__), "data", "subscribers.json")

# LinkedIn (populated by setup_linkedin.py --auth)
LINKEDIN_CLIENT_ID = os.getenv("LINKEDIN_CLIENT_ID", "")
LINKEDIN_CLIENT_SECRET = os.getenv("LINKEDIN_CLIENT_SECRET", "")
LINKEDIN_ACCESS_TOKEN = os.getenv("LINKEDIN_ACCESS_TOKEN", "")
LINKEDIN_REFRESH_TOKEN = os.getenv("LINKEDIN_REFRESH_TOKEN", "")
LINKEDIN_TOKEN_EXPIRY = os.getenv("LINKEDIN_TOKEN_EXPIRY", "0")
LINKEDIN_ORGANIZATION_ID = os.getenv("LINKEDIN_ORGANIZATION_ID", "")
LINKEDIN_MEMBER_URN = os.getenv("LINKEDIN_MEMBER_URN", "")


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


def validate_linkedin_config():
    """Called before LinkedIn posting — separate from core validate_config so
    dry-run and test modes don't require LinkedIn credentials."""
    missing = []
    if not LINKEDIN_CLIENT_ID:
        missing.append("LINKEDIN_CLIENT_ID")
    if not LINKEDIN_CLIENT_SECRET:
        missing.append("LINKEDIN_CLIENT_SECRET")
    if not LINKEDIN_ACCESS_TOKEN:
        missing.append("LINKEDIN_ACCESS_TOKEN (run: python setup_linkedin.py --auth)")
    if not LINKEDIN_ORGANIZATION_ID and not LINKEDIN_MEMBER_URN:
        missing.append("LINKEDIN_MEMBER_URN or LINKEDIN_ORGANIZATION_ID (run: python setup_linkedin.py --auth)")
    if missing:
        raise EnvironmentError(
            f"Missing LinkedIn environment variables: {', '.join(missing)}\n"
            f"Run: python setup_linkedin.py --auth"
        )
