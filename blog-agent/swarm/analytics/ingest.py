"""Analytics ingestion — pull search + engagement data into Supabase, per post per day.

Idempotent by construction. Every run re-pulls a trailing window and upserts on
the natural key, because Search Console revises the last 2-3 days after first
publishing them. Re-pulling must *correct* rows, never duplicate them, so the
window overlap is a feature rather than wasted work.

Failure policy: each source is independent. Search Console being misconfigured
must not cost you the GA4 pull, so a source that fails is reported in the log and
the others continue — but the failure is always stated. A run that quietly wrote
nothing and a run with genuinely no traffic look identical otherwise.
"""
from __future__ import annotations

import os
from datetime import date, datetime, timedelta, timezone
from typing import Any, Callable, Iterable

from swarm.analytics import ga4, gsc, slugmap

UPSERT_CHUNK = 500


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, str(default)).strip())
    except Exception:
        return default


def _chunks(rows: list[dict], size: int = UPSERT_CHUNK) -> Iterable[list[dict]]:
    for i in range(0, len(rows), size):
        yield rows[i:i + size]


def _upsert(db: Any, table: str, rows: list[dict], on_conflict: str, log: list[str]) -> int:
    """Batched upsert on a natural key. Returns rows written."""
    if not rows:
        return 0
    written = 0
    for chunk in _chunks(rows):
        try:
            db.table(table).upsert(chunk, on_conflict=on_conflict).execute()
            written += len(chunk)
        except Exception as exc:
            log.append(f"  ! upsert into {table} failed for {len(chunk)} rows: {exc}")
    return written


# ── aggregation ───────────────────────────────────────────────────────────────
def _fold_search(rows: list[dict], key: Callable[[dict], tuple | None]) -> dict[tuple, dict]:
    """Collapse rows onto a key, summing counts and weighting position correctly.

    Several URLs routinely map to one slug (www vs apex, trailing slash, tracking
    params), so folding is not optional. `position` is a per-impression average:
    combining rows means weighting by impressions. A plain mean would flatter
    every post that has one lightly-seen page ranking well.
    """
    acc: dict[tuple, dict] = {}
    for row in rows:
        k = key(row)
        if k is None:
            continue
        slot = acc.setdefault(k, {"clicks": 0, "impressions": 0, "pos_weight": 0.0})
        impressions = int(row.get("impressions") or 0)
        slot["clicks"] += int(row.get("clicks") or 0)
        slot["impressions"] += impressions
        slot["pos_weight"] += float(row.get("position") or 0.0) * impressions

    for slot in acc.values():
        impressions = slot["impressions"]
        slot["ctr"] = round(slot["clicks"] / impressions, 6) if impressions else 0.0
        # Position without impressions is undefined, not zero — zero would read as
        # "ranked first", the most misleading value available.
        slot["position"] = round(slot["pos_weight"] / impressions, 2) if impressions else None
    return acc


def _fold_ga4(rows: list[dict], resolve: Callable[[str], str | None]) -> dict[tuple, dict]:
    """Collapse GA4 path rows onto (date, slug).

    `engagement_rate` is a ratio over sessions, and the report does not return
    sessions, so it is re-weighted by views. That is an approximation — exact
    only when views per session is constant across the folded paths. Views are
    the closest proxy available, and the alternative (averaging ratios) is
    reliably worse.
    """
    acc: dict[tuple, dict] = {}
    for row in rows:
        slug = resolve(row.get("path") or "")
        if not slug:
            continue
        k = (row["date"], slug)
        slot = acc.setdefault(k, {"views": 0, "users": 0, "engaged_seconds": 0.0, "er_weight": 0.0})
        views = int(row.get("views") or 0)
        slot["views"] += views
        slot["users"] += int(row.get("users") or 0)
        slot["engaged_seconds"] += float(row.get("engaged_seconds") or 0.0)
        slot["er_weight"] += float(row.get("engagement_rate") or 0.0) * views

    for slot in acc.values():
        views = slot["views"]
        slot["engagement_rate"] = round(slot["er_weight"] / views, 6) if views else None
    return acc


# ── per-source ingestion ──────────────────────────────────────────────────────
def _ingest_gsc(db: Any, index: dict[str, str], start: date, end: date,
                log: list[str]) -> tuple[int, int]:
    """Search Console → post_metrics_daily (page totals) + post_queries_daily."""
    if not gsc.site_url():
        log.append("  gsc: GSC_SITE_URL not set — skipped")
        return 0, 0

    now = datetime.now(timezone.utc).isoformat()
    resolve = lambda url: slugmap.resolve(url, index)  # noqa: E731

    # Page totals. Authoritative — see the gsc module docstring on why these are
    # fetched separately from the query breakdown rather than summed from it.
    page_rows = gsc.fetch_page_rows(start, end)
    folded = _fold_search(page_rows, lambda r: (
        (r["date"], resolve(r.get("page", ""))) if resolve(r.get("page", "")) else None
    ))
    metrics = [{
        "date": d, "slug": slug, "source": "gsc",
        "impressions": v["impressions"], "clicks": v["clicks"],
        "ctr": v["ctr"], "position": v["position"], "fetched_at": now,
    } for (d, slug), v in folded.items()]
    written = _upsert(db, "post_metrics_daily", metrics, "date,slug,source", log)
    log.append(f"  gsc: {len(page_rows)} page rows -> {written} post-days")

    # Query breakdown.
    query_rows = gsc.fetch_query_rows(start, end)
    folded_q = _fold_search(query_rows, lambda r: (
        (r["date"], resolve(r.get("page", "")), r.get("query", ""))
        if resolve(r.get("page", "")) and r.get("query") else None
    ))
    queries = [{
        "date": d, "slug": slug, "query": q,
        "impressions": v["impressions"], "clicks": v["clicks"],
        "ctr": v["ctr"], "position": v["position"], "fetched_at": now,
    } for (d, slug, q), v in folded_q.items()]
    written_q = _upsert(db, "post_queries_daily", queries, "date,slug,query", log)
    log.append(f"  gsc: {len(query_rows)} query rows -> {written_q} post-day-queries")
    return written, written_q


def _ingest_ga4(db: Any, index: dict[str, str], start: date, end: date,
                log: list[str]) -> int:
    """GA4 → post_metrics_daily (engagement side)."""
    if not ga4.property_id():
        log.append("  ga4: GA4_PROPERTY_ID not set — skipped")
        return 0

    now = datetime.now(timezone.utc).isoformat()
    rows = ga4.fetch_page_rows(start, end)
    folded = _fold_ga4(rows, lambda p: slugmap.resolve(p, index))
    metrics = [{
        "date": d, "slug": slug, "source": "ga4",
        "views": v["views"], "users": v["users"],
        "engaged_seconds": round(v["engaged_seconds"], 2),
        "engagement_rate": v["engagement_rate"], "fetched_at": now,
    } for (d, slug), v in folded.items()]
    written = _upsert(db, "post_metrics_daily", metrics, "date,slug,source", log)
    log.append(f"  ga4: {len(rows)} path rows -> {written} post-days")
    return written


def _ingest_firstparty(db: Any, start: date, end: date, log: list[str]) -> int:
    """blog_views → post_metrics_daily. Cheap, and independent of Google entirely.

    Currently a no-op in practice: the pixel exists but is not installed on the
    site, so the table is empty. Wiring it now means the column lights up the day
    the snippet ships rather than needing a second pass.
    """
    rows = (db.table("blog_views").select("slug,viewed_at")
            .gte("viewed_at", start.isoformat())
            .lte("viewed_at", (end + timedelta(days=1)).isoformat())
            .limit(200000).execute().data or [])
    if not rows:
        log.append("  firstparty: no view events in window (pixel not installed yet)")
        return 0

    now = datetime.now(timezone.utc).isoformat()
    counts: dict[tuple[str, str], int] = {}
    for row in rows:
        slug = row.get("slug")
        stamp = str(row.get("viewed_at") or "")[:10]
        if slug and stamp:
            counts[(stamp, slug)] = counts.get((stamp, slug), 0) + 1

    metrics = [{"date": d, "slug": slug, "source": "firstparty", "views": n, "fetched_at": now}
               for (d, slug), n in counts.items()]
    written = _upsert(db, "post_metrics_daily", metrics, "date,slug,source", log)
    log.append(f"  firstparty: {len(rows)} events -> {written} post-days")
    return written


# ── entry point ───────────────────────────────────────────────────────────────
def run_ingest(db: Any, days: int | None = None) -> list[str]:
    """Pull the trailing window from every configured source. Returns a log."""
    days = days if days is not None else _env_int("ANALYTICS_INGEST_DAYS", 7)
    end = date.today()
    start = end - timedelta(days=max(1, days))

    log = [f"[analytics] ingest {start} -> {end} ({days}d window)"]

    index = slugmap.build_index(db)
    log.append(f"  slug index: {len(index)} known paths")
    if not index:
        log.append("  ! no published posts to attribute to — nothing to ingest")
        return log

    for name, fn in (
        ("gsc", lambda: _ingest_gsc(db, index, start, end, log)),
        ("ga4", lambda: _ingest_ga4(db, index, start, end, log)),
        ("firstparty", lambda: _ingest_firstparty(db, start, end, log)),
    ):
        try:
            fn()
        except Exception as exc:
            # Stated, never swallowed: a silent skip here would leave the learning
            # loop scoring posts on a window that was never actually fetched.
            log.append(f"  ! {name} FAILED: {exc}")

    log.append("[analytics] done")
    return log


def check() -> list[str]:
    """Probe every source and report what is and is not configured."""
    log = ["[analytics] configuration check"]

    from swarm.analytics.auth import service_account_email

    email = service_account_email()
    log.append(f"  service account: {email or '(could not read credentials file)'}")

    for name, probe in (("Search Console", gsc.probe), ("GA4", ga4.probe)):
        try:
            result = probe()
        except Exception as exc:
            log.append(f"  {name}: ERROR {exc}")
            continue
        if result.get("ok"):
            extra = {k: v for k, v in result.items() if k != "ok"}
            log.append(f"  {name}: OK {extra}")
        else:
            log.append(f"  {name}: NOT READY — {result.get('error')}")
    return log
