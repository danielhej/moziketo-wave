#!/usr/bin/env python3
"""E2E: Search → play_state ready → stream TTFB."""

from __future__ import annotations

import json
import os
import sys
import time
import urllib.error
import urllib.request


def main() -> None:
    base = os.environ.get("WAVE_URL", "https://api.moziketo.ir").rstrip("/")
    secret = os.environ.get("WAVE_ADMIN_KEY") or os.environ.get("ADMIN_API_KEY")
    if not secret:
        print("Set WAVE_ADMIN_KEY or ADMIN_API_KEY", file=sys.stderr)
        sys.exit(1)

    q = sys.argv[1] if len(sys.argv) > 1 else "bohemian rhapsody"
    url = f"{base}/api/v1/search?q={urllib.parse.quote(q)}&limit=6"
    headers = {"X-Admin-Key": secret, "Accept": "application/json"}

    print(f"GET {url}")
    t0 = time.perf_counter()
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            data = json.loads(resp.read())
    except urllib.error.HTTPError as exc:
        print(f"HTTP {exc.code}: {exc.read()[:500]}")
        sys.exit(1)
    search_ms = round((time.perf_counter() - t0) * 1000)

    hits = data.get("hits") or []
    ready = [h for h in hits if h.get("play_state") == "ready" and not h.get("in_catalog")]
    print(f"search_ms={search_ms} hits={len(hits)} ready={len(ready)}")

    for h in hits[:6]:
        state = h.get("play_state") or ("catalog" if h.get("in_catalog") else "-")
        print(f"  {h.get('title','?')[:32]:32} state={state} job={h.get('job_id','')[:8] if h.get('job_id') else '-'}")

    if not ready:
        print("No ready hit in search response (set PREPARE_SEARCH_WAIT_SEC=25 on wave for full wait)")
        # Stream may still work if background prepare finished — try first non-catalog hit
        nc = [h for h in hits if not h.get("in_catalog") and h.get("key")]
        if not nc:
            sys.exit(0)
        hit = nc[0]
        print(f"Trying stream anyway (background prepare): {hit.get('title')}")
    else:
        hit = ready[0]

    stream_url = f"{base}/api/v1/stream/{hit['key']}"
    t1 = time.perf_counter()
    sreq = urllib.request.Request(stream_url, headers=headers)
    with urllib.request.urlopen(sreq, timeout=30) as resp:
        chunk = resp.read(8192)
    ttfb_ms = round((time.perf_counter() - t1) * 1000)
    print(f"\nstream key={hit['key']} ttfb={ttfb_ms}ms bytes={len(chunk)} type={resp.headers.get('Content-Type')}")
    print(f"total search→audio start ≈ {search_ms + ttfb_ms}ms (if click immediately after search)")


if __name__ == "__main__":
    import urllib.parse

    main()
