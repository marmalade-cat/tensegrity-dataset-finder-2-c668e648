Tensegrity Dataset Finder — prototype

Run with Python 3.8+. This is a minimal prototype that fetches given paper URLs, extracts links, heuristically identifies dataset files (CSV/JSON) and known host links, and writes a manifest (manifest.json) and crawl log (crawl.log).

Usage:

1. Edit `main.py` `SEED_URLS` list with paper/webpage URLs.
2. python main.py

Outputs:
- manifest.json: array of normalized records (url, host, origin, type, size_bytes, notes)
- crawl.log: line-oriented log for manual review

Limitations: No concurrency, no robots.txt, basic HTML parsing only. Use responsibly.