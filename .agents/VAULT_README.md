# Buteforce Unified Memory Vault

**Path:** `D:\Projects\Buteforce\.agents`  
**Owner:** Dhyan Vrit — Buteforce founder  
**Purpose:** Single persistent memory brain shared across ALL AI agents on this machine

---

## How to access this vault

This vault is mounted as the **`obsidian-vault` MCP server** in:
- Claude Code (`~/.claude/settings.json`)
- Cursor (`~/.cursor/mcp.json`)
- Google Antigravity (`~/.gemini/antigravity/mcp_config.json`)
- VS Code / GitHub Copilot (`AppData/Roaming/Code/User/mcp.json`)

Use MCP file tools (`read_file`, `list_directory`, `write_file`, `search_files`) to interact with it.

---

## Session start — always do this

```
1. read_file("knowledge/INDEX.md")          → understand active projects
2. read_file(<relevant knowledge file>)      → load task-specific context
3. Proceed with full context
```

## Session end — always do this

```
1. write_file("knowledge/codex_conversations.md")  → append session notes
2. write_file(<changed knowledge file>)             → update any changed facts
```

---

## Vault map

### `knowledge/` — Long-term facts (source of truth)

| File | Contents |
|------|----------|
| `INDEX.md` | Active projects + what to load per task |
| `hooter_product_plan.md` | Hooter retail analytics — full enterprise plan, phases, roadmap |
| `tech_stack.md` | All tech decisions (Next.js 16, FastAPI, YOLOv8, Supabase, GCP, Vercel) |
| `brand_bible.md` | Buteforce brand — voice, visual identity, rules |
| `icp.md` | Ideal customer profile |
| `competitors.md` | Market + competitor analysis (TangoEye, etc.) |
| `founder.md` | Dhyan's background, working style, decision framework |
| `dhyan_psychology.md` | Personality, communication preferences |
| `marketing_engine.md` | Growth strategy, content machine |
| `seo_strategy.md` | SEO approach |
| `content_calendar.md` | Blog + content calendar |
| `outreach_templates.md` | Sales / outreach templates |
| `case_studies.md` | Customer case studies |
| `codex_conversations.md` | Rolling session log — all agents write here |

### `rules/` — How memory works
- `memory.md` — Rules for reading/writing this vault

### `workflows/` — Step-by-step protocols  
- `active_memory.md` — What to load per session type
- `load-memory.md` — Memory loading workflow
- `codex-active-brain.md` — Active brain retrieval pattern

### `graphify-out/` — Knowledge graph (token-efficient queries)
- `graph.json` — Full graph of all vault content
- `GRAPH_REPORT.md` — God nodes, communities, surprising connections
- Use `graphify query "<question>"` instead of reading raw files when graph exists

---

## Active projects (as of 2026-04-18)

| Project | Path | Status |
|---------|------|--------|
| **Hooter** | `D:\Projects\Staff heat map\` | Active — Phase 1 done, Phase 2 next |
| **Buteforce Blog Agent** | `D:\Projects\Buteforce\` | Active |
| **Buteforce Website** | `D:\Projects\Buteforce\Site\` | Active |
| **Company setup** | (in knowledge files) | Active |

---

## Rules

1. **Read before you act.** Always check the relevant knowledge file before answering any product/brand/tech question.
2. **Write after you act.** Always save meaningful work to `codex_conversations.md` and update facts in-place.
3. **Never duplicate.** If a fact already exists in a knowledge file, update it — don't create a new file.
4. **Graph first.** If `graphify-out/graph.json` exists, query it instead of reading all files. It's 70x more token-efficient.
5. **Cross-agent consistency.** Every agent reads the same vault. Don't contradict what another agent wrote.
