---
description: Active Learning Memory Protocol — Dhyan's Autonomous Knowledge System
---

# Active Memory Protocol

## Purpose
Every AI agent operating in this workspace MUST follow this protocol to maintain a continuously accurate, personalized knowledge base about Dhyan and Buteforce.

---

## On Every Session Start

1. **Read these files before doing ANYTHING else:**
   - `.agents/knowledge/dhyan_psychology.md` — Dhyan's personality, taste, and decision matrix
   - `.agents/knowledge/brand_bible.md` — Buteforce brand identity and anti-patterns
   - `.agents/knowledge/founder.md` — Contact details, professional identity, voice
   - `.agents/knowledge/tech_stack.md` — All technical conventions and known issues
   - `.agents/knowledge/marketing_engine.md` — Lead gen pipeline and operational context

2. **Do NOT proceed with any task until this knowledge is loaded.**

---

## Active Learning: Detect & Update

Monitor every user message for signals that indicate a **preference change** or **priority shift**. Triggers include:
- "I don't like X anymore"
- "Stop doing Y"
- "Actually, let's change Z to..."
- Any contradiction of a rule in the knowledge files
- A new decision that supersedes an old one

### When a trigger is detected:
1. Immediately update the relevant `.agents/knowledge/*.md` file
2. Strikethrough the old value for traceability
3. Apply the new rule in the current task immediately
4. Do NOT ask for confirmation to update the knowledge base — just do it

---

## Active Learning: Capture New Knowledge

After completing any significant task, append a brief log entry to the relevant file:
- New technical discovery → `tech_stack.md`
- New brand decision → `brand_bible.md`
- New personal preference learned → `dhyan_psychology.md`
- New lead/marketing insight → `marketing_engine.md`

---

## The Golden Rules (Never Violate)
1. **Never ask Dhyan to repeat himself.** If it's in the knowledge files, use it.
2. **Speed over ceremony.** When he says "go" or "continue", DO NOT ask clarifying questions. Execute.
3. **Show, don't tell.** Run code, open browsers, make changes — then report results.
4. **If in doubt about his taste, refer to `dhyan_psychology.md`.**
5. **Never contradict the brand bible without explicit instruction.**
