"""Where demand data comes from. One interface, four backings, one env var.

    DEMAND_PROVIDER=gsc          free      · proven demand, cannot veto
    DEMAND_PROVIDER=dataforseo   paid      · real Google Ads volume, vetoes
    DEMAND_PROVIDER=google_ads   free*     · needs an Ads account, coarse ranges
    DEMAND_PROVIDER=none         off       · explicit opt-out, logged loudly

Switching provider is a restart, not a refactor. Nothing above this module knows
which one answered — the gate reads `can_falsify` off whatever it is handed and
records `name` on every verdict, so a topic scored under Search Console and a
topic scored under DataForSEO are never silently compared as if they had passed
the same test.

The failure policy is the one `analytics/ingest.py` already established: a source
that breaks is reported, never swallowed, and never turned into a plausible-looking
number. A stub that invents volumes would be worse than no provider at all, since
the learning layer cannot tell an invented figure from a measured one.
"""
from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from typing import Any

from swarm.demand import Measurement

REQUEST_TIMEOUT = 30

# DataForSEO addresses markets by name; the gate speaks ISO country codes because
# that is what the rest of the swarm uses (`scout_signals.geo`, `DEMAND_GEO`).
# Only the markets Buteforce actually writes for are mapped — an unmapped code is
# an error rather than a silent fallback to the United States, which would return
# confident, well-formed, entirely irrelevant volumes.
_LOCATIONS = {
    "IN": "India",
    "US": "United States",
    "GB": "United Kingdom",
    "AE": "United Arab Emirates",
    "SG": "Singapore",
    "AU": "Australia",
}


def _now() -> datetime:
    return datetime.now(timezone.utc)


# ── none ──────────────────────────────────────────────────────────────────────
class NullProvider:
    """The switched-off state, as an object rather than a branch.

    Exists so `DEMAND_PROVIDER=none` travels the same code path as every other
    setting. The gate short-circuits before reaching it, but a provider that is
    absent and a provider that is present-and-inert behave differently under test,
    and the second is the one worth being able to construct.
    """
    name = "none"
    can_falsify = False

    def lookup(self, keyword: str, geo: str) -> Measurement:
        return Measurement(keyword, evidence={"provider": "none"})


# ── gsc ───────────────────────────────────────────────────────────────────────
class SearchConsoleProvider:
    """First-party demand: queries this site already earns impressions for.

    Not a volume estimate and never presented as one. Search Console reports what
    *this* audience typed and this site appeared for — a smaller universe than the
    market, but the only one measured rather than modelled, and the one that
    produced both of the site's real wins. "sarvam code" and "computer vision
    fmcg" were sitting in this table for weeks before anyone acted on them.

    `can_falsify = False`, and that constraint is the whole reason this provider
    is safe to run as the default. It cannot know about a keyword the site has
    never ranked for, so silence here means "no record", not "no demand". The gate
    reads that flag and refuses to let this provider veto anything.

    Matching is exact-then-substring. A post targeting "computer vision quality
    control india" should inherit the evidence of the rising query "computer
    vision quality control", because they are the same demand — but the wider
    match is recorded in the evidence so the inheritance is auditable rather than
    assumed.
    """
    name = "gsc"
    can_falsify = False

    def __init__(self, db: Any, window_days: int = 90) -> None:
        self._db = db
        self._window_days = window_days
        self._rows: list[dict] | None = None

    def _load(self) -> list[dict]:
        if self._rows is None:
            cutoff = (_now() - timedelta(days=self._window_days)).date().isoformat()
            self._rows = (self._db.table("post_queries_daily")
                          .select("query,impressions,clicks,position")
                          .gte("date", cutoff).limit(50000).execute().data or [])
        return self._rows

    def lookup(self, keyword: str, geo: str) -> Measurement:
        try:
            rows = self._load()
        except Exception as exc:
            return Measurement(keyword, error=f"Search Console read failed: {exc}"[:300])

        exact, partial = [], []
        for row in rows:
            query = (row.get("query") or "").strip().lower()
            if not query:
                continue
            if query == keyword:
                exact.append(row)
            elif keyword in query or query in keyword:
                partial.append(row)

        matched = exact or partial
        if not matched:
            return Measurement(keyword, evidence={
                "provider": "gsc",
                "window_days": self._window_days,
                "note": "no Search Console record — this provider cannot prove absence",
            })

        impressions = sum(int(r.get("impressions") or 0) for r in matched)
        clicks = sum(int(r.get("clicks") or 0) for r in matched)
        weight = sum(float(r.get("position") or 0) * int(r.get("impressions") or 0)
                     for r in matched)
        # Position is a per-impression average; a plain mean across rows would
        # flatter every keyword with one lightly-seen page ranking well. Same
        # rule the analytics ingester follows, for the same reason.
        position = round(weight / impressions, 1) if impressions else None

        return Measurement(keyword, volume=impressions, found=True, evidence={
            "provider": "gsc",
            "measure": "site impressions, not market search volume",
            "window_days": self._window_days,
            "match": "exact" if exact else "substring",
            "matched_queries": sorted({(r.get("query") or "") for r in matched})[:8],
            "impressions": impressions,
            "clicks": clicks,
            "avg_position": position,
        })


# ── dataforseo ────────────────────────────────────────────────────────────────
class DataForSeoProvider:
    """Google Ads search volume, pay-as-you-go, no Ads account required.

    The falsifiable provider — the one that can say "0 searches a month" and mean
    it, which is what turns the gate from advisory into enforcing. At Buteforce's
    volume (roughly eight keywords per ideation batch) this is small change; the
    endpoint bills per request, not per keyword, and accepts up to 1,000 keywords
    in one call.

    Zero is reported as a finding, not as an absence. DataForSEO returns a row
    with `search_volume: 0` for a phrase it knows and simply nobody searches, and
    that row is the single most useful thing this module can produce — it is the
    verdict that would have stopped "AI precision agriculture India" before a
    token was spent on it.
    """
    name = "dataforseo"
    can_falsify = True

    ENDPOINT = ("https://api.dataforseo.com/v3/keywords_data/"
                "google_ads/search_volume/live")

    def __init__(self, login: str, password: str) -> None:
        self._auth = (login, password)

    def lookup(self, keyword: str, geo: str) -> Measurement:
        location = _LOCATIONS.get(geo.upper())
        if not location:
            return Measurement(keyword, error=(
                f"DEMAND_GEO={geo!r} is not a mapped market. Add it to "
                "_LOCATIONS in swarm/demand/providers.py rather than letting the "
                "lookup silently answer for another country."))

        import requests  # local: the import-clean policy module must stay clean

        try:
            resp = requests.post(
                self.ENDPOINT, auth=self._auth, timeout=REQUEST_TIMEOUT,
                json=[{
                    "keywords": [keyword],
                    "location_name": location,
                    "language_code": "en",
                    # Google's own default. Stated rather than inherited, because
                    # partner-network volumes run materially higher and would
                    # quietly lift every keyword over the floor.
                    "search_partners": False,
                }],
            )
        except Exception as exc:
            return Measurement(keyword, error=f"DataForSEO request failed: {exc}"[:300])

        if resp.status_code != 200:
            return Measurement(keyword, error=(
                f"DataForSEO HTTP {resp.status_code}: {resp.text[:160]}"))

        try:
            payload = resp.json() or {}
            tasks = payload.get("tasks") or []
            task = tasks[0] if tasks else {}
        except Exception as exc:
            return Measurement(keyword, error=f"DataForSEO returned unparseable JSON: {exc}")

        # A 200 with a task-level error code is the shape a bad credential or an
        # exhausted balance arrives in. Reading only the HTTP status would turn
        # "your account is empty" into "this keyword has no demand" — the exact
        # class of mistake that cost eight topics on 2026-08-27, when an
        # OpenRouter 402 was retried as if it were transient.
        code = task.get("status_code")
        if code and int(code) >= 40000:
            return Measurement(keyword, error=(
                f"DataForSEO task error {code}: {task.get('status_message')}"))

        results = task.get("result") or []
        if not results:
            return Measurement(keyword, error="DataForSEO returned no result rows")

        row = results[0] or {}
        volume = row.get("search_volume")
        if volume is None:
            # Distinct from zero: Google has no data for this phrase at all,
            # which is not the same claim as "nobody searches it".
            return Measurement(keyword, found=True, volume=None, evidence={
                "provider": "dataforseo", "location": location,
                "note": "no search_volume returned for this keyword",
            })

        return Measurement(keyword, volume=int(volume), found=True, evidence={
            "provider": "dataforseo",
            "measure": "Google Ads average monthly searches",
            "location": location,
            "competition": row.get("competition"),
            "cpc": row.get("cpc"),
            "monthly_searches": (row.get("monthly_searches") or [])[:3],
        })


# ── google_ads ────────────────────────────────────────────────────────────────
class GoogleAdsProvider:
    """Placeholder for Keyword Planner via the Google Ads API.

    Deliberately unimplemented rather than faked, following the same rule as
    `sources.py:paid_trends_provider()`. Free with an Ads account, but it returns
    bucketed ranges ("100–1K") unless the account is actively spending, so the
    adapter has to decide how a range becomes a single number before it can be
    compared against a floor — and that decision belongs in code someone wrote on
    purpose, not in a stub that guesses the midpoint.

    To enable: install `google-ads`, set the OAuth credentials plus
    `GOOGLE_ADS_CUSTOMER_ID`, and implement `lookup` here. Nothing else changes.
    """
    name = "google_ads"
    can_falsify = True

    def lookup(self, keyword: str, geo: str) -> Measurement:
        raise NotImplementedError(
            "DEMAND_PROVIDER=google_ads is set but no adapter is implemented. "
            "Add it in swarm/demand/providers.py:GoogleAdsProvider.lookup(), or "
            "use DEMAND_PROVIDER=dataforseo / gsc.")


# ── resolution ────────────────────────────────────────────────────────────────
def resolve_provider(db: Any | None = None):
    """The configured provider, or the closest safe thing to it.

    Misconfiguration degrades rather than crashes, but never silently. A
    DataForSEO credential that is missing falls back to Search Console — the
    engine keeps producing, with a gate that promotes instead of vetoing — and
    says so at full volume, because a gate quietly running at reduced power is
    exactly the failure this whole module was built to end.
    """
    choice = os.environ.get("DEMAND_PROVIDER", "gsc").strip().lower()

    if choice == "none":
        print("[demand] DEMAND_PROVIDER=none — the demand gate is OFF. Topics will "
              "be queued without any check that anyone searches for them.", flush=True)
        return NullProvider()

    if choice == "dataforseo":
        login = os.environ.get("DATAFORSEO_LOGIN", "").strip()
        password = os.environ.get("DATAFORSEO_PASSWORD", "").strip()
        if login and password:
            return DataForSeoProvider(login, password)
        print("[demand] ! DEMAND_PROVIDER=dataforseo but DATAFORSEO_LOGIN/"
              "DATAFORSEO_PASSWORD are not set — falling back to Search Console, "
              "which CANNOT reject a keyword. The gate is running at reduced power.",
              flush=True)
        choice = "gsc"

    if choice == "google_ads":
        return GoogleAdsProvider()

    if choice != "gsc":
        print(f"[demand] ! DEMAND_PROVIDER={choice!r} is not a known provider — "
              "using Search Console.", flush=True)

    if db is None:
        # Same construction `run.py` and `supabase_tool` use. Callers inside the
        # pipeline always hand their own client down; this is only for a direct
        # `python -m swarm.demand` style check from a shell.
        from supabase import create_client

        db = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_KEY"])
    return SearchConsoleProvider(db)
