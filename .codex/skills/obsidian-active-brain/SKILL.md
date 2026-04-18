---
name: obsidian-active-brain
description: Use for Buteforce workspace tasks that depend on knowledge about Dhyan, Buteforce, active projects, prior decisions, or when Codex should retrieve from and update the Obsidian vault exposed in this workspace at .agents.
---

# Obsidian Active Brain

This skill turns the Obsidian vault into the working memory layer for Buteforce tasks.

## Vault Layout

- Vault root: `.agents`
- `.agents` points to the Obsidian vault at `D:\Projects\Buteforce\.agents`
- Core knowledge: `knowledge/*.md`
- Rules: `rules/*.md`
- Workflows: `workflows/*.md`

## Before Doing Project-Specific Work

1. Read `knowledge/INDEX.md`.
2. Read `workflows/codex-active-brain.md`.
3. Read only the knowledge files relevant to the task.
4. If the task depends on recent context, read `knowledge/codex_conversations.md`.

## What To Load By Topic

- Dhyan preferences, taste, decision style:
  `knowledge/dhyan_psychology.md`
- Founder identity, voice, positioning:
  `knowledge/founder.md`
- Brand and creative direction:
  `knowledge/brand_bible.md`
- Tech conventions, architecture, bugs, repo paths:
  `knowledge/tech_stack.md`
- Marketing operations, lead gen, funnel logic:
  `knowledge/marketing_engine.md`

## Retrieval Workflow

- For quick retrieval, run:
  `python .codex/skills/obsidian-active-brain/scripts/obsidian_memory.py search "<query>"`
- Use the most relevant notes, not the entire vault.
- Prefer durable notes over raw conversation history.

## Update Workflow

After a significant task, capture durable knowledge in the smallest correct file:

- Personal preference -> `knowledge/dhyan_psychology.md`
- Founder/company identity -> `knowledge/founder.md`
- Brand rule or taste decision -> `knowledge/brand_bible.md`
- Technical decision, bug, path, infra fact -> `knowledge/tech_stack.md`
- Marketing or workflow insight -> `knowledge/marketing_engine.md`
- Session-specific handoff or unresolved thread -> `knowledge/codex_conversations.md`

When updating:

1. Keep updates concise and factual.
2. Preserve history when a rule changes.
3. Avoid storing secrets, tokens, or one-off noise.
4. Record only durable facts, preferences, decisions, and unresolved threads.

## Memory Hygiene

- Do not dump entire conversations into durable files.
- Do not use `codex_conversations.md` as the source of truth for stable facts.
- If a vault note is stale, fix it as part of the task when appropriate.
