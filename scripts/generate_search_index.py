#!/usr/bin/env python3
"""Generate search.json for client-side search.

Output: search.json (array)
Fields: title, url, date, excerpt, tags

Usage:
  scripts/generate_search_index.py --root . --base https://ai.liexpress.cc
"""

import argparse
import html
import json
import re
from pathlib import Path
from typing import Optional

TITLE_RE = re.compile(r"<title>(.*?)</title>", re.I | re.S)
META_DESC_RE = re.compile(r"<meta\s+name=\"description\"\s+content=\"(.*?)\"\s*/?>", re.I | re.S)
JSONLD_RE = re.compile(r"<script\s+type=\"application/ld\+json\"[^>]*>(.*?)</script>", re.I | re.S)
DATE_RE = re.compile(r"\b(20\d{2}-\d{2}-\d{2})\b")


def strip_tags(s: str) -> str:
    s = re.sub(r"<[^>]+>", "", s)
    s = html.unescape(s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def parse_jsonld(text: str) -> list[dict]:
    out = []
    for block in JSONLD_RE.findall(text):
        block = block.strip()
        if not block:
            continue
        try:
            data = json.loads(block)
            if isinstance(data, dict):
                out.append(data)
            elif isinstance(data, list):
                out.extend([x for x in data if isinstance(x, dict)])
        except Exception:
            continue
    return out


def pick_title(text: str) -> str:
    m = TITLE_RE.search(text)
    if not m:
        return "(untitled)"
    t = strip_tags(m.group(1))
    t = re.sub(r"\s*\|\s*Mr\.\s*Qizhi\s*$", "", t)
    return t.strip() or "(untitled)"


def pick_excerpt(text: str) -> str:
    m = META_DESC_RE.search(text)
    return strip_tags(m.group(1)) if m else ""


def pick_date(text: str, jsonlds: list[dict]) -> Optional[str]:
    for d in jsonlds:
        if d.get("@type") in ("Article", "BlogPosting"):
            v = d.get("datePublished") or d.get("dateCreated")
            if isinstance(v, str) and DATE_RE.search(v):
                return DATE_RE.search(v).group(1)
    m = DATE_RE.search(text)
    return m.group(1) if m else None


def pick_tags(jsonlds: list[dict]) -> list[str]:
    for d in jsonlds:
        if d.get("@type") in ("Article", "BlogPosting"):
            kw = d.get("keywords")
            if isinstance(kw, str) and kw.strip():
                return [p.strip() for p in kw.split(",") if p.strip()]
            if isinstance(kw, list):
                return [str(x).strip() for x in kw if str(x).strip()]
    return []


def load_json(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=".")
    ap.add_argument("--base", default="https://ai.liexpress.cc")
    args = ap.parse_args()

    root = Path(args.root).resolve()
    post_root = root / "post"

    alias_map = None
    alias_path = root / "data" / "tags-alias.json"
    if alias_path.exists():
        x = load_json(alias_path)
        if isinstance(x, dict):
            alias_map = x

    items = []
    for d in sorted([x for x in post_root.iterdir() if x.is_dir()]):
        hp = d / "index.html"
        if not hp.exists():
            continue
        text = hp.read_text(encoding="utf-8", errors="ignore")
        jsonlds = parse_jsonld(text)

        title = pick_title(text)
        excerpt = pick_excerpt(text)
        date = pick_date(text, jsonlds) or "1970-01-01"
        tags = pick_tags(jsonlds)
        if alias_map:
            tags = [alias_map.get(t, t) for t in tags]
        # de-dup
        seen = set()
        tags2 = []
        for t in tags:
            k = t.strip().lower()
            if not k or k in seen:
                continue
            seen.add(k)
            tags2.append(t.strip())

        slug = d.name
        items.append(
            {
                "title": title,
                "url": f"{args.base}/post/{slug}/",
                "date": date,
                "excerpt": excerpt,
                "tags": tags2,
            }
        )

    items.sort(key=lambda x: (x.get("date", ""), x.get("url", "")), reverse=True)
    (root / "search.json").write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Generated search.json with {len(items)} posts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
