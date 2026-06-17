# -*- coding: utf-8 -*-
"""
LinkedIn OAuth Setup — one-time script to authorize the newsletter agent
to post to the SoCal AI Solutions company page.

Usage:
  python setup_linkedin.py --auth        # Full OAuth flow → saves tokens to .env
  python setup_linkedin.py --org-id      # Fetch and print your organization ID
  python setup_linkedin.py --test-post   # Post a test message to verify everything works
"""

import argparse
import os
import sys
import time
import json
import webbrowser
import urllib.parse
from http.server import HTTPServer, BaseHTTPRequestHandler
from dotenv import load_dotenv, set_key
import requests

_ENV_PATH = os.path.join(os.path.dirname(__file__), ".env")
LINKEDIN_API_BASE = "https://api.linkedin.com/v2"
REDIRECT_URI = "http://localhost:8000/callback"
SCOPES = "w_member_social openid profile"

load_dotenv(_ENV_PATH, override=True)


# ── OAuth callback handler ──────────────────────────────────────────────────

_auth_code: str = ""


class _CallbackHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        global _auth_code
        parsed = urllib.parse.urlparse(self.path)
        params = urllib.parse.parse_qs(parsed.query)

        if "code" in params:
            _auth_code = params["code"][0]
            self.send_response(200)
            self.send_header("Content-type", "text/html")
            self.end_headers()
            self.wfile.write(b"""
                <html><body style="font-family:sans-serif;text-align:center;padding:60px">
                <h2 style="color:#4f46e5">Authorization successful!</h2>
                <p>You can close this tab and return to the terminal.</p>
                </body></html>
            """)
        else:
            error = params.get("error_description", ["Unknown error"])[0]
            self.send_response(400)
            self.send_header("Content-type", "text/html")
            self.end_headers()
            self.wfile.write(f"<html><body>Error: {error}</body></html>".encode())

    def log_message(self, *args):
        pass  # suppress request logs


# ── Auth flow ───────────────────────────────────────────────────────────────

def run_auth():
    client_id = os.getenv("LINKEDIN_CLIENT_ID", "").strip()
    client_secret = os.getenv("LINKEDIN_CLIENT_SECRET", "").strip()

    if not client_id or not client_secret:
        print("\nMissing LINKEDIN_CLIENT_ID or LINKEDIN_CLIENT_SECRET in .env")
        print("Add them first:\n")
        print("  LINKEDIN_CLIENT_ID=your_client_id")
        print("  LINKEDIN_CLIENT_SECRET=your_client_secret\n")
        sys.exit(1)

    # Build auth URL
    params = {
        "response_type": "code",
        "client_id": client_id,
        "redirect_uri": REDIRECT_URI,
        "scope": SCOPES,
        "state": "newsletter_agent",
    }
    auth_url = "https://www.linkedin.com/oauth/v2/authorization?" + urllib.parse.urlencode(params)

    print("\n" + "=" * 60)
    print("  LinkedIn OAuth Authorization")
    print("=" * 60)
    print("\nOpening your browser to LinkedIn authorization page...")
    print("Log in with the account that ADMINISTERS the SoCal AI Solutions company page.\n")
    webbrowser.open(auth_url)

    # Start local callback server
    server = HTTPServer(("localhost", 8000), _CallbackHandler)
    server.timeout = 300
    print("Waiting for authorization (5 min timeout)...")
    server.handle_request()

    if not _auth_code:
        print("ERROR: No authorization code received.")
        sys.exit(1)

    # Exchange code for tokens
    resp = requests.post(
        "https://www.linkedin.com/oauth/v2/accessToken",
        data={
            "grant_type": "authorization_code",
            "code": _auth_code,
            "redirect_uri": REDIRECT_URI,
            "client_id": client_id,
            "client_secret": client_secret,
        },
        timeout=15,
    )

    if resp.status_code != 200:
        print(f"ERROR: Token exchange failed [{resp.status_code}]: {resp.text}")
        sys.exit(1)

    data = resp.json()
    access_token = data["access_token"]
    refresh_token = data.get("refresh_token", "")
    expires_in = data.get("expires_in", 5184000)  # default 60 days
    expiry = str(time.time() + expires_in)

    # Save to .env
    set_key(_ENV_PATH, "LINKEDIN_ACCESS_TOKEN", access_token)
    set_key(_ENV_PATH, "LINKEDIN_TOKEN_EXPIRY", expiry)
    if refresh_token:
        set_key(_ENV_PATH, "LINKEDIN_REFRESH_TOKEN", refresh_token)

    print("\n✓ Tokens saved to .env")
    print(f"  Access token expires in: {expires_in // 86400} days")
    if refresh_token:
        print("  Refresh token: saved (auto-renewal enabled)")
    else:
        print("  NOTE: No refresh token returned. You may need to re-run --auth in 60 days.")

    # Fetch member URN via OpenID userinfo
    print("\nFetching your member URN...")
    ui_resp = requests.get(
        "https://api.linkedin.com/v2/userinfo",
        headers={"Authorization": f"Bearer {access_token}"},
        timeout=15,
    )
    if ui_resp.status_code == 200:
        sub = ui_resp.json().get("sub", "")
        if sub:
            set_key(_ENV_PATH, "LINKEDIN_MEMBER_URN", f"urn:li:person:{sub}")
            print(f"  ✓ Member URN saved (urn:li:person:{sub})")
        else:
            print("  WARNING: Could not extract sub from userinfo response.")
    else:
        print(f"  WARNING: Could not fetch userinfo [{ui_resp.status_code}] — posts will use org URN if set.")

    print("\nSetup complete. Run a test with:")
    print("  python setup_linkedin.py --test-post\n")


# ── Org ID fetch ────────────────────────────────────────────────────────────

def fetch_org_id(token: str = ""):
    if not token:
        load_dotenv(_ENV_PATH, override=True)
        token = os.getenv("LINKEDIN_ACCESS_TOKEN", "")
    if not token:
        print("No access token found. Run --auth first.")
        sys.exit(1)

    # Get the member's profile to find administered orgs
    resp = requests.get(
        f"{LINKEDIN_API_BASE}/organizationalEntityAcls",
        params={"q": "roleAssignee", "role": "ADMINISTRATOR", "projection": "(elements*(organizationalTarget~(id,vanityName,localizedName)))"},
        headers={
            "Authorization": f"Bearer {token}",
            "X-Restli-Protocol-Version": "2.0.0",
        },
        timeout=15,
    )

    if resp.status_code != 200:
        # Fallback: ask user to find it manually
        print(f"\nCould not auto-fetch org ID [{resp.status_code}].")
        print("Find it manually:")
        print("  1. Go to linkedin.com/company/socal-a-i-solutions-llc/admin/")
        print("  2. Look at the URL — it will contain a numeric ID")
        print("  3. OR check the URL when you click Edit Page")
        print("\nThen add to .env:")
        print("  LINKEDIN_ORGANIZATION_ID=<the numeric ID>")
        return

    data = resp.json()
    elements = data.get("elements", [])

    if not elements:
        print("\nNo administered organizations found for this account.")
        print("Make sure you logged in with the account that ADMINISTERS the company page.")
        return

    print("\nOrganizations you administer:")
    for el in elements:
        org = el.get("organizationalTarget~", {})
        org_id = org.get("id", "")
        name = org.get("localizedName", org.get("vanityName", "Unknown"))
        print(f"  {name}: {org_id}")

        # Auto-save if it looks like SoCal AI
        if "socal" in name.lower() or "ai solution" in name.lower():
            set_key(_ENV_PATH, "LINKEDIN_ORGANIZATION_ID", str(org_id))
            print(f"  ✓ Saved LINKEDIN_ORGANIZATION_ID={org_id} to .env")


# ── Test post ───────────────────────────────────────────────────────────────

def run_test_post():
    load_dotenv(_ENV_PATH, override=True)
    token = os.getenv("LINKEDIN_ACCESS_TOKEN", "")
    org_id = os.getenv("LINKEDIN_ORGANIZATION_ID", "")
    member_urn = os.getenv("LINKEDIN_MEMBER_URN", "")

    if not token:
        print("No access token. Run: python setup_linkedin.py --auth")
        sys.exit(1)

    if org_id:
        author = f"urn:li:organization:{org_id}"
        print("Posting as: company page")
    elif member_urn:
        author = member_urn
        print("Posting as: personal profile (company page posting requires Marketing Developer Platform approval)")
    else:
        print("No author URN. Run: python setup_linkedin.py --auth")
        sys.exit(1)

    test_text = (
        "Test post from the SoCal AI Solutions newsletter automation system. "
        "If you see this post, everything is working correctly. "
        "Please delete this post."
    )

    resp = requests.post(
        f"{LINKEDIN_API_BASE}/ugcPosts",
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "X-Restli-Protocol-Version": "2.0.0",
        },
        json={
            "author": author,
            "lifecycleState": "PUBLISHED",
            "specificContent": {
                "com.linkedin.ugc.ShareContent": {
                    "shareCommentary": {"text": test_text},
                    "shareMediaCategory": "NONE",
                }
            },
            "visibility": {
                "com.linkedin.ugc.MemberNetworkVisibility": "PUBLIC"
            },
        },
        timeout=15,
    )

    if resp.status_code == 201:
        post_urn = resp.headers.get("X-RestLi-Id", "unknown")
        print(f"\n✓ Test post published! URN: {post_urn}")
        print("Check your LinkedIn company page and delete the test post.")
    else:
        print(f"\nERROR [{resp.status_code}]: {resp.text}")
        if resp.status_code == 403:
            print("\nPermission denied. Make sure:")
            print("  1. Your app has 'Marketing Developer Platform' approved (check Products tab)")
            print("  2. You logged in as an ADMINISTRATOR of the company page")
            print("  3. The w_organization_social scope was granted")


# ── CLI ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="LinkedIn OAuth setup for SoCal AI Newsletter Agent"
    )
    parser.add_argument("--auth", action="store_true", help="Run OAuth flow, save tokens to .env")
    parser.add_argument("--org-id", action="store_true", help="Fetch and save your LinkedIn organization ID")
    parser.add_argument("--test-post", action="store_true", help="Post a test message to verify the setup")
    args = parser.parse_args()

    if args.auth:
        run_auth()
    elif args.org_id:
        fetch_org_id()
    elif args.test_post:
        run_test_post()
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
