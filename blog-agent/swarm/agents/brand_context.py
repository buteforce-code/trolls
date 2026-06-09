"""
Shared brand memory loader.
All agents call _brand_context() to inject Buteforce identity.
"""
from __future__ import annotations
import os
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
_CONFIG_ROOT = _REPO_ROOT / "config"
_WORKSPACE_ROOT = _REPO_ROOT.parent


def _candidate_knowledge_roots() -> list[Path]:
    roots: list[Path] = []
    env_root = os.environ.get("BUTEFORCE_KNOWLEDGE_ROOT", "").strip()
    if env_root:
        roots.append(Path(env_root))
    roots.extend([
        _WORKSPACE_ROOT / ".agents" / "knowledge",
        Path("D:/Projects/Buteforce/.agents/knowledge"),
    ])
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


def _brand_context() -> str:
    brand_bible = _read(_CONFIG_ROOT / "brand-bible.md") or _read_knowledge_file("brand_bible.md")
    dhyan = _read_knowledge_file("dhyan_psychology.md")
    founder = _read_knowledge_file("founder_profile.md", "founder.md")
    return f"""
=== BRAND BIBLE ===
{brand_bible[:3000]}

=== FOUNDER PERSONALITY (Dhyan Karthik) ===
{dhyan[:1500]}

=== FOUNDER PROFILE ===
{founder[:800]}
""".strip()


def _seo_context() -> str:
    seo = _read(_CONFIG_ROOT / "seo-strategy.md") or _read_knowledge_file("seo_strategy.md")
    return f"""
=== SEO STRATEGY (India-first keyword clusters) ===
{seo[:2600]}
""".strip()


def _strategy_context() -> str:
    """Positioning + ICP geography. Repo-local and authoritative — it overrides any
    older global ICP framing baked into the brand bible or agent prompts.
    """
    positioning = _read(_CONFIG_ROOT / "positioning.md") or _read_knowledge_file("positioning.md")
    if not positioning:
        # Hard fallback so the engine never silently reverts to a generic ICP.
        positioning = (
            "Buteforce is Chennai's Industrial AI Company — precision AI systems for India's "
            "manufacturing corridor (Hyundai, Michelin, Renault/Nissan, BMW in Tamil Nadu). "
            "ICP: CTOs, plant heads, quality/ops leaders and founders at manufacturers and "
            "multi-location retailers in India, especially the Chennai/Tamil Nadu corridor. "
            "India-first — do not default to a US/UK/UAE/AU audience."
        )
    return f"""
=== POSITIONING & ICP (authoritative — India-first) ===
{positioning[:2600]}
""".strip()
