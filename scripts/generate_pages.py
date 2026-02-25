#!/usr/bin/env python3
"""Generate lightweight helper pages for the static blog.

Generates:
- tags.html: tag index + per-tag listing
- archive.html: archive by year/month
- about.html: short profile + what to expect

All pages are generated from existing `post/*/index.html` (best-effort extraction)
so we avoid introducing a framework.

Usage:
  scripts/generate_pages.py --root . --base https://ai.liexpress.cc
"""

import argparse
import html
import json
import re
from dataclasses import dataclass
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
    if m:
        return strip_tags(m.group(1))
    return ""


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


@dataclass
class Post:
    slug: str
    title: str
    date: str
    excerpt: str
    tags: list[str]


def read_posts(root: Path) -> list[Post]:
    post_root = root / "post"
    posts: list[Post] = []
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
        posts.append(Post(slug=d.name, title=title, date=date, excerpt=excerpt, tags=tags))
    posts.sort(key=lambda p: (p.date, p.slug), reverse=True)
    return posts


def page_head(base: str, title: str, desc: str) -> str:
    return f"""<!DOCTYPE html>
<html lang=\"en\">
<head>
  <meta charset=\"utf-8\" />
  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />
  <title>{html.escape(title)} | Mr. Qizhi</title>
  <meta name=\"description\" content=\"{html.escape(desc)}\" />
  <link rel=\"stylesheet\" href=\"{base}/styles/main.css\">
  <link rel=\"canonical\" href=\"{base}/\"> 
</head>
<body>
  <div class=\"main\">
    <div class=\"site-header\">
      <a href=\"{base}/\"><h1 class=\"site-title\">Mr. Qizhi</h1></a>
      <p class=\"site-description\">AI · Urban Planning · Gov-Tech · Digital Transformation · Digital Twin</p>
      <div class=\"top-nav\">
        <a href=\"{base}/about.html\">About</a>
        <a href=\"{base}/tags.html\">Tags</a>
        <a href=\"{base}/archive.html\">Archive</a>
      </div>
    </div>

    <div class=\"main-content\">\n"""


def page_tail() -> str:
    return """
    </div>

    <div class=\"site-footer\">
      <p>© 2026 Mr. Qizhi | AI Powered Content</p>
      <p><a href=\"https://liexpress.cc/\">Main Blog</a> · <a href=\"https://x.com/liexpressok\" target=\"_blank\" rel=\"noopener\">𝕏 @liexpressok</a></p>
    </div>
  </div>
</body>
</html>
"""


def render_simple_list(posts: list[Post], base: str) -> str:
    out = "<div class=\"page\">\n"
    for p in posts:
        out += (
            "  <article class=\"post-item\">\n"
            f"    <h2 class=\"post-title\"><a href=\"{base}/post/{p.slug}/\">{html.escape(p.title)}</a></h2>\n"
            "    <div class=\"post-meta\">\n"
            f"      <span class=\"post-date\">{html.escape(p.date)}</span>\n"
            "    </div>\n"
            f"    <p class=\"post-excerpt\">{html.escape(p.excerpt)}</p>\n"
            "  </article>\n"
        )
    out += "</div>\n"
    return out


def gen_about(root: Path, base: str):
    title = "About"
    desc = "About Mr. Qizhi"
    body = """
<div class="page">
  <div class="page-card">
    <h2>About</h2>
    <p>Mr. Qizhi writes about AI, urban planning, Gov-Tech, digital transformation, and digital twin cities — with a focus on practical frameworks, delivery systems, and real-world tradeoffs.</p>
    <p>If you’re new here, start from the homepage (latest posts), then use Tags / Archive to browse by topic or time.</p>
  </div>
</div>
"""
    (root / "about.html").write_text(page_head(base, title, desc) + body + page_tail(), encoding="utf-8")


def gen_archive(root: Path, base: str, posts: list[Post]):
    title = "Archive"
    desc = "Archive by time"
    # group by YYYY-MM
    groups: dict[str, list[Post]] = {}
    for p in posts:
        ym = p.date[:7]
        groups.setdefault(ym, []).append(p)

    body = ["<div class=\"page\">", "  <div class=\"page-card\">", "    <h2>Archive</h2>"]
    for ym in sorted(groups.keys(), reverse=True):
        body.append(f"    <h3 class=\"archive-month\">{html.escape(ym)}</h3>")
        body.append("    <ul class=\"archive-list\">")
        for p in groups[ym]:
            body.append(
                f"      <li><a href=\"{base}/post/{p.slug}/\">{html.escape(p.title)}</a> <span class=\"archive-date\">{html.escape(p.date)}</span></li>"
            )
        body.append("    </ul>")
    body += ["  </div>", "</div>"]

    (root / "archive.html").write_text(page_head(base, title, desc) + "\n".join(body) + page_tail(), encoding="utf-8")


def load_json(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def norm_tag(t: str, alias_map: dict[str, str] | None) -> str:
    t = t.strip()
    t = re.sub(r"\s+", " ", t)
    if alias_map and t in alias_map:
        t = alias_map[t]
    return t


def tag_anchor(t: str) -> str:
    # stable and url-safe anchor
    a = t.lower()
    a = re.sub(r"[^a-z0-9\u4e00-\u9fff]+", "-", a)
    a = a.strip("-")
    return a or "tag"


def gen_tags(root: Path, base: str, posts: list[Post]):
    title = "Tags"
    desc = "Browse by tags"

    # Optional tag alias map
    alias_map = None
    alias_path = root / "data" / "tags-alias.json"
    if alias_path.exists():
        x = load_json(alias_path)
        if isinstance(x, dict):
            alias_map = x

    tagmap: dict[str, list[Post]] = {}
    for p in posts:
        for t in p.tags:
            t = norm_tag(t, alias_map)
            if not t:
                continue
            tagmap.setdefault(t, []).append(p)

    # Sort tags by post count desc then name
    tags_sorted = sorted(tagmap.items(), key=lambda kv: (-len(kv[1]), kv[0].lower()))

    body = ["<div class=\"page\">", "  <div class=\"page-card\">", "    <h2>Tags</h2>"]

    # tag index
    body.append("    <div class=\"tag-index\">")
    for t, ps in tags_sorted:
        body.append(
            f"      <a class=\"tag-chip\" href=\"#{html.escape(tag_anchor(t))}\">{html.escape(t)} <span class=\"tag-count\">{len(ps)}</span></a>"
        )
    body.append("    </div>")

    # per tag
    for t, ps in tags_sorted:
        body.append(f"    <h3 id=\"{html.escape(tag_anchor(t))}\" class=\"tag-title\">{html.escape(t)} <span class=\"tag-count\">{len(ps)}</span></h3>")
        body.append("    <ul class=\"tag-list\">")
        for p in ps:
            body.append(
                f"      <li><a href=\"{base}/post/{p.slug}/\">{html.escape(p.title)}</a> <span class=\"archive-date\">{html.escape(p.date)}</span></li>"
            )
        body.append("    </ul>")

    body += ["  </div>", "</div>"]

    (root / "tags.html").write_text(page_head(base, title, desc) + "\n".join(body) + page_tail(), encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=".")
    ap.add_argument("--base", default="https://ai.liexpress.cc")
    args = ap.parse_args()

    root = Path(args.root).resolve()
    posts = read_posts(root)

    gen_about(root, args.base)
    gen_archive(root, args.base, posts)
    gen_tags(root, args.base, posts)

    print("Generated about.html, archive.html, tags.html")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
