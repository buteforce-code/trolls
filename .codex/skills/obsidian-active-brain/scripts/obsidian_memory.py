from __future__ import annotations

import argparse
import math
import re
import sys
from collections import Counter
from pathlib import Path


VAULT_ROOT = Path(".agents").resolve()
SEARCH_ROOTS = [
    VAULT_ROOT / "knowledge",
    VAULT_ROOT / "rules",
    VAULT_ROOT / "workflows",
]
WORD_RE = re.compile(r"[A-Za-z0-9_]+")

if hasattr(sys.stdout, "buffer") and (sys.stdout.encoding or "").lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def tokenize(text: str) -> list[str]:
    return [match.group(0).lower() for match in WORD_RE.finditer(text)]


def markdown_files() -> list[Path]:
    files: list[Path] = []
    for root in SEARCH_ROOTS:
        if root.exists():
            files.extend(sorted(root.rglob("*.md")))
    return files


def score_file(path: Path, query_terms: list[str]) -> tuple[float, int, str]:
    content = path.read_text(encoding="utf-8-sig", errors="ignore")
    terms = tokenize(content)
    counts = Counter(terms)
    overlap = sum(counts[t] for t in query_terms)
    title_boost = sum(3 for t in query_terms if t in path.stem.lower())
    density = overlap / max(len(terms), 1)
    score = overlap + title_boost + math.log1p(density * 1000)
    preview = " ".join(content.split())[:220]
    return score, overlap, preview


def cmd_search(query: str, limit: int) -> int:
    query_terms = tokenize(query)
    if not query_terms:
        print("Query is empty.")
        return 1

    ranked = []
    for path in markdown_files():
        score, overlap, preview = score_file(path, query_terms)
        if overlap:
            ranked.append((score, path, preview))

    ranked.sort(key=lambda item: item[0], reverse=True)

    if not ranked:
        print("No matching notes found.")
        return 0

    for score, path, preview in ranked[:limit]:
        rel = path.relative_to(VAULT_ROOT)
        print(f"[{score:.2f}] {rel}")
        print(f"  {preview}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Search the Buteforce Obsidian active brain.")
    sub = parser.add_subparsers(dest="command", required=True)

    search = sub.add_parser("search", help="Rank relevant vault notes for a query")
    search.add_argument("query", help="Search query")
    search.add_argument("--limit", type=int, default=8, help="Max number of results")

    args = parser.parse_args()

    if args.command == "search":
        return cmd_search(args.query, args.limit)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
