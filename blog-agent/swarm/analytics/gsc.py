"""Google Search Console reader.

Two separate queries, on purpose:

  * `fetch_page_rows`  — dimensions [date, page]         → authoritative page totals
  * `fetch_query_rows` — dimensions [date, page, query]  → what each page ranks for

They are NOT interchangeable, and the query rows must never be summed to
reconstruct page totals. Search Console omits queries that fall below its
anonymisation threshold, so the query breakdown is systematically *short* of the
page total — often by a wide margin on a low-traffic site. Collapsing these into
one call to "save an API round trip" silently understates every impression count
in the system, and nothing downstream would flag it.

Averaging rule, for the same reason: `position` is a per-impression average.
Aggregating it across rows requires weighting by impressions. A plain mean of
positions is always wrong and usually flattering.
"""
from __future__ import annotations

import os
from datetime import date
from typing import Any, Iterator
from urllib.parse import quote

from swarm.analytics.auth import (
    GSC_SCOPE,
    REQUEST_TIMEOUT,
    AnalyticsAuthError,
    authorized_session,
    explain_http_error,
)

API_ROOT = "https://searchconsole.googleapis.com/webmasters/v3"
# Search Console's hard per-request ceiling.
ROW_LIMIT = 25000


class SearchConsoleError(RuntimeError):
    pass


def site_url() -> str | None:
    """The GSC property identifier.

    Two shapes exist and they are not interchangeable:
      * Domain property     → `sc-domain:buteforce.com`
      * URL-prefix property → `https://www.buteforce.com/`  (trailing slash matters)

    A wrong-but-well-formed value returns an empty result set rather than an
    error, which reads exactly like "no traffic" — hence the explicit check in
    `probe()` below.
    """
    return os.environ.get("GSC_SITE_URL", "").strip() or None


def _post(session: Any, site: str, body: dict) -> dict:
    url = f"{API_ROOT}/sites/{quote(site, safe='')}/searchAnalytics/query"
    resp = session.post(url, json=body, timeout=REQUEST_TIMEOUT)
    if resp.status_code != 200:
        raise SearchConsoleError(explain_http_error(resp, "Search Console"))
    return resp.json() or {}


def _paged(session: Any, site: str, dimensions: list[str],
           start: date, end: date) -> Iterator[dict]:
    """Yield every row for the window, walking Search Console's row pagination.

    `dataState: "all"` includes the most recent 2-3 days, which Google is still
    revising.

    "final" was the original choice, on the reasoning that storing numbers which
    later change is untidy. Measured against the live property, that reasoning
    cost far more than it saved: final data stopped at 2026-08-03 with 179
    impressions where "all" showed 732 through 2026-08-05. A newsjacked post does
    most of its work in its first 72 hours, so the setting was blind to exactly
    the events worth reacting to, and the dashboard would have contradicted the
    Search Console UI by a factor of four.

    Provisional rows are safe here because the ingester re-pulls a trailing
    window every run and upserts on (date, slug, source) — a value revised by
    Google overwrites the provisional one within a day. The learning layer is
    insulated separately: it only scores posts older than MIN_AGE_DAYS, so
    unsettled edge days never reach the bandit.
    """
    start_row = 0
    while True:
        payload = _post(session, site, {
            "startDate": start.isoformat(),
            "endDate": end.isoformat(),
            "dimensions": dimensions,
            "type": "web",
            "dataState": "all",
            "rowLimit": ROW_LIMIT,
            "startRow": start_row,
        })
        rows = payload.get("rows") or []
        for row in rows:
            yield row
        if len(rows) < ROW_LIMIT:
            return
        start_row += ROW_LIMIT


def _shape(row: dict, dimensions: list[str]) -> dict:
    keys = row.get("keys") or []
    out: dict[str, Any] = dict(zip(dimensions, keys))
    out["clicks"] = int(row.get("clicks") or 0)
    out["impressions"] = int(row.get("impressions") or 0)
    out["ctr"] = float(row.get("ctr") or 0.0)
    out["position"] = float(row.get("position") or 0.0)
    return out


def fetch_page_rows(start: date, end: date, site: str | None = None) -> list[dict]:
    """[{date, page, clicks, impressions, ctr, position}] — authoritative totals."""
    site = site or site_url()
    if not site:
        raise SearchConsoleError("GSC_SITE_URL is not set")
    dims = ["date", "page"]
    session = authorized_session(GSC_SCOPE)
    return [_shape(r, dims) for r in _paged(session, site, dims, start, end)]


def fetch_query_rows(start: date, end: date, site: str | None = None) -> list[dict]:
    """[{date, page, query, ...}] — incomplete by design (see module docstring)."""
    site = site or site_url()
    if not site:
        raise SearchConsoleError("GSC_SITE_URL is not set")
    dims = ["date", "page", "query"]
    session = authorized_session(GSC_SCOPE)
    return [_shape(r, dims) for r in _paged(session, site, dims, start, end)]


def probe(site: str | None = None) -> dict:
    """Verify credentials, API enablement and the property identifier in one call.

    Returns a dict rather than raising so `--check-analytics` can report every
    misconfiguration at once instead of one per run.
    """
    site = site or site_url()
    if not site:
        return {"ok": False, "error": "GSC_SITE_URL is not set", "site": None}
    try:
        session = authorized_session(GSC_SCOPE)
    except AnalyticsAuthError as exc:
        return {"ok": False, "error": str(exc), "site": site}

    from datetime import timedelta

    end = date.today() - timedelta(days=3)
    start = end - timedelta(days=27)
    try:
        payload = _post(session, site, {
            "startDate": start.isoformat(),
            "endDate": end.isoformat(),
            "dimensions": ["date"],
            "rowLimit": 5,
        })
    except SearchConsoleError as exc:
        return {"ok": False, "error": str(exc), "site": site}

    rows = payload.get("rows") or []
    if not rows:
        return {
            "ok": False,
            "site": site,
            "error": (
                f"Authenticated, but {site!r} returned no rows for the last 28 days. "
                "Usually the property identifier is the wrong shape: a Domain property "
                "must be 'sc-domain:buteforce.com', a URL-prefix property must be the "
                "exact prefix including scheme, www and trailing slash."
            ),
        }
    return {"ok": True, "site": site, "days_with_data": len(rows)}
