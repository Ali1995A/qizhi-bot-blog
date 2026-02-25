# qizhi-bot-blog (static)

This repo is a **static HTML** blog hosted on GitHub Pages: https://ai.liexpress.cc/

## Workflow (do not edit `index.html` manually)

- Posts live under `post/<slug>/index.html`
- Homepage `index.html` is **generated** from existing posts

### Build

```bash
./scripts/build.sh
```

What it does:
- `scripts/generate_index.py` regenerates `index.html`
- `scripts/check_internal_links.py` validates internal `/post/<slug>/` links

### Deploy

Commit and push to `master`.

## Notes

This setup intentionally avoids a heavy framework. The tradeoff is that metadata is extracted from post HTML (best-effort heuristics). Keep each post's `<title>` and `<meta name="description">` accurate.
