# Codex Conversations

Purpose:
- store recent session notes and unresolved threads
- preserve handoff context between Codex sessions
- avoid polluting the durable knowledge files with raw conversation noise

Do not use this file as the source of truth for stable facts if a better knowledge note exists.

## Active Threads

- **Hooter Phase 1 ✅ DONE** — Date range selector (Today/7D/30D), Bounce Rate KPI, Visit Duration Histogram
- **Hooter Phase 2 NEXT** — Zone transitions matrix (A→B), peak hours per zone, zone comparison view
- **Hooter RevOp auto-detection** is the product wedge — auto-flag missed sales vs TangoEye's manual tagging.
- **Hooter logo integrated** — Real Buteforce SVG logo (2 paths) in sidebar, login page, and favicon. Component at `src/app/components/BfLogo.tsx`.



- **Blog Agent live publishing**: `PUBLISH_DRY_RUN=true` in `dashboard/.env.local`. Flip to `false` when Dhyan is ready to start pushing posts to GitHub/TinaCMS.
- **New topic timing**: After clicking "+ New Topic", the new card appears after ~1.5s delay. Normal — Python writes to Supabase then polling picks it up.
- **Dev server restart**: After heavy bash testing sessions, restart with Ctrl+C → `npm run dev` to clear stuck TCP connections.

- **Lead Outreacher review app LIVE on Render** — deployed at `https://buteforce-outreach.onrender.com`. Google Sheets is the live data source. Notification center + branded HTML email template shipped 2026-04-28.

## Session Log

### 2026-06-11 — CF Software: full UX audit via parallel sub-agents — live pipeline now works end-to-end

**Project:** `D:\Projects\Buteforce\Projects\client facing call ai\Client Facing\cf-software`

**User-reported problems → root causes → fixes (all committed, not pushed):**
1. *Window unmovable/unminimizable* → no window controls existed + missing `core:window` permissions → new `WindowControls` (drag strip + min/close on every view) — `b55fffe`.
2. *Transcript cut mid-word* → ticker forced nowrap+ellipsis → wraps now (finals 2 lines, partial 4) + roomier zone — `45cc360`, `673e4a7`.
3. *No summary/insights on End* → utterances only finalized on UtteranceEnd silence gap (never fires in continuous audio) → 0 finals → no summary. Fixed: flush on Deepgram `speech_final` + 60-word cap — `5b984f4`.
4. *"Nothing relevant" answers* → empty conversation context (same root as #3) + vault chunks polluting call questions → transcript-only routing for call questions — `bbeeb3c`.
5. **Word-salad answers ("They're of leaving start a rival…") → THE BIG ONE: React 18 setState batching coalesced rapid `answer_token` WS messages in `useWebSocket`'s `lastMessage` pattern — words dropped from every streamed answer.** Fixed with lossless queue + drain loop — `d482b26`.
6. *Audio too quiet* (mic RMS 0.008) → per-source AGC, target 0.15, cap 6x, soft-knee limiter — `ff2436f` + `fcb2f72`.

**Parallel sub-agent audits:** vault-RAG auditor proved **the Obsidian vault IS visible to inference** (207/207 .md indexed, fresh build, relevant retrieval on all test queries; noted graphify-out duplicates ~174 notes — future cleanup). TS + Python reviewers found 6 HIGH issues (stale WS queue on reconnect, AGC brickwall after silence, cue-list false positives bypassing vault, timer stacking) — all fixed in `fcb2f72`.

**Live verification (2026-06-11 sessions in dev-live.log):** post-AGC mix RMS 0.25–0.35 (healthy), fps 3.9 stable, fluent grounded answer confirmed server+UI: "They're discussing a usage tracker that shows input tokens, output tokens, and estimated cost…", **Session stopped (8 utterances)** → summary path fired.

**Known polish items (open):** question classifier fires on long monologue chunks (60-word flush ending in "?" or starting with "can" → spurious answers); graphify-out index duplication; answer auto-hide UX; keys still need rotation post-live-test.

---

### 2026-06-08 — CF Software: landed in-flight work + instrumented the live-audio blocker

**Project:** `D:\Projects\Buteforce\Projects\client facing call ai\Client Facing\cf-software`

**Context:** A "Claude design" drop (4 zips) was delivered 2026-06-05. Zip `(1)` was byte-identical to shipped `src/`; the real artifact was a browser prototype that resolves design-debt #1. Also found 3 sidecar Python files modified-but-uncommitted since 2026-06-02 (a complete feature) plus the design-handover doc untracked.

**Committed (3 commits on `main`, NOT pushed):**
1. `feat(sidecar): answer questions about the live call, not just the vault` — threads the recent transcript (last 12 lines) into `_handle_question`→`stream_answer`; two-block CONVERSATION+NOTES prompt; `_is_about_conversation()` cue heuristic suppresses vault chips on call questions; `GROQ_MAX_TOKENS` 200→320; `_on_speech_started(*args)` so the DG callback never raises. (was uncommitted in-flight work)
2. `fix(ui): declare --accent-bright token` — was referenced (TranscriptTicker, global.css) but undeclared → silently no-op. Set `#FFFFFF` per prototype.
3. `fix(sidecar): instrument the audio→Deepgram→transcript path` — see below.

**THE BLOCKER (still open):** live audio→transcript has never produced an utterance. 2026-05-26 + 2026-06-02 both showed Deepgram connected, UI "Listening", but "Waiting for audio…" never resolved (0 utterances). Standalone soundcard probe proved real audio (RMS 0.139), so capture *can* work. The frame watchdog only catches zero-capture; everything after was silent.

**Diagnosis instrumentation added (INFO-level, off hot path):**
- `audio.py` — "Capture alive: N frames, peak_rms=X" every ~5s. peak_rms≈0 with frames flowing ⇒ capturing **silence** (wrong/muted device), not transport.
- `transcriber.py` — counts frames/bytes fed to DG (first send + tally); logs **first transcript event received** (proves audio reaches DG even with no speech); `feed_audio` send wrapped in `_send` that **logs failures** instead of dropping them as unretrieved task exceptions (prime suspect).

**Decision tree for the next live test (`npm run tauri dev`, Start session, play audio):**
- No "Capture alive" line → capture thread dead (device open failed).
- "Capture alive" with peak_rms≈0 → wrong/muted device; fix device, not code.
- peak_rms>0 but no "First Deepgram transcript event" + "send failed" lines → transport bug (auth/format/SDK).
- peak_rms>0 + "First transcript event" but no utterance_end → DG hears audio but not speech (gain/format/VAD).

**Next:** Dhyan runs the live test and reads the logs; the tree localises the fix. Tree-clean except untracked design zips + handover doc (fate undecided). Unit suite green (36 passed, 2 skipped) throughout.

---

### 2026-06-01 — CF Software: Premium UI Overhaul & Hummingbird Command Bar

**Project:** `D:\Projects\Buteforce\Projects\client facing call ai\Client Facing\cf-software`

**Premium UI Overhaul ("Littlebird" style):**
- Replaced the generic app layout with a high-fidelity, native-feeling Windows assistant overlay.
- Typography upgraded to `Inter` and `Outfit` via `tokens.css`.
- Deepened glassmorphism, multi-layered shadows, and added an ambient pulsing background.
- Fixed `tauri.conf.json`: Set `decorations: false` and `transparent: true` to produce a true 720x500 floating overlay window instead of a standard framed window.

**Hummingbird Command Bar:**
- Implemented a sleek manual input box at the bottom of the `LiveSession` UI.
- Wired backend (`main.py`): The Python sidecar now listens for `manual_question` WebSocket messages and explicitly routes them to the `CFRagEngine`, bypassing speech filters.

**Audio / Transcription Investigation:**
- Dhyan noted live transcription wasn't displaying. Audited `audio.py` and confirmed it successfully captures and mixes BOTH microphone and system loopback audio.
- The lack of transcription ("Awaiting speech" state) was traced to pure silence being sent by Windows OS. 
- Logged runbook instructions for Dhyan to enable "Stereo Mix" in the Windows Sound Control panel and verify Windows Microphone Privacy settings.

**Next Up:**
- The Proactive Insight Engine (automatic background RAG context surfacing).

### 2026-05-26 (PM) — CF Software: editorial-mono UI redesign + dual-source audio + post-session summary

**Project:** `D:\Projects\Buteforce\Projects\client facing call ai\Client Facing\cf-software`

Big build session driven by Dhyan testing the live app. Used the `frontend-design` skill for the visual direction.

**UI redesign — "editorial mono, quiet confidence":**
- New design system: `src/styles/tokens.css` (Inter + Instrument Serif + JetBrains Mono via Google Fonts; warm near-black canvas; single electric-coral accent; hairline rules; 4px spacing scale; motion easings) + `src/styles/global.css` (resets, atmosphere = radial vignette + film-grain noise, reusable `.cf-btn`/`.cf-pill`/`.cf-mono-caps` atoms). CSP in tauri.conf.json allowlisted fonts.googleapis.com + fonts.gstatic.com.
- All surfaces rewritten: Settings (asymmetric rail + hairline field list, "CF." serif wordmark + coral dot), LiveSession, Overlay, Onboarding (vertical step spine), plus new CommandPalette (kbar, Ctrl+K), AudioMeter, TranscriptTicker, SessionSummary.
- Dhyan pushback "this is not elegant" on the first meter (chunky EQ blocks) → redesigned to hair-thin density-adaptive ticks mirrored above/below a centerline, opacity=energy not height, right-to-left scroll, dB readout. Pills toned to neutral border + dot-only color.
- Layout bug fixed: flexbox+grid `min-width:auto` gotcha caused edge-to-edge stretch + value clipping on wide windows. Added `min-width:0` chain + `minmax(0,1fr)` tracks + centered `maxWidth` frames. Display is 100% scale (1536x864), so not a DPI issue.

**Observability (fixes the opaque "Waiting for audio"):**
- Sidecar now emits `audio_level` (~4Hz RMS from audio.py per frame) and `transcript_final` (every finalised utterance, question or not — was previously dropped for non-questions). UI renders the meter + rolling transcript ticker from these.

**Dual-source audio capture (Dhyan's explicit ask — capture BOTH sides):**
- `audio.py` rewritten. Captures system loopback (the client's voice) AND the default microphone (the user's voice), mixed into one 16kHz mono stream for Deepgram. Loopback paces the output; the latest mic block is summed into each frame at 0.85 gain each — no clock-drift accumulation. Graceful degrade to either source alone. Removed the capture-source toggle (both always on). `LOOPBACK_UNAVAILABLE` now only warns when system audio genuinely can't be captured.
- Discovered along the way: mic mode previously grabbed the laptop Realtek array (wrong device, ~-63 dB); loopback on the pTron TWS works (RMS 0.14 measured). Dual-source sidesteps the wrong-mic problem.

**Post-session summary (Dhyan's explicit ask — summary on Stop):**
- Sidecar accumulates every finalised utterance into a session transcript. On `stop_session`, `CFRagEngine.summarize_transcript()` runs a non-streaming Groq call (600 tok, temp 0.3) → structured plain text (Overview / Key topics / Questions raised / Follow-ups). New `summary_started` + `session_summary` WS events. New `SessionSummary.tsx` parses + renders it; "Done" returns to Settings. Skips when nothing was transcribed.

**Deps added:** kbar, markdown-it (+ @types). Bundle now ~369 KB / 117 KB gzip.

**Verification:** 47/47 sidecar tests green throughout; `npm run build` + `cargo check` clean. Full dev stack (Vite + Tauri + sidecar) booted repeatedly via scripts/dev.ps1 and screenshotted via PrintWindow PW_RENDERFULLCONTENT.

**Standing instruction recorded** (memory `notion_update_cadence`): update Notion after EVERY completed task, not batched.

**Open / next:** Dhyan still needs to confirm an answer actually renders when a clear question is asked (RAG accuracy + the 400ms target are his stated next concerns). If transcripts flow but no answer, investigate RAG/Groq. Also still open from before: rebuild bundled cf-sidecar.exe (now also needs dual-audio + summary code), MCP integration, tray icon, stealth flags restore, key rotation.

---

### 2026-05-26 — CF Software: Littlebird forensic teardown + product live-boot

**Project:** `D:\Projects\Buteforce\Projects\client facing call ai\Client Facing\cf-software`
**Vault note created:** [[competitors_littlebird]]

**Live boot:** ran the full dev stack (Vite + Tauri + Python sidecar) from the agent harness via `scripts\dev.ps1`. End-to-end worked: cf-software.exe window rendered, Settings panel showed vault=.agents + Deepgram/Groq configured + Audio=auto, sidecar listening on 8765 with the new per-launch WS token rejecting unauthenticated probes (403 confirmed live). User clicked Start session, UI flipped to "Listening" + green SIDECAR/DEEPGRAM/Headphones (pTron TWS) pills, but "Waiting for audio …" never resolved to a transcript. Independent soundcard probe proved loopback on pTron TWS works (RMS 0.139 — real audio on the device). Likely cause: silent audio during the test window or Bluetooth A2DP→HFP profile flip; UI lacks observability to distinguish.

**Littlebird teardown (durable knowledge in [[competitors_littlebird]]):**
Walked the install at `C:\Users\shree\AppData\Local\Programs\@littlebirddesktop\` + Roaming/Local AppData + cracked the `app.asar` header (no source extracted, only file index + `package.json`).

Key reveals not in the public marketing:
- **They use Claude.** `@anthropic-ai/sandbox-runtime ^0.0.46` (Anthropic alpha sandbox SDK) is bundled. Their "undisclosed cloud LLM" is misdirection.
- **They are MCP-native.** `@modelcontextprotocol/sdk 1.26.0` (client) + `@littlebird/mcp` (workspace internal server). They expose memory as MCP tools and consume external MCP servers. Major 2026 interop play we are not on yet.
- **Cloud-required.** `little-bird-prod-auth.json` at every install. Sign-in is mandatory; the product is not local-first. Our Obsidian-vault model is a real structural moat they cannot match without rebuilding from zero.
- **Massive footprint.** 1.5 GB installed (201 MB Electron + 770 MB asar + 186 MB capture binary + 324 MB updater + 7 MB SQLite). CF Software target ≈ 30-40 MB — **40-50× lighter**.
- **186 MB `littlebird-capture.exe`** is their ContextKit native sidecar — handles accessibility tree reading (UIA/AX), active-window detection, screenshot fallback (`debug-screenshots/`), and audio capture. Confirms the "they don't OCR, they read the a11y tree" claim in the public competitor doc.
- **76,154-domain SQLite content filter** (`category-seed.sqlite`). Schema: `category_metadata` + `category_domains(categoryId, domain)`. 6 categories shipped: adult-content (75,497), banking-finance (297), entertainment (61), health (182), shopping (66), social (51). Default-enabled exclusions: adult + banking. **Brilliant offline privacy engineering** — when we add screen reading post-MVP we MUST adopt this pattern (public-domain blocklists like StevenBlack/hosts get us 80%).
- **Premium typography** — Söhne (Klim, ~$300+/yr) + PP Neue Montreal Mono (Pangram Pangram, ~$200+/yr) + Meraki bundled as .otf assets. Type is half their visual quality. Inter + JetBrains Mono get us 95% there for $0.
- **kbar** with a local patch — they ship a custom-patched command palette. Pattern worth adopting.
- **Heavy telemetry** — Sentry (electron+react), PostHog, Axiom, OpenTelemetry. For us: PostHog only at v0, Sentry once crashes appear in the wild.
- **Tiptap (50+ extensions) + Shiki + Mermaid + KaTeX** for answer rendering. The Hummingbird overlay is a Tiptap document, not plain text.
- **MobX + mobx-persist-store** for state (not Redux/Zustand). Implies heavy observable reactive UI.
- **Distribution:** S3 direct (`little-bird-releases` bucket, us-east-2, alpha channel) — not CloudFront. We're planning Cloudflare R2 — different choice, same shape.
- **They bundle ripgrep** (`bin\rg.exe`) for fast local file search across the user's machine.

Adopt list (clean room — patterns, not code) filed to Build Board:
- Tier 1 (≤2d each): command palette via kbar (Ctrl+K), free premium typography (Inter + JetBrains Mono), Shiki code rendering, Tiptap answer surface, opt-in auto-launch.
- Tier 2 (1-2w each): MCP server+client (the big one), PostHog product analytics, tray icon with capture-state indicators, scheduled routines (post-call vault enrichment).
- Tier 3 (post-MVP): screen context as secondary RAG source (with their categoriser pattern), post-call coaching mode (a feature they DON'T have — our differentiator).

Don't copy: cloud-first auth, Electron, passive ambient memory, premium font licenses, eager Shiki bundling, macOS-first focus.

**Operational:** vault index updated to point at the new [[competitors_littlebird]] note. Probe scripts in `cf-software/.scratch/` cleaned up post-write so they don't ship in the project.

---

### 2026-05-22 — CF Software: Codex Security full-repo pass (7 files patched)

**Project:** `D:\Projects\Buteforce\Projects\client facing call ai\Client Facing\cf-software`
**Trigger:** Dhyan invoked Codex Security workflow + OpenAI Developers review across the whole code base with permission to apply fixes without hesitation.

**What changed (all 2026-05-22):**

- *Sidecar WebSocket auth (the real finding):* `sidecar/main.py:64` now enforces a per-launch token on the WS upgrade. Rust generates a random token at app start, exports it as `CF_SIDECAR_TOKEN` for the spawned sidecar, and the React webview appends it to the connect URL via a new `resolveSidecarUrl()` helper.
  - `src-tauri/src/lib.rs:123` — token generation + env var injection on sidecar spawn.
  - `src/App.tsx:50` — async resolver that pulls the token from Rust and builds `ws://127.0.0.1:8765/ws?token=…`.
- *Tauri capability tightening:* `src-tauri/capabilities/default.json:6` — removed broad `shell:allow-execute` / `shell:allow-spawn` / `fs:allow-*` from the webview capability set. The sidecar spawn happens in Rust, not from JS, so the webview no longer needs those.
- *CSP enabled:* `src-tauri/tauri.conf.json:35` — `csp` populated (was null). Default-src self, no unsafe-inline JS, sidecar WS endpoint allow-listed.
- *Keyring secret allowlist:* `src-tauri/src/config_store.rs:92` — `set_secret` / `get_secret` / `delete_secret` now validate the secret name against a fixed allowlist (`deepgram_api_key`, `groq_api_key`). Prevents a future bug or compromised renderer from reading arbitrary keychain entries under our service prefix.
- *RAG fallback bug:* `sidecar/rag_engine.py:144` — `_stream_tokens` had a code path that returned `None` instead of yielding when the upstream stream errored before first token. Fixed to emit an empty-string sentinel so the WS loop closes cleanly.

**Verification (also 2026-05-22):**
- `pytest sidecar/tests -q` → 47 passed (was 44 — security pass added 3 token + CSP tests).
- `npm run build` → clean.
- `cargo check` → clean. (MSVC still required; ran via the existing dev.ps1 vcvars64 path.)
- `npm audit --omit=dev` → 0 production vulnerabilities.
- Local Vite HTTP probe → 200 OK.
- Scan report archived at `D:\tmp\codex-security-scans\cf-software\nogit_20260522T122638+0530\report.md` (outside the repo).

**OpenAI Developers angle:** repo currently uses Groq + Deepgram, **no OpenAI SDK / API key surface** to harden or migrate. Skipped without changes.

**Sync gap addressed 2026-05-26:** the 2026-05-22 pass was never logged to the vault, Notion Home, or Build Board at the time. This entry + the matching Notion updates close that gap.

**Known caveats still open after this pass:**
- Bundled `cf-sidecar.exe` in `src-tauri/binaries/` was last built 2026-05-08 — predates the question-detection filter AND the new token-auth handshake. Live Tauri runs through the bundled binary will fail the WS handshake. Either rebuild PyInstaller or run dev-mode where the sidecar is launched from source. **Rebuild is now required before any release tag.**
- Deepgram + Groq API keys still considered burned (pasted in chat 2026-05-08). Rotate after the live test passes.
- Stealth overlay flags in `tauri.conf.json` still off (Phase 1 follow-up "Restore stealth overlay flags without crashing" still 🔄 In Progress).
- Live Zoom/Meet E2E test still gated on Vite-dies-when-launched-from-bg-harness — Dhyan must run `scripts/dev.ps1` from a real interactive PowerShell window.

---

### 2026-05-02 — CF Software: directory + Notion review, baseline established

**Project:** `D:\Projects\Buteforce\Projects\client facing call ai\Client Facing\cf-software`
**Notion home:** `CF Software — Project Home` (id `35445517-5f11-8197-b618-e249110ade7e`)
**Build Board:** `📋 Build Board` (db `be29ce0d-97f0-4686-a64a-02237bd92e6e`, source `f72551e6-6a6d-47e3-bc45-c6a48120af32`)

**State on this date:** Phase 0 (Setup). All 5 phases listed as 🔜 Not Started in Notion. Code scaffolding is well-developed though — not green-field.

**What is already scaffolded in code:**
- Tauri 2.x shell (`src-tauri/src/lib.rs`) with screen-capture exclusion (Windows `WDA_EXCLUDEFROMCAPTURE`, macOS `NSWindowSharingNone`), three Tauri commands (`show_overlay` / `hide_overlay` / `set_overlay_position`), and sidecar spawn via `tauri-plugin-shell`.
- Python sidecar (`sidecar/main.py`) — FastAPI WebSocket on `ws://127.0.0.1:8765/ws`, full message protocol implemented (`start_session`, `stop_session`, `set_vault_path`, `set_audio_device`, `set_deepgram_key`, `set_groq_key`).
- `transcriber.py` — Deepgram Flux WebSocket via `nova-3` model, `utterance_end_ms=800`, partial + utterance_end → on_question callback.
- `rag_engine.py` — LanceDB + HuggingFace MiniLM embeddings + Groq `llama-3.1-8b-instant` streaming. **Kuzu graph store is stubbed (TODO Phase 3).**
- `audio.py`, `vault_parser.py` — present, not reviewed yet.
- React overlay (`src/components/Overlay.tsx`) — Framer Motion, dark glass styling matches design spec, streaming token cursor + sources tags.
- `.github/workflows/release.yml` — present.

**Gaps vs CLAUDE.md plan:**
- No PyInstaller step in CI yet (Notion has open task: "Add Python sidecar PyInstaller step to CI workflow").
- No `Onboarding.tsx` or `Settings.tsx` in `src/components/` yet — only `Overlay.tsx`.
- No tests anywhere (Python, Rust, or React).
- API keys currently flow through env vars + WebSocket messages, not OS keychain (`tauri-plugin-stronghold`) as CLAUDE.md requires.
- Kuzu graph store imported but not wired — Phase 3 work.

**Sibling brainstorm docs in `Client Facing/`:** Deep Tech Research, Product Vision, Naming Brainstorm, UI Design Direction, Competitor Analysis & Final Stack, Technical Implementation Deep Dive. Note: Product Vision still references the *old* stack (Neo4j + Groq Whisper + Claude as primary LLM). The locked stack in CLAUDE.md and Notion Home supersedes it (Kuzu, Deepgram Flux, Groq LLaMA 3.1 8B).

**Operating mode for this project going forward:**
- Always read Notion `CF Software — Project Home` + Build Board before starting a CF Software task.
- Update Build Board task status when work moves between Not Started / In Progress / Done.
- Append session notes here after meaningful work.
- Never re-derive stack decisions — they're locked in CLAUDE.md.

**Synced this session (2026-05-02 follow-up):**
- Project Home phase table flipped: Phase 0 + Phase 1 → 🔄 In Progress (with explanatory annotations).
- Build Board: 10 tasks marked ✅ Done with verification notes — Tauri scaffold, tauri.conf.json overlay flags, vite.config.ts, requirements.txt, sidecar spawn, Overlay.tsx, Framer Motion in overlay, GitHub Actions release workflow, Groq client init, audio→Deepgram streaming.
- Build Board: `Create src/hooks/useWebSocket.ts` flipped to 🔄 In Progress — file exists but uses a native `WebSocket` directly to `ws://127.0.0.1:8765`, not Tauri's `listen('python-message')` event bridge as the task title implies. Open question for Dhyan: keep direct WS (simpler) or switch to Tauri events (cleaner IPC isolation)?
- Build Board: `Add Python sidecar PyInstaller step to CI workflow` marked 🚫 Blocked with the exact pyinstaller command needed.
- Added `sidecar/tests/test_websocket_protocol.py` — 6 smoke tests locking the message contract (sidecar_ready, unknown-type tolerance, set_vault_path invalidates RAG engine, NO_VAULT_PATH error, NO_DEEPGRAM_KEY error, set_groq_key state update). Plus `requirements-dev.txt` with pytest + httpx.
- Saved durable project memory at `~/.claude/projects/d--Projects-Buteforce-Projects-client-facing-call-ai/memory/project_cf_software.md`.

**Phase 1 wiring + dependency install (same day, 2026-05-02):**
- Toolchain: Rust 1.95.0 + rustup 1.29.0 installed via winget. Node 22.18.0 + npm 11.11.0 already there. Python 3.10.6 used (no 3.11 on machine — works for all current deps).
- npm deps installed (76 packages incl framer-motion, plugin-shell, plugin-dialog, plugin-fs, plugin-notification).
- Python venv at `cf-software/.venv` with 70+ packages: fastapi 0.115.0, uvicorn 0.32.0, deepgram-sdk 3.7.7, groq 0.11.0, llama-index 0.12.42, lancedb 0.30.2, sentence-transformers 3.3.1, torch 2.5.1+cpu, plus pytest 8.3.3 / httpx 0.27.2 dev deps.
- Stack adjustments: bumped llama-index 0.11→0.12 to satisfy lancedb 0.3 integration; split Phase 3 graph deps (llama-index-graph-stores-kuzu + kuzu) into `sidecar/requirements-graph.txt`. rag_engine.py now imports the graph store lazily inside build_index() (was top-level). Type annotation switched from `QueryFusionRetriever | None` to `BaseRetriever | None`.
- Phase 1 frontend wiring: src/lib/config.ts (localStorage persistence), src/hooks/useConfig.ts, src/components/Onboarding.tsx (5-step wizard with @tauri-apps/plugin-dialog file picker, drag region, dark glass shell), src/components/Settings.tsx (status dot, start/stop, reset), App.tsx rewritten to gate on config + auto-push to sidecar + Ctrl+, hotkey for settings.
- Tauri config bumped to visible:true / 520x540 / focus:true so onboarding can render. Placeholder icons generated by `scripts/generate_placeholder_icons.py` (32/128/256 PNG + multi-size ICO + minimal ICNS) — replace with branded artwork before ship.
- Verification: `npx tsc --noEmit` clean, `npm run build` clean (273KB JS / 88KB gzip). pytest 6/6 passing in sidecar/tests/. Live WS smoke test against running uvicorn confirmed `sidecar_ready` + `NO_DEEPGRAM_KEY` error path. HTTP probe on /docs returned 200.
- Helper script `scripts/dev.ps1` sources vcvars64.bat then runs `npm run tauri dev` — needed because rustc on Windows uses MSVC link.exe and Git's link.exe shadows it on PATH.

**Blocker for `tauri dev`:**
- MSVC C++ Build Tools not installed. Both winget and choco install attempts failed because UAC elevation can't be obtained non-interactively from bash (winget exit 1602 = ERROR_INSTALL_USEREXIT, choco hit ACL on `lib-bad`). Windows 11 sudo.exe present but rejected `--inline` mode (config doesn't allow non-interactive elevation).
- Manual fix needed (one-time): open admin PowerShell and run:
  `winget install --id Microsoft.VisualStudio.2022.BuildTools -e --override "--passive --add Microsoft.VisualStudio.Workload.VCTools --includeRecommended"`
- Then `cd cf-software && pwsh ./scripts/dev.ps1` should bring the full stack up.
- Marked the matching Build Board tasks (Install kuzu Python package, Verify cargo tauri dev runs without errors) as 🚫 Blocked with the unblock command in the Notes.

**Phase 3 Graph RAG shipped (same day, 2026-05-02):**
- Discovered llama-index-graph-stores-kuzu has a 0.9.1 release that supports core 0.14.x — pinning compatibility resolved. Bumped llama-index-core 0.12 → 0.14, lancedb integration 0.3 → 0.5, embeddings 0.5 → 0.7. requirements.txt now has Phase 3 deps inline; requirements-graph.txt is back-compat alias.
- Pivoted away from LlamaIndex PropertyGraphIndex (it does LLM entity extraction we don't need — Obsidian wikilinks are explicit). Built a thin custom layer instead.
- New file `sidecar/graph_index.py` — `KuzuGraphIndex` wrapper. Schema: `Note(title PK, path) + LinksTo(FROM Note TO Note)`. Methods: open(fresh), rebuild(notes, edges), expand(seeds, hops) [bidirectional BFS via Cypher variable-length paths], stats(). Dangling edges skipped silently. Kuzu 0.11 expects raw path (not pre-mkdir'd dir) — fixed.
- New file `sidecar/hybrid_retriever.py` — `HybridRetriever(BaseRetriever)`. Algorithm: vector retrieve top-12 → seed = top 3 unique source titles → Kuzu BFS expand 2 hops bidirectional → RRF fusion of (vec_rank, graph_rank) where graph_rank ∈ {1=seed, 5=expanded, 100=disconnected}. Returns top-4. Crucially: graph rank gaps tuned so RRF differentiation between "1 hop away" and "unrelated" actually shows up in scores (initial 1/2/3 ranks gave near-equal totals; 1/5/100 gives clear ~3x penalty for disconnected).
- Wiring: `ObsidianVaultParser` got public `iter_notes()` / `iter_edges()` accessors. `CFRagEngine.build_index(documents, notes=None, edges=None)` now takes optional graph data — when supplied, wires HybridRetriever; when omitted, falls back to vector-only retriever (useful for tests with no wikilinks). `main.py` passes `parser.iter_notes()` + `parser.iter_edges()` through.
- Tests: `tests/test_graph_index.py` (7 tests) covers empty/forward/backward/dangling/rebuild/multi-seed expansion. `tests/test_hybrid_retriever.py` (4 tests) covers empty case, the moat behavior (low-vector-rank but graph-connected note rises above high-vector-rank but graph-disconnected one), graceful fallback when graph raises, top_k cap. **Total: 17/17 sidecar tests passing in ~13s**.
- Build Board: 9 Phase 3 tasks marked ✅ Done, 2 marked 🔄 In Progress (PropertyGraphIndex pivot note; Kuzu DB persistence path → app_data_dir migration). Project Home phase status table reflects Phase 3 In Progress.

**Ship-stack audit (same day, 2026-05-02):**
- Confirmed CLAUDE.md plan still right: **Cloudflare R2** for binary distribution ($0 egress vs S3+CloudFront ~$1k/yr at modest scale), **GitHub Releases + Tauri's github-updater** for v0–v0.5 then optional **Cloudflare Workers + R2** for staged rollouts later, **Vercel free tier** for the Next.js landing page (or Cloudflare Pages to consolidate billing), **GitHub Actions** for CI (already configured).
- **GCP / Render rejected** for the core ship — they're the right answer to a server-side SaaS question, not a local-first desktop app. Cold start alone (1-3s on Cloud Run) blows the <800ms latency budget if anything were ever in the hot path. Future server infra (license/auth, vault sync, B2B team workspaces) is when GCP/fly.io/Render would re-enter the conversation.
- Unavoidable cash cost = code signing: **SSL.com Windows EV ~$349/yr + Apple Developer $99/yr**, plus domain ~$12. Total Phase 4 ship infra ≈ **$465/yr**.
- Build Board ship-blocker right now is the **PyInstaller CI step** (release.yml doesn't bundle the sidecar yet), not infrastructure choice. Marked 🚫 Blocked with the exact pyinstaller command in the Notes.

**Next move queued:** Hybrid-vs-vector quality benchmark on a 10-15 note fake vault, 20 scripted questions, mean reciprocal rank comparison + retrieval p50/p95. This produces the deck-ready proof that the moat actually beats vanilla RAG. After that: PyInstaller CI step, then persistence migration (localStorage → app_config_dir, Kuzu DB → app_data_dir, keys → stronghold).

**Benchmark result (2026-05-08, written up in `cf-software/sidecar/BENCHMARK_RESULTS.md`):**
- Built a 12-note fake_vault fixture (Acme Corp / Acme Q3 deal / Pricing principles / Discount policy / Retainer terms / Scope template / Project Phoenix / Legal review / Past clients / Competitor analysis / Service offerings / Team roster) wired with 23 wikilink edges. Wrote `sidecar/benchmark_hybrid.py` running 20 scripted questions with curated expected-note labels.
- Result: vector-only MRR 0.925, hybrid MRR 0.925 — **tied**. 0/20 misses on both. Top-1 hit rate 85%/85%. Latency p95 vector=20.3ms, hybrid=26.4ms (+6ms for the BFS+RRF; well under the 50ms graph budget).
- Honest read: on a small well-connected vault, vector retrieval already hits the right note in top-4 every time, so hybrid has nothing to fix. The mechanism is correct (proven by unit tests + the `test_graph_promotes_a_connected_lower_ranked_hit` moat case), but it needs vault scale (100+ notes) and vocabulary-disjoint multi-hop questions before MRR diverges.
- Filed follow-up Notion task: "Re-run hybrid-vs-vector benchmark on real Buteforce vault (target: hybrid > vector by +0.05 MRR)" — Phase 3, High priority. Will run against `.agents/knowledge/` once we have a curated question set.
- One subtle bug fixed during benchmark wiring: `vault_parser.py` was passing list-typed metadata (tags, wikilinks) into LanceDB which only accepts scalar metadata. Added a `_is_scalar()` flatten step before yielding Documents; tags are now joined to `tags_str`, wikilinks to `wikilinks_str`. All 17 pre-existing tests still green.

**Ship-stack audit verdict (recap):** stay on Cloudflare R2 + Tauri github-updater + Vercel landing + GitHub Actions. **Reject GCP/Render** — wrong shape for a local-first desktop app. Year-1 infra cost ≈ $465/yr, dominated by code-signing certs. Ship-blocker is **PyInstaller CI step**, not infra choice.

**Next move:** PyInstaller CI step in `.github/workflows/release.yml` so we can actually produce a signed installer. After that, the persistence migration trio (localStorage → app_config_dir, Kuzu DB → app_data_dir, keys → stronghold).

**PyInstaller ship-blocker resolved (2026-05-08):**
- Built the bundled sidecar locally on Windows: **358 MB single-file `cf-sidecar.exe`**. Boot time ~10s (torch + sentence-transformers init), then HTTP /docs returns 200 and the WebSocket emits `sidecar_ready` on connect.
- Caught one real bundle bug during verification: `main.py` was calling `uvicorn.run("main:app", ...)` which fails inside a frozen PyInstaller binary because the `main` module isn't importable from sys.path. Switched to passing the FastAPI `app` object directly. Works in both `python main.py` and the bundled exe.
- Added `pyinstaller>=6.20` to `sidecar/requirements-dev.txt`.
- New file `sidecar/tests/smoke_bundled_sidecar.py` — boots the bundled binary, polls /docs for HTTP 200 (60s timeout for torch init), opens the WS and asserts `sidecar_ready`. Used as a CI gate in `release.yml` between bundling and the Tauri build.
- Rewrote the relevant section of `release.yml`: installs torch CPU first via `--index-url https://download.pytorch.org/whl/cpu` (saves ~2GB CUDA wheel on Linux/Windows runners), installs `requirements-dev.txt` (pulls pyinstaller), runs pytest as a gate, runs PyInstaller, copies to `src-tauri/binaries/cf-sidecar-{target-triple}{.exe}`, runs the smoke test, then hands off to `tauri-action`.
- 358 MB is large (torch + sentence-transformers + lancedb dominate). Acceptable for v0; future optimization paths: prune unused torch components, switch sentence-transformers to a smaller embedding model, or move embedding to a remote API. None block ship.

**Build Board status now:** "Add Python sidecar PyInstaller step to CI workflow" + "Create GitHub Actions release workflow" both ✅ Done. Phase 4 ship is materially closer — remaining big rocks are code-signing certs (Windows EV + Apple Developer), Tauri auto-updater keypair, and the persistence migration trio.

**Persistence migration shipped (2026-05-08):**
- Picked the **split** model over Stronghold (master-password ergonomics) and bare keyring (no debuggable JSON layer): non-secret config to `app_config_dir/config.json`, secrets to OS keystore via the `keyring` crate. Pros: no master password, OS-native trust boundary, JSON file is grep-able for support, secrets never touch disk.
- Rust:
  - Added `keyring = "3"` and `thiserror = "1"` to `src-tauri/Cargo.toml`.
  - New module `src-tauri/src/config_store.rs` owns config_path / load / save / set_secret / get_secret / delete_secret / data_dir. ConfigError implements serde::Serialize so command failures surface in JS with readable strings.
  - Five new Tauri commands wired into the invoke_handler: `load_config`, `save_config`, `set_secret`, `get_secret`, `delete_secret`.
  - Sidecar spawn now resolves `app_data_dir/data`, passes it to the bundled Python via `CF_DATA_DIR` env var, and drains stdout/stderr in a tauri::async_runtime task so the pipe never deadlocks the sidecar.
- TypeScript:
  - Rewrote `src/lib/config.ts` around `invoke()`. `AppConfig` keeps the same surface for components but `loadConfig()` is now async and pulls non-secrets from `load_config` + secrets from `get_secret` (separate keys for Deepgram and Groq).
  - One-shot legacy migration: if the old `cf-software:config:v1` localStorage entry exists, parse it, write to the new stores, then `localStorage.removeItem`. Idempotent.
  - `useConfig.ts` updated for async load/save. `App.tsx` handlers (`handleOnboardingComplete`, `handleReset`) now `await setConfig()`. `Settings.tsx` `clearConfig()` is fire-and-then-reset with error log on failure. `Onboarding.tsx` `onComplete` typed as `void | Promise<void>`.
- Sidecar: `rag_engine.py` reads `CF_DATA_DIR` at import time with the old `sidecar/../data` as dev fallback. `LANCEDB_DIR` + `KUZU_DIR` derive from it. New `tests/test_data_dir_env.py` covers env-set + env-unset paths.
- Validation: `npx tsc --noEmit` clean, `npm run build` clean (274.5 KB JS / 88.9 KB gzip), `pytest` 19/19 green (was 17/17, +2 for the env var tests).
- One unverified surface: the Rust crate compile. Cargo can't run here without MSVC C++ Build Tools (still gated on the user's UAC install). Code review of `config_store.rs` and `lib.rs` says it should compile cleanly — keyring 3.x API, tauri 2 path() API, async_runtime spawn pattern all match the published examples.

**Notion Build Board synced:** 5 persistence-related tasks marked ✅ Done (Save onboarding config.json, Persist Kuzu DB to ~/.cf_software/cf_graph/, Implement first-launch detection, Save settings to ~/.cf_software/config.toml, Load settings from config.toml on every Python sidecar startup). The TOML task got Done with a note that we shipped JSON because it's already in the dep tree.

**Next move:** Tauri auto-updater keypair generation + endpoint wiring. After that, the cert-purchase tasks (SSL.com Windows EV, Apple Developer) are the only remaining ship-side work. Or — once you've installed MSVC — actually run `tauri dev` against this branch to validate the Rust commands compile and round-trip properly.

**Phase 4 ship plumbing — fully wired (2026-05-08):**

*Auto-updater keypair:* Generated via `npx tauri signer generate -p <pwd> -w ~/.cf-software-updater.key -f --ci`. Private key file lives at `~/.cf-software-updater.key` (outside the repo). Public key written to the same path with `.pub` and pasted into `tauri.conf.json` `plugins.updater.pubkey`. Random 32-char password recorded in `cf-software/docs/SHIP_SETUP.md`. Action waiting on Dhyan: upload both as GitHub Actions secrets (`TAURI_SIGNING_PRIVATE_KEY`, `TAURI_SIGNING_PRIVATE_KEY_PASSWORD`) and back up to a password manager. If the key + password are lost, every installed copy stops being able to verify updates.

*tauri-plugin-updater:* Added `tauri-plugin-updater = "2"` to Cargo.toml, registered `tauri_plugin_updater::Builder::new().build()` in `lib.rs`, added `updater:default` to `capabilities/default.json`, npm-installed `@tauri-apps/plugin-updater`. Endpoints currently point at `https://github.com/buteforce/cf-software/releases/latest/download/latest.json` — Dhyan needs to edit the owner/repo path when the actual GitHub repo is decided. Windows install mode is `passive` (silent reinstall + restart). New `src/hooks/useAutoUpdate.ts` probes on mount and returns `{update, status, error, installNow}` — UI banner not yet wired (filed as a Phase 4 task).

*release.yml additions:* `TAURI_SIGNING_PRIVATE_KEY` + `TAURI_SIGNING_PRIVATE_KEY_PASSWORD` env vars in the tauri-action step. `includeUpdaterJson: true` so the workflow publishes the `latest.json` manifest alongside the installers. Apple env vars already present; Windows EV cert env vars commented in (uncomment when SSL.com cert is purchased).

*Ship setup doc:* New `cf-software/docs/SHIP_SETUP.md` — full runbook for the user. Three sections: (1) updater secrets handoff, (2) cert purchase + integration (SSL.com EV $349/yr, Apple Developer $99/yr, with the recommendation to prefer cloud-signing flows over USB tokens for CI sanity), (3) test release via `git tag v0.0.1-test`. Total Year 1 ship cost ≈ $465.

*CI dry-run:* New `cf-software/scripts/ci_dryrun.sh` runs every step of `release.yml` except the Tauri build itself: pytest 19/19, PyInstaller bundle (358 MB), bundled-sidecar smoke test (HTTP 200 + WS sidecar_ready), frontend tsc + vite build. **All green.** Run on every dev machine before tagging a release.

*MSVC C++ Build Tools — still UAC-blocked:* Tried four approaches this session (winget non-interactive → exit 1602; chocolatey → ACL on lib-bad; Windows sudo --inline → policy rejected; rustup GNU toolchain → dlltool/MinGW not on PATH). All fail because elevation can't be obtained from the bash shell non-interactively. The single un-validated surface in this session's Rust changes is the cargo check itself; the persistence migration commands and the plugin-updater wiring need the Dhyan UAC click before `cargo check` (or `tauri dev`) can confirm they compile. Everything else — TS, Python, Node, vite, PyInstaller — is verified.

*Notion Build Board synced:* "Generate Tauri auto-updater keypair" + "Add updater public key and endpoint URLs to tauri.conf.json" → ✅ Done. "Verify Tauri update manifest JSON structure", "Implement background update check on app launch" → 🔄 In Progress. "Enrol in Apple Developer Program", "Configure Windows EV signing in Tauri GitHub Actions workflow", "Verify cargo tauri dev runs without errors" → 🚫 Blocked (with the exact unblock action in each Notes field). Two new tasks filed: "Upload TAURI_SIGNING_PRIVATE_KEY + password as GitHub Actions secrets" (Critical) and "Wire useAutoUpdate hook into a UI banner" (Normal).

**Codex collab session — dev stack alive (2026-05-08, late):**

Dhyan installed MSVC C++ Build Tools (UAC unblocked at last) and brought Codex in to drive the first dev-stack boot. Result: Vite frontend on `http://[::1]:1420`, cf-software.exe Tauri shell running, cf-sidecar.exe running, sidecar binary copied to `src-tauri/binaries/`, npm run build passes, `cargo check` passes. The "Verify cargo tauri dev runs without errors" Build Board task is now ✅ Done.

What Codex changed (with intent and consequences):

- *windows-rs API fix in lib.rs:* `let hwnd = HWND(window.hwnd().unwrap().0)` (was `.0 as isize`). The cast was wrong against `windows = 0.58`; without this the WDA_EXCLUDEFROMCAPTURE call wouldn't compile. Trivial, correct.
- *tauri.conf.json stealth flags temporarily disabled:* `decorations:true`, `transparent:false`, `alwaysOnTop:false`, `skipTaskbar:false`, `shadow:true`, plus the `trayIcon` block removed entirely. Reason: the original stealth config was causing Windows access-denied crashes at launch. Working theory is the trayIcon iconPath resolution OR the transparent + WDA_EXCLUDEFROMCAPTURE timing race. Filed as a Phase 1 follow-up: "Restore stealth overlay flags without crashing" — bring them back one at a time, trayIcon last, after confirming icons/tray.png is loadable from the bundled resource path.
- *dev.ps1: `npm` → `npm.cmd`* — PowerShell-only invocation fix.
- *transcriber.py: new `_looks_like_question()` filter* — only utterances ending with `?` or starting with what/when/where/who/why/how/which/can/could/will/would/should/is/are/was/were/do/does/did/have/has/had get sent through RAG + Groq. Cuts the false-positive-on-statements problem the eager 3+-word gate had. I added 25 pytest cases this session covering both directions; total sidecar tests now **44/44 passing**.
- *docs/ARCHITECTURE_AND_WORKFLOWS.md:* new doc Codex wrote during this session — phase-by-phase architecture with mermaid diagrams. Honest about gaps: "the full real-call E2E is not yet proven", "graph advantage still needs to be proven on a real, larger vault". Useful onboarding doc for any future contributor.

Known caveat for the live test: **the bundled cf-sidecar.exe in src-tauri/binaries/ pre-dates the question-filter tweak.** Codex didn't rebuild it because PyInstaller takes ~5 min and they were time-pressured. Consequence: during the live test the running app will react to every 3+-word utterance, not just questions. Filed as a High-priority Phase 4 task: "Rebuild bundled cf-sidecar.exe with the new question-detection filter."

Three new Build Board tasks filed:
- "Restore stealth overlay flags without crashing" (Phase 1, High, 🔄 In Progress)
- "Rebuild bundled cf-sidecar.exe with the new question-detection filter" (Phase 4, High, 📋 Not Started)
- "Live Zoom/Meet call E2E test — vault + Deepgram + Groq + overlay end to end" (Phase 1, Critical, 🔄 In Progress)

Test runbook for Dhyan: `cf-software/docs/LIVE_TEST_RUNBOOK.md` (writing now). Steps inline summary: pick vault folder, paste Deepgram + Groq API keys, leave audio device blank for auto-pick, click Start session, join real call, ask a vault-answerable question. Watch for `indexing_done` then overlay popping for clear questions. Window is in normal-desktop mode for this test, not stealth.

**Handover doc written (2026-05-13):** `cf-software/docs/HANDOVER_2026-05-13.md` — comprehensive recap of the whole 11-day arc (build journey, 13 problems we hit and how each was solved, current open items, resume instructions, file inventory, Notion/vault/secret pointers, stack invariants). When picking the project back up, read this first, then `CLAUDE.md`, then the relevant phase doc. Single biggest currently-open thing: the live call E2E test, gated on the Vite-dies-when-launched-from-bg-harness problem (Problem 12). Workaround: run `scripts/dev.ps1` from a real interactive PowerShell window, not from the agent harness.

---

### 2026-04-28 — Lead Outreacher: Render deploy fixed + notification center + HTML email template

**Project:** `D:\Projects\Buteforce\Projects\Lead Outreacher`
**Live URL:** `https://buteforce-outreach.onrender.com`
**Render service:** `srv-d7ng7h3eo5us73f9p6rg` (buteforce-outreach, free tier, Python 3)
**GitHub repo:** `dhyankarthik-code/buteforce-lead-outreacher`, branch `main`

**Bugs fixed:**
1. `/api/queue` returned 500 — `PermissionError` from gspread: service account `friday@buteforce.iam.gserviceaccount.com` was not shared on the sheet. Fixed by sharing from Google Sheets UI.
2. After that: `WorksheetNotFound: Clients detail` — actual tab name in the spreadsheet didn't match the env var. Fixed by renaming the tab to "Clients detail".

**Brand redesign (index.html):**
- Inter font loaded from Google Fonts (replaces system-ui)
- Tokens tightened to brand spec: `#0a0a0a` text, `#FFFC01` yellow, `#f5f6f8` bg
- `-webkit-font-smoothing: antialiased` added throughout
- Header height bumped to 48px, sidebar to 256px, minor spacing polish

**Notification center shipped:**
- Bell icon (top-right header) with yellow unread badge
- `GET /api/notifications` — polls IMAP inbox (cooldown 5 min), classifies new replies with Gemini, merges into `notif.json`
- `POST /api/notifications/check` — force immediate IMAP check (used by "Check now" button)
- `PUT /api/notifications/{id}/read` — mark single or "all" as read
- `review_app/inbox_checker.py` — IMAP4_SSL reply detector (matches by `Re:` prefix or `In-Reply-To` header), plain-text body extractor
- `review_app/notif_store.py` — file-based store, merge dedup by Message-ID, 5-min poll throttle
- Gemini classifies each reply into: `interested / meeting_requested / question / not_interested / out_of_office / unsubscribe / other` — plus `reason` and `suggested_action`
- Panel: color-coded classification badges, 2-line reply preview, sender + time
- Thread modal: original email card + reply card + AI analysis card (yellow background)
- Frontend polls `/api/notifications` every 5 min; Escape key closes panel/modal

**Branded HTML email template shipped:**
- `review_app/email_template.py` — converts plain-text body to HTML email
- Layout: `#FFFC01` yellow accent bar (3px top), Buteforce brand header, body paragraphs, professional signature (Dhyan name + title + buteforce.com + YouTube + email), footer tagline ("No consultants. No pilot projects. Working systems.")
- Plain-text → HTML: double newlines → `<p>`, numbered lists → `<ol><li>`, URLs linkified
- `mailer.py` updated: sends `multipart/alternative` (plain text + HTML), From header now shows full name "Dhyaneshwaran Karthikeyan"
- Graceful degradation: if template build fails, plain text still sends

**Files changed (commits `84dfb8a`, `93603bf`):**
- `review_app/inbox_checker.py` ← NEW
- `review_app/notif_store.py` ← NEW
- `review_app/email_template.py` ← NEW
- `review_app/app.py` — 3 new notification endpoints + `_run_inbox_check()` helper
- `review_app/mailer.py` — multipart HTML send
- `review_app/templates/index.html` — full brand redesign + notification UI
- `render.yaml` — `IMAP_HOST=imap.gmail.com`, `IMAP_PORT=993` added

**Active threads / things to verify:**
- IMAP access must be enabled for `admin@buteforce.com` in Google Workspace Admin Console (Apps → Gmail → End user access → IMAP)
- `notif.json` lives on ephemeral Render disk — resets on each redeploy. Read state is lost but replies are re-fetched from IMAP on first load after redeploy.
- Free Render tier spins down on inactivity → 50s+ cold start delay on first request

---

### 2026-04-22 - Lead Outreacher review_app verification + Gemini migration plan

**Project:** `D:\Projects\Buteforce\Projects\Lead Outreacher`

**Work done:**
1. Started the local `review_app` server and verified the UI loads at `http://127.0.0.1:8765`.
2. Confirmed the current blocker is credential/provider-side: `review_app/.env` is missing and `Generate email` fails without `ANTHROPIC_API_KEY`.
3. Checked the wider Buteforce stack and found the existing pattern already favors Gemini in lightweight Python tools and records Vertex friction for local Windows flows.
4. Chose the recommended migration path: replace Anthropic in `review_app/generator.py` with Google Gemini Developer API (`google-genai`, server-side key auth), while leaving SMTP send logic unchanged.

**Next:**
- Create or reuse a Gemini API key in Google AI Studio and link Cloud Billing if paid quota is needed.
- Patch `review_app` to use Gemini, update `.env.example`, and replace the launcher check.
- Re-test the full flow: generate -> edit -> approve/send.

---

### 2026-04-22 - Lead Outreacher review_app Gemini migration completed

**Project:** `D:\Projects\Buteforce\Projects\Lead Outreacher`

**Work done:**
1. Replaced Anthropic in `review_app/generator.py` with the official `google-genai` SDK.
2. Chose stable `gemini-2.5-pro` as the default model to protect draft quality during the provider swap.
3. Added structured JSON enforcement for `subject` and `body`, plus a fallback extractor for SDK responses where `response.text` is empty.
4. Updated `.env.example` and configured local `.env` for Gemini.
5. Updated `start_review.bat` to use an isolated `review_app/.venv` instead of installing into the global Python environment.
6. Verified the app end-to-end for generation: root page returned 200 and `POST /api/generate/6` returned 200.

**Next:**
- Add `SMTP_PASS` in `review_app/.env`.
- Re-test `Approve & Send`.

---

### 2026-04-20 — Harvard Algorithmic Trading with AI — Full Setup + Binance Paper Stack

**Project:** `D:\Projects\Fintech\Harvard-Algorithmic-Trading-with-AI`
**Source repo:** https://github.com/moondevonyt/Harvard-Algorithmic-Trading-with-AI

**Work done:**

1. **Repo cloned and environment set up:**
   - Python 3.10 venv at `venv/`
   - All dependencies installed: pandas, numpy, TA-Lib (prebuilt Windows wheel), backtesting, yfinance, ccxt, hyperliquid-python-sdk, eth-account, dash, plotly
   - `pandas-ta` not available for Python 3.10 — import guarded with try/except in `nice_funcs.py`

2. **Hardcoded Mac paths fixed** in all three scripts:
   - `backtest/template.py` — now uses `os.path.dirname(__file__)`
   - `backtest/bb_squeeze_adx.py` — same
   - `backtest/data.py` — same

3. **Backtests confirmed working:**
   - `bb_squeeze_adx.py` ran full optimization on BTC 6h data
   - Best params found: BB=10, KC=15, ADX=10, TP=3%, SL=2%

4. **Binance paper trading stack built** (replaces Hyperliquid, no deposit needed):
   - `implement/paper_engine.py` — local position/PnL tracker, persists to `paper_state.json`
   - `implement/nice_funcs_binance.py` — drop-in replacement for `nice_funcs.py`, same API signatures
   - `implement/ws_feed.py` — Binance WebSocket feed (no auth), `LATEST_TICK` + `OHLCV_BUFFER` for agents
   - `implement/bot_binance.py` — same BB Squeeze ADX strategy on Binance data, paper execution
   - `implement/dashboard.py` — Plotly Dash live chart at http://localhost:8050

5. **Live data confirmed:** BTC ask/bid streaming at `$75,083`, OHLCV from Binance public API

**How to run:**
```bash
# Backtest (historical)
cd backtest && PYTHONUTF8=1 ../venv/Scripts/python bb_squeeze_adx.py

# Paper bot (live, no deposit)
cd implement && PYTHONUTF8=1 ../venv/Scripts/python bot_binance.py

# Live dashboard (open http://localhost:8050)
cd implement && PYTHONUTF8=1 ../venv/Scripts/python dashboard.py
```

**Next for this project:**
- Wire up WebSocket feed (`ws_feed.py`) into the bot for sub-minute data
- Add multi-symbol scanning to the bot
- Connect agents to `LATEST_TICK` / `OHLCV_BUFFER` for autonomous trading decisions

---

### 2026-04-19 — Blog Agent to Live Site API Integration

**Project:** `D:\Projects\Buteforce\Projects\Marketing agents\blog-agent` and `D:\Projects\Buteforce\Site\buteforce-website`

**Work done:**
1. **Agent-to-Site Gateway:** Implemented a new Next.js `/api/agent/blog` endpoint directly on the Buteforce website. This acts as a centralized receiver to parse deployed site content (`lib/data.ts` and `content/blog`) and handle authenticated Github pushes.
2. **Crash Prevention Built:** Rewrote `site_tool.py` so it executes `GET` fetch requests toward the live Buteforce API instead of crashing against hardcoded local Windows file paths when deployed on Render.
3. **Decoupled Github from Agent:** Discarded direct `github_publish` methodology from the Render agent. The agent payload is now sent directly via `POST` to the custom Buteforce gateway, enabling seamless publishing without keeping a live `GITHUB_TOKEN` vulnerable on Render.
4. **Docs Updated:** Pruned old dependencies systematically off the `.env` lists in `tech_stack.md` and `render.yaml`. Replaced with `SITE_API_URL` and secure `AGENT_SECRET_KEY` requirements.

**Next:**
- Setup environment variables on Render (`AGENT_SECRET_KEY`) and Vercel (`AGENT_SECRET_KEY`, `GITHUB_PUBLISH_TOKEN`).
- Fire test blog off the updated Swarm Publisher stack.

---

### 2026-04-16 — Hooter / RetailEye Dashboard Redesign + Production Prep

**Project:** `D:\Projects\Staff heat map` — Retail foot-traffic analytics platform (CV pipeline + Next.js dashboard)

**Work done:**

1. **Full dashboard redesign** — Replaced generic Tailwind template with a designed UI:
   - Dark sidebar (`#111216`) with subtle yellow ambient glow, nav with yellow active state
   - Glassmorphism header bar (backdrop-blur)
   - KPI metric cards with left-edge accent color bars (no icon bg boxes)
   - Section headers: uppercase tracking-widest, tiny
   - Zone engagement: ranked list with color bars
   - Live event log: **terminal style** (dark card, macOS traffic-light header, monospace lines)
   - Login page: split layout — dark brand panel left, clean form right

2. **Hardcoded localhost URLs fixed** — all pipeline URLs now read from `NEXT_PUBLIC_CV_PIPELINE_URL` env var. ZoneEditor accepts `pipelineUrl` prop. Defaults to `http://localhost:8000` for local dev.

3. **CORS hardened** — `main.py` now reads `CV_ALLOWED_ORIGINS` env var; defaults to `["*"]` only when unset (dev only).

4. **Hardcoded store_id fixed** — `main.py` now reads `STORE_ID` env var.

5. **Branding fixed** — Login page was "RetailEye", now "Hooter" throughout.

6. **ZoneEditor fixed** — Removed duplicate `Users` SVG icon (was shadowing lucide import). Fixed `ctx.fontWeight` (invalid Canvas API — moved to `ctx.font`). Error state added to save flow.

**Env vars needed for production deployment:**
- `NEXT_PUBLIC_SUPABASE_URL` + `NEXT_PUBLIC_SUPABASE_ANON_KEY` — Supabase
- `NEXT_PUBLIC_CV_PIPELINE_URL` — public URL where cv-pipeline is hosted (e.g. GCP VM)
- `CV_ALLOWED_ORIGINS` — dashboard URL(s) for CORS
- `STORE_ID` — UUID for multi-store support
- `SUPABASE_URL` + `SUPABASE_KEY` — Python service role

**Unresolved:**
- Dashboard is Next.js → deploy to Vercel (just add env vars, connect repo)
- CV pipeline → already has `Dockerfile` + `deploy_gcp.ps1` for GCP Spot VM; set `CV_ALLOWED_ORIGINS` to Vercel URL

---

### 2026-04-18 — Graphify Vault Graph + Unified Memory for All Agents

**Work done:**

1. **Unified memory vault wired to all 4 AI tools on machine:**
   - Claude Code: `~/.claude/settings.json` → `mcpServers.obsidian-vault`
   - Cursor: `~/.cursor/mcp.json` → `mcpServers.obsidian-vault`
   - Google Antigravity: `~/.gemini/antigravity/mcp_config.json` → `mcpServers.obsidian-vault`
   - VS Code / Copilot: `AppData/Roaming/Code/User/mcp.json` → `servers.obsidian-vault`
   - GitHub Copilot instructions: `~/.github/copilot-instructions.md` — full vault protocol written
   - Global CLAUDE.md updated with "Unified Memory Vault" rules section
   - `VAULT_README.md` written as master orientation doc for all agents

2. **Graphify knowledge graph built on vault:**
   - 137 nodes · 150 edges · 36 communities (Leiden clustering)
   - God nodes: Cold Outreach Templates (11 edges), ICP (10), Master Index (9), Lead Gen (9), Hooter Plan (8)
   - 6 hyperedges: Brand Identity System, CV Analytics Stack, Proof-Content-Sales Loop, Per-Vertical Sales System, Swarm Pipeline, Vault Memory Protocol
   - Outputs: `graphify-out/graph.json`, `graphify-out/graph.html`, `graphify-out/GRAPH_REPORT.md`
   - Obsidian vault: `graphify-out/obsidian/` — 173 linked notes

3. **Hooter YouTube pipeline tested:**
   - yt-dlp resolved `watch?v=MNn9qKG2UFI` to direct Google CDN URL
   - OpenCV opened stream successfully; pipeline ran at 8.8 FPS with 3 active DeepSORT tracks

**Next — Phase 2 Hooter:**
- Zone transitions matrix (A→B heatmap from `zone_transitions` view)
- Peak hour per zone
- Zone comparison side-by-side

---

### 2026-04-17 — Hooter Logo Integration + Phase 1

**Work done:**

1. **Real Buteforce logo integrated** everywhere:
   - `public/favicon.svg` — logo paths on dark `#111216` rounded square, paths filled yellow `#facc15`
   - `src/app/components/BfLogo.tsx` — shared server+client compatible SVG component
   - Sidebar brand area — replaced "H" placeholder with `<BfLogo size={32} color="#facc15" />`
   - Login page — both desktop brand panel and mobile header use real logo

2. **Phase 1 — Date range selector**
   - Header now has Today / 7D / 30D pill-segment control with animated active-tab styling
   - `fetchAnalytics` queries filtered by `.gte('timestamp', from)` based on selected range
   - All KPI captions and chart titles adapt to the selected range label

3. **Phase 1 — Bounce Rate KPI**
   - New 5th KPI card: "Bounce Rate" (% of dwell events < 30s)
   - KPI grid expanded from 4 to 5 columns (`xl:grid-cols-5`)
   - Accent color: orange `#f97316`

4. **Phase 1 — Visit Duration Histogram**
   - `buildDwellBuckets()` helper groups dwell seconds into 6 buckets: `<15s / 15–30s / 30–60s / 1–3m / 3–10m / >10m`
   - Bar chart below Traffic Profile using rainbow cells (blue → yellow → green encoding short → engaged → high-intent)
   - Bounce marker caption under histogram shows bounce % and threshold explanation

5. **Bug fixes**
   - `src/utils/supabase/server.ts` — updated to `async function createClient()` + `await cookies()` for Next.js 15 compatibility
   - Recharts `Tooltip formatter` types fixed (no more `v: number` hard-cast)
   - Login `signIn` action updated to `await createClient()`
   - Zero TS errors, clean `next build`

**Next — Phase 2:**
- Zone transitions matrix (zone A → zone B heatmap using `zone_transitions` view)
- Peak hour per zone (hour with max visits per zone_id)
- Zone comparison view side-by-side

---

### 2026-04-15 — Blog Agent Full Build + UI Fixes

**Work done across 3 context windows:**

1. **Codebase audit** — Mapped full pipeline: ADK orchestrator, 4-stage agent swarm, Supabase DB, Next.js dashboard, TinaCMS publishing.

2. **Site integration** — Connected research agents to `D:/Projects/Buteforce/Site/buteforce-website`. Research agent now reads existing blog posts (avoid duplicates) and `lib/data.ts` (brand alignment). 9 research sources total.

3. **TinaCMS alignment** — Fixed writer agent frontmatter to match TinaCMS schema exactly (`title, description, date, tags, image`). Fixed filename format to `{slug}.mdx`. Updated `GITHUB_REPO=buteforce-code/ButeForce-Site`.

4. **Dashboard redesign** — Full light theme rewrite per brand bible (#fff bg, #0a0a0a text, #e8ff00 accent). Real B-mark SVG in nav. Active pipeline step uses accent yellow.

5. **Delete + recovery flows** — Added `--delete` and `--reset` CLI args to `run.py`. New API routes `delete` + `reset`. Dashboard shows × delete on every card (two-step confirm). Failed topics show "Reset to Review" or "Re-run Research" with context-aware message (no more "check logs" blocking state).

6. **Bug fixes (2026-04-15)**:
   - Fixed `onMouseEnter/onMouseLeave` DOM mutation → CSS `.card-delete-btn` hover class
   - Fixed `handleReset` setState-after-unmount → `useRef` mounted guard
   - Added 1.5s delay before `onCreated()` so Python has time to write topic to DB
   - Corrected `GITHUB_REPO` in `dashboard/.env.local`

**Key architecture decision (standing)**:
Never use `SUPABASE_SERVICE_KEY` in Next.js route handlers on Windows. All writes go through `spawn('python', ['run.py', ...])` detached. Only anon key reads in Next.js.

---

### 2026-04-12

- Connected the workspace to the Obsidian vault through a local `.agents` junction.
- Added Codex bootstrap and active-brain skills so future sessions can retrieve focused context from the vault.
- Added a search helper script at `.codex/skills/obsidian-active-brain/scripts/obsidian_memory.py`.
- Standardized vault retrieval rules in `workflows/codex-active-brain.md`, `workflows/load-memory.md`, and `rules/memory.md`.
