# Rewrite brief — FMCG computer vision (page-2 fix)

**Slug:** `computer-vision-for-fmcg-manufacturing-in-india-what-unileve`
**Status as of 2026-08-06:** 413 impressions / 0 clicks / position 17.8 over 90 days.
The single highest-ROI page on the site: demand is already proven, so this needs a
rewrite rather than backlinks.

---

## What the data says (not opinion — measured)

| Query | Impressions | Position |
|---|---|---|
| `computer vision fmcg` | 294 | 18.2 |
| `computer vision in fmcg industry` | 99 | 17.0 |

Those two queries are **95% of the page's impressions**, and neither contains a
geography.

## Diagnosis — three separate faults

**1. Over-qualified targeting.** The page targets
`computer vision FMCG India manufacturing`; the demand is on `computer vision
fmcg`. India is a qualifier the searcher is not typing, and leading with it
narrows the page away from its own traffic.

**2. Thin.** 805 words against commercial-intent queries where the ranking set
runs 2,000+. Position 17.8 with strong impressions is the signature of a page
Google considers relevant but insubstantial.

**3. Written about the vendor, not the problem.** Current headings:

- The Current Landscape of FMCG in India
- The Buteforce Angle: Precision in Indian Context
- Transformational Impacts and Challenges
- Conclusion: Embracing a Smart Future with Buteforce

Two of four name the company. None names a defect, a line speed, or a number.
`config/gsc-signals.md` already recorded that FMCG buyers search the *defect and
the line* — "unsealed sachet detection", "fill-level inspection", "date-code OCR
verification" — and that the competitors who rank lead with the defect plus a
throughput figure. This page does neither.

---

## The rewrite

### Title
> Computer Vision for FMCG Manufacturing: Defects, Line Speed, and What It Costs

Leads with the query. Drops India from the title (it stays in the body, where it
supports rather than restricts).

### Meta title (≤60 chars)
> Computer Vision in FMCG: Defect Detection at Line Speed

### Meta description (≤155 chars)
> How computer vision catches seal, fill, cap and date-code defects on FMCG lines
> at 120+ units/min — accuracy, integration, and real deployment costs.

### Target keyword
`computer vision fmcg` — matched to the 294-impression query, not the aspiration.

### Structure — one defect per section, each with a number

1. **What computer vision actually inspects on an FMCG line** — the six defect
   classes, as buyers name them
2. **Seal and sachet integrity** — unsealed/partial seal detection, why thermal
   variance defeats fixed-threshold vision
3. **Fill-level and underfill detection** — tolerance bands, why transparent and
   metallised packaging need different approaches
4. **Cap and closure inspection** — missing/cocked cap, torque proxies
5. **Date-code and batch-code OCR verification** — the compliance case; why this
   is the highest-liability defect class
6. **Label presence and alignment** — mislabel detection, multi-SKU changeover
7. **Line speed: what 120 units/min demands** — camera, lighting, edge inference
   budget; where cloud round-trips break
8. **Accuracy in practice** — precision/recall tradeoff, cost of a false reject
   vs a missed defect
9. **What it costs** — bands, integration effort, what drives the number
10. **Deploying on Indian FMCG lines** — where India belongs: a section, not the
    frame

Target 2,000–2,400 words.

### Rules for the rewrite

- Every section opens with the defect a line engineer would name, not a benefit.
- At least one concrete number per section.
- Buteforce appears in at most two sections. The page earns the click by
  answering the query; the pitch comes after.
- Reuse the verified proof numbers already in the brand profile (99.2% accuracy,
  120/min) — do not invent new ones.
- Interlink: up to the FMCG pillar, sideways to a sibling defect post. A page-2
  page rises fastest when a cluster of internal links points at it.

---

## How to run it

The DB `target_keyword` has been corrected already, so the intent-drift detector
stops firing on a keyword that was never the real one. The content rewrite itself
goes through the normal pipeline and its review gate:

```bash
python run.py --topic "computer-vision-for-fmcg-manufacturing-in-india-what-unileve" --stage write
```

Then approve from the dashboard. Nothing republishes to the live site without
that approval.

## How to tell if it worked

Watch `/performance` for this slug. Success is position crossing under 10 and CTR
leaving zero. Give it 14–28 days — the maturity floor exists for this reason, and
reading the result sooner will measure noise.
