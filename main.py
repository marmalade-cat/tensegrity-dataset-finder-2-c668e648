#!/usr/bin/env python3
"""
Minimal prototype crawler for dataset discovery.
- Standard library only
- Seed URLs configured in SEED_URLS
- Writes manifest.json and crawl.log
"""
import sys
import json
import time
import urllib.request
import urllib.parse
from html.parser import HTMLParser

# ----- Configuration -----
SEED_URLS = [
    "https://www.nature.com/articles/example-paper",  # replace with real start URLs
    "https://africavernaculararchitecture.com/example-page"
]
USER_AGENT = "MarmaladeDatasetFinder/0.1 (+https://example.local)"
KNOWN_DATA_HOSTS = [
    "figshare.com",
    "zenodo.org",
    "github.com",
    "data.world",
    "osf.io",
    "datadryad.org"
]
CANDIDATE_EXT = [".csv", ".json", ".ndjson", ".geojson", ".xlsx"]
OUTPUT_MANIFEST = "manifest.json"
OUTPUT_LOG = "crawl.log"
TIMEOUT = 15

# ----- HTML link extractor -----
class LinkExtractor(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links = []

    def handle_starttag(self, tag, attrs):
        if tag.lower() == "a":
            href = dict(attrs).get("href")
            if href:
                self.links.append(href)

# ----- Helpers -----

def log(msg):
    t = time.strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{t}] {msg}"
    print(line)
    with open(OUTPUT_LOG, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def fetch_url_head(url):
    req = urllib.request.Request(url, method="HEAD", headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            headers = dict(resp.getheaders())
            return headers
    except Exception as e:
        log(f"HEAD failed for {url}: {e}")
        return {}


def fetch_url(url):
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            content_type = resp.headers.get_content_type()
            body = resp.read()
            return content_type, body
    except Exception as e:
        log(f"GET failed for {url}: {e}")
        return None, b""


def normalize_record(url, origin, headers):
    parsed = urllib.parse.urlparse(url)
    host = parsed.netloc.lower()
    content_type = headers.get("Content-Type") or headers.get("content-type")
    length = headers.get("Content-Length") or headers.get("content-length")
    try:
        size_bytes = int(length) if length else None
    except Exception:
        size_bytes = None
    # guess type by extension
    lower = parsed.path.lower()
    file_type = None
    for ext in CANDIDATE_EXT:
        if lower.endswith(ext):
            file_type = ext.lstrip('.')
            break
    if not file_type and content_type:
        if "json" in content_type:
            file_type = "json"
        elif "csv" in content_type or "excel" in content_type:
            file_type = "csv"
    notes = []
    if any(k in host for k in KNOWN_DATA_HOSTS):
        notes.append("known-data-host")
    if file_type:
        notes.append("by-extension-or-type")
    if not notes:
        notes.append("heuristic-suspect")
    return {
        "url": url,
        "host": host,
        "origin": origin,
        "file_type": file_type,
        "size_bytes": size_bytes,
        "content_type": content_type,
        "notes": notes
    }

# ----- Main crawl logic -----

def extract_links_from_html(base_url, html_bytes):
    try:
        text = html_bytes.decode("utf-8", errors="replace")
    except Exception:
        text = html_bytes.decode("latin1", errors="replace")
    p = LinkExtractor()
    p.feed(text)
    abs_links = []
    for href in p.links:
        href = href.strip()
        if not href:
            continue
        # ignore javascript: and mailto:
        if href.startswith("javascript:") or href.startswith("mailto:"):
            continue
        abs_links.append(urllib.parse.urljoin(base_url, href))
    return abs_links


def is_candidate_link(url):
    lower = url.lower()
    for ext in CANDIDATE_EXT:
        if lower.endswith(ext):
            return True
    for host in KNOWN_DATA_HOSTS:
        if host in lower:
            return True
    # also candidate if query suggests download
    if any(k in lower for k in ["download", "file", "dataset", "supplementary"]):
        return True
    return False


def crawl_seed(origin_url):
    records = []
    log(f"Crawling seed: {origin_url}")
    ctype, body = fetch_url(origin_url)
    if body:
        links = extract_links_from_html(origin_url, body)
        log(f"Found {len(links)} links on {origin_url}")
        # filter
        candidates = [u for u in links if is_candidate_link(u)]
        log(f"{len(candidates)} candidate links for datasets on {origin_url}")
        for u in candidates:
            # attempt HEAD to get content-type and length
            headers = fetch_url_head(u) or {}
            rec = normalize_record(u, origin_url, headers)
            # if no type from HEAD, try GET for small check of content-type
            if not rec["file_type"] and not rec["content_type"]:
                ctype2, _ = fetch_url(u)
                if ctype2:
                    rec["content_type"] = ctype2
            records.append(rec)
    else:
        log(f"No body fetched for seed {origin_url}")
    return records


def main():
    all_records = []
    # clear log
    open(OUTPUT_LOG, "w", encoding="utf-8").close()
    for url in SEED_URLS:
        recs = crawl_seed(url)
        all_records.extend(recs)
    # normalize manifest: remove duplicates by URL
    seen = set()
    normalized = []
    for r in all_records:
        u = r["url"]
        if u in seen:
            continue
        seen.add(u)
        normalized.append(r)
    with open(OUTPUT_MANIFEST, "w", encoding="utf-8") as f:
        json.dump(normalized, f, indent=2)
    log(f"Wrote {len(normalized)} records to {OUTPUT_MANIFEST}")

if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        log("Interrupted")
        sys.exit(1)
