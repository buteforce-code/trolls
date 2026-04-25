---
links: "[[INDEX]] | [[brand_bible]] | [[content_calendar]] | [[marketing_engine]] | [[icp]]"
type: strategy
last-updated: 2026-04-15
---

# SEO Strategy — Buteforce

> Keyword clusters, blog targets, and on-page rules.
> GEO (Generative Engine Optimization) already implemented — see [[marketing_engine#Lead Sources]]
> Content pipeline that maps to these keywords → [[content_calendar#Blog Post Pipeline]]
> Brand voice rules for all blog content → [[brand_bible#Manifesto]]

---

## ⚠️ GSC Issue: Page With Redirect (Resolved 2026-04-24)
GSC reported "Page with redirect" validation failure — Googlebot was crawling `http://buteforce.com/` (HTTP) which redirected to HTTPS.

**Fix applied (commit eefd461):**
- Added explicit 301 redirects in `next.config.ts` for `http://` → `https://` (via `x-forwarded-proto` header) and `www.buteforce.com` → `buteforce.com`
- Fixed `app/sitemap.ts`: replaced dynamic `new Date()` lastModified (was marking all pages as freshly modified on every deploy) with fixed content-accurate dates

**Next steps:**
1. After Vercel deploys (2–3 min), go to GSC → Indexing → Pages → "Page with redirect" → click **Validate Fix**
2. Re-submit sitemap: GSC → Sitemaps → `buteforce.com/sitemap.xml` → Resubmit
3. Request indexing for key pages: homepage, /services, /work, /lp/ai-audit

---

## Target Keyword Clusters

### Cluster 1: AI Automation Agency
| Keyword | Intent | Priority |
|---|---|---|
| AI automation agency | Commercial | 🔴 High |
| custom AI automation | Commercial | 🔴 High |
| AI workflow automation for business | Commercial | 🟡 Medium |
| hire AI automation developer | Commercial | 🔴 High |
| build AI automation system | Commercial | 🟡 Medium |

### Cluster 2: Computer Vision
| Keyword | Intent | Priority |
|---|---|---|
| computer vision for manufacturing | Commercial | 🔴 High |
| quality control computer vision | Commercial | 🔴 High |
| custom YOLOv8 development | Commercial | 🟡 Medium |
| defect detection AI | Commercial | 🟡 Medium |

### Cluster 3: Document AI / OCR
| Keyword | Intent | Priority |
|---|---|---|
| document AI processing | Commercial | 🔴 High |
| custom OCR solution | Commercial | 🔴 High |
| invoice extraction automation | Commercial | 🟡 Medium |
| document processing automation | Informational | 🟡 Medium |

### Cluster 4: AI Agents
| Keyword | Intent | Priority |
|---|---|---|
| AI agent for real estate | Commercial | 🔴 High |
| build AI agent business | Commercial | 🟡 Medium |
| autonomous AI agent development | Commercial | 🟡 Medium |

---

## Blog SEO Targets — Priority Order
*(Ordered by: buyer intent + competition level. Do in this sequence.)*

| # | Post Title | Target Keyword | ICP | Status |
|---|---|---|---|---|
| 1 | Why your AI automation project failed (and how to fix it) | AI automation project failure | All | 🔲 To write |
| 2 | How to automate quality control with computer vision | computer vision quality control | Manufacturing | 🔲 To write |
| 3 | AI agents for real estate: handle 70% of inquiries automatically | AI agent for real estate | Real estate | 🔲 To write |
| 4 | OCR vs Document AI: which one does your business need? | document AI vs OCR | Finance | 🔲 To write |
| 5 | How to calculate ROI of AI automation before you build | AI automation ROI | All | 🔲 To write |
| 6 | The hidden cost of manual data entry in finance ops | manual data entry automation | Finance | 🔲 To write |
| 7 | n8n vs Zapier vs custom Python: which stack is right for you? | n8n vs zapier automation | Technical buyers | 🔲 To write |

**Why post #1 goes first:** Targets buyers who already tried AI and failed — highest purchase intent, lowest competition. Maps directly to the battle card: *"most AI projects fail because someone built the wrong thing correctly."*

---

## Blog Post Formula (apply to every post)
1. Title: target keyword + specific claim or number
2. First 100 words must contain the target keyword naturally
3. H2/H3 structure throughout — helps Google parse content
4. Specific metrics, not vague claims (99.2%, not "high accuracy")
5. 3–5 internal links to service pages
6. Every post ends with CTA: *"Want to know what to automate first? Free 30-min AI audit → buteforce.com/lp/ai-audit"*
7. Meta description: under 160 chars, includes target keyword

---

## On-Page SEO Checklist (per blog post)
- [ ] Target keyword in H1
- [ ] Target keyword in first 100 words
- [ ] 3–5 internal links to service pages
- [ ] CTA to Free AI Audit in every post
- [ ] Meta description under 160 chars
- [ ] Alt text on all images

---

## GEO (Generative Engine Optimization)
Already partially implemented (llms.txt, JSON-LD). Expand with:
- FAQ-style "questions we get asked" sections on each service page — LLMs pull from structured Q&A
- Free directory listings: Clutch, DesignRush, G2 — LLMs cite these for "best AI agency" queries
- Test: search "best AI automation agency for manufacturing" in ChatGPT + Perplexity — note who appears, study their llms.txt

---

## Last Updated
- Date: 2026-04-15
