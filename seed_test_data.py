#!/usr/bin/env python3
"""
CS Cheatsheet test data seeder.

Creates realistic Intercom test data to exercise every section of the CS Cheatsheet app:

  USER INFO section
    - Two contacts with all CDAs: segment, region, settings access, impersonation consent
    - A shared company with "Company created at" set ~2 years ago

  PROBLEM SUMMARIES section
    - Multi-problem conversation: 2 distinct issues (workflow + settings), with Fin + admin
      replies, multiple Intercom links (workflow, custom action, outbound, conversation),
      and 3 images
    - Single-problem conversation: 1 issue (Fin content sync), with admin reply,
      knowledge-hub + article + series links, and 2 images

  OPEN TICKETS section
    - 3 additional open tickets for the multi-problem contact
    - 2 additional open tickets for the single-problem contact

Usage:
    python seed_test_data.py --token YOUR_INTERCOM_TOKEN --admin-id YOUR_ADMIN_ID

Find your admin ID at:
    https://app.intercom.com/a/apps/YOUR_APP_ID/settings/teammates
    or by running: curl -H "Authorization: Bearer TOKEN" https://api.intercom.io/admins
"""

from __future__ import annotations

import argparse
import sys
import time
from datetime import datetime, timedelta, timezone

import httpx

API_BASE = "https://api.intercom.io"
API_VERSION = "2.11"

# Public placeholder images from picsum.photos — real JPEGs, no auth needed
IMGS = {
    "settings_error":  ("https://picsum.photos/seed/settingserror/600/400",  "blank settings page white screen"),
    "workflow_error":  ("https://picsum.photos/seed/workflowerror/600/400",  "workflow trigger history zero triggers"),
    "console_error":   ("https://picsum.photos/seed/consoleerror/600/400",   "chrome console showing 403 permissions error"),
    "fin_missing":     ("https://picsum.photos/seed/finmissing/600/400",     "Fin saying no return policy found"),
    "fin_fix":         ("https://picsum.photos/seed/finfix/600/400",         "Fin AI sources panel articles enabled"),
}


def img_tag(key: str) -> str:
    url, alt = IMGS[key]
    return f'<img src="{url}" alt="{alt}">'


# ─── HTTP client ──────────────────────────────────────────────────────────────

class IntercomClient:
    def __init__(self, token: str) -> None:
        self._headers = {
            "Authorization": f"Bearer {token}",
            "Intercom-Version": API_VERSION,
            "Accept": "application/json",
            "Content-Type": "application/json",
        }

    def get(self, path: str) -> dict:
        with httpx.Client(timeout=30.0) as c:
            r = c.get(f"{API_BASE}{path}", headers=self._headers)
            r.raise_for_status()
            return r.json()

    def post(self, path: str, data: dict) -> dict:
        with httpx.Client(timeout=30.0) as c:
            r = c.post(f"{API_BASE}{path}", headers=self._headers, json=data)
            r.raise_for_status()
            return r.json()


# ─── Intercom API helpers ─────────────────────────────────────────────────────

def get_app_id(client: IntercomClient) -> str:
    try:
        data = client.get("/admins")
        admins = data.get("admins") or []
        if admins:
            app = admins[0].get("app") or {}
            return str(app.get("id_code") or app.get("id") or "")
    except Exception as exc:
        print(f"  ⚠  Could not fetch app_id: {exc}")
    return "YOUR_APP_ID"


def create_company(client: IntercomClient) -> dict:
    two_years_ago = int((datetime.now(tz=timezone.utc) - timedelta(days=730)).timestamp())
    return client.post("/companies", {
        "company_id": f"cs-cheatsheet-test-{int(time.time())}",
        "name": "Acme Corp (CS Test)",
        "custom_attributes": {
            "Company created at": two_years_ago,
        },
    })


def create_contact(
    client: IntercomClient,
    name: str,
    email: str,
    segment: str,
    region: str,
    settings_access: bool,
    impersonation: bool,
) -> dict:
    return client.post("/contacts", {
        "name": name,
        "email": email,
        "role": "user",
        "custom_attributes": {
            "Support team customer segment": segment,
            "Support team customer region": region,
            "Can access workspace settings": settings_access,
            "Has impersonation consent": impersonation,
        },
    })


def attach_company(client: IntercomClient, contact_id: str, company_id: str) -> None:
    client.post(f"/contacts/{contact_id}/companies", {"id": company_id})


def new_conversation(client: IntercomClient, contact_id: str, body_html: str) -> dict:
    return client.post("/conversations", {
        "from": {"type": "user", "id": contact_id},
        "body": body_html,
    })


def reply_admin(client: IntercomClient, conv_id: str, admin_id: str, body_html: str) -> None:
    client.post(f"/conversations/{conv_id}/reply", {
        "message_type": "comment",
        "type": "admin",
        "admin_id": admin_id,
        "body": body_html,
    })


def reply_user(
    client: IntercomClient,
    conv_id: str,
    contact_id: str,
    admin_id: str,
    body_html: str,
) -> None:
    """Add a user reply; falls back to a labelled admin note if the API rejects it."""
    try:
        client.post(f"/conversations/{conv_id}/reply", {
            "message_type": "comment",
            "type": "user",
            "intercom_user_id": contact_id,
            "body": body_html,
        })
    except httpx.HTTPStatusError:
        # The REST API does not always allow user replies on programmatically-created
        # conversations — use a visually distinct admin note as fallback.
        reply_admin(
            client,
            conv_id,
            admin_id,
            f"<em>[Simulated customer reply]</em><br><br>{body_html}",
        )


# ─── Conversation builders ────────────────────────────────────────────────────

def build_multi_problem_conv(
    client: IntercomClient,
    contact_id: str,
    admin_id: str,
    app_id: str,
) -> str:
    """
    Creates a conversation with TWO distinct problems:
      1. Workflow 47823 not triggering (custom action OAuth expired)
      2. Workspace settings page blank (permissions cache stale)

    Includes: workflow link, custom action link, outbound link, conversation link,
    and 3 images spread across multiple messages.
    """
    a = app_id

    # Message 1 — customer opens ticket
    conv = new_conversation(client, contact_id, f"""
<p>Hello, I'm dealing with two urgent issues blocking our team right now.</p>

<p><strong>Problem 1 — Workflow stopped triggering</strong><br>
Our main customer onboarding workflow has had 0 triggers since yesterday afternoon.
Customers are not receiving their welcome messages. The workflow is:<br>
<a href="https://app.intercom.com/a/apps/{a}/workflows/47823">Workflow 47823 – Customer Onboarding</a></p>

<p><strong>Problem 2 — Workspace settings page is blank</strong><br>
When any of our admins click Settings we get a completely white screen.
This is blocking us from managing team permissions.</p>

<p>Screenshot of the blank settings page:<br>
{img_tag("settings_error")}</p>
""")
    conv_id = conv["id"]
    _pause()

    # Message 2 — Fin responds
    reply_admin(client, conv_id, admin_id, f"""
<p>Hi! I'm Fin, Intercom's AI agent. I can see both issues.</p>

<p>For the <strong>workflow issue</strong>, workflow 47823 shows 0 trigger events since
23:14 yesterday. This typically happens when a connected custom action endpoint goes
down or an OAuth token expires. I found this help article which covers the most
common causes:<br>
<a href="https://app.intercom.com/a/apps/{a}/articles/8834521">Troubleshooting workflow triggers (Article 8834521)</a></p>

<p>For the <strong>settings blank page</strong>, I'd recommend trying an incognito window
first — this rules out a browser cache issue. If the problem persists, it may be a
permissions layer bug that needs a teammate to investigate.</p>

<p>I'm escalating this now.</p>
""")
    _pause()

    # Message 3 — customer follows up with more detail + extra images
    reply_user(client, conv_id, contact_id, admin_id, f"""
<p>Tried incognito — still blank.</p>

<p>I also noticed our outbound email series hasn't sent for 20 hours now:<br>
<a href="https://app.intercom.com/a/apps/{a}/outbound/email/30291">Onboarding Email Series (Campaign 30291)</a></p>

<p>Workflow trigger history screenshot:<br>
{img_tag("workflow_error")}</p>

<p>Chrome DevTools showing the error on the settings page:<br>
{img_tag("console_error")}</p>
""")
    _pause()

    # Message 4 — admin digs in and finds root causes
    reply_admin(client, conv_id, admin_id, f"""
<p>Hi, I've investigated both issues.</p>

<p><strong>Problem 1 — Workflow root cause found</strong><br>
Workflow 47823 calls a custom action to sync data to your CRM:<br>
<a href="https://app.intercom.com/a/apps/{a}/custom-actions/15629">CRM Sync Custom Action (15629)</a><br>
The OAuth token for this action expired approximately 25 hours ago — which matches the
exact time triggers dropped to zero. The token refresh is failing due to a credential
rotation on the CRM side.</p>

<p>I also found a related open conversation from last week about this same action:<br>
<a href="https://app.intercom.com/a/apps/{a}/conversations/1234000001">Previous CRM sync report</a></p>

<p><strong>Problem 2 — Settings blank page</strong><br>
This is a known permissions-cache bug that appears after workspace ownership transfers.
I've cleared the cache on our end — please try again now.</p>

<p><strong>Possible next steps:</strong></p>
<ul>
  <li>Re-authorise the CRM sync custom action with updated OAuth credentials</li>
  <li>Test workflow 47823 manually once the custom action is reconnected</li>
  <li>Confirm settings page is now loading correctly</li>
</ul>
""")

    return conv_id


def build_single_problem_conv(
    client: IntercomClient,
    contact_id: str,
    admin_id: str,
    app_id: str,
) -> str:
    """
    Creates a conversation with ONE problem:
      Help Center articles are excluded from Fin's AI knowledge sources.

    Includes: knowledge hub link, article link, series link, report link, and 2 images.
    """
    a = app_id

    # Message 1 — customer opens ticket
    conv = new_conversation(client, contact_id, f"""
<p>Hi, our Help Center articles have completely disappeared from Fin's responses.</p>

<p>Customers are asking about our return policy and Fin says it has no information —
but the article is published and visible in our Help Center:<br>
<a href="https://app.intercom.com/a/apps/{a}/articles/7722088">Return Policy (Article 7722088)</a></p>

<p>I can see all articles are "Live" in the knowledge hub:<br>
<a href="https://app.intercom.com/a/apps/{a}/knowledge-hub">Knowledge Hub</a></p>

<p>Screenshot of Fin's incorrect "I don't know" response:<br>
{img_tag("fin_missing")}</p>
""")
    conv_id = conv["id"]
    _pause()

    # Message 2 — Fin responds and escalates
    reply_admin(client, conv_id, admin_id, f"""
<p>Hi! I'm Fin. I can see the issue you're describing.</p>

<p>Your articles are published but I'm not able to access them as knowledge sources.
This can happen when articles are removed from the AI source list, often during a
bulk edit operation. I'm also checking your Series configuration in case the
content is linked there:<br>
<a href="https://app.intercom.com/a/apps/{a}/series/9923">Customer Onboarding Series</a></p>

<p>I'm handing this to a support teammate who can check and fix the AI source configuration directly.</p>
""")
    _pause()

    # Message 3 — admin finds root cause and fixes it
    reply_admin(client, conv_id, admin_id, f"""
<p>Hi, I've found and fixed the issue.</p>

<p>During a bulk edit 3 days ago, 12 articles (including article 7722088) were
accidentally removed from Fin's AI content sources. The content analytics report
showed the drop-off clearly:<br>
<a href="https://app.intercom.com/a/apps/{a}/reports">Content Analytics Report</a></p>

<p>I've re-added all 12 articles to the AI sources. The knowledge sync takes up to
30 minutes to propagate.</p>

<p>Screenshot confirming the fix is applied:<br>
{img_tag("fin_fix")}</p>

<p>Can you test Fin's response to the return policy question in about 30 minutes?</p>
""")

    return conv_id


def create_open_ticket(
    client: IntercomClient,
    contact_id: str,
    subject: str,
    body: str,
) -> str:
    conv = new_conversation(
        client,
        contact_id,
        f"<p><strong>{subject}</strong></p><p>{body}</p>",
    )
    return conv["id"]


def _pause(seconds: float = 0.8) -> None:
    """Small delay between API calls to avoid rate-limiting."""
    time.sleep(seconds)


# ─── Main ─────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="Seed CS Cheatsheet test data in Intercom")
    parser.add_argument("--token", required=True, help="Intercom API token")
    parser.add_argument(
        "--admin-id",
        required=True,
        help="Your admin ID (used for replies — find at /admins or in your profile URL)",
    )
    args = parser.parse_args()

    client = IntercomClient(args.token)
    admin_id = args.admin_id

    print("\n══════════════════════════════════════════")
    print("   CS Cheatsheet — Test Data Seeder")
    print("══════════════════════════════════════════\n")

    # Workspace
    print("1/6  Fetching workspace info...")
    app_id = get_app_id(client)
    print(f"     App ID: {app_id}\n")

    # Company
    print("2/6  Creating test company...")
    company = create_company(client)
    company_id = company["id"]
    print(f"     ✓ {company['name']}  (id={company_id})\n")
    _pause()

    # Contacts
    print("3/6  Creating test contacts...")
    contact_multi = create_contact(
        client,
        name="Alex Chen (CS Test – Multi)",
        email=f"cs-test-multi-{int(time.time())}@example.com",
        segment="Enterprise",
        region="EMEA",
        settings_access=True,
        impersonation=False,
    )
    _pause()
    contact_single = create_contact(
        client,
        name="Jordan Lee (CS Test – Single)",
        email=f"cs-test-single-{int(time.time())}@example.com",
        segment="Mid-Market",
        region="Americas",
        settings_access=False,
        impersonation=True,
    )
    print(f"     ✓ {contact_multi['name']}  (id={contact_multi['id']})")
    print(f"     ✓ {contact_single['name']}  (id={contact_single['id']})\n")
    _pause()

    # Attach company
    print("4/6  Attaching contacts to company...")
    attach_company(client, contact_multi["id"], company_id)
    _pause()
    attach_company(client, contact_single["id"], company_id)
    print(f"     ✓ Both contacts linked to {company['name']}\n")
    _pause()

    # Main conversations
    print("5/6  Building test conversations...")
    print("     → Multi-problem conversation (workflow + settings issues)...")
    multi_conv_id = build_multi_problem_conv(client, contact_multi["id"], admin_id, app_id)
    print(f"       ✓ Conversation {multi_conv_id}")
    _pause(1.5)

    print("     → Single-problem conversation (Fin knowledge sync)...")
    single_conv_id = build_single_problem_conv(client, contact_single["id"], admin_id, app_id)
    print(f"       ✓ Conversation {single_conv_id}\n")
    _pause(1.5)

    # Open tickets
    print("6/6  Creating open tickets...")
    tickets_multi = [
        ("Webhook not firing on conversation close",
         "Our webhook endpoint receives all events except conversation.closed. "
         "We've verified the endpoint is reachable and the HMAC signature is correct."),
        ("CSV contact export generating empty files",
         "When I export the full contact list to CSV the downloaded file is empty (0 rows). "
         "This started after the latest workspace update."),
        ("Team inbox notification delay",
         "Agents are seeing a 15-20 minute delay on new conversation notifications. "
         "This is causing SLA breaches on our P1 queue."),
    ]
    for subject, body in tickets_multi:
        tid = create_open_ticket(client, contact_multi["id"], subject, body)
        print(f"     ✓ {subject[:50]}…  ({tid})")
        _pause()

    tickets_single = [
        ("API rate limits triggering unexpectedly",
         "We're hitting 429 errors on POST /conversations despite being well under "
         "the documented 500 req/min limit. Error spikes at exactly :00 and :30."),
        ("Custom bot routing conversations to wrong team",
         "Conversations tagged 'billing' are routing to the general support inbox "
         "instead of the billing team. Started after we renamed the billing team."),
    ]
    for subject, body in tickets_single:
        tid = create_open_ticket(client, contact_single["id"], subject, body)
        print(f"     ✓ {subject[:50]}…  ({tid})")
        _pause()

    # Summary
    base_url = f"https://app.intercom.com/a/apps/{app_id}/conversations"
    print(f"""
══════════════════════════════════════════
  ✅  TEST DATA CREATED
══════════════════════════════════════════

  App ID : {app_id}
  Company: {company['name']}  ({company_id})
           Created: ~2 years ago  → tenure shows in User Info section

  Contact 1 — Multi-Problem
    Name     : {contact_multi['name']}
    CDAs     : Enterprise · EMEA · Settings ✅ · Impersonation ❌
    Conversation → {base_url}/{multi_conv_id}
    Exercises:
      • 2 problems detected (workflow trigger + settings blank page)
      • Links: workflow, custom action, outbound, article, conversation
      • Images: 3 (settings error, workflow history, console error)
      • Open tickets: 3

  Contact 2 — Single-Problem
    Name     : {contact_single['name']}
    CDAs     : Mid-Market · Americas · Settings ❌ · Impersonation ✅
    Conversation → {base_url}/{single_conv_id}
    Exercises:
      • 1 problem (full detail shown inline, no More info button)
      • Links: knowledge hub, article, series, report
      • Images: 2 (Fin missing response, Fin fix confirmation)
      • Open tickets: 2

  Open the conversation URLs above in the Intercom inbox to test the app.
══════════════════════════════════════════
""")


if __name__ == "__main__":
    main()
