#!/usr/bin/env python3
"""Find Kellyoke links that have gone dead.

This is a link archive to fan-uploaded copies, so link rot is the main long-term
risk: an upload gets removed and the entry silently points at nothing.

YouTube's oEmbed endpoint needs no API key and answers 404 for a video that is
removed, private or blocked. Anything else (429, 403, a timeout) says nothing
about the video and everything about being a datacenter IP, so it is recorded as
"unknown" rather than counted as dead. If too much of the run comes back unknown
the result is untrustworthy as a whole, and the script says so instead of
reporting a list of false alarms.

Writes dead-links.json and prints a summary. Exit code is 0 unless the run
itself could not be trusted, so a scheduled job reports rather than fails.
"""
import argparse
import csv
import json
import random
import sys
import time
import urllib.error
import urllib.request
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OEMBED = "https://www.youtube.com/oembed?format=json&url=https://www.youtube.com/watch?v="
UA = "Mozilla/5.0 (compatible; kellyoke-linkcheck/1.0; +https://github.com/)"
# above this share of unknowns the run tells us about the network, not the links
UNKNOWN_LIMIT = 0.10


def probe(vid, tries=3):
    """Return 'ok', 'dead', or 'unknown' for one video id."""
    for attempt in range(tries):
        try:
            req = urllib.request.Request(OEMBED + vid, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=20) as r:
                return "ok" if r.status == 200 else "unknown"
        except urllib.error.HTTPError as e:
            if e.code in (401, 403, 404):
                # oEmbed answers 401/403 for private and blocked, 404 for removed
                return "dead"
            if e.code == 429:
                time.sleep(5 * (attempt + 1) + random.random())
                continue
            return "unknown"
        except Exception:
            time.sleep(2 * (attempt + 1))
    return "unknown"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0,
                    help="check only a random sample of this many ids")
    ap.add_argument("--workers", type=int, default=4)
    args = ap.parse_args()

    rows = list(csv.DictReader(open(ROOT / "performances.csv", encoding="utf-8")))
    by_id = {}
    for r in rows:
        if r["video_id"]:
            by_id.setdefault(r["video_id"], []).append(r)
    ids = sorted(by_id)
    if args.limit and args.limit < len(ids):
        ids = random.sample(ids, args.limit)
    print(f"checking {len(ids)} unique video ids", flush=True)

    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        results = dict(zip(ids, pool.map(probe, ids)))

    tally = Counter(results.values())
    unknown_share = tally["unknown"] / len(ids) if ids else 0
    dead = sorted(v for v, s in results.items() if s == "dead")

    report = {
        "checked": len(ids),
        "ok": tally["ok"],
        "dead": tally["dead"],
        "unknown": tally["unknown"],
        "unknown_share": round(unknown_share, 3),
        "trustworthy": unknown_share <= UNKNOWN_LIMIT,
        "dead_links": [
            {"video_id": v,
             "url": f"https://www.youtube.com/watch?v={v}",
             "entries": [{"air_date": r["air_date"], "song": r["song"],
                          "performed_by": r["performed_by"]} for r in by_id[v]]}
            for v in dead
        ],
    }
    (ROOT / "dead-links.json").write_text(json.dumps(report, indent=1), encoding="utf-8")

    print(f"ok {tally['ok']}   dead {tally['dead']}   unknown {tally['unknown']} "
          f"({unknown_share:.1%})")
    if not report["trustworthy"]:
        print(f"\nToo many unknowns (> {UNKNOWN_LIMIT:.0%}) to trust this run. "
              "That is usually rate limiting on a shared runner IP, not link rot. "
              "Not reporting a dead list.")
        return 0
    for d in report["dead_links"]:
        first = d["entries"][0]
        extra = len(d["entries"]) - 1
        also = f"  (+{extra} more entries)" if extra else ""
        print(f"  DEAD {d['video_id']}  {first['air_date']}  {first['song']}{also}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
