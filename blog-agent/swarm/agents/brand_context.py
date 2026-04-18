"""
Shared brand memory loader.
All agents call _brand_context() to inject Buteforce identity.
"""
from __future__ import annotations
from pathlib import Path

KNOWLEDGE_ROOT = Path("D:/Projects/Buteforce/.agents/knowledge")
_REPO_ROOT = Path(__file__).resolve().parents[2]
_CONFIG_ROOT = _REPO_ROOT / "config"


def _read(path: Path, fallback: str = "") -> str:
    try:
        return path.read_text(encoding="utf-8").strip()
    except Exception:
        return fallback


def _brand_context() -> str:
    brand_bible = _read(_CONFIG_ROOT / "brand-bible.md") or _read(KNOWLEDGE_ROOT / "brand_bible.md")
    dhyan = _read(KNOWLEDGE_ROOT / "dhyan_psychology.md")
    founder = _read(KNOWLEDGE_ROOT / "founder_profile.md")
    return f"""
=== BRAND BIBLE ===
{brand_bible[:3000]}

=== FOUNDER PERSONALITY (Dhyan Karthik) ===
{dhyan[:1500]}

=== FOUNDER PROFILE ===
{founder[:800]}
""".strip()
