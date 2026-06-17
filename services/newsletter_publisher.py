"""
Newsletter Publisher — copies the weekly newsletter HTML to the public website
and deploys it to Netlify so it can be linked from LinkedIn.

Output URL: https://socalaisolutions.com/newsletters/YYYY-MM-DD

Local mode (default): copies file to WEBSITE_DIR, runs netlify-cli deploy.
GitHub Actions mode:  uses the Netlify Deploy API to add only the newsletter
                      file to the existing live site (no local website checkout needed).
"""

import hashlib
import os
import re
import subprocess
import time

import requests

# Local website path — override via WEBSITE_DIR env var.
_DEFAULT_WEBSITE_DIR = r"C:\Users\luisn\Desktop\neptune\socalai-website"
WEBSITE_DIR = os.getenv("WEBSITE_DIR", _DEFAULT_WEBSITE_DIR)
NEWSLETTERS_DIR = os.path.join(WEBSITE_DIR, "newsletters")

NETLIFY_API = "https://api.netlify.com/api/v1"

# Subscribe banner injected at the top of the web version
_SUBSCRIBE_BANNER = """\
<div style="background:#4f46e5;padding:14px 24px;text-align:center;font-family:Arial,sans-serif;">
  <span style="color:#fff;font-size:14px;">
    📬 Enjoying this? Get AI insights in your inbox every Tuesday &mdash;
    <a href="https://socalaisolutions.com/#newsletter"
       style="color:#fff;font-weight:bold;text-decoration:underline;">Subscribe free</a>
  </span>
</div>
"""


class NewsletterPublisher:
    def publish(self, html: str, date_str: str) -> str:
        """
        Prepare the newsletter for web and deploy to Netlify.
        Returns the public URL.

        In GitHub Actions (GITHUB_ACTIONS=true), deploys via Netlify API so no
        local website checkout is required. Locally, copies to WEBSITE_DIR and
        runs the netlify-cli.
        """
        web_html = self._prepare_for_web(html)
        url = f"https://socalaisolutions.com/newsletters/{date_str}"

        if os.getenv("GITHUB_ACTIONS") == "true":
            self._deploy_via_api(web_html, date_str)
        else:
            self._deploy_local(web_html, date_str)

        return url

    # ── Deploy strategies ────────────────────────────────────────────────────

    def _deploy_local(self, html: str, date_str: str) -> None:
        """Copy newsletter to local website dir and run netlify-cli."""
        os.makedirs(NEWSLETTERS_DIR, exist_ok=True)
        dest = os.path.join(NEWSLETTERS_DIR, f"{date_str}.html")
        with open(dest, "w", encoding="utf-8") as f:
            f.write(html)
        self._run_netlify_cli()

    def _deploy_via_api(self, html: str, date_str: str) -> None:
        """
        Deploy only the newsletter file to the live Netlify site using the
        Deploy API. Preserves all existing site content.
        """
        api_token = os.getenv("NETLIFY_API_TOKEN", "")
        site_id = os.getenv("NETLIFY_SITE_ID", "")
        if not api_token or not site_id:
            raise EnvironmentError(
                "NETLIFY_API_TOKEN and NETLIFY_SITE_ID must be set for GitHub Actions deploy."
            )

        headers = {
            "Authorization": f"Bearer {api_token}",
            "Content-Type": "application/json",
        }
        html_bytes = html.encode("utf-8")
        file_sha1 = hashlib.sha1(html_bytes).hexdigest()
        newsletter_path = f"/newsletters/{date_str}.html"

        # 1. Fetch the current live deploy's file list
        resp = requests.get(
            f"{NETLIFY_API}/sites/{site_id}/deploys",
            headers=headers,
            params={"per_page": 1},
            timeout=15,
        )
        resp.raise_for_status()
        deploys = resp.json()
        if not deploys:
            raise RuntimeError("No existing Netlify deploys found for site.")

        latest_deploy_id = deploys[0]["id"]
        resp = requests.get(
            f"{NETLIFY_API}/deploys/{latest_deploy_id}/files",
            headers=headers,
            timeout=15,
        )
        resp.raise_for_status()
        existing_files = resp.json()

        # Build file digest map: path → sha1
        file_map = {f["id"]: f["sha"] for f in existing_files if "id" in f and "sha" in f}
        # Add (or overwrite) the newsletter file
        file_map[newsletter_path] = file_sha1

        # 2. Create a new deploy
        resp = requests.post(
            f"{NETLIFY_API}/sites/{site_id}/deploys",
            headers=headers,
            json={"files": file_map},
            timeout=15,
        )
        resp.raise_for_status()
        deploy = resp.json()
        deploy_id = deploy["id"]
        required = deploy.get("required", [])

        # 3. Upload only the files Netlify says it needs (should just be the newsletter)
        if file_sha1 in required:
            upload_headers = {
                "Authorization": f"Bearer {api_token}",
                "Content-Type": "application/octet-stream",
            }
            resp = requests.put(
                f"{NETLIFY_API}/deploys/{deploy_id}/files{newsletter_path}",
                headers=upload_headers,
                data=html_bytes,
                timeout=30,
            )
            resp.raise_for_status()

        # 4. Wait for the deploy to go live (max ~60s)
        self._wait_for_deploy(deploy_id, headers)

    def _wait_for_deploy(self, deploy_id: str, headers: dict, timeout: int = 60) -> None:
        deadline = time.time() + timeout
        while time.time() < deadline:
            resp = requests.get(
                f"{NETLIFY_API}/deploys/{deploy_id}",
                headers=headers,
                timeout=10,
            )
            resp.raise_for_status()
            state = resp.json().get("state", "")
            if state == "ready":
                return
            if state in ("error", "failed"):
                raise RuntimeError(f"Netlify deploy {deploy_id} failed (state: {state})")
            time.sleep(3)
        raise TimeoutError(f"Netlify deploy {deploy_id} did not go live within {timeout}s")

    def _run_netlify_cli(self) -> None:
        """Run the Netlify CLI deploy and stream output."""
        cmd = f'netlify deploy --dir "{WEBSITE_DIR}" --prod'
        result = subprocess.run(
            cmd,
            cwd=WEBSITE_DIR,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=120,
            shell=True,
        )
        if result.returncode != 0:
            raise RuntimeError(
                f"Netlify deploy failed:\n{result.stdout}\n{result.stderr}"
            )
        for line in result.stdout.splitlines():
            if "Website URL" in line or "Live URL" in line or "socalaisolutions" in line:
                print(f"   {line.strip()}")
                break

    # ── HTML preparation ─────────────────────────────────────────────────────

    def _prepare_for_web(self, html: str) -> str:
        """Clean up email-specific content and add web subscribe banner."""
        html = re.sub(
            r"<p[^>]*>Don't want these emails\?.*?</p>",
            "",
            html,
            flags=re.DOTALL | re.IGNORECASE,
        )
        html = html.replace("%%UNSUBSCRIBE_URL%%", "#")

        if "<body" in html.lower():
            html = re.sub(
                r"(<body[^>]*>)",
                r"\1" + _SUBSCRIBE_BANNER,
                html,
                count=1,
                flags=re.IGNORECASE,
            )
        else:
            html = _SUBSCRIBE_BANNER + html

        return html
