#!/usr/bin/env python3
"""Fill original release years Wikipedia has no article for, from MusicBrainz.

    python3 fetch_musicbrainz.py [--limit N] [--dry-run]

Roughly a sixth of the performances name a song that has no Wikipedia article
at all, mostly independent or very recent artists. No amount of infobox or
category work reaches those, so this asks a music database instead.

The year this writes means what it means everywhere else in the archive: the
year the SONG was first released, by anyone, not the year of the recording the
show happens to credit. "Blues in the Night" is credited here to Ella
Fitzgerald, but the song is 1941 and that is the year it gets.

Reaching that takes three steps, because a recording search alone answers a
different question:

  1. Search recordings by title AND artist. The artist is what makes the match
     trustworthy: a bare title search will happily return someone else's song.
     Two guards apply, a search score of at least MIN_SCORE and a credited
     artist that matches the one asked for, compared on normalized text.
  2. Follow the matched recordings to their work. The work is the song itself,
     so every cover of it hangs off the same work.
  3. Browse every recording of that work and take the earliest release.

Step 3 is why SEARCH_LIMIT is 100 rather than a handful. Search ranks by text
score, never by date, so the original studio recording routinely sits outside
the top few hits: at limit 5 "On the Road Again" dated Willie Nelson to 1995 or
2001 depending on the run, against a true 1980.

A work with no recordings dated, or no work link at all, falls back to the
earliest release among the artist's own matched recordings, which also caps the
work answer: a song cannot be newer than a recording of it that already exists.
See first_release for why the earliest date is not taken naively.

What this cannot do is invent coverage MusicBrainz lacks. "Trouble Blues" is
Charles Brown in 1949, but the work linked from Sam Cooke's recording holds
thirteen dated recordings and none of them is Brown's, so the answer comes out
1961. Wrong by twelve years, still closer than the 1963 it replaces.

Only ever adds a year where the archive has none from Wikipedia. A year stated
by an infobox or a category always wins, and is never looked up. The cache in
mb_meta.json is keyed on (song, artist) and carries the CACHE_VERSION that
produced it, so a re-run costs nothing for anything already resolved by the
current logic and silently redoes anything left by older logic. Safe to
interrupt: the cache is written after every lookup.
"""
import argparse
import collections
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request

S = os.path.dirname(os.path.abspath(__file__))
BASE = "https://musicbrainz.org/ws/2"
UA = "KellyokeResearch/1.0 (https://github.com/ismayc/kellyoke)"
MIN_SCORE = 90
SEARCH_LIMIT = 100   # search ranks by text score, so the original sits deep
WORK_PROBES = 3      # matched recordings asked which work they belong to
BROWSE_PAGES = 10    # at 100 a page, enough for any song in this archive
OUTLIER_GAP = 5      # years: a lone date this far ahead of the rest is an error
PAUSE = 1.6          # MusicBrainz asks for one request a second; leave room
CACHE = "mb_meta.json"
CACHE_VERSION = 2    # bump to re-derive every cached year


def norm(s):
    """Compare artist names without punctuation, case or the joining words."""
    s = (s or "").lower()
    s = re.sub(r"\b(feat\.?|featuring|ft\.?|with|and|&|the)\b", " ", s)
    s = re.sub(r"[^a-z0-9 ]", " ", s)
    return " ".join(s.split())


def get(path, params):
    url = f"{BASE}/{path}?" + urllib.parse.urlencode(params)
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


def year_of(date):
    return int(date[:4]) if re.match(r"^(1[5-9]\d{2}|20\d{2})", date or "") else None


def earliest(rec):
    """Earliest release year of one recording, from the search response."""
    dates = [rec.get("first-release-date") or ""]
    for rel in rec.get("releases") or []:
        dates.append(rel.get("date") or "")
    yrs = [y for y in (year_of(d) for d in dates) if y]
    return min(yrs) if yrs else None


def work_of(recordings):
    """The work these recordings share, or None.

    Asks several of them rather than one because a recording is not always
    linked to its work, and takes the most commonly named work so a stray
    medley or sample credit cannot outvote the song itself.
    """
    counts = collections.Counter()
    for rec in recordings[:WORK_PROBES]:
        d = get(f"recording/{rec['id']}", {"fmt": "json", "inc": "work-rels"})
        time.sleep(PAUSE)
        for rel in (d or {}).get("relations") or []:
            w = rel.get("work")
            if w and w.get("id"):
                counts[w["id"]] += 1
    return counts.most_common(1)[0][0] if counts else None


def work_years(wid):
    """How many recordings of this work carry each release year."""
    years = collections.Counter()
    total, off, truncated = None, 0, False
    for _ in range(BROWSE_PAGES):
        d = get("recording", {"work": wid, "fmt": "json",
                              "limit": 100, "offset": off})
        time.sleep(PAUSE)
        if d is None:
            break
        total = d.get("recording-count", 0)
        for rec in d.get("recordings") or []:
            y = year_of(rec.get("first-release-date"))
            if y:
                years[y] += 1
        off += 100
        if off >= (total or 0):
            break
    else:
        truncated = total is not None and off < total
    return years, truncated


def first_release(years):
    """Earliest year among a work's recordings, ignoring a lone early outlier.

    Not a bare min(). MusicBrainz carries the occasional mis-dated recording,
    and min() is exactly the function that a single bad date poisons. The work
    for "Blues in the Night" holds one 1930 entry, from a band that had stopped
    recording, against three from 1941: Woody Herman, Artie Shaw and Cab
    Calloway, which is the year the song was actually written.

    So a year is dropped only when it is both alone and far out in front. One
    recording sitting more than OUTLIER_GAP years before everything else is a
    data error far more often than it is the original. A year with a second
    recording behind it, or one close on the heels of the next, is kept, which
    matters because an original single is often the only recording of its year.
    """
    if not years:
        return None
    ys = sorted(years)
    while len(ys) > 1 and years[ys[0]] == 1 and ys[1] - ys[0] > OUTLIER_GAP:
        ys.pop(0)
    return ys[0]


def lookup(song, artist):
    """(year, why, detail) for one credit, or (None, reason, detail)."""
    q = f'recording:"{song}" AND artist:"{artist}"'
    d = get("recording", {"query": q, "fmt": "json", "limit": SEARCH_LIMIT})
    if d is None:
        return None, "request failed", {}
    keep = []
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
        keep.append(rec)
    if not keep:
        return None, "no confident match", {}
    time.sleep(PAUSE)

    # the credited artist's own earliest, kept as the fallback and for reporting
    artist_year = min([y for y in (earliest(r) for r in keep) if y], default=None)

    wid = work_of(keep)
    if wid:
        years, truncated = work_years(wid)
        work_year = first_release(years)
        # The song cannot be newer than a recording of it that already exists.
        # MusicBrainz work coverage is uneven, and a thin work will happily
        # report a date later than the credit we started from: the work behind
        # Bonnie Raitt's "Love Me Like a Man" holds 15 dated recordings whose
        # earliest is 1991, against her own 1972. Her recording is direct
        # evidence the song is at least that old, so it caps the answer.
        year = min([y for y in (work_year, artist_year) if y], default=None)
        if year:
            return year, "musicbrainz", {
                "path": "work", "work": wid, "artist_year": artist_year,
                "work_year": work_year, "capped": bool(
                    work_year and artist_year and artist_year < work_year),
                "dated": sum(years.values()), "truncated": truncated,
            }
    if artist_year:
        return artist_year, "musicbrainz", {
            "path": "artist", "artist_year": artist_year,
        }
    return None, "no dated recording", {"path": "artist"}


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

    # Which credits are ours to answer. A year Wikipedia stated is never
    # touched; a year this script wrote is fair game, because enrich.py has
    # already written orig_year back into matched.json and a plain "has no
    # year" test would now skip every credit this script has ever resolved.
    wanted = {}
    for r in rows:
        for p in r["perfs"]:
            artist = (p.get("artist") or "").strip()
            if not artist:
                continue
            if p.get("orig_year") and p.get("year_src") not in ("", "musicbrainz"):
                continue
            wanted.setdefault(f"{p['song']}\t{artist}", (p["song"], artist))

    todo = [k for k in wanted if cache.get(k, {}).get("v") != CACHE_VERSION]
    stale = sum(1 for k in todo if k in cache)
    print(f"{len(wanted)} credits in scope, {len(todo)} to look up "
          f"({stale} cached by older logic, {len(todo) - stale} never tried)")
    if args.dry_run:
        for k in todo[:40]:
            print("   ", wanted[k][0], "|", wanted[k][1])
        return

    if args.limit:
        todo = todo[:args.limit]
    found = moved = failed = 0
    for i, k in enumerate(todo, 1):
        song, artist = wanted[k]
        was = cache.get(k, {}).get("year")
        year, why, detail = lookup(song, artist)
        # A network failure is not an answer. Caching it at the current version
        # would retire the credit permanently: the next run sees a current
        # entry and skips it, so one dropped request silently costs a year that
        # was already resolved. "The Thing I Love" lost its 2025 that way.
        if why == "request failed":
            print(f"  [{i}/{len(todo)}] {song[:32]:34} {artist[:20]:22} "
                  f"-> request failed, not cached", flush=True)
            failed += 1
            time.sleep(PAUSE)
            continue
        cache[k] = dict(detail, year=year, why=why, v=CACHE_VERSION)
        if year:
            found += 1
        note = ""
        if was and year and was != year:
            moved += 1
            note = f"  (was {was})"
        print(f"  [{i}/{len(todo)}] {song[:32]:34} {artist[:20]:22} "
              f"-> {year or why}{note}", flush=True)
        json.dump(cache, open(cache_p, "w"), indent=1)   # resumable
        time.sleep(PAUSE)

    hits = sum(1 for v in cache.values() if v.get("year"))
    paths = collections.Counter(v.get("path", "-") for v in cache.values())
    print(f"\n{found} years this run, {moved} of them changed a cached value; "
          f"{hits} of {len(cache)} credits resolved")
    if failed:
        print(f"{failed} request failures, left uncached so a re-run retries them")
    print(f"resolved via: {dict(paths)}")


if __name__ == "__main__":
    main()
