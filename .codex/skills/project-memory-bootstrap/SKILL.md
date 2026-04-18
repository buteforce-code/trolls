---
name: project-memory-bootstrap
description: Bootstrap Buteforce project context from the Obsidian vault exposed in this workspace at .agents whenever the user asks to continue work, recover context, or resume a prior thread.
---

# Buteforce Project Memory Bootstrap

Use this project-local bootstrap for the Buteforce workspace.

## Vault

- Source of truth: `.agents` in this workspace
- The `.agents` folder is a junction to `D:\Projects\Buteforce\.agents`
- Read `knowledge/INDEX.md` first.
- Then load only the files needed for the current task.

## Default Read Order

1. `knowledge/INDEX.md`
2. `knowledge/dhyan_psychology.md`
3. `knowledge/brand_bible.md`
4. `knowledge/founder.md`
5. `knowledge/tech_stack.md`
6. `knowledge/marketing_engine.md`

## Recent Context

If the user is continuing an interrupted task, also read:

- `knowledge/codex_conversations.md`
- Any project log or handoff file in the current workspace

Prefer durable knowledge files over the conversation log when they conflict.

## Retrieval Rules

- Pull in only the notes relevant to the request.
- Treat the vault as higher-priority project context than model memory.
- If the workspace contains fresher factual evidence than the vault, use the fresher evidence and note that the vault should be updated.

## Output Format

When bootstrapping, summarize:

- Current State
- Relevant Memory Loaded
- Open Issues
- Next 3 Actions
