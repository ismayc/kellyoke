#!/usr/bin/env python3
"""Match every Kellyoke performance to the best available video.

v3 adds: the official channel's "Kelly Clarkson Sings 'X'" finale/By-Request
uploads, hand-verified overrides for medleys and awkward titles, and a report
of how often one video has to stand in for several separate performances.
"""
import json, re, os, unicodedata, collections
from difflib import SequenceMatcher

S = os.path.dirname(os.path.abspath(__file__))

# ---- hand-verified links, checked one by one against YouTube search results --
OFFICIAL = "The Kelly Clarkson Show (official)"
OV = {
    # medleys: the episode has one video covering all of its songs
    ("2020-09-21", None): ("hH3ucwLncDw", "KC Videos archive", "TV theme medley"),
    ("2022-09-12", None): ("_mN3df_e7Ds", "KC Videos archive", "premiere medley"),
    ("2024-09-23", None): ("ZoxDNzdNbsI", "KC Videos archive", "dance medley"),
    # series finale + Kelly By Request: official uploads, not titled "Kellyoke"
    ("2026-08-31", "Sober"):        ("liE_aOke6d4", OFFICIAL, ""),
    ("2026-08-31", "Piece by Piece"): ("HqgAXODLmLc", OFFICIAL, ""),
    ("2026-08-31", "I'd Be Lyin'"): ("Q8dGh6adZvE", OFFICIAL, ""),
    ("2026-08-31", "Didn't I"):     ("5UZE1wgrVkA", OFFICIAL, ""),
    ("2026-08-31", "Since U Been Gone"): ("U94lBqHmE-o", OFFICIAL, ""),
    ("2026-08-31", "Stronger (What Doesn't Kill You)"): ("eYuPU2XvCww", OFFICIAL, ""),
    # titles the fuzzy matcher could not reach
    ("2019-11-25", "Ain't Goin' Down ('Til the Sun Comes Up)"):
        ("w4vMRQiq2-0", "KC Videos archive", ""),
    ("2021-05-10", "Dude (Looks Like a Lady)"): ("Y8uYc76_bdo", "KC Videos archive", ""),
    ("2022-04-19", "I Ran (So Far Away)"):      ("enY31hVxJCc", "KC Videos archive", ""),
    ("2023-03-13", "She Wants to Move"):        ("3SmlaLyYaug", "KC Videos archive", ""),
    ("2024-10-01", "Lovin', Touchin', Squeezin'"): ("ytpnQsNTVPE", "Xavier Del Cid archive", ""),
    ("2024-10-22", "All the Stars"):            ("JNZ4tomXpOY", "Xavier Del Cid archive", ""),
    # Two names for one song, and each source parenthesized the other one.
    # norm() strips parentheses, so the wiki's "Day-O (The Banana Boat Song)"
    # became "day o" and the clip's "Banana Boat (Day-O)" became "banana boat",
    # scoring 0.375 against a 0.86 threshold. The clip was in the pool the whole
    # time. Fix an alternate title with an override here, never by loosening
    # norm(): a lower threshold buys this one song at the cost of false matches
    # across the other thousand.
    ("2024-10-31", "Day-O (The Banana Boat Song)"):
        ("h6gxn1gc91A", "KC Videos archive", ""),
    ("2024-12-03", "All the Stars"):            ("JNZ4tomXpOY", "Xavier Del Cid archive", ""),
    # other uploaders, verified by title + runtime
    ("2019-12-05", "Scars to Your Beautiful"): ("vr_hkOZZkLY", "Other upload", ""),
    ("2020-01-31", "All My Life"):             ("JJV4RKDq5jQ", "Other upload", ""),
    ("2024-05-28", "Make You Feel My Love"):   ("R7TvyUR3LWY", "Other upload", "duet with Ben Platt"),
    ("2025-05-21", "Go Home W U"):             ("-NZOYVA0tIs", "Other upload", "duet with Keith Urban"),
    # weekly recap compilations - the only surviving copy
    ("2023-12-21", "Christmas in Sarajevo"):   ("JNWBrhA0ung", "Weekly recap", "inside a recap"),
    ("2024-01-09", "Tossed Salad and Scrambled Eggs"): ("sWgKsv7gLq0", "Weekly recap", "inside a recap"),
    ("2024-07-09", "Tossed Salad and Scrambled Eggs"): ("sWgKsv7gLq0", "Weekly recap", "inside a recap"),
}

RANK = {OFFICIAL: 0, "KC Videos archive": 1, "Courtney O'shea archive": 2,
        "Xavier Del Cid archive": 3, "Other upload": 4, "Weekly recap": 5}


def norm(t):
    if not t:
        return ""
    t = unicodedata.normalize("NFKD", t)
    t = "".join(c for c in t if not unicodedata.combining(c))
    t = t.lower().replace("&", " and ").replace("’", "'").replace("‘", "'")
    t = re.sub(r"\bfeat\.?\b|\bft\.?\b|\bfeaturing\b", " ", t)
    t = re.sub(r"\(.*?\)|\[.*?\]", " ", t)
    t = re.sub(r"[^a-z0-9 ]+", " ", t)
    return re.sub(r"^the ", "", re.sub(r"\s+", " ", t).strip())


def sim(a, b):
    return SequenceMatcher(None, a, b).ratio()


def rawnorm(t):
    """norm() without the parenthesis-stripping, so a qualifier stays visible."""
    t = unicodedata.normalize("NFKD", t or "")
    t = "".join(c for c in t if not unicodedata.combining(c))
    t = t.lower().replace("&", " and ").replace("’", "'").replace("‘", "'")
    t = re.sub(r"[^a-z0-9 ]+", " ", t)
    return re.sub(r"\s+", " ", t).strip()


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
    return [json.loads(l) for l in open(p) if l.strip()] if os.path.exists(p) else []


# "Cameo-oke", "Cameooke", "Cameoke", and the official channel's "Cameo oke"
# with a space. Missing the fourth spelling hid eight real guest clips and one
# Kelly cover from the pool entirely.
HINT = re.compile(r"kellyoke|kelloyke|cameo?\s*-?\s*oke", re.I)
# a clip that shows a guest singing, not Kelly
GUESTCLIP = re.compile(r"cameo?\s*-?\s*oke|\(guest\)|performed by", re.I)

# Typos in the Wikipedia source. Each is one entry, and each splits an artist
# across two names in the "most covered" chart. Unambiguous, so corrected here.
ARTIST_FIX = {"Billie Ellish": "Billie Eilish",
              "San Ryder": "Sam Ryder",
              "Chole Qisha": "Chloe Qisha"}
MEDLEY = re.compile(r"medley|recap", re.I)
FINALE_ONLY = re.compile(r"series finale|kelly by request", re.I)


def ex_official(t):
    # "Kelly Clarkson Sings 'X' | Series Finale" / "| Kelly By Request"
    m = re.match(r"^kelly clarkson sings ['\"](.+?)['\"]\s*\|", t, re.I)
    if m:
        return m.group(1), "Kelly Clarkson"
    if not HINT.search(t):
        return None
    body = re.sub(r"^kelly clarkson (covers|sings)\s*", "", t.split("|")[0].strip(), flags=re.I)
    m = re.match(r"['\"](.+?)['\"]\s*(?:by|from)\s+(.*)$", body, re.I)
    if m:
        return m.group(1), m.group(2)
    m = re.match(r"['\"](.+?)['\"]\s*$", body)
    return (m.group(1), "") if m else None


def ex_pipe(t):
    m0 = re.match(r"^(.*?(?:kellyoke|kelloyke)[^|\-]*)\s*[|\-]\s*(.+)$", t, re.I)
    if not m0:
        return None
    body = re.sub(r"\[.*?\]", " ", m0.group(2)).strip()
    m = re.match(r"^(.*?)\s*\(([^()]*)\)\s*$", body)
    return (m.group(1).strip(), m.group(2).strip()) if m else (body.strip(), "")


def ex_xavier(t):
    if not HINT.search(t):
        return None
    body = re.split(r"\s+[l|]\s+", t)[0].strip()
    # guest turns read "Josh Groban' Covers 'Over the Rainbow' By Cameo oke":
    # drop the stray possessive so the real quotes pair up
    body = re.sub(r"(\w)'\s+(covers|sings|lip syncs)\b", r"\1 \2", body, flags=re.I)
    body = re.sub(r"^kelly clarkson (covers|sings)\s*", "", body, flags=re.I)
    # A cleanly quoted title is the most reliable thing in these uploads. A
    # quote only delimits when it is not inside a word: the apostrophes in
    # "I'm Still Standing" and "Covers' You're" are not quotes.
    QUOTED = r"(?:^|(?<=\s))['\"](\S.*?\S)['\"](?=\s|$)"
    m = re.search(QUOTED + r"\s+(?:by|from)\s+(.*)$", body, re.I)
    if m:
        return (m.group(1).strip(), m.group(2).strip(" '\""))
    q = re.findall(QUOTED, body)
    if q:
        return (q[-1].strip(), "")
    m = re.match(r"['\"]?(.+?)['\"]?\s+(?:by|from)\s+(.*)$", body, re.I)
    return (m.group(1).strip(" '\""), m.group(2).strip()) if m else None


official = {v["id"]: v for v in load("channel_videos.jsonl") if v.get("id")}
for v in load("playlist_videos.jsonl"):
    if v.get("id"):
        official.setdefault(v["id"], v)

pool, byid, SRC_OF = [], {}, {}
for vids, ex, label in [
        (list(official.values()), ex_official, OFFICIAL),
        (load("kcvideos.jsonl"),  ex_pipe,     "KC Videos archive"),
        (load("courtney.jsonl"),  ex_pipe,     "Courtney O'shea archive"),
        (load("xavier.jsonl"),    ex_xavier,   "Xavier Del Cid archive")]:
    for v in vids:
        t = v.get("title") or ""
        byid[v.get("id")] = v
        got = ex(t)
        if not got:
            continue
        ns = norm(got[0])
        # a medley/recap video must not be matched to a single song by title,
        # and the finale / "Kelly By Request" uploads belong only to their own
        # night - without this they outrank the archive copy for earlier dates
        if not ns or MEDLEY.search(t) or FINALE_ONLY.search(t):
            continue
        SRC_OF[v.get("id")] = label
        pool.append({"ntitle": ns, "nartist": norm(got[1]), "rank": RANK[label],
                     "id": v.get("id"), "raw": t, "source": label,
                     "duration": v.get("duration"),
                     "guest": bool(GUESTCLIP.search(t))})

print("video pool:", len(pool), dict(collections.Counter(p["source"] for p in pool)))

idx = collections.defaultdict(list)
for p in pool:
    idx[p["ntitle"][:4]].append(p)
    idx[p["ntitle"].split(" ")[0]].append(p)


def best(song, artist, cameo=False):
    ns, na = norm(song), norm(artist)
    if not ns:
        return None
    # a qualifier in the song title, e.g. the "(Lyana's Song)" that separates
    # Amy Grant's "Home" from three other songs of that name
    _mq = re.search(r"\(([^()]+)\)", song or "")
    qual = rawnorm(_mq.group(1)) if _mq else ""

    def score(c):
        out = []
        for p in c:
            s = tsim(ns, p["ntitle"])
            if s < 0.86:
                continue
            a = sim(na, p["nartist"]) if (na and p["nartist"]) else None
            # A perfect title match normally outranks a weak artist match: the
            # wiki credits whoever wrote the song, the upload credits whoever
            # made it famous, so "That's Life" is Marion Montgomery to one and
            # Frank Sinatra to the other and both are right. That reasoning only
            # holds when the titles really are the same. norm() strips
            # parentheses, so a song whose title carries a qualifier can match a
            # different song perfectly. Require the upload to mention the
            # qualifier before letting a perfect title score waive the artist.
            strong = s >= 0.99 and (not qual or qual in rawnorm(p["raw"]))
            if not strong and a is not None and a < 0.5:
                continue
            out.append((s*3 + (a or 0) + (1 if s >= 0.995 else 0), -p["rank"], s, a, p))
        return out

    cands = list({id(p): p for p in idx.get(ns[:4], []) + idx.get(ns.split(" ")[0], [])}.values())
    if cameo:
        # A guest sang this one. Only a clip marked as a guest turn can show
        # it. A Kelly clip of the same song is the wrong performer, so there is
        # no fallback: better no link than a link to somebody else.
        sc = score([p for p in cands if p["guest"]]) or score([p for p in pool if p["guest"]])
    else:
        # Kelly sang it. Prefer clips not marked as guest turns, but allow one
        # as a last resort: an uploader occasionally tags a Kelly cover
        # "Cameo oke" by mistake.
        sc = (score([p for p in cands if not p["guest"]])
              or score([p for p in pool if not p["guest"]])
              or score(cands) or score(pool))
    if not sc:
        return None
    sc.sort(key=lambda x: (-x[0], -x[1]))
    t = sc[0]
    return {"v": t[4], "ts": round(t[2], 3), "as": (round(t[3], 3) if t[3] is not None else None)}


DA = {}
_dap = os.path.join(S, "date_assign.json")
if os.path.exists(_dap):
    DA = json.load(open(_dap))


def dkey(d, song):
    return f"{d}|{norm(song)}"


rows = []
for ep in json.load(open(os.path.join(S, "episodes.json"))):
    d = ep["date_iso"]
    perfs = []
    for song, artist in ep["songs"]:
        artist = ARTIST_FIX.get(artist, artist)
        ov = OV.get((d, song)) or OV.get((d, None))
        if ov:
            vid, src, note = ov
            v = byid.get(vid, {})
            perfs.append({"song": song, "artist": artist, "video_id": vid,
                          "video_title": v.get("title") or "", "source": src,
                          "duration": v.get("duration"), "title_sim": None,
                          "artist_sim": None, "note": note, "verified": True})
            continue
        # date_assign pairs Kelly's repeat performances with Kelly's clips; a
        # guest turn must never be handed one of those
        da = None if ep["cameo"] else DA.get(dkey(d, song))
        if da:
            v = byid.get(da, {})
            src = SRC_OF.get(da, "KC Videos archive")
            perfs.append({"song": song, "artist": artist, "video_id": da,
                          "video_title": v.get("title") or "", "source": src,
                          "duration": v.get("duration"), "title_sim": None,
                          "artist_sim": None, "note": "matched by upload date",
                          "verified": True})
            continue
        m = best(song, artist, cameo=bool(ep["cameo"]))
        perfs.append({"song": song, "artist": artist,
                      "video_id": m["v"]["id"] if m else None,
                      "video_title": m["v"]["raw"] if m else None,
                      "source": m["v"]["source"] if m else None,
                      "duration": m["v"]["duration"] if m else None,
                      "title_sim": m["ts"] if m else None,
                      "artist_sim": m["as"] if m else None,
                      "note": "", "verified": False})
    # an episode-level medley override also covers episodes with no parsed song
    if not perfs and (d, None) in OV:
        vid, src, note = OV[(d, None)]
        v = byid.get(vid, {})
        perfs.append({"song": ep["aux_raw"] or "Medley", "artist": "", "video_id": vid,
                      "video_title": v.get("title") or "", "source": src,
                      "duration": v.get("duration"), "title_sim": None,
                      "artist_sim": None, "note": note, "verified": True,
                      "label_only": True})
    rows.append({**ep, "perfs": perfs})

json.dump(rows, open(os.path.join(S, "matched.json"), "w"), indent=1)

allp = [(r, p) for r in rows for p in r["perfs"]]
kelly = [(r, p) for r, p in allp if not r["cameo"]]
guest = [(r, p) for r, p in allp if r["cameo"]]
hit = lambda xs: sum(1 for _, p in xs if p["video_id"])
print(f"\nentries {len(allp)}   with video {hit(allp)}")
print(f"  Kelly  {len(kelly):5d}  with video {hit(kelly):5d}  ({hit(kelly)/len(kelly):.1%})")
print(f"  guest  {len(guest):5d}  with video {hit(guest):5d}")
print("\nby source:", dict(collections.Counter(p["source"] for _, p in allp if p["source"])))

dup = collections.Counter(p["video_id"] for _, p in allp if p["video_id"])
shared = {v: c for v, c in dup.items() if c > 1}
print(f"\nvideos standing in for >1 performance: {len(shared)}"
      f"  (covering {sum(shared.values())} entries)")
print("unmatched Kelly performances:", sum(1 for _, p in kelly if not p["video_id"]))
for r, p in kelly:
    if not p["video_id"]:
        print(f'   {r["date_iso"]}  {p["song"]!r} by {p["artist"]!r}')
