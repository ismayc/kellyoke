#!/usr/bin/env python3
"""Invariant checks for the published Kellyoke data.

These run against the repo's own output files, with no network and no cached
scrape data, so CI can verify a change without rebuilding anything.

Most of these exist because the invariant was broken at some point and the break
was invisible: every individual row still looked plausible. Reading the failure
message should tell you what to fix, not just that something is off.

Exit code 0 if every check passes, 1 otherwise.
"""
import csv
import datetime
import json
import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FAILURES = []
CHECKS_RUN = 0

COLUMNS = ["air_date", "season", "episode_overall", "episode_in_season", "song",
           "original_artist", "genre", "original_release_year",
           "years_since_release", "performed_by", "is_cameo", "duet_with",
           "version_covered", "rerun", "video_id", "video_url", "video_source",
           "video_title", "video_views", "video_seconds"]

WATCH_URL = "https://www.youtube.com/watch?v="
# the watch_videos endpoint silently truncates past this many ids
PLAYLIST_CAP = 50


def check(label, ok, detail=""):
    global CHECKS_RUN
    CHECKS_RUN += 1
    if ok:
        print(f"  ok    {label}")
    else:
        print(f"  FAIL  {label}")
        if detail:
            for line in str(detail).splitlines():
                print(f"          {line}")
        FAILURES.append(label)


def main():
    rows = list(csv.DictReader(open(ROOT / "performances.csv", encoding="utf-8")))

    print("\nperformances.csv")
    check("column names and order", list(rows[0].keys()) == COLUMNS,
          f"got: {list(rows[0].keys())}")
    check("has rows", len(rows) > 0)

    bad_dates = [r["air_date"] for r in rows if not iso(r["air_date"])]
    check("air_date is ISO yyyy-mm-dd", not bad_dates, bad_dates[:5])

    bad_season = sorted({r["season"] for r in rows} - {str(n) for n in range(1, 8)})
    check("season is 1 to 7", not bad_season, bad_season)

    for col in ("is_cameo", "rerun"):
        bad = sorted({r[col] for r in rows} - {"yes", "no"})
        check(f"{col} is yes or no", not bad, bad)

    check("every row names a song", all(r["song"].strip() for r in rows))

    bad_url = [r["air_date"] for r in rows
               if r["video_id"] and r["video_url"] != WATCH_URL + r["video_id"]]
    check("video_url matches video_id", not bad_url, bad_url[:5])

    orphan = [r["air_date"] for r in rows if r["video_url"] and not r["video_id"]]
    check("no video_url without a video_id", not orphan, orphan[:5])

    # The show aired weekdays only, across all seven seasons. A weekend date
    # means a parsing error upstream, and it is the same fact that lets a clip
    # claiming a Saturday be dismissed as a bad description rather than a bad link.
    weekend = [r["air_date"] for r in rows
               if iso(r["air_date"]) and iso(r["air_date"]).weekday() >= 5]
    check("no episode airs at the weekend", not weekend, weekend[:5])

    # A guest sang the opener on Cameo-oke mornings. A clip of Kelly singing that
    # same song on another night is the wrong person on screen, so the two sets of
    # links must never touch. This was violated for twelve entries once.
    kelly = {r["video_id"] for r in rows if r["video_id"] and r["is_cameo"] == "no"}
    guest = {r["video_id"] for r in rows if r["video_id"] and r["is_cameo"] == "yes"}
    shared = sorted(kelly & guest)
    check("no clip is shared by a guest turn and a Kelly performance", not shared,
          f"{len(shared)} shared: {shared[:5]}")

    dup_ep = [k for k, n in Counter(
        (r["air_date"], r["song"]) for r in rows).items() if n > 1]
    check("no duplicate (air_date, song) row", not dup_ep, dup_ep[:5])

    print("\nvideo-urls.txt")
    urls = {line.strip().rsplit("=", 1)[1]
            for line in open(ROOT / "video-urls.txt", encoding="utf-8")
            if line.startswith("https")}
    check("every id appears in the CSV", urls <= (kelly | guest),
          sorted(urls - (kelly | guest))[:5])
    check("holds exactly the Kelly-only clips", urls == kelly,
          f"only in file: {sorted(urls - kelly)[:5]}\n"
          f"only in CSV:  {sorted(kelly - urls)[:5]}")

    print("\nPLAYLISTS.md")
    text = (ROOT / "PLAYLISTS.md").read_text(encoding="utf-8")
    parts = re.findall(r"part \d+ of \d+ \((\d+) videos\)\]"
                       r"\(https://www\.youtube\.com/watch_videos\?video_ids=([\w,\-]+)\)",
                       text)
    check("has playlist parts", bool(parts))
    if parts:
        declared = [int(n) for n, _ in parts]
        actual = [len(ids.split(",")) for _, ids in parts]
        check("each part declares its real length", declared == actual,
              f"declared {sum(declared)} vs actual {sum(actual)}")
        over = [n for n in actual if n > PLAYLIST_CAP]
        check(f"no part exceeds {PLAYLIST_CAP} videos", not over, over)
        flat = {i for _, ids in parts for i in ids.split(",")}
        check("every playlist id appears in the CSV", flat <= (kelly | guest),
              sorted(flat - (kelly | guest))[:5])
        check("playlists cover exactly the Kelly-only clips", flat == kelly,
              f"only in playlists: {sorted(flat - kelly)[:5]}\n"
              f"missing from playlists: {sorted(kelly - flat)[:5]}")

    print("\nrendered pages")
    for name in ("index.html", "explore.html"):
        raw = (ROOT / name).read_bytes()
        check(f"{name}: declares a charset", b"<meta charset" in raw)
        # a double-escaped CSS escape once emitted a real NUL, which made grep
        # treat the file as binary and silently report nothing
        check(f"{name}: no NUL bytes", raw.count(0) == 0, f"{raw.count(0)} found")
        # design_tokens carries doubled braces for f-string embedding; forgetting
        # to undouble them breaks the whole stylesheet without any error
        check(f"{name}: no unexpanded '{{{{'", b"{{" not in raw)
        check(f"{name}: non-trivial size", len(raw) > 50_000, f"{len(raw)} bytes")

    print("\nshare card")
    og = ROOT / "og-image.png"
    check("og-image.png exists", og.exists())
    if og.exists():
        raw = og.read_bytes()
        # PNG: 8-byte signature, 4-byte chunk length, "IHDR", then width, height
        sig_ok = raw[:8] == b"\x89PNG\r\n\x1a\n" and raw[12:16] == b"IHDR"
        check("og-image.png is a PNG", sig_ok)
        if sig_ok:
            w = int.from_bytes(raw[16:20], "big")
            h = int.from_bytes(raw[20:24], "big")
            check("og-image.png is 1200x630", (w, h) == (1200, 630), f"got {w}x{h}")
        # most platforms refuse to fetch a card over about 5 MB
        check("og-image.png under 5 MB", len(raw) < 5_000_000,
              f"{len(raw) / 1024:.0f} KB")

    for name in ("index.html", "explore.html"):
        page = (ROOT / name).read_text(encoding="utf-8")
        head = page[:4000]
        for tag in ("og:title", "og:image", "og:url", "twitter:card"):
            check(f"{name}: declares {tag}", tag in head,
                  "missing, or pushed out of the implied <head> by earlier content")
        check(f"{name}: og:image is an absolute URL",
              'content="https://kellyokes.netlify.app/og-image.png"' in head)

    print("\nREADME numbers agree with the data")
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    genre = Counter(r["genre"] for r in rows)
    stats = {
        "guest turns with a video": len([r for r in rows
                                         if r["is_cameo"] == "yes" and r["video_id"]]),
        "guest turns": len([r for r in rows if r["is_cameo"] == "yes"]),
        "Kelly performances": len([r for r in rows if r["is_cameo"] == "no"]),
        "Kelly with a video": len([r for r in rows
                                   if r["is_cameo"] == "no" and r["video_id"]]),
        "entries": len(rows),
        "no genre": sum(1 for r in rows if not r["genre"].strip()),
    }
    claims = [
        (r"only (\d[\d,]*) of (\d[\d,]*) have a video",
         ("guest turns with a video", "guest turns")),
        (r"(\d[\d,]*) of Kelly's (\d[\d,]*) are linked to a video",
         ("Kelly with a video", "Kelly performances")),
        (r"(\d[\d,]*) of (\d[\d,]*) entries have no genre", ("no genre", "entries")),
        (r"All (\d[\d,]*) entries, one row each", ("entries",)),
        (r"\*\*(\d[\d,]*) performances by Kelly\*\*", ("Kelly performances",)),
    ]
    for pattern, keys in claims:
        m = re.search(pattern, readme)
        if not m:
            check(f"README states: {pattern[:44]}", False, "claim not found in README")
            continue
        for got, key in zip(m.groups(), keys):
            check(f"README {key} = {stats[key]}", int(got.replace(",", "")) == stats[key],
                  f"README says {got}, data says {stats[key]:,}")
    for fam in ("Pop", "Rock", "Country"):
        m = re.search(rf"(\d[\d,]*) {fam.lower()}\b", readme)
        if m:
            check(f"README {fam.lower()} count = {genre[fam]}",
                  int(m.group(1).replace(",", "")) == genre[fam],
                  f"README says {m.group(1)}, data says {genre[fam]}")

    print(f"\n{CHECKS_RUN} checks, {len(FAILURES)} failed")
    if FAILURES:
        print("\nfailed:")
        for f in FAILURES:
            print(f"  - {f}")
        print("\nIf a count moved because the data legitimately changed, update "
              "README.md to match; these numbers go stale silently otherwise.")
        return 1
    return 0


def iso(s):
    try:
        return datetime.date.fromisoformat(s)
    except (ValueError, TypeError):
        return None


if __name__ == "__main__":
    sys.exit(main())
