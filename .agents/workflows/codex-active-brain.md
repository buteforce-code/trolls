---
description: Codex retrieval and memory update workflow for the Buteforce Obsidian vault.
---

# Codex Active Brain

This vault is the active memory layer for Codex work in the Buteforce workspace.

## Session Start

1. Read `knowledge/INDEX.md`.
2. Read the core knowledge files that are relevant to the request.
3. Read `knowledge/codex_conversations.md` only when the task depends on recent context or unresolved threads.
4. Prefer durable knowledge notes over raw conversation history.

## Retrieval Rules

- Load the minimum useful context.
- Retrieve by topic, not by habit.
- When a repo or workspace file is fresher than the vault, trust the fresher source and update the vault if the fact is durable.

## Update Rules

Store new knowledge in the smallest correct place:

- Preferences, taste, working style -> `knowledge/dhyan_psychology.md`
- Founder identity, voice, positioning -> `knowledge/founder.md`
- Brand decisions, anti-patterns, creative rules -> `knowledge/brand_bible.md`
- Technical conventions, bugs, architecture, repo paths -> `knowledge/tech_stack.md`
- Marketing strategy, outreach, funnel logic, campaign process -> `knowledge/marketing_engine.md`
- Session notes, unresolved blockers, recent handoffs -> `knowledge/codex_conversations.md`

## What To Save

Save:

- stable preferences
- durable business facts
- important technical discoveries
- decisions that future sessions will need
- unresolved blockers that should survive session boundaries

Do not save:

- secrets, keys, or credentials
- large raw logs
- repetitive conversation filler
- facts that already exist unchanged in a better note

## Logging Style

- Keep entries short and factual.
- Use dates.
- Link to files, repos, or topics when helpful.
- If a rule changes, preserve traceability instead of silently overwriting meaning.
