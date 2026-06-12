# Littlebird — Forensic Teardown

> **Source:** local install at `C:\Users\shree\AppData\Local\Programs\@littlebirddesktop\` + Roaming/Local AppData + `app.asar` header walk.
> **Date:** 2026-05-26
> **Package:** `@littlebird/desktop` v0.78.15 (alpha channel)
> **Why this exists:** competitive intelligence to inform CF Software roadmap. Architecture patterns only — no source code lifted.

Related: [[cf_software_plan]], [[competitors]].

---

## TL;DR

Littlebird is a **cloud-required Electron Anthropic-powered passive memory app** that ships ~205 MB of Chromium runtime + a 186 MB native capture binary + a 770 MB asar bundle. Their UX moat is the Hummingbird overlay; their privacy story is a 76,154-domain SQLite categoriser; their AI moat is being early on **MCP** (Model Context Protocol). They're heavy and cloud-bound — but the UX/polish bar is real and we can take specific patterns without taking the architecture.

---

## 1. Install footprint (Windows)

| Path | Purpose | Size |
|---|---|---|
| `…\Programs\@littlebirddesktop\Littlebird.exe` | Electron shell | 201 MB |
| `…\Programs\@littlebirddesktop\resources\app.asar` | App bundle (JS+modules) | 770 MB |
| `…\Programs\@littlebirddesktop\resources\bin\littlebird-capture.exe` | ContextKit sidecar | **186 MB** |
| `…\Programs\@littlebirddesktop\resources\bin\rg.exe` | Bundled ripgrep | 5 MB |
| `…\Programs\@littlebirddesktop\resources\category-seed.sqlite` | Domain content classifier | 7 MB |
| `…\Programs\@littlebirddesktop\resources\srt-cli\cli.mjs` | Transcript→SRT exporter | 0.4 MB |
| `…\AppData\Local\@littlebirddesktop-updater\installer.exe` | Auto-update cache | 324 MB |
| `…\AppData\Roaming\Littlebird\remote_categories.sqlite` | Live-fetched categorisation | 8 MB (+WAL) |
| `…\AppData\Local\Littlebird\debug-screenshots\` | Fallback screenshot cache | dyn |

**Headline numbers:**
- **Installed footprint ≈ 1.5 GB** before any user data.
- Tauri CF Software target ≈ **30-40 MB**. We are **40-50x lighter** before we even compete on features.

---

## 2. Architecture (reconstructed)

```
┌──────────────────────────────────────────────────────────────────┐
│  Littlebird.exe (Electron main process)                          │
│  └── dist-electron/main/index.js (780 KB)                        │
│      ├─ Window mgmt (main + Hummingbird overlay window)          │
│      ├─ IPC ↔ renderer + capture sidecar                         │
│      ├─ Auto-updater (S3: little-bird-releases, us-east-2)       │
│      └─ Cloud auth (little-bird-prod-auth.json — JWT/OAuth)      │
│                                                                  │
│  ↓ ↑ IPC                                                         │
│                                                                  │
│  WebView (renderer process)                                      │
│  ├── Radix UI Themes + Tiptap + Mermaid + Shiki + KaTeX          │
│  ├── MobX + mobx-persist-store                                   │
│  ├── kbar command palette (patched)                              │
│  ├── TanStack Query/Router/Table                                 │
│  └── Hummingbird overlay (separate hummingbird.html)             │
│                                                                  │
│  ↓ spawns                                                        │
│                                                                  │
│  littlebird-capture.exe (ContextKit native sidecar, 186 MB)      │
│  ├── Accessibility tree reader (UIA on Win / AX on Mac)          │
│  ├── Active window + bundle ID detector                          │
│  ├── Screenshot fallback (debug-screenshots/)                    │
│  ├── Domain classifier lookup (against category-seed.sqlite)     │
│  └── Audio capture (system loopback)                             │
│                                                                  │
│  ↓ ↑                                                             │
│                                                                  │
│  Cloud (S3 + their API)                                          │
│  ├── @anthropic-ai/sandbox-runtime ^0.0.46  ← Claude             │
│  ├── @modelcontextprotocol/sdk 1.26.0  ← MCP client              │
│  ├── @littlebird/mcp (workspace, internal)  ← MCP server         │
│  ├── Axiom (logs) + Sentry (errors) + PostHog (product)          │
│  └── OpenTelemetry (traces)                                      │
└──────────────────────────────────────────────────────────────────┘
```

**The big architectural reveals:**

1. **They use Claude** via `@anthropic-ai/sandbox-runtime ^0.0.46`. Their "undisclosed cloud LLM" public posture is misdirection. Pre-release sandbox runtime — they're an early Anthropic partner.
2. **They are an MCP server AND client.** `@littlebird/mcp` (workspace package, their own) + `@modelcontextprotocol/sdk` 1.26.0. They expose their memory as MCP tools and consume external MCP servers. This is *the* AI-ecosystem play of 2026 and we're not on it yet.
3. **Cloud-required.** `little-bird-prod-auth.json` exists at every install. The product cannot function without sign-in. Our local-first vault is a genuine moat — they cannot match it without rebuilding.
4. **`littlebird-capture.exe` is 186 MB** — a native sidecar (likely Rust, given size + perf profile). Our `cf-sidecar.exe` will land ~358 MB *with* Torch, more once we ship Phase 3 graph. Their capture binary is *lean for what it does* — they pre-compile native, we ship the Python ML runtime.
5. **They write their own ripgrep wrapper** — 5 MB `rg.exe` bundled. Used for fast local file search across the user's machine when they look at the screen.

---

## 3. Bundled dependency tells (the most interesting deps)

From the asar `package.json` (144 dependencies). Filtered to architecture-revealing entries:

| Dependency | Version | What it tells us |
|---|---|---|
| `@anthropic-ai/sandbox-runtime` | ^0.0.46 | Cloud LLM = Claude, sandbox runtime (early access) |
| `@modelcontextprotocol/sdk` | 1.26.0 | They are an MCP client |
| `@littlebird/mcp` | workspace:* | They run an internal MCP server |
| `@axiomhq/js` | ^1.3.1 | Centralised logs to Axiom |
| `@sentry/electron` + `@sentry/react` | 10.44.0 | Crash + error telemetry |
| `posthog-js` | ^1.290 | Product analytics (funnel, retention) |
| `@opentelemetry/*` | various | Distributed tracing |
| `@radix-ui/themes` | ^3.2.1 | Premium UI primitives (the polish source) |
| `@tiptap/*` (50+ extensions) | 3.6.6 | Rich answer rendering — tables, code, math, tasks, youtube |
| `shiki` | ^3.3 | Syntax highlighting for code answers |
| `mermaid` | ^11.12.3 | Diagram rendering in answers |
| `katex` | bundled | Math rendering |
| `kbar` (PATCHED) | beta.48 | Command palette (Cmd+K UX) — patched in-house |
| `framer-motion` | ^11.15 | Animations (same as us) |
| `mobx` + `mobx-persist-store` | 6.15 | State management — reactive, persistent |
| `@tanstack/react-query/router/table` | 5.65/1.145/8.21 | Modern React stack |
| `node-mac-permissions` | ^2.5 | macOS permissions for mic/screen/accessibility |
| `bplist-parser/creator` | (top-level) | They parse macOS binary plists (iMessage, prefs) |
| `chokidar` | (top-level) | They watch local files for changes |
| `@prisma/client` | (transitive) | SQLite via Prisma ORM |

**Fonts (bundled as .otf assets):**
- **Söhne** (Klim Type Foundry, ~$300+ license) — body
- **PP Neue Montreal Mono** (Pangram Pangram, ~$200+ license) — mono
- **Meraki Regular** — display

They paid for premium type. Type is **half** of why their UI looks expensive.

---

## 4. AppData / userData layout (Roaming\Littlebird)

| File | What | Notes |
|---|---|---|
| `little-bird-prod-auth.json` | Cloud auth token | JWT/OAuth — required to function |
| `app-settings.json` | App-level config | `appVisibilityMode`, launch-at-login |
| `app-exclusions.json` | Privacy controls | bundle IDs, domains, enabled category exclusions |
| `hummingbird-v4.json` | Overlay config | `enableHummingbird`, `hummingbirdShortcut: "option+option"`, voice toggle |
| `meetings-v1.json` | Meeting UI prefs | reminder lead time, window position |
| `menubar-calendar-v1.json` | Menu-bar calendar | preview lead time, events shown |
| `notifications-v1.json` | Notification state | per-notification dedupe |
| `window-settings.json` | Window geometry | traffic-light position, zoom |
| `crash-detection-store.json` | Crash recovery | last-known-good state |
| `app-update.yml` (in install) | Updater config | provider:s3, bucket:little-bird-releases, region:us-east-2, channel:alpha |
| `contextkit.pid` | Sidecar PID file | for crash recovery |
| `IndexedDB/`, `Local Storage/` | Renderer storage | Standard Chromium dirs |
| `Cache/`, `Code Cache/`, `GPUCache/` | Browser caches | Cleared on update |
| `Crashpad/` | Chromium crash dumps | Auto-uploaded to Sentry |
| `running-app-icons/` | Cached app icons | For "you were just in App X" UX |

**Key insight on Hummingbird config:** the shortcut format is a string (`"option+option"`). Built for user customisation. Our settings UI should expose hotkey rebinding the same way.

---

## 5. The privacy categoriser (76,154 rows)

`category-seed.sqlite` (7 MB shipped) and its grown sibling `remote_categories.sqlite` in userData (8 MB, refreshed from a CDN — that's why "remote") together implement Littlebird's **offline content filter**.

**Schema:**
```sql
CREATE TABLE category_metadata (
  categoryId TEXT PRIMARY KEY,
  updatedAt INTEGER NOT NULL,
  domainCount INTEGER NOT NULL,
  fetchedAt INTEGER NOT NULL
);
CREATE TABLE category_domains (
  categoryId TEXT NOT NULL,
  domain TEXT NOT NULL,
  PRIMARY KEY (categoryId, domain)
);
CREATE INDEX idx_domains_category ON category_domains(categoryId);
```

**Shipped categories + row counts:**

| categoryId | domains | What it blocks |
|---|---|---|
| `adult-content` | 75,497 | Porn / dating / cam sites |
| `banking-finance` | 297 | Bank portals, financial dashboards |
| `entertainment` | 61 | Streaming, gaming |
| `health` | 182 | Medical portals, patient sites |
| `shopping` | 66 | E-commerce checkout pages |
| `social` | 51 | Social networks |

**Default-enabled exclusions** (from `app-exclusions.json`): `adult-content` + `banking-finance`. The rest are opt-in.

**How it likely works:** every time the capture binary reads a window with a URL bar, it normalises the domain, hits this SQLite (microseconds via the index), and if it matches an enabled exclusion category, the page text never reaches the memory store. **Zero ML cost, zero network cost, zero false positives.**

**Why this matters for CF Software:** the *moment* we add screen reading (Phase 2+), we MUST have an equivalent privacy filter — it's a feature category, not a polish item. The good news: public-domain blocklists (StevenBlack/hosts, Cisco Umbrella popularity lists) get us 80% of the way for free.

---

## 6. How they handle screen reading (inferred)

We didn't find source code — just bundled binaries + paths. But the evidence points clearly:

- `littlebird-capture.exe` is a long-running native process (PID file present, restarted on crash).
- `dist/assets/accessibility-DHYgy4vg.png` + `accessibility.lazy-*.js` → onboarding flow walks users through granting the accessibility permission.
- `node-mac-permissions` is in package.json → they programmatically check macOS permissions.
- `running-app-icons/` cache → they enumerate the running apps via OS APIs.
- `debug-screenshots/` dir (empty on this install) → screenshot fallback when accessibility tree is unavailable.

**Their approach (reconstructed):**
1. Capture binary polls active window every ~1s via OS APIs (Windows UIA / macOS AX).
2. Reads accessibility tree → structured text per element.
3. If accessibility unavailable (some apps refuse) → fall back to native screenshot + OCR.
4. Looks up domain against category-seed → if excluded, drop on the floor.
5. Otherwise hashes content + sends incremental delta to cloud for embedding + storage.
6. UI keeps a "running app" thumbnail in `running-app-icons/` so the user can see "you were just in Chrome".

---

## 7. What CF Software should adopt — concrete patterns

Each item below is a **pattern**, not code. All implementations to be clean-room.

### Tier 1 — Quick wins (≤ 2 days each)

#### A. Command palette (kbar pattern)
- Adopt `kbar` (MIT) at the source level.
- Bind to `Ctrl+K`.
- Actions: "Ask about…", "Switch vault", "Restart sidecar", "Open settings", "Show last answer", "Reset session".
- **Why:** zero-context power-user surface that ships with one library install.

#### B. Premium typography (free alternatives)
- Body: Inter (free, near-identical to Söhne for our use case) or Geist Sans.
- Mono: JetBrains Mono or Geist Mono.
- Set up CSS custom properties for type tokens now so swapping later is trivial.
- **Why:** the *biggest* perceived-quality lift per hour of work.

#### C. Shiki for code rendering
- When RAG returns code in an answer, render with Shiki (we get ~150 languages free).
- Shiki ships big (every grammar) — lazy-load like they do (`abap-*.js`, `actionscript-*.js`).
- **Why:** code-heavy answers (which Obsidian vaults often contain) look professional instantly.

#### D. Tiptap for the answer surface
- Render the streaming Groq answer through Tiptap with markdown extension.
- Gives us tables, task lists, code blocks, math (KaTeX), and inline-editable answers in one move.
- **Why:** the overlay becomes a *document* the user can edit + save back to the vault.

#### E. Auto-launch on login (opt-in during onboarding)
- Already supported via `tauri-plugin-autostart`.
- Default OFF (they default ON — we differentiate on respect-for-user).
- Onboarding step: "Run CF Software automatically when you log in?"

### Tier 2 — Architectural adoptions (1-2 weeks each)

#### F. MCP server + client (huge moat opportunity)
- **Server:** expose `cf_search_vault(query)`, `cf_get_note(path)`, `cf_recent_calls()`, `cf_question_answered(timestamp)` as MCP tools so Claude Desktop / Cursor / any MCP-aware tool can query your vault.
- **Client:** let CF Software invoke OTHER MCP servers — e.g., during a call, hit a Linear MCP for tickets, a Notion MCP for docs, a calendar MCP for context.
- Use `@modelcontextprotocol/sdk` (TypeScript) in the Tauri shell.
- **Why:** Littlebird is on MCP; we should be too. This is the 2026 AI agent interop layer.

#### G. Telemetry stack (PostHog only)
- Add PostHog product analytics (events: install / first_session / first_answer / 7d_active / weekly_active).
- Skip Sentry/Axiom/OpenTelemetry — overkill for our stage. Add Sentry if/when crashes appear in the wild.
- **Why:** we currently have ZERO usage signal. Cannot iterate without it.

#### H. Tray icon with capture-state indicators
- Match their `ContextCollectionDisabled/Enabled/Excluded/SignIn` icon pattern.
- States: 🟢 listening, 🟡 paused, 🔴 no vault, ⚪ idle.
- Right-click menu: Start / Stop / Open Settings / Quit.
- Use Tauri's `tauri-plugin-tray` (or Tauri 2's built-in tray API).
- **Why:** the app belongs in the tray, not the taskbar, for an always-on tool.

#### I. Routines = scheduled vault enrichment
- "After every session, append a Q&A log note to the vault."
- "Every Monday 9am, summarise last week's call topics and surface stale vault notes."
- Use a simple JSON config + Tauri scheduled commands.
- **Why:** retention feature — every session makes the vault better, which makes the next session better.

### Tier 3 — Differentiated features (longer, post-MVP)

#### J. Screen context as secondary retrieval source
- *Only after Phase 1 + 2 ship and the call use-case is validated.*
- Use Windows UI Automation (UIA) via a Rust wrapper from Tauri.
- Mac fallback: AXUIElement.
- **MUST ship with a domain categoriser equivalent to theirs** (free hosts files give us 80%).
- **Why:** matches their core feature but only as an enrichment to vault context — we're not changing identity.

#### K. Post-call coaching mode
- Analyse transcript after session → "You got asked about ISO 27001 three times but your vault has no note on it."
- This is a feature *they don't have* (Littlebird is reactive, not coaching).
- **Why:** this is the unique angle the CF Software competitive doc already named — now we can scope it.

---

## 8. What we should NOT copy

- **Cloud-first auth.** Their forced sign-in is a constraint, not a feature. Our local-first vault is the moat.
- **Electron.** Stay on Tauri — 40-50x size advantage is real, measurable, and structural.
- **Passive ambient memory.** Their noisy "scrape everything" memory is the opposite of our intentional Obsidian vault story. The signal-to-noise advantage is ours; don't dilute it.
- **Premium font licenses.** Söhne + PP Mono = ~$500/yr we don't need. Inter + JetBrains Mono get 95% of the way for $0.
- **Bundling every Shiki grammar eagerly.** They lazy-load each language — we should too if we adopt Shiki. Don't ship 200 MB of language bundles.
- **macOS-first focus.** They're macOS primary, Windows beta. We're Windows-first by intent. Don't apologise for the inverse.

---

## 9. The one-line strategy update

> Littlebird validates that **people will pay $17/mo for an AI overlay that knows their context**. They built it cloud-first, Electron-heavy, and ambient. CF Software wins on the inverse: **local-first, lightweight, intentional, real-time call-shaped**.
>
> The next 90 days are not about feature parity. They're about taking their three best *patterns* (Hummingbird-style hotkey UX, command palette, premium typography) and our three best *bets* (Obsidian vault as moat, sub-500ms latency, MCP-native) and shipping a v0.1 that feels obviously better for the call-assistant use case.

---

## 10. Filed Build Board items (see Notion)

Tasks A-K from §7 will be added to the Build Board with Phase + Priority. Tier 1 → Phase 1/4 polish. Tier 2 → Phase 2/3. Tier 3 → backlog.

*End of teardown. Probe scripts in `cf-software/.scratch/` will be deleted post-write.*
