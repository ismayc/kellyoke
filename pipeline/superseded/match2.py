#!/usr/bin/env python3
"""Match each Kellyoke performance to the best available YouTube video.

Sources, in preference order:
  0  The Kelly Clarkson Show official channel (videos tab + every channel playlist)
  1  KC Videos archive          (systematic 'Kellyoke | Song (Artist)' mirror)
  2  Courtney O'shea archive    (same convention, later seasons)
  3  Xavier Del Cid archive     (lower resolution, last resort)
"""
import json, re, os, unicodedata, collections
from difflib import SequenceMatcher

S = os.path.dirname(os.path.abspath(__file__))


def norm(t):
    if not t:
        return ""
    t = unicodedata.normalize("NFKD", t)
    t = "".join(c for c in t if not unicodedata.combining(c))
    t = t.lower().replace("&", " and ").replace("’", "'").replace("‘", "'")
    t = re.sub(r"\bfeat\.?\b|\bft\.?\b|\bfeaturing\b", " ", t)
    t = re.sub(r"\(.*?\)", " ", t)
    t = re.sub(r"\[.*?\]", " ", t)
    t = re.sub(r"[^a-z0-9 ]+", " ", t)
    t = re.sub(r"\s+", " ", t).strip()
    return re.sub(r"^the ", "", t)


def sim(a, b):
    return SequenceMatcher(None, a, b).ratio()


def tsim(a, b):
    r = sim(a, b)
    if not a or not b:
        return r
    short, long_ = (a, b) if len(a) <= len(b) else (b, a)
    if len(short) >= 7 and len(short.split()) >= 2:
        if short in long_ or set(short.split()) <= set(long_.split()):
            r = max(r, 0.93)
    return r


def load(name):
    p = os.path.join(S, name)
    if not os.path.exists(p):
        return []
    return [json.loads(l) for l in open(p) if l.strip()]


KELLYOKE_HINT = re.compile(r"kellyoke|cameo-?oke", re.I)


def extract_official(title):
    if not KELLYOKE_HINT.search(title):
        return None
    body = title.split("|")[0].strip()
    body = re.sub(r"^kelly clarkson (covers|sings)\s*", "", body, flags=re.I)
    m = re.match(r"['\"](.+?)['\"]\s*(?:by|from)\s+(.*)$", body, re.I)
    if m:
        return m.group(1), m.group(2)
    m = re.match(r"['\"](.+?)['\"]\s*$", body)
    return (m.group(1), "") if m else None


def extract_pipe(title):
    """'Kellyoke | Song (Artist)' and 'Kellyoke - Song (Artist)'."""
    m0 = re.match(r"^(.*?kellyoke[^|\-]*)\s*[|\-]\s*(.+)$", title, re.I)
    if not m0 or not re.search(r"kellyoke", m0.group(1), re.I):
        return None
    body = re.sub(r"\[.*?\]", " ", m0.group(2)).strip()
    m = re.match(r"^(.*?)\s*\(([^()]*)\)\s*$", body)
    return (m.group(1).strip(), m.group(2).strip()) if m else (body.strip(), "")


def extract_xavier(title):
    if not KELLYOKE_HINT.search(title):
        return None
    body = re.split(r"\s+[l|]\s+", title)[0].strip()
    body = re.sub(r"^kelly clarkson (covers|sings)\s*", "", body, flags=re.I)
    m = re.match(r"['\"]?(.+?)['\"]?\s+(?:by|from)\s+(.*)$", body, re.I)
    return (m.group(1).strip(" '\""), m.group(2).strip()) if m else None


official = {v["id"]: v for v in load("channel_videos.jsonl")}
for v in load("playlist_videos.jsonl"):          # channel playlists add ~200 more
    official.setdefault(v["id"], v)

SOURCES = [
    (list(official.values()), extract_official, 0, "The Kelly Clarkson Show (official)"),
    (load("kcvideos.jsonl"),  extract_pipe,     1, "KC Videos archive"),
    (load("courtney.jsonl"),  extract_pipe,     2, "Courtney O'shea archive"),
    (load("xavier.jsonl"),    extract_xavier,   3, "Xavier Del Cid archive"),
]

pool = []
for vids, extract, rank, label in SOURCES:
    for v in vids:
        got = extract(v.get("title") or "")
        if not got:
            continue
        ns = norm(got[0])
        if not ns:
            continue
        pool.append({"ntitle": ns, "nartist": norm(got[1]), "rank": rank,
                     "id": v.get("id"), "raw": v.get("title"), "source": label,
                     "duration": v.get("duration"), "views": v.get("view_count")})

print("video pool:", len(pool), collections.Counter(p["source"] for p in pool))

idx = collections.defaultdict(list)
for p in pool:
    idx[p["ntitle"][:4]].append(p)
    idx[p["ntitle"].split(" ")[0]].append(p)


def best_video(song, artist):
    ns, na = norm(song), norm(artist)
    if not ns:
        return None

    def score(cands):
        out = []
        for p in cands:
            s = tsim(ns, p["ntitle"])
            if s < 0.86:
                continue
            a = sim(na, p["nartist"]) if (na and p["nartist"]) else None
            if s < 0.99 and a is not None and a < 0.5:
                continue          # same-ish title, clearly different song
            out.append((s * 3 + (a or 0.0) + (1.0 if s >= 0.995 else 0.0),
                        -p["rank"], s, a, p))
        return out

    cands = {id(p): p for p in idx.get(ns[:4], []) + idx.get(ns.split(" ")[0], [])}.values()
    scored = score(cands) or score(pool)
    if not scored:
        return None
    scored.sort(key=lambda x: (-x[0], -x[1]))
    t = scored[0]
    return {"v": t[4], "ts": round(t[2], 3), "as": (round(t[3], 3) if t[3] is not None else None)}


rows = []
for ep in json.load(open(os.path.join(S, "episodes.json"))):
    perfs = []
    for song, artist in ep["songs"]:
        m = best_video(song, artist)
        perfs.append({
            "song": song, "artist": artist,
            "video_id": m["v"]["id"] if m else None,
            "video_title": m["v"]["raw"] if m else None,
            "source": m["v"]["source"] if m else None,
            "duration": m["v"]["duration"] if m else None,
            "title_sim": m["ts"] if m else None,
            "artist_sim": m["as"] if m else None,
        })
    rows.append({**ep, "perfs": perfs})

json.dump(rows, open(os.path.join(S, "matched.json"), "w"), indent=1)

perfs = [(r, p) for r in rows for p in r["perfs"]]
kelly = [(r, p) for r, p in perfs if not r["cameo"]]
cameo = [(r, p) for r, p in perfs if r["cameo"]]
hit = lambda xs: sum(1 for _, p in xs if p["video_id"])
print(f"\nall entries    {len(perfs):5d}  matched {hit(perfs):5d}  ({hit(perfs)/len(perfs):.1%})")
print(f"  Kelly        {len(kelly):5d}  matched {hit(kelly):5d}  ({hit(kelly)/len(kelly):.1%})")
print(f"  Cameo-oke    {len(cameo):5d}  matched {hit(cameo):5d}")
print("\nby source:", collections.Counter(p["source"] for _, p in perfs if p["source"]))
print("\nunmatched Kelly performances by season:")
for s in range(1, 8):
    sub = [p for r, p in kelly if r["season"] == s]
    print(f"  S{s}: {sum(1 for p in sub if not p['video_id']):3d} / {len(sub):3d}")
