#!/usr/bin/env python3
"""Use each video's own stated 'Original airdate' to confirm or correct its link.

This is stronger evidence than a title match: it comes from the uploader's own
description, so where a song was covered on several nights it settles which
night a given clip is.
"""
import json, os, re, datetime, unicodedata, collections
from difflib import SequenceMatcher

S = os.path.dirname(os.path.abspath(__file__))
air = json.load(open(os.path.join(S, "video_airdates.json")))
rows = json.load(open(os.path.join(S, "matched.json")))

MEDLEY = re.compile(r"medley|recap", re.I)


def norm(t):
    t = unicodedata.normalize("NFKD", t or "")
    t = "".join(c for c in t if not unicodedata.combining(c))
    t = t.lower().replace("&", " and ")
    t = re.sub(r"\bfeat\.?\b|\bft\.?\b", " ", t)
    t = re.sub(r"\(.*?\)|\[.*?\]", " ", t)
    t = re.sub(r"[^a-z0-9 ]+", " ", t)
    return re.sub(r"^the ", "", re.sub(r"\s+", " ", t).strip())


def songtitle(t):
    m = re.match(r"^.*?(?:kellyoke|kelloyke)[^|\-]*[|\-]\s*(.+)$", t or "", re.I)
    if m:
        b = re.sub(r"\[.*?\]", " ", m.group(1))
        return re.sub(r"\s*\([^()]*\)\s*$", "", b).strip()
    m = re.match(r"^['\"](.+?)['\"]", t or "")
    return m.group(1) if m else (t or "")


# every known video, with its title
titles = {}
for fn in ("channel_videos.jsonl", "playlist_videos.jsonl", "kcvideos.jsonl",
           "courtney.jsonl", "xavier.jsonl"):
    p = os.path.join(S, fn)
    if not os.path.exists(p):
        continue
    for line in open(p):
        if not line.strip():
            continue
        v = json.loads(line)
        if v.get("id") and v.get("title") and v["id"] not in titles:
            titles[v["id"]] = v["title"]

by_date = collections.defaultdict(list)
for vid, d in air.items():
    by_date[d].append(vid)

d0 = datetime.date.fromisoformat
verified = corrected = rerun_ok = offby1 = yeartypo = unresolved = 0
changes = []

for r in rows:
    ep = r["date_iso"]
    for p in r["perfs"]:
        v = p["video_id"]
        if not v:
            continue
        stated = air.get(v)
        # a medley/recap clip legitimately covers a whole episode or week
        if MEDLEY.search(titles.get(v, "")):
            p["date_check"] = "medley"
            continue
        if stated == ep:
            p["date_check"] = "verified"
            verified += 1
            continue

        # is there a clip that states exactly this episode's date and matches the song?
        best, bs = None, 0.0
        for cand in by_date.get(ep, []):
            s = SequenceMatcher(None, norm(p["song"]), norm(songtitle(titles.get(cand, "")))).ratio()
            if s > bs:
                best, bs = cand, s
        if best and bs >= 0.86 and best != v:
            changes.append((ep, p["song"], v, best, round(bs, 2)))
            p["video_id"] = best
            p["video_title"] = titles.get(best, "")
            p["date_check"] = "corrected"
            corrected += 1
            continue

        if stated is None:
            p["date_check"] = "unstated"
            unresolved += 1
        elif r["rerun"]:
            p["date_check"] = "rerun"      # clip shows the first airing, as expected
            rerun_ok += 1
        elif abs((d0(stated) - d0(ep)).days) <= 1:
            p["date_check"] = "offby1"
            offby1 += 1
        elif stated[5:] == ep[5:]:
            p["date_check"] = "yeartypo"   # same month/day, wrong year in the description
            yeartypo += 1
        else:
            p["date_check"] = "mismatch"
            unresolved += 1

# ---------------------------------------------------------------------------
# Refine what is left. "mismatch" was carrying two very different things: links
# that are genuinely unexplained, and the already-known case where a song was
# sung on several nights but only one night's clip was ever posted, so every
# date points at that one clip. The second is a gap in the archive, not a bad
# link, and calling it a mismatch overstated the problem by two orders.
users = collections.defaultdict(list)
for r in rows:
    for p in r["perfs"]:
        if p.get("video_id"):
            users[p["video_id"]].append((r["date_iso"], bool(r["cameo"]), p))

upload = json.load(open(os.path.join(S, "upload_dates.json"))) \
    if os.path.exists(os.path.join(S, "upload_dates.json")) else {}

SOLID = {"verified", "corrected", "offby1", "yeartypo"}
reprise = baddate = preair = 0
for r in rows:
    for p in r["perfs"]:
        # A clip uploaded before this episode aired cannot be this episode's
        # performance. Same conclusion as a reprise, reached from the upload
        # date instead of the description.
        if p.get("date_check") == "unstated":
            u = upload.get(p["video_id"])
            if u and u[:4] + "-" + u[4:6] + "-" + u[6:8] < r["date_iso"]:
                p["date_check"] = "preair"
                preair += 1
            continue
        if p.get("date_check") != "mismatch":
            continue
        # Does another episode share this clip, sing the same song, have solid
        # evidence for it, AND have the same kind of performer? Then this clip
        # is that other airing. The performer check matters: a guest turn
        # sharing a clip with a Kelly performance is the wrong person on
        # screen, not a reprise.
        me = bool(r["cameo"])
        sibs = [(d, c, q) for d, c, q in users[p["video_id"]] if d != r["date_iso"]]
        if any(c == me and q.get("date_check") in SOLID
               and SequenceMatcher(None, norm(p["song"]), norm(q["song"])).ratio() >= 0.85
               for _d, c, q in sibs):
            p["date_check"] = "reprise"
            reprise += 1
            continue
        # The show never aired at the weekend (0 of 1,233 episodes), so a clip
        # claiming a Saturday or Sunday has an unreliable date, not a bad link.
        stated = air.get(p["video_id"])
        if stated and d0(stated).weekday() >= 5:
            p["date_check"] = "baddate"
            baddate += 1

json.dump(rows, open(os.path.join(S, "matched.json"), "w"), indent=1)

print(f"verified against the clip's own airdate : {verified}")
print(f"corrected to a clip stating that date   : {corrected}")
print(f"rerun (clip shows the first airing)     : {rerun_ok}")
print(f"within a day (two fallible sources)     : {offby1}")
print(f"description year typo                   : {yeartypo}")
print(f"reprise (only one night's clip posted)  : {reprise}")
print(f"clip dated to a weekend, show never was : {baddate}")
print(f"uploaded before the episode aired       : {preair}")
print(f"still unexplained / no stated date      : {unresolved - reprise - baddate - preair}")
print("\ncorrections made:")
for c in changes[:25]:
    print(f"    {c[0]}  {c[1][:34]:36s} {c[2]} -> {c[3]}  (title sim {c[4]})")
print(f"    ... {len(changes)} total" if len(changes) > 25 else "")
