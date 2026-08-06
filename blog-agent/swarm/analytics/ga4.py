"""GA4 Data API reader.

Search Console answers "did anyone find it?"; GA4 answers "did anyone stay?".
The learning loop needs both — a post that wins impressions but loses readers is
a different failure from one nobody sees, and they call for opposite fixes.

Metric choice:
  screenPageViews        raw pageviews
  totalUsers             distinct people
  userEngagementDuration seconds of foreground engagement (SUM, not average)
  engagementRate         share of sessions GA4 counts as engaged

`userEngagementDuration` is a total. Per-user engagement is derived at read time
rather than stored, so the stored row stays additive across days.
"""
from __future__ import annotations

import os
from datetime import date, datetime
from typing import Any

from swarm.analytics.auth import (
    GA4_SCOPE,
    REQUEST_TIMEOUT,
    AnalyticsAuthError,
    authorized_session,
    explain_http_error,
)

API_ROOT = "https://analyticsdata.googleapis.com/v1beta"
PAGE_SIZE = 100000

METRICS = ["screenPageViews", "totalUsers", "userEngagementDuration", "engagementRate"]


class GA4Error(RuntimeError):
    pass


def property_id() -> str | None:
    """Numeric GA4 property id, e.g. '412345678'.

    Not the `G-XXXXXXX` measurement id — that identifies a data *stream* and is
    rejected by this API, so it is caught explicitly rather than left to surface
    as a confusing 400.
    """
    raw = os.environ.get("GA4_PROPERTY_ID", "").strip()
    return raw or None


def _validate(pid: str) -> str:
    if pid.upper().startswith("G-"):
        raise GA4Error(
            f"GA4_PROPERTY_ID is set to {pid!r}, which is a measurement ID. The Data API "
            "needs the numeric property ID from GA4 Admin → Property details (top right)."
        )
    if not pid.isdigit():
        raise GA4Error(f"GA4_PROPERTY_ID should be all digits, got {pid!r}.")
    return pid


def _parse_ga4_date(value: str) -> str:
    """GA4 returns dates as 'YYYYMMDD'; the rest of the pipeline speaks ISO."""
    try:
        return datetime.strptime(value, "%Y%m%d").date().isoformat()
    except ValueError:
        return value


def _num(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def fetch_page_rows(start: date, end: date, pid: str | None = None) -> list[dict]:
    """[{date, path, views, users, engaged_seconds, engagement_rate}] for the window."""
    pid = _validate(pid or property_id() or "")
    session = authorized_session(GA4_SCOPE)

    rows: list[dict] = []
    offset = 0
    while True:
        body = {
            "dateRanges": [{"startDate": start.isoformat(), "endDate": end.isoformat()}],
            "dimensions": [{"name": "date"}, {"name": "pagePath"}],
            "metrics": [{"name": m} for m in METRICS],
            "limit": PAGE_SIZE,
            "offset": offset,
            # Without this GA4 silently drops rows it considers low-volume, which
            # on a small site is most of them.
            "keepEmptyRows": False,
        }
        resp = session.post(f"{API_ROOT}/properties/{pid}:runReport", json=body,
                            timeout=REQUEST_TIMEOUT)
        if resp.status_code != 200:
            raise GA4Error(explain_http_error(resp, "GA4 Data"))
        payload = resp.json() or {}

        batch = payload.get("rows") or []
        for row in batch:
            dims = [d.get("value", "") for d in (row.get("dimensionValues") or [])]
            mets = [m.get("value", "0") for m in (row.get("metricValues") or [])]
            if len(dims) < 2 or len(mets) < 4:
                continue
            rows.append({
                "date": _parse_ga4_date(dims[0]),
                "path": dims[1],
                "views": int(_num(mets[0])),
                "users": int(_num(mets[1])),
                "engaged_seconds": round(_num(mets[2]), 2),
                "engagement_rate": round(_num(mets[3]), 6),
            })

        offset += len(batch)
        if len(batch) < PAGE_SIZE or offset >= int(payload.get("rowCount") or 0):
            return rows


def probe(pid: str | None = None) -> dict:
    """Verify credentials, API enablement and property access in one call."""
    raw = pid or property_id()
    if not raw:
        return {"ok": False, "error": "GA4_PROPERTY_ID is not set", "property": None}
    try:
        validated = _validate(raw)
        session = authorized_session(GA4_SCOPE)
    except (GA4Error, AnalyticsAuthError) as exc:
        return {"ok": False, "error": str(exc), "property": raw}

    from datetime import timedelta

    end = date.today()
    start = end - timedelta(days=27)
    body = {
        "dateRanges": [{"startDate": start.isoformat(), "endDate": end.isoformat()}],
        "metrics": [{"name": "screenPageViews"}],
        "limit": 1,
    }
    resp = session.post(f"{API_ROOT}/properties/{validated}:runReport", json=body,
                        timeout=REQUEST_TIMEOUT)
    if resp.status_code != 200:
        return {"ok": False, "error": explain_http_error(resp, "GA4 Data"), "property": validated}

    payload = resp.json() or {}
    rows = payload.get("rows") or []
    views = int(_num(rows[0]["metricValues"][0]["value"])) if rows else 0
    return {"ok": True, "property": validated, "views_28d": views}
