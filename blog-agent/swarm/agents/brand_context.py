"""
Shared brand memory loader — the prose half of a tenant's identity.

Structured, gate-critical facts (proof numbers, competitors, byline, thresholds) live in
`swarm/brand.py` as a validated `BrandProfile`. The long-form prose an agent needs — the brand
bible, positioning, SEO strategy, founder voice — stays as markdown, because a human revises it
and markdown is what they will revise it in.

TENANT RESOLUTION
Content is looked up in this order, first hit wins:

  1. the profile's inline field  (`positioning`, `icp`, `voice_guardrails`) — for tenants
     configured entirely from JSON, which is what a DB-backed tenant will be
  2. `config/<slug>/<file>.md`   — per-tenant markdown, the normal case once there are two
     brands
  3. `config/<file>.md`          — flat layout, kept so the Buteforce files work untouched
  4. the shared knowledge vault  — Buteforce's Obsidian vault only

WHAT CHANGED AND WHY
This module used to end its search at a literal `Path("D:/Projects/Buteforce/.agents/knowledge")`,
so on any other machine the agents ran with an empty brand context and nobody found out until
the copy came back wrong. It also carried a hardcoded Buteforce positioning string as a "hard
fallback" — correct when there was one brand, actively dangerous with two, because a client
tenant with a missing file would have silently published *our* positioning under *their* byline.
Both are gone: the vault is opt-in via env var, and a tenant with no positioning raises.
"""
from __future__ import annotations

import os
from pathlib import Path

from swarm import brand
from swarm.brand import BrandProfile

_REPO_ROOT = Path(__file__).resolve().parents[2]
_CONFIG_ROOT = _REPO_ROOT / "config"
_WORKSPACE_ROOT = _REPO_ROOT.parent


class MissingBrandContent(RuntimeError):
    """A tenant is missing prose an agent needs. Never fall back to another brand's."""


def _candidate_knowledge_roots() -> list[Path]:
    """The shared Obsidian vault. Buteforce-only, and entirely optional.

    `BRAND_KNOWLEDGE_ROOT` is the current name; `BUTEFORCE_KNOWLEDGE_ROOT` is still read so
    existing `.env` files keep working.
    """
    roots: list[Path] = []
    for var in ("BRAND_KNOWLEDGE_ROOT", "BUTEFORCE_KNOWLEDGE_ROOT"):
        value = os.environ.get(var, "").strip()
        if value:
            roots.append(Path(value))
    roots.append(_WORKSPACE_ROOT / ".agents" / "knowledge")
    return roots


def _first_existing(paths: list[Path]) -> Path | None:
    for path in paths:
        if path.exists():
            return path
    return None


KNOWLEDGE_ROOT = _first_existing(_candidate_knowledge_roots())


def _read(path: Path, fallback: str = "") -> str:
    try:
        return path.read_text(encoding="utf-8").strip()
    except Exception:
        return fallback


def _read_knowledge_file(*names: str, fallback: str = "") -> str:
    if not KNOWLEDGE_ROOT:
        return fallback
    for name in names:
        text = _read(KNOWLEDGE_ROOT / name)
        if text:
            return text
    return fallback


def _content_roots(profile: BrandProfile) -> list[Path]:
    """Per-tenant directory first, flat `config/` second."""
    return [_CONFIG_ROOT / profile.slug, _CONFIG_ROOT]


def _read_content(profile: BrandProfile, *names: str, vault_names: tuple[str, ...] = ()) -> str:
    """Resolve one piece of tenant prose across the search order documented above."""
    for root in _content_roots(profile):
        for name in names:
            text = _read(root / name)
            if text:
                return text
    return _read_knowledge_file(*vault_names) if vault_names else ""


def _brand_context(profile: BrandProfile | None = None) -> str:
    p = profile or brand.active()
    brand_bible = _read_content(p, "brand-bible.md", vault_names=("brand_bible.md",))
    voice = p.voice_guardrails or _read_content(p, "voice.md")
    founder = _read_content(
        p, "founder.md", vault_names=("founder_profile.md", "founder.md")
    )
    personality = _read_content(p, "founder-personality.md", vault_names=("dhyan_psychology.md",))

    return f"""
=== BRAND BIBLE ({p.name}) ===
{brand_bible[:3000]}

=== VOICE ===
{voice[:1200]}

=== AUTHOR PERSONALITY ({p.author_name}) ===
{personality[:1500]}

=== AUTHOR PROFILE ===
{founder[:800]}
""".strip()


def _seo_context(profile: BrandProfile | None = None) -> str:
    p = profile or brand.active()
    seo = _read_content(p, "seo-strategy.md", vault_names=("seo_strategy.md",))
    return f"""
=== SEO STRATEGY (keyword clusters) ===
{seo[:2600]}
""".strip()


def _signals_context(profile: BrandProfile | None = None) -> str:
    """What has actually earned impressions and rank. Injected into the Ideator (topic
    selection) and Research agents so the engine doubles down on proven demand instead of
    guessing.

    Two files, both optional, and they do different jobs:

      gsc-signals.md            hand-written. Competitor analysis and the defect-level
                                vocabulary real buyers search with — knowledge that came
                                from somebody reading the market, not from an export.
                                Never generated over.
      gsc-signals-generated.md  written by the learning run on every pass. Current
                                measured performance per post and per arm, with sample
                                sizes.

    Curated insight is placed first: it is the more durable of the two, and when the
    measured table is thin (early days, few matured posts) it is also the more reliable.
    """
    p = profile or brand.active()
    curated = _read_content(p, "gsc-signals.md")
    measured = _read_content(p, "gsc-signals-generated.md")
    if not curated and not measured:
        return ""

    blocks = []
    if curated:
        blocks.append(f"--- curated market knowledge ---\n{curated[:2600]}")
    if measured:
        blocks.append(f"--- measured performance (auto-generated) ---\n{measured[:2200]}")

    body = "\n\n".join(blocks)
    return f"""
=== SEARCH SIGNALS (proven demand — double down here) ===
{body}
""".strip()


def _strategy_context(profile: BrandProfile | None = None) -> str:
    """Positioning + ICP. Authoritative — it overrides any older framing baked into the brand
    bible or agent prompts.

    Raises when a tenant has none. There is deliberately no default: a wrong positioning is not
    a degraded prompt, it is one client's identity published under another's name.
    """
    p = profile or brand.active()
    positioning = p.positioning or _read_content(
        p, "positioning.md", vault_names=("positioning.md",)
    )
    if not positioning:
        searched = " · ".join(str(r / "positioning.md") for r in _content_roots(p))
        raise MissingBrandContent(
            f"No positioning for tenant {p.slug!r}. Set `positioning` in "
            f"profiles/{p.slug}.json, or add positioning.md in one of: {searched}. "
            "Refusing to fall back to another brand's positioning."
        )

    parts = [positioning[:3400]]

    icp = p.icp or _read_content(p, "icp.md")
    if icp:
        parts.append(icp[:1200])

    if p.do_not_name:
        parts.append(f"Do not name or reference: {', '.join(p.do_not_name)}.")

    body = "\n\n".join(parts)
    return f"=== POSITIONING & ICP (authoritative) ===\n{body}"
