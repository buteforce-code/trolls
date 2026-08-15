"""
GEO template — the answer-engine shape every post must have, and the gate that enforces it.

WHY THIS EXISTS
AI Visibility SCAN 001 (2026-07-26, `.agents/knowledge/ai_visibility.md`) measured Buteforce at
**0/18 recommended, 0/18 cited** across the frozen buyer-prompt set. The Princeton GEO study is the
prescription: statistics, quotations and citations lift AI visibility +30-40%, while adjective-led
copy lifts nothing. Answer engines quote a self-contained paragraph sitting under a question-shaped
heading; they cannot quote a vibe.

So this module encodes six requirements as ONE template change that every future post inherits:

  1. QUESTION H2 + ANSWER   — >=2 `## ...?` headings, each followed immediately by a 40-160 word
                              self-contained prose answer. This is the quotable unit.
  2. HARD NUMBERS           — >=2 canonical proof numbers from `.agents/knowledge/case_studies.md`,
                              and ZERO puffery adjectives standing in for a number.
  3. COMPETITOR TABLE       — a real comparison table naming >=2 actual competitors. Honest
                              comparison is what gets a page cited as a source rather than skipped
                              as a brochure (SCAN 001 finding 1: this category's citation graph is
                              vendor-owned listicles).
  4. "NOT A FIT IF" SECTION — explicit disqualification. Stated limits are the strongest citation
                              signal a vendor page can carry.
  5. VISIBLE dateModified   — freshness, rendered on-page and in JSON-LD.
  6. NAMED AUTHOR           — a person, not "the team". Entity signal; SCAN 001's root cause was
                              an entity gap, not a content gap.

DESIGN SPLIT — the repo has already been burned once by trusting a prompt (the 2026-06-29
gpt-4o switch silently halved output; five thin posts shipped). So:
  - (1)-(4) are AUTHORED by the writer, then VERIFIED here. A failure returns a precise repair
    brief; the orchestrator retries once, then holds the topic for human review. Never publishes.
  - (5)-(6) are pure metadata, so they are INJECTED deterministically. Nothing to get wrong.

`GEO_TEMPLATE_RULES` is the prompt half, injected into the writer. `audit()` is the gate half.
The prompt is advisory. The gate is not.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timezone

from swarm import brand
from swarm.brand import BrandProfile

# ── Where the brand-specific half now lives ───────────────────────────────────────────────
# Identity, proof numbers, competitors and the gate thresholds used to be literals here, which
# meant one deployment was one brand forever. They are now fields on a `BrandProfile`
# (`swarm/brand.py`, `profiles/<slug>.json`), and every audit function takes the profile it is
# judging against.
#
# The module-level names below (`AUTHOR_NAME`, `PROOF_NUMBERS`, `COMPETITORS`,
# `BANNED_ADJECTIVES`, `MIN_*`, `ANSWER_*`) still resolve, via `__getattr__`, to the ACTIVE
# profile's values — so existing callers and tests keep working unchanged. They are resolved
# lazily on first access rather than at import, which keeps this module import-clean: importing
# `geo` never touches disk, so a missing profile fails where it is used, not where it is
# imported.
_PROFILE_BACKED: dict[str, str] = {
    "AUTHOR_NAME": "author_name",
    "COMPETITORS": "competitors",
    "BANNED_ADJECTIVES": "banned_adjectives",
    "MIN_QUESTION_H2": "thresholds.min_question_h2",
    "ANSWER_MIN_WORDS": "thresholds.answer_min_words",
    "ANSWER_MAX_WORDS": "thresholds.answer_max_words",
    "MIN_PROOF_NUMBERS": "thresholds.min_proof_numbers",
    "MIN_COMPETITORS_IN_TABLE": "thresholds.min_competitors_in_table",
    "MIN_TABLE_BODY_ROWS": "thresholds.min_table_body_rows",
    "NOT_A_FIT_MIN_WORDS": "thresholds.not_a_fit_min_words",
}


def __getattr__(name: str):
    """Resolve legacy module constants from the active profile, on demand."""
    if name == "GEO_TEMPLATE_RULES":
        return template_rules()
    if name == "PROOF_NUMBERS":
        # Legacy shape: {label: compiled pattern}. Preserved for callers that introspect it.
        return {p.label: p.regex for p in brand.active().proof_points}
    path = _PROFILE_BACKED.get(name)
    if path is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    value = brand.active()
    for part in path.split("."):
        value = getattr(value, part)
    return value


# ── Requirement 4: explicit disqualification ──────────────────────────────────────────────
# Brand-independent: every company has situations where it is the wrong answer, and the
# phrasings a writer reaches for to say so are the same in any category.
NOT_A_FIT_HEADING = re.compile(
    r"not\s+a\s+fit|not\s+for\s+you|when\s+not\s+to|when\s+this\s+(?:doesn'?t|does\s+not)|"
    r"who\s+should\s*n[o']?t|wrong\s+fit|don'?t\s+(?:need|buy)|skip\s+this|"
    r"where\s+this\s+(?:fails|breaks)|when\s+to\s+walk\s+away",
    re.I,
)
NOT_A_FIT_MIN_WORDS = 40


# ── Markdown parsing helpers ──────────────────────────────────────────────────────────────
_FRONTMATTER = re.compile(r"^(\s*---\s*\n)(.*?)(\n---\s*\n)(.*)$", re.DOTALL)


def split_frontmatter(mdx: str) -> tuple[str, str]:
    """Return (frontmatter_body, post_body). Frontmatter is '' when there is none."""
    m = _FRONTMATTER.match(mdx)
    return (m.group(2), m.group(4)) if m else ("", mdx)


def _strip_code_fences(body: str) -> str:
    """Blank out fenced code blocks so a '## ' inside one is not read as a heading."""
    out: list[str] = []
    in_fence = False
    for line in body.splitlines():
        if line.lstrip().startswith("```"):
            in_fence = not in_fence
            out.append("")
            continue
        out.append("" if in_fence else line)
    return "\n".join(out)


@dataclass(frozen=True)
class Section:
    """One heading and the raw lines beneath it, up to the next heading of any level."""

    level: int
    heading: str
    lines: tuple[str, ...]

    @property
    def is_question(self) -> bool:
        return self.heading.rstrip().endswith("?")

    @property
    def text(self) -> str:
        return "\n".join(self.lines)

    @property
    def first_paragraph(self) -> str:
        """The prose block that sits *directly* under the heading.

        Stops at a blank line, a nested heading, or any non-prose construct (list, table,
        image, blockquote, fence). If the first thing under the heading is a bullet list or a
        table, the answer block is empty by design — answer engines quote sentences.
        """
        collected: list[str] = []
        for raw in self.lines:
            line = raw.strip()
            if not line:
                if collected:
                    break
                continue
            if re.match(r"^(#{1,6}\s|[-*+]\s|\d+[.)]\s|\||>|!\[|```|<)", line):
                break
            collected.append(line)
        return " ".join(collected)


def parse_sections(body: str) -> list[Section]:
    stripped = _strip_code_fences(body)
    sections: list[Section] = []
    level = 0
    heading = ""
    buf: list[str] = []
    for line in stripped.splitlines():
        m = re.match(r"^(#{1,6})\s+(.*)$", line)
        if not m:
            if heading:
                buf.append(line)
            continue
        if heading:
            sections.append(Section(level, heading, tuple(buf)))
        level, heading, buf = len(m.group(1)), m.group(2).strip(), []
    if heading:
        sections.append(Section(level, heading, tuple(buf)))
    return sections


def _word_count(text: str) -> int:
    return len(text.split())


@dataclass(frozen=True)
class Table:
    header: tuple[str, ...]
    rows: tuple[tuple[str, ...], ...]

    @property
    def text(self) -> str:
        return " | ".join(self.header) + " " + " ".join(" | ".join(r) for r in self.rows)


def parse_tables(body: str) -> list[Table]:
    """Extract GFM pipe tables: a header row followed by a `|---|` separator."""

    def cells(line: str) -> tuple[str, ...]:
        return tuple(c.strip() for c in line.strip().strip("|").split("|"))

    lines = _strip_code_fences(body).splitlines()
    tables: list[Table] = []
    i = 0
    while i < len(lines) - 1:
        header, sep = lines[i].strip(), lines[i + 1].strip()
        if header.startswith("|") and re.fullmatch(r"\|[\s:|-]+\|", sep):
            rows: list[tuple[str, ...]] = []
            j = i + 2
            while j < len(lines) and lines[j].strip().startswith("|"):
                rows.append(cells(lines[j]))
                j += 1
            tables.append(Table(cells(header), tuple(rows)))
            i = j
            continue
        i += 1
    return tables


# ── The gate ──────────────────────────────────────────────────────────────────────────────
@dataclass
class GeoReport:
    """Outcome of one audit. `failures` are repair instructions, written for the writer."""

    failures: list[str] = field(default_factory=list)
    found_numbers: list[str] = field(default_factory=list)
    question_answers: int = 0

    @property
    def ok(self) -> bool:
        return not self.failures

    def as_brief(self) -> str:
        """The repair brief handed back to the writer on a retry."""
        items = "\n".join(f"  {n}. {f}" for n, f in enumerate(self.failures, 1))
        return (
            "YOUR DRAFT FAILED THE GEO TEMPLATE GATE — REJECTED.\n"
            "Every post must carry the answer-engine template. Fix exactly these, changing "
            "nothing else that already works:\n"
            f"{items}\n"
            "Keep the full length and every section that passed. Do not restructure the "
            "argument; add what is missing."
        )


def _audit_question_answers(
    sections: list[Section], report: GeoReport, profile: BrandProfile
) -> None:
    t = profile.thresholds
    question_h2s = [s for s in sections if s.level == 2 and s.is_question]
    compliant = [
        s for s in question_h2s
        if t.answer_min_words <= _word_count(s.first_paragraph) <= t.answer_max_words
    ]
    report.question_answers = len(compliant)
    if len(compliant) >= t.min_question_h2:
        return

    if not question_h2s:
        report.failures.append(
            f"No question-form H2. Add at least {t.min_question_h2} H2 headings phrased as the "
            "exact question a buyer would type or ask an AI assistant (they must end in '?'), "
            f"each followed immediately by a self-contained {t.answer_min_words}-{t.answer_max_words} "
            "word prose answer that makes sense quoted on its own, with no pronoun referring "
            "back to earlier text. Elaborate after that paragraph, not inside it."
        )
        return

    detail = "; ".join(
        f'"{s.heading}" has a {_word_count(s.first_paragraph)}-word answer block'
        for s in question_h2s
        if s not in compliant
    )
    report.failures.append(
        f"Only {len(compliant)} of {len(question_h2s)} question-form H2s carry a compliant "
        f"{t.answer_min_words}-{t.answer_max_words} word answer directly underneath "
        f"({t.min_question_h2} needed). Fix: {detail}. The answer must be the FIRST thing under "
        "the heading — prose, not a list or table — and self-contained."
    )


def _audit_proof_numbers(body: str, report: GeoReport, profile: BrandProfile) -> None:
    report.found_numbers = profile.found_proof_points(body)
    if len(report.found_numbers) < profile.thresholds.min_proof_numbers:
        report.failures.append(
            f"Only {len(report.found_numbers)} hard proof number(s) present "
            f"({profile.thresholds.min_proof_numbers} needed). Use the real, unrounded figures "
            f"from {profile.name}'s own delivered work — {', '.join(profile.proof_labels)} — in "
            "the sections where they are genuinely relevant, each attached to what produced it. "
            "Never invent a number and never round these."
        )

    hits = sorted({b for b in profile.banned_adjectives if b.lower() in body.lower()})
    if hits:
        report.failures.append(
            f"Adjectives standing in for evidence: {', '.join(hits)}. Delete every one and put "
            "the number, the mechanism or the named example in its place. A claim without a "
            "figure is not quotable and answer engines skip it."
        )


def _audit_competitor_table(
    body: str, report: GeoReport, profile: BrandProfile, cluster: str | None = None
) -> None:
    t = profile.thresholds
    # Name the rivals for *this* post's market. A failure that says "you need two competitors"
    # without saying which two is a failure the writer cannot act on — and the repair pass gets
    # exactly one attempt, so an unactionable brief burns the whole retry.
    candidates = profile.competitors_for(cluster)
    suggestion = ", ".join(candidates[:6])

    tables = parse_tables(body)
    if not tables:
        report.failures.append(
            "No comparison table. Add one markdown table that compares the real options a buyer "
            f"is actually choosing between — at least {t.min_competitors_in_table} named "
            f"competitors alongside {profile.name}, across {t.min_table_body_rows}+ rows. "
            f"Use these exact names: {suggestion}. Be accurate and fair about where they win; a "
            "table that only flatters us gets read as a brochure and cited by nobody."
        )
        return

    for table in tables:
        named = profile.named_competitors(table.text)
        if len(named) >= t.min_competitors_in_table and len(table.rows) >= t.min_table_body_rows:
            return

    best = max(tables, key=lambda tb: len(tb.rows))
    named = profile.named_competitors(best.text)
    missing = [c for c in candidates if c not in named][:6]
    report.failures.append(
        f"The comparison table is not competitor-inclusive: its largest table has "
        f"{len(best.rows)} row(s) and names {len(named)} known competitor(s)"
        f"{' (' + ', '.join(named) + ')' if named else ''}. It needs "
        f"{t.min_competitors_in_table}+ real named competitors across {t.min_table_body_rows}+ "
        "rows, with an honest column showing where each one is the better choice. "
        f"Add rows for these, spelled exactly like this: {', '.join(missing)}. "
        "Only names from that list count — a real vendor the gate does not know still fails."
    )


def _audit_not_a_fit(sections: list[Section], report: GeoReport, profile: BrandProfile) -> None:
    minimum = profile.thresholds.not_a_fit_min_words
    for s in sections:
        if s.level in (2, 3) and NOT_A_FIT_HEADING.search(s.heading):
            if _word_count(s.text) >= minimum:
                return
            report.failures.append(
                f'The "{s.heading}" section is only {_word_count(s.text)} words. Give it at '
                f"least {minimum}: name the specific situations where a buyer should "
                "not hire us, and say what they should do instead."
            )
            return
    report.failures.append(
        'No "not a fit if…" section. Add an H2 that explicitly disqualifies readers — the volumes, '
        "budgets, timelines or problem shapes where this is the wrong answer, and what to do "
        "instead. Stated limits are the strongest credibility signal on the page and the reason "
        "an answer engine treats it as a source instead of an ad."
    )


def _audit_metadata(frontmatter: str, report: GeoReport) -> None:
    """Metadata is injected by `inject_metadata`, so a miss here means injection was skipped."""
    for key in ("author", "dateModified"):
        if not re.search(rf"(?m)^{key}\s*:\s*\S", frontmatter):
            report.failures.append(
                f"Frontmatter is missing `{key}`. It must be present so the page renders a "
                "named author and a visible last-updated date."
            )


def audit(
    mdx: str, *, profile: BrandProfile | None = None, cluster: str | None = None
) -> GeoReport:
    """Verify one finished post against the GEO template, for one brand.

    Pure function, no LLM. `profile` defaults to the active brand, so a single-tenant caller
    passes only the MDX; a multi-tenant one passes the tenant's profile explicitly.

    `cluster` changes no pass/fail decision — it only narrows which rival names a failure
    message suggests, so the repair brief proposes vendors from the post's own market.
    """
    profile = profile or brand.active()
    frontmatter, body = split_frontmatter(mdx)
    sections = parse_sections(body)
    report = GeoReport()
    _audit_question_answers(sections, report, profile)
    _audit_proof_numbers(body, report, profile)
    _audit_competitor_table(body, report, profile, cluster)
    _audit_not_a_fit(sections, report, profile)
    _audit_metadata(frontmatter, report)
    return report


# ── Deterministic metadata injection (requirements 5 + 6) ─────────────────────────────────
def inject_metadata(
    mdx: str,
    *,
    author: str = "",
    date_modified: str = "",
    profile: BrandProfile | None = None,
) -> str:
    """Set `author` and `dateModified` in the frontmatter. Idempotent.

    `dateModified` is always refreshed — that is the point of it. `author` is only added when
    absent, so a guest byline set upstream survives. Returns the MDX unchanged if it has no
    frontmatter (the length gate would already have failed such a draft).
    """
    m = _FRONTMATTER.match(mdx)
    if not m:
        return mdx
    head, fm, close, body = m.groups()
    author = author or (profile or brand.active()).author_name
    date_modified = date_modified or datetime.now(timezone.utc).strftime("%Y-%m-%d")

    if re.search(r"(?m)^dateModified\s*:", fm):
        fm = re.sub(r'(?m)^dateModified\s*:.*$', f'dateModified: "{date_modified}"', fm, count=1)
    else:
        fm = f'{fm}\ndateModified: "{date_modified}"'

    if not re.search(r"(?m)^author\s*:", fm):
        fm = f'{fm}\nauthor: "{author}"'

    return f"{head}{fm}{close}{body}"


# ── Prompt half — injected into the writer ────────────────────────────────────────────────
def template_rules(profile: BrandProfile | None = None, cluster: str | None = None) -> str:
    """The writer-facing half of the template, written for one brand.

    Derived from the SAME profile the gate reads, so the instructions and the enforcement
    cannot drift apart — which is what happened when the proof numbers lived in markdown for
    the prompt and in regexes for the gate.

    `cluster` selects which rivals to name. Without it the writer was told a fixed vendor list
    existed, told the gate checked against it, and never shown it — so it had to guess a closed
    vocabulary. That is what held the FMCG draft that named only Infosys.
    """
    p = profile or brand.active()
    t = p.thresholds
    proof_line = " · ".join(p.proof_labels)

    # Capped: the full registry is 84 names, and a wall of vendors buys nothing over a
    # relevant shortlist while costing tokens on every writer call and every repair.
    candidates = p.competitor_shortlist(cluster)
    rival_list = "\n".join(f"     {name}" for name in candidates)
    rival_examples = ", ".join(candidates[:2]) if len(candidates) >= 2 else "a named rival"

    return f"""
=== GEO TEMPLATE (NON-NEGOTIABLE — EVERY POST) ===
This blog is written to be quoted by AI answer engines (ChatGPT, Perplexity, AI Overviews) as
much as to rank on Google. Research is unambiguous: statistics, quotations and citations raise
AI visibility 30-40%; adjectives raise it zero. A deterministic gate checks all six of the
following before anything publishes, and a failure blocks the post. Build them in as you write.

1. QUESTION-FORM H2s WITH SELF-CONTAINED ANSWERS
   At least {t.min_question_h2} of your H2 headings must be the exact question a buyer would
   type, or ask an assistant, ending in "?". Directly under each, write ONE paragraph of
   {t.answer_min_words}-{t.answer_max_words} words that fully answers it and still makes sense
   quoted alone on someone else's screen — name the subject, no "this", no "as we saw above".
   Then elaborate in the paragraphs after it. The answer paragraph must be prose: not a list,
   not a table.

2. HARD NUMBERS, NEVER ADJECTIVES
   Use at least {t.min_proof_numbers} of {p.name}'s real delivered figures where they genuinely
   apply, each attached to what produced it: {proof_line}.
   Quote them exactly — never round. Any performance claim without a number gets cut. These
   words are banned outright: {', '.join(p.banned_adjectives[:12])}…
   If you cannot attach a figure or a named mechanism to a claim, delete the claim.

3. COMPETITOR-INCLUSIVE COMPARISON TABLE
   One markdown table comparing the options the buyer is really choosing between — at least
   {t.min_competitors_in_table} named competitors alongside {p.name}, {t.min_table_body_rows}+
   rows.

   THE GATE ONLY ACCEPTS THESE NAMES. Pick at least {t.min_competitors_in_table} from this
   list and spell them exactly as written here:
   {rival_list}

   Prefer the ones the research digest actually discusses — its summary, key_facts and
   what_people_say name the products this post is about. If the digest names a vendor that is
   not on the list above, you may still discuss it in prose, but the table must also carry
   {t.min_competitors_in_table}+ names from the list or the post is blocked. Do not paraphrase
   into a category ("a SaaS platform", "other AI tools") and do not invent a vendor.
   Include a column that says honestly where each rival is the better choice — e.g.
   {rival_examples} beat us on off-the-shelf reliability. A table that only flatters {p.name} is
   a brochure and gets cited by nobody.

4. AN EXPLICIT "NOT A FIT IF…" SECTION
   One H2 that disqualifies readers by name: the volumes, budgets, timelines and problem shapes
   where {p.name} is the wrong answer, and what they should do instead. At least
   {t.not_a_fit_min_words} words. This is the highest-credibility block on the page — write it
   like you are talking someone out of a bad purchase, because you are.

5 & 6. dateModified + named author are injected automatically after you write. Do not add them
   to the frontmatter yourself, and do not sign the post in the body.
""".strip()
