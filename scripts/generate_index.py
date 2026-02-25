#!/usr/bin/env python3
"""Generate qizhi-bot-blog index.html from post/*/index.html.

Design goals (for Leo):
- Stop manual homepage editing (source of drift / broken links).
- Deterministic output (same input => same index.html).
- Best-effort extraction from existing static HTML posts.
- Homepage is an *entry page* (featured + topics + latest), still static.

Heuristics:
- title: <title>...</title> (strip suffix "| Mr. Qizhi")
- description/excerpt: <meta name="description" content="..."> (fallback: first <p> in .post-content)
- date: JSON-LD Article.datePublished (fallback: regex in page for YYYY-MM-DD)
- tags: JSON-LD keywords (comma-separated) or meta keywords

Config:
- data/featured.json: list of featured slugs for "Start here" section
- data/tags-alias.json: tag normalization map (optional)

Usage:
  scripts/generate_index.py --root . --base https://ai.liexpress.cc --limit 60
"""

import argparse
import datetime as dt
import html
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


def load_json(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None

TITLE_RE = re.compile(r"<title>(.*?)</title>", re.I | re.S)
META_DESC_RE = re.compile(r"<meta\s+name=\"description\"\s+content=\"(.*?)\"\s*/?>", re.I | re.S)
META_KEYWORDS_RE = re.compile(r"<meta\s+name=\"keywords\"\s+content=\"(.*?)\"\s*/?>", re.I | re.S)
HTML_LANG_RE = re.compile(r"<html[^>]*\slang=\"([^\"]+)\"", re.I)
JSONLD_RE = re.compile(r"<script\s+type=\"application/ld\+json\"[^>]*>(.*?)</script>", re.I | re.S)
FIRST_P_RE = re.compile(r"<div class=\"post-content\"[\s\S]*?<p>([\s\S]*?)</p>", re.I)
DATE_RE = re.compile(r"\b(20\d{2}-\d{2}-\d{2})\b")


def strip_tags(s: str) -> str:
    s = re.sub(r"<[^>]+>", "", s)
    s = html.unescape(s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


@dataclass
class Post:
    slug: str
    url: str
    title: str
    date: str  # YYYY-MM-DD
    tags: str  # rendered string like "#AI #GovTech"
    tag_list: list[str]
    excerpt: str


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


def pick_date(text: str, jsonlds: list[dict]) -> Optional[str]:
    # Prefer Article.datePublished
    for d in jsonlds:
        if d.get("@type") in ("Article", "BlogPosting"):
            v = d.get("datePublished") or d.get("dateCreated")
            if isinstance(v, str) and DATE_RE.search(v):
                return DATE_RE.search(v).group(1)
    # Fallback: any date-like token
    m = DATE_RE.search(text)
    if m:
        return m.group(1)
    return None


def pick_tags(text: str, jsonlds: list[dict]) -> list[str]:
    # Prefer JSON-LD keywords
    for d in jsonlds:
        if d.get("@type") in ("Article", "BlogPosting"):
            kw = d.get("keywords")
            if isinstance(kw, str) and kw.strip():
                return [p.strip() for p in kw.split(",") if p.strip()]
            if isinstance(kw, list):
                return [str(x).strip() for x in kw if str(x).strip()]
    # Fallback: meta keywords
    m = META_KEYWORDS_RE.search(text)
    if m:
        return [p.strip() for p in strip_tags(m.group(1)).split(",") if p.strip()]
    return []


def norm_tags(tags: list[str], alias_map: dict[str, str] | None, limit: int = 10) -> str:
    out: list[str] = []
    for t in tags:
        t = t.strip()
        if not t:
            continue
        if alias_map and t in alias_map:
            t = alias_map[t]
        # normalize spacing
        t = re.sub(r"\s+", " ", t)
        out.append(t)
    # de-dup stable
    seen = set()
    dedup = []
    for t in out:
        k = t.lower()
        if k in seen:
            continue
        seen.add(k)
        dedup.append(t)
    return " ".join([f"#{t}" for t in dedup[:limit]])


def pick_title(text: str) -> str:
    m = TITLE_RE.search(text)
    if not m:
        return "(untitled)"
    t = strip_tags(m.group(1))
    # common suffix
    t = re.sub(r"\s*\|\s*Mr\.\s*Qizhi\s*$", "", t)
    return t.strip() or "(untitled)"


def pick_excerpt(text: str) -> str:
    m = META_DESC_RE.search(text)
    if m:
        ex = strip_tags(m.group(1))
        return ex
    m = FIRST_P_RE.search(text)
    if m:
        ex = strip_tags(m.group(1))
        return ex
    return ""


INDEX_TEMPLATE_HEAD = """<!DOCTYPE html>
<html lang=\"en\">
<head>
  <meta charset=\"utf-8\" />
  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />
  <meta name=\"description\" content=\"Mr. Qizhi - Expert in urban planning, AI technology, Gov-Tech, digital transformation, smart cities, and digital twins.\" />
  <meta name=\"keywords\" content=\"AI, urban planning, GovTech, digital transformation, smart city, digital twin, government\" />
  <meta name=\"author\" content=\"Mr. Qizhi\" />
  <meta property=\"og:site_name\" content=\"Mr. Qizhi\" />
  <meta property=\"og:title\" content=\"Mr. Qizhi | AI and Urban Planning Insights\" />
  <meta property=\"og:description\" content=\"Expert analysis of AI applications in urban planning, Gov-Tech innovation, digital transformation, and digital twin cities.\" />
  <meta property=\"og:type\" content=\"website\" />
  <meta property=\"og:url\" content=\"{base}/\" />
  <meta name=\"twitter:card\" content=\"summary\" />
  <title>Mr. Qizhi | AI and Urban Planning Insights</title>
  <link rel=\"stylesheet\" href=\"{base}/styles/main.css\">
  <link rel=\"canonical\" href=\"{base}/\"> 
  <script type=\"application/ld+json\">
  {{
    \"@context\": \"https://schema.org\",
    \"@type\": \"WebSite\",
    \"name\": \"Mr. Qizhi\",
    \"url\": \"{base}/\",
    \"description\": \"AI · Urban Planning · Gov-Tech · Digital Transformation · Digital Twin\",
    \"inLanguage\": [\"en\", \"zh\"],
    \"publisher\": {{
      \"@type\": \"Person\",
      \"name\": \"Mr. Qizhi\"
    }}
  }}
  </script>
</head>
<body>
  <div class=\"main\">
    <div class=\"site-header\">
      <h1 class=\"site-title\">Mr. Qizhi</h1>
      <p class=\"site-description\">AI · Urban Planning · Gov-Tech · Digital Transformation · Digital Twin</p>
      <div class=\"top-nav\">
        <a href=\"about.html\">About</a>
        <a href=\"tags.html\">Tags</a>
        <a href=\"archive.html\">Archive</a>
      </div>
    </div>

    <div class=\"main-content\">\n"""

INDEX_TEMPLATE_TAIL = """
    </div>

    <div class=\"site-footer\">
      <p>© 2026 Mr. Qizhi | AI Powered Content</p>
      <p><a href=\"https://liexpress.cc/\">Main Blog</a> · <a href=\"https://x.com/liexpressok\" target=\"_blank\" rel=\"noopener\">𝕏 @liexpressok</a></p>
    </div>
  </div>

  <script async src=\"https://www.googletagmanager.com/gtag/js?id=G-314CM6M56H\"></script>
  <script>
    window.dataLayer = window.dataLayer || [];
    function gtag(){dataLayer.push(arguments);}
    gtag('js', new Date());
    gtag('config', 'G-314CM6M56H');
  </script>
</body>
</html>
"""


def render_post(p: Post) -> str:
    return (
        "        <article class=\"post-item\">\n"
        f"          <h2 class=\"post-title\"><a href=\"post/{p.slug}/\">{html.escape(p.title)}</a></h2>\n"
        "          <div class=\"post-meta\">\n"
        f"            <span class=\"post-date\">{html.escape(p.date)}</span>\n"
        f"            <span class=\"post-tags\">{html.escape(p.tags)}</span>\n"
        "          </div>\n"
        f"          <p class=\"post-excerpt\">{html.escape(p.excerpt)}</p>\n"
        "        </article>\n\n"
    )


def render_section(title: str, inner_html: str) -> str:
    return (
        "<section class=\"home-section\">\n"
        f"  <div class=\"home-section-title\">{html.escape(title)}</div>\n"
        f"  {inner_html}\n"
        "</section>\n\n"
    )


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=".")
    ap.add_argument("--base", default="https://ai.liexpress.cc")
    ap.add_argument("--limit", type=int, default=60)
    args = ap.parse_args()

    root = Path(args.root).resolve()
    post_root = root / "post"
    if not post_root.exists():
        print(f"ERROR: post directory not found: {post_root}", file=sys.stderr)
        return 2

    # Optional tag alias map
    alias_map = None
    alias_path = root / "data" / "tags-alias.json"
    if alias_path.exists():
        x = load_json(alias_path)
        if isinstance(x, dict):
            alias_map = x

    posts: list[Post] = []

    for d in sorted([x for x in post_root.iterdir() if x.is_dir()]):
        html_path = d / "index.html"
        if not html_path.exists():
            continue
        slug = d.name
        text = html_path.read_text(encoding="utf-8", errors="ignore")
        jsonlds = parse_jsonld(text)

        title = pick_title(text)
        excerpt = pick_excerpt(text)
        date = pick_date(text, jsonlds) or "1970-01-01"
        tag_list = pick_tags(text, jsonlds)
        tags = norm_tags(tag_list, alias_map, limit=10)

        posts.append(
            Post(
                slug=slug,
                url=f"{args.base}/post/{slug}/",
                title=title,
                date=date,
                tags=tags,
                tag_list=tag_list,
                excerpt=excerpt,
            )
        )

    # Sort by date desc, then slug desc for determinism
    def key(p: Post):
        return (p.date, p.slug)

    posts = sorted(posts, key=key, reverse=True)

    # Featured slugs
    featured = []
    feat_path = root / "data" / "featured.json"
    if feat_path.exists():
        fx = load_json(feat_path)
        if isinstance(fx, dict) and isinstance(fx.get("slugs"), list):
            featured = [str(s) for s in fx.get("slugs") if str(s)]

    by_slug = {p.slug: p for p in posts}
    featured_posts = [by_slug[s] for s in featured if s in by_slug]

    latest_posts = [p for p in posts if p.slug not in set(featured)][: args.limit]

    # Topic hub: top tags by frequency (exclude empty)
    freq = {}
    for p in posts:
        for t in p.tag_list:
            t = alias_map.get(t, t) if alias_map else t
            t = t.strip()
            if not t:
                continue
            freq[t] = freq.get(t, 0) + 1
    top_tags = [t for t, _ in sorted(freq.items(), key=lambda kv: (-kv[1], kv[0].lower()))][:10]

    out = INDEX_TEMPLATE_HEAD.format(base=args.base)

    # Hero
    out += "<section class=\"home-hero\">\n"
    out += "  <div class=\"home-hero-card\">\n"
    out += "    <div class=\"home-hero-kicker\">Mr. Qizhi</div>\n"
    out += "    <h2 class=\"home-hero-title\">AI, Urban Planning & GovTech — practical frameworks and delivery systems.</h2>\n"
    out += "    <div class=\"home-hero-actions\">\n"
    out += "      <a class=\"btn-primary\" href=\"#start-here\">Start here</a>\n"
    out += "      <a class=\"btn-secondary\" href=\"tags.html\">Browse tags</a>\n"
    out += "    </div>\n"
    out += "  </div>\n"
    out += "</section>\n\n"

    # Featured
    out += "<div id=\"start-here\"></div>\n"
    inner = "<div class=\"post-list\">\n" + "".join(render_post(p) for p in featured_posts) + "</div>"
    out += render_section("Start here", inner)

    # Topics
    def tag_anchor(t: str) -> str:
        a = t.lower()
        a = re.sub(r"[^a-z0-9\u4e00-\u9fff]+", "-", a)
        a = a.strip("-")
        return a or "tag"

    chips = "<div class=\"topic-grid\">\n"
    for t in top_tags:
        chips += (
            f"  <a class=\"topic-card\" href=\"tags.html#{html.escape(tag_anchor(t))}\">"
            f"{html.escape(t)} <span class=\"topic-count\">{freq[t]}</span></a>\n"
        )
    chips += "</div>"
    out += render_section("Topics", chips)

    # Latest
    inner2 = "<div class=\"post-list\">\n" + "".join(render_post(p) for p in latest_posts) + "</div>"
    out += render_section("Latest", inner2)

    out += INDEX_TEMPLATE_TAIL

    (root / "index.html").write_text(out, encoding="utf-8")
    print(f"Generated index.html with {len(posts)} posts ({len(featured_posts)} featured, {len(latest_posts)} latest).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
