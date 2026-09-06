#!/usr/bin/env python3
"""Attach genre, original release year and popularity to every performance.

Genre and year come from the linked song's Wikipedia infobox, falling back to
the artist's infobox for genre when the song has no article. View counts come
from the channel dumps already on disk.
"""
import json, os, re, collections

S = os.path.dirname(os.path.abspath(__file__))
rows = json.load(open(os.path.join(S, "matched.json")))
meta = json.load(open(os.path.join(S, "wiki_meta.json")))
links = json.load(open(os.path.join(S, "links.json")))

JUNK = re.compile(r"^(cite|ref|http|www|isbn|p\.|pp\.|\d+)"
                  r"|^(hlist|flatlist|ubl|plainlist|unbulleted list|div col)$", re.I)

# ordered rules: first match wins, so "pop rock" lands in Rock and
# "country pop" in Country, which is how each is normally filed
FAMILY = [
    ("Christmas",       r"christmas|holiday|noel|carol"),
    ("Gospel",          r"gospel|worship|contemporary christian|\bccm\b|spiritual"),
    ("Musical theatre", r"musical theat|show ?tune|broadway|west end|musical film|\bmusical\b"),
    ("Latin",           r"latin|reggaeton|salsa|bachata|cumbia|tejano|mariachi|ranchera|bossa nova"),
    ("Reggae",          r"reggae|ska\b|dancehall|rocksteady"),
    ("World",           r"calypso|mento|exotica|afrobeat|highlife|worldbeat|k-?pop"),
    ("Hip hop",         r"hip.?hop|\brap\b|trap\b|g-funk"),
    ("Metal",           r"metal"),
    ("Punk",            r"punk"),
    ("Country",         r"country|bluegrass|americana|honky.?tonk|western swing|nashville"),
    ("Rock",            r"rock"),
    ("Rock",            r"new wave|grunge|shoegaze|\bemo\b|alternative|britpop|psychedelia"),
    ("R&B / Soul",      r"r&b|rhythm and blues|soul|funk|motown|doo.?wop|new jack swing|quiet storm"),
    ("Pop",             r"pop"),
    ("Electronic",      r"disco|house|techno|\bedm\b|electronic|dance|trance|electro|synth|club|garage"),
    ("Jazz / Blues",    r"jazz|blues|swing|ragtime|big band|lounge|standard|torch song|vocal"),
    ("Folk",            r"folk|singer.?songwriter|celtic|bluesy folk|traditional"),
    ("Classical",       r"classical|opera|aria|orchestral|baroque|choral|hymn|light music|^light$|easy listening"),
]


def family(g):
    g = (g or "").lower()
    for name, pat in FAMILY:
        if re.search(pat, g):
            return name
    return ""


def clean_genres(gs):
    out = []
    for g in gs or []:
        g = g.strip()
        if not g or JUNK.match(g) or len(g) < 2:
            continue
        if g.lower() not in [o.lower() for o in out]:
            out.append(g)
    return out


song_by_disp = {k: v for k, v in links["song_links"].items()}
art_by_disp = {k: v for k, v in links["artist_links"].items()}


def artist_candidates(artist):
    """The credit as written, then the ways it might name a real article.

    A credit is not always an article title. "Eve featuring Gwen Stefani" is a
    billing, and "JP Saxe and Julia Michaels" is two people; neither has a page,
    so an exact lookup found nothing and the genre came out blank. The full
    string is tried first and always, because "Fitz & The Tantrums" and
    "Aly & AJ" are band names that splitting would destroy.

    Falling back to one half of a collaboration is a deliberate approximation:
    the genre of the lead credit is a better guess for the song than no genre
    at all, and every family here is broad enough to survive it.
    """
    artist = (artist or "").strip()
    if not artist:
        return []
    out = [artist]
    lead = re.split(r"\s+(?:featuring|feat\.?|ft\.?|with)\s+", artist, flags=re.I)[0].strip()
    if lead and lead != artist:
        out.append(lead)
    for part in re.split(r"\s*(?:&|\band\b)\s*", lead, flags=re.I):
        part = part.strip()
        if part and part not in out:
            out.append(part)
    return out

# ---- view counts from whatever dump holds each video --------------------
views, durs = {}, {}
for fn in ("channel_videos.jsonl", "playlist_videos.jsonl", "kcvideos.jsonl",
           "courtney.jsonl", "xavier.jsonl"):
    p = os.path.join(S, fn)
    if not os.path.exists(p):
        continue
    for line in open(p):
        if not line.strip():
            continue
        v = json.loads(line)
        i = v.get("id")
        if not i:
            continue
        if v.get("view_count") and i not in views:
            views[i] = v["view_count"]
        if v.get("duration") and i not in durs:
            durs[i] = v["duration"]

# ---- duet partners -----------------------------------------------------------
# Wikipedia only sometimes records these. The archives mark many in the video
# title as "[with X]", and a few are known from reporting on the episode.
WITH_RE = re.compile(r"\[\s*with\s+([^\]]+)\]", re.I)
DUET_OVERRIDE = {
    # The Voice Hour: Kelly takes verse one, the other coaches join in
    ("2019-11-21", "Neon Moon"): "Blake Shelton, Gwen Stefani & John Legend",
}

stats = collections.Counter()
for r in rows:
    yr = int(r["date_iso"][:4])
    for p in r["perfs"]:
        disp = p["song"].lower()
        sart = song_by_disp.get(disp)
        sm = meta["song"].get(sart) if sart else None
        genres = clean_genres(sm["genres"]) if sm else []
        year = sm["year"] if sm else None
        src = "song" if genres else ""
        if not genres:
            for cand in artist_candidates(p["artist"] or ""):
                am = meta["artist"].get(art_by_disp.get(cand.lower(), ""))
                if am:
                    genres = clean_genres(am["genres"])
                    if genres:
                        src = "artist"
                        break
        fam = family(genres[0]) if genres else ""
        if not fam:
            for g in genres[1:]:
                fam = family(g)
                if fam:
                    break
        p["genres"] = genres[:4]
        p["genre"] = fam or "Not listed"
        p["genre_src"] = src
        p["orig_year"] = year
        p["decade"] = (year // 10 * 10) if year else None
        p["age_at_cover"] = (yr - year) if year and year <= yr else None
        # performance-level duet: episode note, then the video title, then a known fix
        duet = r.get("duet") or ""
        if not duet and p.get("video_title"):
            m = WITH_RE.search(p["video_title"])
            if m:
                duet = m.group(1).strip()
        duet = DUET_OVERRIDE.get((r["date_iso"], p["song"]), duet)
        p["duet"] = duet
        p["views"] = views.get(p["video_id"]) if p["video_id"] else None
        if p["video_id"] and not p.get("duration"):
            p["duration"] = durs.get(p["video_id"])
        stats[fam or "Not listed"] += 1

json.dump(rows, open(os.path.join(S, "matched.json"), "w"), indent=1)

allp = [p for r in rows for p in r["perfs"]]
print(f"performances {len(allp)}")
print(f"  with a genre        : {sum(1 for p in allp if p['genre']!='Not listed')}"
      f"  ({sum(1 for p in allp if p['genre_src']=='song')} from the song article,"
      f" {sum(1 for p in allp if p['genre_src']=='artist')} from the artist)")
print(f"  with a release year : {sum(1 for p in allp if p['orig_year'])}")
print(f"  with a view count   : {sum(1 for p in allp if p['views'])}")
print(f"  with a duration     : {sum(1 for p in allp if p.get('duration'))}")
ndu = sum(1 for r in rows for q in r["perfs"] if q.get("duet"))
nfrom_ep = sum(1 for r in rows for q in r["perfs"] if q.get("duet") and r.get("duet"))
print(f"  duets identified    : {ndu}  ({nfrom_ep} from the episode note,"
      f" {ndu-nfrom_ep} recovered from video titles or known fixes)")
print("\ngenre spread:")
for g, n in stats.most_common():
    print(f"  {n:5d}  {g}")
yrs = [p["orig_year"] for p in allp if p["orig_year"]]
print(f"\noriginal release years: {min(yrs)} to {max(yrs)}")
dec = collections.Counter(p["decade"] for p in allp if p["decade"])
for d in sorted(dec):
    print(f"  {d}s: {dec[d]}")
