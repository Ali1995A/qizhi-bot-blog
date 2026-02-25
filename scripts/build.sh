#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

# Regenerate homepage from posts
./scripts/generate_index.py --root . --base "https://ai.liexpress.cc" --limit 80

# Generate helper pages
./scripts/generate_pages.py --root . --base "https://ai.liexpress.cc"

# Generate search index
./scripts/generate_search_index.py --root . --base "https://ai.liexpress.cc"

# Validate internal links among posts (fast offline check)
./scripts/check_internal_links.py --base "https://ai.liexpress.cc" --root .

echo "Build OK"
