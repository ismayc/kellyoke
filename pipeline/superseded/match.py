#!/usr/bin/env python3
"""Match each Wikipedia-sourced Kellyoke performance to the best YouTube video."""
import json, re, os, unicodedata
from difflib import SequenceMatcher

S = os.path.dirname(os.path.abspath(__file__))

# ---------------------------------------------------------------- normalizing
def norm(t):
    if not t:
        return ""
    t = unicodedata.normalize("NFKD", t)
    t = "".join(c for c in t if not unicodedata.combining(c))
    t = t.lower()
    t = t.replace("&", " and ").replace("’", "'").replace("‘", "'")
    t = re.sub(r"\bfeat\.?\b|\bft\.?\b|\bfeaturing\b", " ", t)
    t = re.sub(r"\(.*?\)", " ", t)          # drop parentheticals
    t = re.sub(r"\[.*?\]", " ", t)
    t = re.sub(r"[^a-z0-9 ]+", " ", t)
    t = re.sub(r"\s+", " ", t).strip()
    t = re.sub(r"^the ", "", t)
    return t


def sim(a, b):
    return SequenceMatcher(None, a, b).ratio()


def tsim(a, b):
    """Title similarity that tolerates length variants:
    'I Ran' vs 'I Ran So Far Away', 'You Make My Dreams' vs '... Come True'."""
    r = sim(a, b)
    if not a or not b:
        return r
    short, long_ = (a, b) if len(a) <= len(b) else (b, a)
    # only allow the containment boost for distinctive strings, so that a
    # one-word title like "You" cannot swallow "You Make My Dreams"
    if len(short) >= 7 and len(short.split()) >= 2:
        ts, tl = set(short.split()), set(long_.split())
        if short in long_ or ts <= tl:
            r = max(r, 0.93)
    return r


# ------------------------------------------------------------ load video pool
def load(path):
    out = []
    if not os.path.exists(path):
        return out
    with open(path) as f:
        for line in f:
            line = line.strip()
            if line:
                out.append(json.loads(line))
    return out


official = load(os.path.join(S, "channel_videos.jsonl"))
kc = load(os.path.join(S, "kcvideos.jsonl"))
xa = load(os.path.join(S, "xavier.jsonl"))

KELLYOKE_HINT = re.compile(r"kellyoke|cameo-?oke", re.I)


def extract_official(title):
    """'X' By Y | Kelly Clarkson Kellyoke Cover  /  Kelly Clarkson Covers 'X' By Y | Kellyoke"""
    if not KELLYOKE_HINT.search(title):
        return None
    body = title.split("|")[0].strip()
    body = re.sub(r"^kelly clarkson covers\s*", "", body, flags=re.I)
    m = re.match(r"['\"](.+?)['\"]\s*(?:by|from)\s+(.*)$", body, re.I)
    if m:
        return m.group(1), m.group(2)
    m = re.match(r"['\"](.+?)['\"]\s*$", body)
    if m:
        return m.group(1), ""
    return None


def extract_kc(title):
    """Kellyoke | X (Y)   /   Kellyoke (Classic) | X (Y)"""
    m0 = re.match(r"^(.*?kellyoke[^|\-]*)\s*[|\-]\s*(.+)$", title, re.I)
    if not m0:
        return None
    head, body = m0.group(1), m0.group(2)
    if not re.search(r"kellyoke", head, re.I):
        return None
    body = body.strip()
    body = re.sub(r"\[.*?\]", " ", body)                    # [With Lawrence Zarian]
    m = re.match(r"^(.*?)\s*\(([^()]*)\)\s*$", body)
    if m:
        return m.group(1).strip(), m.group(2).strip()
    return body.strip(), ""


def extract_xavier(title):
    if not KELLYOKE_HINT.search(title):
        return None
    body = re.split(r"\s+[l|]\s+", title)[0].strip()
    body = re.sub(r"^kelly clarkson (covers|sings)\s*", "", body, flags=re.I)
    m = re.match(r"['\"]?(.+?)['\"]?\s+(?:by|from)\s+(.*)$", body, re.I)
    if m:
        return m.group(1).strip(" '\""), m.group(2).strip()
    return None


pool = []   # (norm_title, norm_artist, rank, video_id, raw_title, source)
SOURCES = [
    (official, extract_official, 0, "The Kelly Clarkson Show (official)"),
    (kc,       extract_kc,       1, "KC Videos archive"),
    (xa,       extract_xavier,   2, "Xavier Del Cid archive"),
]
for vids, extract, rank, label in SOURCES:
    for v in vids:
        t = v.get("title") or ""
        got = extract(t)
        if not got:
            continue
        song, artist = got
        ns = norm(song)
        if not ns:
            continue
        pool.append({
            "ntitle": ns, "nartist": norm(artist), "rank": rank,
            "id": v.get("id"), "raw": t, "source": label,
            "duration": v.get("duration"), "views": v.get("view_count"),
        })

print(f"video pool: {len(pool)}  "
      f"(official={sum(1 for p in pool if p['rank']==0)}, "
      f"kc={sum(1 for p in pool if p['rank']==1)}, "
      f"xavier={sum(1 for p in pool if p['rank']==2)})")

# index by first token for speed
from collections import defaultdict
idx = defaultdict(list)
for p in pool:
    idx[p["ntitle"][:4]].append(p)
    idx[p["ntitle"].split(" ")[0]].append(p)


def best_video(song, artist):
    ns, na = norm(song), norm(artist)
    if not ns:
        return None
    def score_over(cands):
        out = []
        for p in cands:
            s = tsim(ns, p["ntitle"])
            if s < 0.86:
                continue
            # a is None when either side has no artist info - that is "unknown",
            # not "disagrees", and must not veto the match
            a = sim(na, p["nartist"]) if (na and p["nartist"]) else None
            # a near-but-not-exact title with a clearly different artist is a
            # different song ("Pride (In the Name of Love)" vs "Ride")
            if s < 0.99 and a is not None and a < 0.5:
                continue
            # exact title match is worth a lot; artist agreement breaks ties
            score = s * 3 + (a or 0.0)
            if s >= 0.995:
                score += 1.0
            out.append((score, -p["rank"], s, a, p))
        return out

    cands = {id(p): p for p in idx.get(ns[:4], []) + idx.get(ns.split(" ")[0], [])}.values()
    scored = score_over(cands)
    if not scored:
        # bucket lookup missed (spelling variants like "Till"/"Til") - full scan
        scored = score_over(pool)
    if not scored:
        return None
    scored.sort(key=lambda x: (-x[0], -x[1]))
    top = scored[0]
    return {"video": top[4], "title_sim": round(top[2], 3), "artist_sim": (round(top[3], 3) if top[3] is not None else None)}


episodes = json.load(open(os.path.join(S, "episodes.json")))

rows = []
for ep in episodes:
    perfs = []
    for (song, artist) in ep["songs"]:
        m = best_video(song, artist)
        perfs.append({
            "song": song,
            "artist": artist,
            "video_id": m["video"]["id"] if m else None,
            "video_title": m["video"]["raw"] if m else None,
            "source": m["video"]["source"] if m else None,
            "duration": m["video"]["duration"] if m else None,
            "title_sim": m["title_sim"] if m else None,
            "artist_sim": m["artist_sim"] if m else None,
        })
    ep2 = dict(ep)
    ep2["perfs"] = perfs
    rows.append(ep2)

json.dump(rows, open(os.path.join(S, "matched.json"), "w"), indent=1)

total = sum(len(r["perfs"]) for r in rows)
hit = sum(1 for r in rows for p in r["perfs"] if p["video_id"])
print(f"performances: {total}")
print(f"matched:      {hit}  ({hit/total:.1%})")
for lbl, rk in [("official", "The Kelly Clarkson Show (official)"),
                ("kc", "KC Videos archive"),
                ("xavier", "Xavier Del Cid archive")]:
    print(f"  via {lbl:8s}: {sum(1 for r in rows for p in r['perfs'] if p['source']==rk)}")
print("\nunmatched by season:")
for s in range(1, 8):
    sub = [p for r in rows if r["season"] == s for p in r["perfs"]]
    print(f"  S{s}: {sum(1 for p in sub if not p['video_id']):3d} / {len(sub):3d}")
