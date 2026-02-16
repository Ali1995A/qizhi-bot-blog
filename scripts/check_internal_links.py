#!/usr/bin/env python3
"""Check that internal post links point to existing post directories.

Scans post/**/index.html and validates links like:
- https://ai.liexpress.cc/post/<slug>/
- /post/<slug>/
- post/<slug>/

Exit code:
  0 = OK
  1 = Missing targets found

Usage:
  scripts/check_internal_links.py [--base https://ai.liexpress.cc] [--root <repo_root>]

Notes:
- This is a fast, offline check to prevent pushing broken internal links (404s).
- It does NOT fetch the network.
"""

import argparse
import re
import sys
from pathlib import Path

HREF_RE = re.compile(r"href=\"([^\"]+)\"")


def norm_target(url: str, base: str) -> str | None:
    url = url.strip()
    if not url or url.startswith("#"):
        return None
    if url.startswith("mailto:") or url.startswith("javascript:"):
        return None

    # Strip base
    if url.startswith(base):
        url = url[len(base):]

    # We only care about /post/<slug>/ links
    m = re.match(r"^/?post/([^/]+)/?", url)
    if m:
        return m.group(1)
    return None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="https://ai.liexpress.cc")
    ap.add_argument("--root", default=str(Path(__file__).resolve().parents[1]))
    args = ap.parse_args()

    root = Path(args.root).resolve()
    post_dir = root / "post"
    if not post_dir.exists():
        print(f"ERROR: post dir not found: {post_dir}", file=sys.stderr)
        return 2

    missing: list[tuple[str, str, str]] = []  # (source_file, href, slug)

    for html in sorted(post_dir.glob("*/index.html")):
        text = html.read_text(encoding="utf-8", errors="ignore")
        for href in HREF_RE.findall(text):
            slug = norm_target(href, args.base)
            if not slug:
                continue
            target = post_dir / slug / "index.html"
            if not target.exists():
                missing.append((str(html.relative_to(root)), href, slug))

    if missing:
        print("Missing internal post targets:")
        for src, href, slug in missing:
            print(f"- in {src}: {href}  (missing post/{slug}/index.html)")
        print(f"TOTAL missing: {len(missing)}")
        return 1

    print("OK: internal post links resolved.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
