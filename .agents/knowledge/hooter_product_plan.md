---
name: Hooter Product Plan
description: Full enterprise product plan, feature roadmap, GCP architecture, and implementation phases for Hooter (retail CV analytics)
type: project
last-updated: 2026-04-16
---

# Hooter — Enterprise Product Plan

> Reference product: TangoEye (tangoeye.ai) — Indian retail CV analytics SaaS
> Competitor pricing: ₹15,000–₹40,000/store/month
> Our cost: ~$30/store/month on GCP Spot → massive margin opportunity

**Why:** Dhyan wants to build an enterprise-grade end-to-end product, not a POC. Has GCP subscription. No real camera yet — using YouTube VOD in the interim.

---

## Video Source (Demo)

Use YouTube VOD downloaded once and looped — more stable than live streams for demos.

```bash
# Download best retail crowd footage
yt-dlp -f "best[height<=720]" "https://www.youtube.com/watch?v=NyLF8nHIpAA" -o demo.mp4

# Or use existing demo.mp4 (Oxford Town Centre) — already good
# Pipeline loops it automatically

# For GCP: pass YouTube URL directly (auto-resolved in main.py)
python main.py --source "https://www.youtube.com/watch?v=YOUR_VIDEO_ID"
```

---

## Four Product Modules (TangoEye Parity + Beyond)

### Module 1: Hooter Traffic
Measure traffic + map in-store journey
- Footfall count (hourly/daily/weekly) ✅ built
- Per-track path trajectory (store x,y per frame) → needs `trajectories` table
- Journey map visualization (animated paths on floorplan)
- Bounce rate (dwell < 60s)
- Visit duration histogram
- Entry/exit heatmap
- Staff vs shopper separation

### Module 2: Hooter Zone
Zone-specific intelligence
- Zone dwell time ✅ built
- Zone heatmap ✅ built
- Zone transition matrix (A→B path analysis)
- Peak hours per zone
- Zone comparison view
- Live per-zone occupancy count
- Zone conversion rate (visited → checkout)

### Module 3: Hooter RevOp (DIFFERENTIATOR)
Missed sale detection — AUTO, not manual like TangoEye
- Rule: dwell in product zone >120s + no checkout visit within 5 min → auto-flag missed sale
- RevOp queue page — staff sees flagged events
- One-click reason tagging (pricing, OOS, quality, damaged)
- Conversion rate per zone (converted vs missed)
- Revenue opportunity estimate (missed × avg basket value config)
- `missed_sales` Supabase table

### Module 4: Hooter StoreOps
Infrastructure + operational intelligence
- Pipeline health heartbeat → `/health` endpoint + `health_beats` table
- Store open/close time detection (first/last person entry)
- Camera uptime monitoring
- Alert engine: crowding, dwell threshold, pipeline down
- Email alerts via Resend
- Daily summary email report (Supabase cron)

---

## GCP Architecture

```
YouTube URL / RTSP
       ↓
GCP Cloud Run — CV Pipeline (FastAPI + YOLOv8 + DeepSORT)
       ↓ events, trajectories, heartbeats
Supabase (Postgres + Realtime + Storage + Edge Functions)
       ↓ reads
Vercel — Next.js Dashboard
       ↓ alerts
Resend → Store Manager Email
```

**Tables needed:**
- `store_events` — zone enter/exit/dwell ✅
- `stores` — multi-tenant store rows (need onboarding flow)
- `trajectories` — x, y, frame, track_id, timestamp (new)
- `missed_sales` — RevOp queue (new)
- `health_beats` — pipeline heartbeat (new)
- `alert_rules` — configurable thresholds (new)

---

## Implementation Phases

| Phase | Week | Focus | Milestone |
|---|---|---|---|
| 0 — Foundation | 1 | GCP deploy, /health, trajectory emit, pipeline banner | Live on GCP |
| 1 — Traffic | 2 | Journey map, bounce rate, date range, visit duration | Traffic parity |
| 2 — Zone | 3 | Zone paths, transitions, peak hours, compare view | Zone parity |
| 3 — RevOp | 4 | Auto missed sale detection, reason tagging, conversion | Differentiated |
| 4 — StoreOps | 5 | Alerts, heartbeat, store open/close, daily email | Ops ready |
| 5 — Enterprise | 6 | Multi-tenant, CSV/PDF export, settings, onboarding | First customer |

---

## Competitive Edge

TangoEye's missed sale tagging requires **manual staff input** — someone has to remember to log it.
Hooter **auto-detects candidates** using CV rules → staff only confirms with one click.
This is a 10x workflow improvement and is buildable with existing DeepSORT tracking.

**Demo moment that closes deals:**
Person spends 3 minutes near a product zone → walks out without buying → Hooter auto-flags it → store manager sees it in RevOp dashboard → tags "Pricing concern" → product team adjusts pricing next week.

---

## Pricing Strategy (when ready)

| Tier | Price | Includes |
|---|---|---|
| Starter | ₹8,000/store/month | Traffic + Zone modules, 1 camera |
| Growth | ₹18,000/store/month | + RevOp, 3 cameras, CSV export |
| Enterprise | ₹35,000/store/month | + StoreOps, unlimited cameras, API access, white-label |

**Why:** 50% cheaper than TangoEye, better RevOp module, GCP-grade infra.
