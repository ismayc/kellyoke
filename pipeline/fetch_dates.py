#!/usr/bin/env python3
"""Fetch upload dates for archive videos of songs Kelly performed more than once.

Where a song was covered on several nights and the archive holds several videos
of it, the videos can be aligned to the air dates chronologically instead of
every date pointing at the same clip.
"""
import json, os, re, subprocess, collections, unicodedata
from difflib import SequenceMatcher

S = os.path.dirname(os.path.abspath(__file__))
YTDLP = os.path.join(S, "venv", "bin", "yt-dlp")
MEDLEY = re.compile(r"medley|recap", re.I)


def norm(t):
    t = unicodedata.normalize("NFKD", t or "")
    t = "".join(c for c in t if not unicodedata.combining(c))
    t = t.lower().replace("&", " and ")
    t = re.sub(r"\(.*?\)|\[.*?\]", " ", t)
    t = re.sub(r"[^a-z0-9 ]+", " ", t)
    return re.sub(r"^the ", "", re.sub(r"\s+", " ", t).strip())


# candidate archive videos, grouped by normalized song title
cands = collections.defaultdict(list)
for fn in ("kcvideos.jsonl", "courtney.jsonl", "xavier.jsonl"):
    p = os.path.join(S, fn)
    if not os.path.exists(p):
        continue
    for line in open(p):
        if not line.strip():
            continue
        v = json.loads(line)
        t = v.get("title") or ""
        if MEDLEY.search(t):
            continue
        m = re.match(r"^.*?(?:kellyoke|kelloyke)[^|\-]*[|\-]\s*(.+)$", t, re.I)
        if not m:
            continue
        body = re.sub(r"\[.*?\]", " ", m.group(1))
        # the archive titles put the artist in the trailing parenthetical
        # ("Kellyoke | Home (Michael Buble)"). Keep it: it is the only thing that
        # tells four different songs called "Home" apart.
        mart = re.search(r"\(([^()]*)\)\s*$", body)
        body = re.sub(r"\s*\([^()]*\)\s*$", "", body)
        k = norm(body)
        if k:
            # The archive omits the artist on Kelly's own songs and marks them
            # "Kellyoke (Classic)" instead, so an absent parenthetical there
            # means Kelly Clarkson, not "unknown".
            vart = norm(mart.group(1)) if mart else ""
            if not vart and re.search(r"\(classic\)", t, re.I):
                vart = "kelly clarkson"
            cands[k].append({"id": v["id"], "title": t, "artist": vart})

rows = json.load(open(os.path.join(S, "matched.json")))
dates = collections.defaultdict(set)
for r in rows:
    if r["cameo"]:
        # a guest's turn is not a repeat of Kelly's performance and must not
        # consume one of her clips in the chronological pairing
        continue
    for p in r["perfs"]:
        if not p.get("label_only"):
            dates[norm(p["song"])].add((r["date_iso"], norm(p.get("artist") or "")))

need = {k for k, d in dates.items()
        if len({x[0] for x in d}) > 1 and len(cands.get(k, [])) > 1}
ids = sorted({c["id"] for k in need for c in cands[k]})
print(f"songs needing disambiguation: {len(need)}   videos to date: {len(ids)}")

cache_path = os.path.join(S, "upload_dates.json")
cache = json.load(open(cache_path)) if os.path.exists(cache_path) else {}
todo = [i for i in ids if i not in cache]
print(f"already cached: {len(ids)-len(todo)}   fetching: {len(todo)}")

for n, vid in enumerate(todo, 1):
    try:
        r = subprocess.run([YTDLP, "--skip-download", "--print", "%(upload_date)s",
                            f"https://www.youtube.com/watch?v={vid}"],
                           capture_output=True, text=True, timeout=60)
        d = r.stdout.strip().splitlines()
        cache[vid] = d[0] if d and d[0].isdigit() else None
    except Exception:
        cache[vid] = None
    if n % 20 == 0:
        print(f"  {n}/{len(todo)}", flush=True)
        json.dump(cache, open(cache_path, "w"))

json.dump(cache, open(cache_path, "w"))
got = sum(1 for i in ids if cache.get(i))
print(f"upload dates resolved: {got}/{len(ids)}")

def asim(a, b):
    """Artist similarity. Containment counts as a match, so "Chuck Berry" and
    "Chuck Berry Kelly Clarkson version" stay one artist."""
    if not a or not b:
        return 0.0
    if a in b or b in a:
        return 1.0
    return SequenceMatcher(None, a, b).ratio()


# chronological pairing: nth air date -> nth-uploaded video.
# That pairing assumes every date under a title key is the same song. Where a
# title is shared by different songs (four unrelated "Home"s, two "River"s), the
# assumption is false and the pairing silently hands one song's clip to another.
# So split the key by artist first and pair only within an artist.
assign = {}
unassigned = []
for k in sorted(need):
    vs = [c for c in cands[k] if cache.get(c["id"])]
    vs.sort(key=lambda c: cache[c["id"]])
    ds = sorted(dates[k])
    if len(vs) < 2:
        continue

    groups = []
    for _d, a in ds:
        if a and not any(asim(a, g) > 0.6 for g in groups):
            groups.append(a)

    if len(groups) <= 1:
        # one song: the original chronological pairing, unchanged
        for i, (d, _a) in enumerate(ds):
            assign[f"{d}|{k}"] = vs[i]["id"] if i < len(vs) else vs[-1]["id"]
        continue

    for g in groups:
        gds = [d for d, a in ds if asim(a, g) > 0.6]
        gvs = [c for c in vs if asim(c["artist"], g) > 0.6]
        if not gvs:
            # no clip of this artist's song: assign nothing rather than borrow a
            # same-titled clip by someone else. match3 falls back on its own.
            unassigned.extend(f"{d}|{k}" for d in gds)
            continue
        for i, d in enumerate(gds):
            assign[f"{d}|{k}"] = gvs[i]["id"] if i < len(gvs) else gvs[-1]["id"]
json.dump(assign, open(os.path.join(S, "date_assign.json"), "w"), indent=1)
print(f"date-aligned assignments: {len(assign)} across {len(need)} songs")
print(f"left unassigned (no clip by that artist): {len(unassigned)}")
for u in sorted(unassigned):
    print(f"    {u}")
