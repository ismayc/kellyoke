#!/usr/bin/env python3
"""Fill original release years Wikipedia has no article for, from MusicBrainz.

    python3 fetch_musicbrainz.py [--limit N] [--dry-run]

Roughly a sixth of the performances name a song that has no Wikipedia article
at all, mostly independent or very recent artists. No amount of infobox or
category work reaches those, so this asks a music database instead.

Only ever adds. A performance that already has a year is not looked up, and the
cache in mb_meta.json is keyed on (song, artist) so a re-run costs nothing for
anything already resolved. Safe to interrupt.

Two guards make a match trustworthy, because a bare title search will happily
return someone else's song:

  * the search score must be at least MIN_SCORE, and
  * the credited artist MusicBrainz returns must match the artist we asked for,
    compared on normalized text rather than exactly

The date taken is the recording's earliest release. That is the original for a
song searched under its original artist, which is how this archive defines
orig_year, and it is why the search is by artist rather than by title alone.
"""
import argparse
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request

S = os.path.dirname(os.path.abspath(__file__))
API = "https://musicbrainz.org/ws/2/recording"
UA = "KellyokeResearch/1.0 (https://github.com/ismayc/kellyoke)"
MIN_SCORE = 90
PAUSE = 1.6          # MusicBrainz asks for one request a second; leave room
CACHE = "mb_meta.json"


def norm(s):
    """Compare artist names without punctuation, case or the joining words."""
    s = (s or "").lower()
    s = re.sub(r"\b(feat\.?|featuring|ft\.?|with|and|&|the)\b", " ", s)
    s = re.sub(r"[^a-z0-9 ]", " ", s)
    return " ".join(s.split())


def get(params):
    url = API + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    for attempt in range(5):
        try:
            with urllib.request.urlopen(req, timeout=45) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            if e.code in (503, 429):          # busy or throttled, not a failure
                time.sleep(PAUSE * (attempt + 2))
                continue
            return None
        except Exception:
            time.sleep(PAUSE * (attempt + 1))
    return None


def credited(rec):
    return " ".join(c.get("name", "") if isinstance(c, dict) else str(c)
                    for c in rec.get("artist-credit") or [])


def earliest(rec):
    dates = [rec.get("first-release-date") or ""]
    for rel in rec.get("releases") or []:
        dates.append(rel.get("date") or "")
    yrs = [int(d[:4]) for d in dates if re.match(r"^(1[5-9]\d{2}|20\d{2})", d or "")]
    return min(yrs) if yrs else None


def lookup(song, artist):
    """(year, why) for one credit, or (None, reason)."""
    q = f'recording:"{song}" AND artist:"{artist}"'
    d = get({"query": q, "fmt": "json", "limit": 5})
    if d is None:
        return None, "request failed"
    best = None
    for rec in d.get("recordings") or []:
        if rec.get("score", 0) < MIN_SCORE:
            continue
        got = norm(credited(rec))
        want = norm(artist)
        if not got or not want:
            continue
        # one has to contain the other: "Lisa Loeb" vs "Lisa Loeb & Nine Stories"
        if not (got in want or want in got):
            continue
        y = earliest(rec)
        if y and (best is None or y < best):
            best = y
    if best is None:
        return None, "no confident match"
    return best, "musicbrainz"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0,
                    help="stop after this many new lookups")
    ap.add_argument("--dry-run", action="store_true",
                    help="list what would be looked up and exit")
    args = ap.parse_args()

    rows = json.load(open(os.path.join(S, "matched.json")))
    cache_p = os.path.join(S, CACHE)
    cache = json.load(open(cache_p)) if os.path.exists(cache_p) else {}

    wanted = {}
    for r in rows:
        for p in r["perfs"]:
            artist = (p.get("artist") or "").strip()
            if p.get("orig_year") or not artist:
                continue
            wanted.setdefault(f"{p['song']}\t{artist}", (p["song"], artist))

    todo = [k for k in wanted if k not in cache]
    print(f"{len(wanted)} credits with no year, {len(todo)} not yet looked up")
    if args.dry_run:
        for k in todo[:40]:
            print("   ", wanted[k][0], "|", wanted[k][1])
        return

    if args.limit:
        todo = todo[:args.limit]
    found = 0
    for i, k in enumerate(todo, 1):
        song, artist = wanted[k]
        year, why = lookup(song, artist)
        cache[k] = {"year": year, "why": why}
        if year:
            found += 1
        print(f"  [{i}/{len(todo)}] {song[:32]:34} {artist[:20]:22} "
              f"-> {year or why}", flush=True)
        json.dump(cache, open(cache_p, "w"), indent=1)   # resumable
        time.sleep(PAUSE)

    hits = sum(1 for v in cache.values() if v.get("year"))
    print(f"\n{found} new years this run; {hits} of {len(cache)} credits resolved")


if __name__ == "__main__":
    main()
