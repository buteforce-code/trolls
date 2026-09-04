"""Where a send actually goes. One interface, three backings, one env var.

    DISTRIBUTE_PROVIDER=manual     default. Queues and surfaces the text; you post it.
    DISTRIBUTE_PROVIDER=linkedin   posts through the LinkedIn member API.
    DISTRIBUTE_PROVIDER=none       off.

Same shape as `swarm/demand/providers.py`, for the same reason: the caller never learns which
one answered, so starting manual and moving to automated is a restart rather than a rewrite.

`manual` is not a stub. It is the honest default for a channel where the account is a real
person's professional identity: it does the scheduling, the spacing, the variant rotation and
the record-keeping, and leaves the ten seconds of paste to a human who can still decide not
to. Everything except the API call is exercised by it, so switching to `linkedin` later
changes one step that has already been proven around.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any

from swarm.distribute import LINKEDIN, X, Send

REQUEST_TIMEOUT = 30


@dataclass(frozen=True)
class Result:
    ok: bool
    external_id: str = ""
    error: str = ""
    manual: bool = False


class ManualProvider:
    """Records the send as needing a human, and hands back the exact text to paste."""

    name = "manual"
    channels = frozenset({LINKEDIN, X})

    def send(self, item: Send) -> Result:
        return Result(ok=True, manual=True)


class NullProvider:
    name = "none"
    channels: frozenset[str] = frozenset()

    def send(self, item: Send) -> Result:
        return Result(ok=False, error="DISTRIBUTE_PROVIDER=none — distribution is switched off")


class LinkedInProvider:
    """Posts to LinkedIn as a member, through the Posts API.

    Needs `LINKEDIN_ACCESS_TOKEN` (scope `w_member_social`) and `LINKEDIN_AUTHOR_URN`
    (`urn:li:person:<id>` for a personal profile, `urn:li:organization:<id>` for a company
    page). Tokens are member-authorised and expire — a 401 here means re-auth, not an outage,
    and is reported as such rather than retried into the ground.

    UNVERIFIED AGAINST THE LIVE API. Written from the documented contract; no credentials
    existed when it was added, so it has never made a real call. `DISTRIBUTE_DRY_RUN` defaults
    to true precisely so the first real send is a deliberate act by someone who can watch it.
    Treat the first live post as a test, and read `LinkedIn-Version` below before assuming a
    failure is a bug in this file — the API is versioned by date header and moves.

    X is deliberately absent: its write API is paid, and the manual provider covers it at
    zero cost until that trade is worth making.
    """

    name = "linkedin"
    channels = frozenset({LINKEDIN})

    ENDPOINT = "https://api.linkedin.com/rest/posts"
    API_VERSION = "202609"

    def __init__(self, token: str, author_urn: str) -> None:
        self._token = token
        self._author = author_urn

    def send(self, item: Send) -> Result:
        if item.channel not in self.channels:
            return Result(ok=False, error=f"{self.name} cannot post to {item.channel!r}")

        import requests  # local: the policy module stays import-clean

        headers = {
            "Authorization": f"Bearer {self._token}",
            "X-Restli-Protocol-Version": "2.0.0",
            "LinkedIn-Version": os.environ.get("LINKEDIN_API_VERSION", self.API_VERSION),
            "Content-Type": "application/json",
        }
        payload = {
            "author": self._author,
            "commentary": item.body,
            "visibility": "PUBLIC",
            "distribution": {
                "feedDistribution": "MAIN_FEED",
                "targetEntities": [],
                "thirdPartyDistributionChannels": [],
            },
            "lifecycleState": "PUBLISHED",
            "isReshareDisabledByAuthor": False,
        }

        try:
            resp = requests.post(self.ENDPOINT, headers=headers, json=payload,
                                 timeout=REQUEST_TIMEOUT)
        except Exception as exc:
            return Result(ok=False, error=f"LinkedIn request failed: {exc}"[:300])

        if resp.status_code in (200, 201):
            # The post id comes back in a header, not the body.
            return Result(ok=True, external_id=resp.headers.get("x-restli-id", ""))

        if resp.status_code == 401:
            return Result(ok=False, error=(
                "LinkedIn 401 — the access token is expired or revoked. Re-authorise; "
                "retrying will not fix it."))
        if resp.status_code == 429:
            return Result(ok=False, error="LinkedIn 429 — rate limited; the next tick will retry.")
        return Result(ok=False, error=f"LinkedIn HTTP {resp.status_code}: {resp.text[:200]}")


def resolve_provider():
    """The configured provider, degrading loudly rather than silently.

    Missing LinkedIn credentials fall back to `manual` — the schedule still runs, the text is
    still prepared, and a person posts it — because the alternative is a distribution lane
    that looks configured and quietly ships nothing, which is the failure this whole module
    was built to end.
    """
    choice = os.environ.get("DISTRIBUTE_PROVIDER", "manual").strip().lower()

    if choice == "none":
        print("[distribute] DISTRIBUTE_PROVIDER=none — distribution is OFF. The social kits "
              "will keep being written and will keep going nowhere.", flush=True)
        return NullProvider()

    if choice == "linkedin":
        token = os.environ.get("LINKEDIN_ACCESS_TOKEN", "").strip()
        author = os.environ.get("LINKEDIN_AUTHOR_URN", "").strip()
        if token and author:
            return LinkedInProvider(token, author)
        print("[distribute] ! DISTRIBUTE_PROVIDER=linkedin but LINKEDIN_ACCESS_TOKEN/"
              "LINKEDIN_AUTHOR_URN are not set — falling back to manual. Sends will be "
              "queued for a human, not posted.", flush=True)
        return ManualProvider()

    if choice != "manual":
        print(f"[distribute] ! DISTRIBUTE_PROVIDER={choice!r} is not a known provider — "
              "using manual.", flush=True)
    return ManualProvider()
