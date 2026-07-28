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

# ── Canonical identity (must match the live site's rendered byline + JSON-LD) ──────────────
# app/blog/[slug]/page.tsx renders "Dhyaneshwaran" with @id https://buteforce.com/#founder.
# One spelling everywhere or the entity splits — the exact failure SCAN 001 measured.
AUTHOR_NAME = "Dhyaneshwaran"

# ── Requirement 1: question-form H2 + self-contained answer ───────────────────────────────
MIN_QUESTION_H2 = 2
ANSWER_MIN_WORDS = 40
ANSWER_MAX_WORDS = 160

# ── Requirement 2: hard numbers, never adjectives ─────────────────────────────────────────
# Source: .agents/knowledge/case_studies.md "Proof Points Summary". Never round these.
PROOF_NUMBERS: dict[str, re.Pattern[str]] = {
    "99.2% vision accuracy": re.compile(r"99\.2\s*%"),
    "94% error reduction": re.compile(r"\b94\s*%"),
    "120 items/min throughput": re.compile(
        r"\b120\s*(?:items?|packs?|units?|products?|parts?)?\s*"
        r"(?:(?:/|per\s+|a\s+)\s*min(?:ute)?s?\b|(?:CPM|PPM)\b)",
        re.I,
    ),
    "70% handled autonomously": re.compile(r"\b70\s*%"),
    "80% average time saved": re.compile(r"\b80\s*%"),
    "95% faster lead response": re.compile(r"\b95\s*%"),
    "sub-second document latency": re.compile(r"sub-?second|<\s*1\s*s(?:ec(?:ond)?)?\b", re.I),
}
MIN_PROOF_NUMBERS = 2

# Adjectives that pretend to be evidence. Every one of these appeared in a shipped post.
# Deliberately excludes words with a legitimate technical sense in this domain ("seamless"
# seal, "robust" fixture) — the writer prompt handles those; this list is unambiguous puffery.
BANNED_ADJECTIVES: tuple[str, ...] = (
    "world-class", "cutting-edge", "cutting edge", "state-of-the-art", "best-in-class",
    "revolutionary", "revolutionis", "revolutioniz", "game-chang", "game chang",
    "transformative", "unparalleled", "groundbreaking", "industry-leading", "unmatched",
    "paradigm shift", "seismic shift", "tectonic shift", "supercharge", "turbocharge",
    "next-generation", "bleeding-edge",
)

# ── Requirement 3: competitor-inclusive comparison table ──────────────────────────────────
# Named vendors AI already recommends for our frozen prompts (SCAN 001 per-prompt results) plus
# the FMCG line-inspection players from config/gsc-signals.md. Naming real rivals honestly is
# the point: a table that only contains "us vs. generic alternative" reads as a brochure.
COMPETITORS: tuple[str, ...] = (
    # Manufacturing / computer vision
    "Cognex", "Keyence", "Omron", "OMRON", "Landing AI", "SwitchOn", "Instrumental",
    "Matroid", "Maddox.ai", "Overview.ai", "Siemens", "NVIDIA",
    "Kritikal Solutions", "XIS.ai", "Jidoka", "Detect Technologies", "Assert AI",
    "Wobot.ai", "Intello Labs", "ParallelDots", "Cogniphi", "Attentive.ai", "SoftmaxAI",
    "Optomech", "Indus Vision", "iFactory", "Binary Semantics", "ImageVision.ai",
    # Indian dev shops that rank for our category
    "Softlabs", "Quytech", "Kody Technolab", "Flexsin", "CreateBytes", "NextBrain",
    # Document AI / OCR
    "Nanonets", "Rossum", "Rillion", "Medius", "Tipalti", "KlearStack", "DocXtract",
    "Turian", "Flowis", "Google Document AI", "Azure Document Intelligence",
    "AWS Textract", "Amazon Textract", "Tesseract", "ABBYY", "Mistral OCR",
    # AI agents / real estate
    "Crescendo", "ManyChat", "Botpress", "ORAI", "JoyzAI", "RealtyChatbot",
    "VoiceGenie", "Aloware", "MindStudio", "Lindy", "Intuz",
    # Automation / agency category
    "UiPath", "Automation Anywhere", "Zapier", "Make.com", "n8n",
    "Accenture", "Infosys", "TCS", "Wipro", "LeewayHertz", "Appinventiv",
)
MIN_COMPETITORS_IN_TABLE = 2
MIN_TABLE_BODY_ROWS = 3

# ── Requirement 4: explicit disqualification ──────────────────────────────────────────────
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


def _audit_question_answers(sections: list[Section], report: GeoReport) -> None:
    question_h2s = [s for s in sections if s.level == 2 and s.is_question]
    compliant = [
        s for s in question_h2s
        if ANSWER_MIN_WORDS <= _word_count(s.first_paragraph) <= ANSWER_MAX_WORDS
    ]
    report.question_answers = len(compliant)
    if len(compliant) >= MIN_QUESTION_H2:
        return

    if not question_h2s:
        report.failures.append(
            f"No question-form H2. Add at least {MIN_QUESTION_H2} H2 headings phrased as the "
            "exact question a buyer would type or ask an AI assistant (they must end in '?'), "
            f"each followed immediately by a self-contained {ANSWER_MIN_WORDS}-{ANSWER_MAX_WORDS} "
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
        f"{ANSWER_MIN_WORDS}-{ANSWER_MAX_WORDS} word answer directly underneath "
        f"({MIN_QUESTION_H2} needed). Fix: {detail}. The answer must be the FIRST thing under "
        "the heading — prose, not a list or table — and self-contained."
    )


def _audit_proof_numbers(body: str, report: GeoReport) -> None:
    report.found_numbers = [name for name, pat in PROOF_NUMBERS.items() if pat.search(body)]
    if len(report.found_numbers) < MIN_PROOF_NUMBERS:
        report.failures.append(
            f"Only {len(report.found_numbers)} hard proof number(s) present "
            f"({MIN_PROOF_NUMBERS} needed). Use the real, unrounded figures from Buteforce's "
            "own delivered work — 99.2% classification accuracy, 120 items/min, 94% reduction "
            "in QC errors, 70% of inquiries handled autonomously, 80% average time saved, "
            "sub-second document latency — in the sections where they are genuinely relevant, "
            "each attached to what produced it. Never invent a number and never round these."
        )

    hits = sorted({b for b in BANNED_ADJECTIVES if b.lower() in body.lower()})
    if hits:
        report.failures.append(
            f"Adjectives standing in for evidence: {', '.join(hits)}. Delete every one and put "
            "the number, the mechanism or the named example in its place. A claim without a "
            "figure is not quotable and answer engines skip it."
        )


def _audit_competitor_table(body: str, report: GeoReport) -> None:
    tables = parse_tables(body)
    if not tables:
        report.failures.append(
            "No comparison table. Add one markdown table that compares the real options a buyer "
            f"is actually choosing between — at least {MIN_COMPETITORS_IN_TABLE} named "
            f"competitors (e.g. {', '.join(COMPETITORS[:4])}) alongside Buteforce, across "
            f"{MIN_TABLE_BODY_ROWS}+ rows. Be accurate and fair about where they win; a table "
            "that only flatters us gets read as a brochure and cited by nobody."
        )
        return

    for table in tables:
        named = {c for c in COMPETITORS if c.lower() in table.text.lower()}
        if len(named) >= MIN_COMPETITORS_IN_TABLE and len(table.rows) >= MIN_TABLE_BODY_ROWS:
            return

    best = max(tables, key=lambda t: len(t.rows))
    named = sorted({c for c in COMPETITORS if c.lower() in best.text.lower()})
    report.failures.append(
        f"The comparison table is not competitor-inclusive: its largest table has "
        f"{len(best.rows)} row(s) and names {len(named)} known competitor(s)"
        f"{' (' + ', '.join(named) + ')' if named else ''}. It needs "
        f"{MIN_COMPETITORS_IN_TABLE}+ real named competitors across {MIN_TABLE_BODY_ROWS}+ rows, "
        "with an honest column showing where each one is the better choice."
    )


def _audit_not_a_fit(sections: list[Section], report: GeoReport) -> None:
    for s in sections:
        if s.level in (2, 3) and NOT_A_FIT_HEADING.search(s.heading):
            if _word_count(s.text) >= NOT_A_FIT_MIN_WORDS:
                return
            report.failures.append(
                f'The "{s.heading}" section is only {_word_count(s.text)} words. Give it at '
                f"least {NOT_A_FIT_MIN_WORDS}: name the specific situations where a buyer should "
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


def audit(mdx: str) -> GeoReport:
    """Verify one finished post against the GEO template. Pure function, no LLM, no I/O."""
    frontmatter, body = split_frontmatter(mdx)
    sections = parse_sections(body)
    report = GeoReport()
    _audit_question_answers(sections, report)
    _audit_proof_numbers(body, report)
    _audit_competitor_table(body, report)
    _audit_not_a_fit(sections, report)
    _audit_metadata(frontmatter, report)
    return report


# ── Deterministic metadata injection (requirements 5 + 6) ─────────────────────────────────
def inject_metadata(mdx: str, *, author: str = AUTHOR_NAME, date_modified: str = "") -> str:
    """Set `author` and `dateModified` in the frontmatter. Idempotent.

    `dateModified` is always refreshed — that is the point of it. `author` is only added when
    absent, so a guest byline set upstream survives. Returns the MDX unchanged if it has no
    frontmatter (the length gate would already have failed such a draft).
    """
    m = _FRONTMATTER.match(mdx)
    if not m:
        return mdx
    head, fm, close, body = m.groups()
    date_modified = date_modified or datetime.now(timezone.utc).strftime("%Y-%m-%d")

    if re.search(r"(?m)^dateModified\s*:", fm):
        fm = re.sub(r'(?m)^dateModified\s*:.*$', f'dateModified: "{date_modified}"', fm, count=1)
    else:
        fm = f'{fm}\ndateModified: "{date_modified}"'

    if not re.search(r"(?m)^author\s*:", fm):
        fm = f'{fm}\nauthor: "{author}"'

    return f"{head}{fm}{close}{body}"


# ── Prompt half — injected into the writer ────────────────────────────────────────────────
_PROOF_LINE = " · ".join(PROOF_NUMBERS)

GEO_TEMPLATE_RULES = f"""
=== GEO TEMPLATE (NON-NEGOTIABLE — EVERY POST) ===
This blog is written to be quoted by AI answer engines (ChatGPT, Perplexity, AI Overviews) as
much as to rank on Google. Research is unambiguous: statistics, quotations and citations raise
AI visibility 30-40%; adjectives raise it zero. A deterministic gate checks all six of the
following before anything publishes, and a failure blocks the post. Build them in as you write.

1. QUESTION-FORM H2s WITH SELF-CONTAINED ANSWERS
   At least {MIN_QUESTION_H2} of your H2 headings must be the exact question a buyer would type,
   or ask an assistant, ending in "?". Directly under each, write ONE paragraph of
   {ANSWER_MIN_WORDS}-{ANSWER_MAX_WORDS} words that fully answers it and still makes sense
   quoted alone on someone else's screen — name the subject, no "this", no "as we saw above".
   Then elaborate in the paragraphs after it. The answer paragraph must be prose: not a list,
   not a table.

2. HARD NUMBERS, NEVER ADJECTIVES
   Use at least {MIN_PROOF_NUMBERS} of Buteforce's real delivered figures where they genuinely
   apply, each attached to what produced it: {_PROOF_LINE}.
   Quote them exactly — never round 99.2% to "over 99%". Any performance claim without a
   number gets cut. These words are banned outright: {', '.join(BANNED_ADJECTIVES[:12])}…
   If you cannot attach a figure or a named mechanism to a claim, delete the claim.

3. COMPETITOR-INCLUSIVE COMPARISON TABLE
   One markdown table comparing the options the buyer is really choosing between — at least
   {MIN_COMPETITORS_IN_TABLE} named competitors alongside Buteforce, {MIN_TABLE_BODY_ROWS}+ rows.
   Pick the ones a reader of THIS post would actually shortlist, and include a column that says
   honestly where each rival is the better choice. Cognex and Keyence beat us on
   off-the-shelf sensor reliability; a SaaS platform beats us on time-to-first-result. Say so.
   A table that only flatters Buteforce is a brochure and gets cited by nobody.

4. AN EXPLICIT "NOT A FIT IF…" SECTION
   One H2 that disqualifies readers by name: the volumes, budgets, timelines and problem shapes
   where Buteforce is the wrong answer, and what they should do instead. At least
   {NOT_A_FIT_MIN_WORDS} words. This is the highest-credibility block on the page — write it
   like you are talking someone out of a bad purchase, because you are.

5 & 6. dateModified + named author are injected automatically after you write. Do not add them
   to the frontmatter yourself, and do not sign the post in the body.
""".strip()
