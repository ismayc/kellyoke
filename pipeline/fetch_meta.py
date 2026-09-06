#!/usr/bin/env python3
"""Fetch genre, original release year and categories for every linked
song / artist article.

    python3 fetch_meta.py [--refresh]

By default an article already in wiki_meta.json is left alone, which makes the
usual run cheap. --refresh re-fetches every cached article instead. That flag
is not optional housekeeping: the cache stores the *parsed* result, not the
wikitext, so a fix to genre_list below changes nothing at all until the pages
it misparsed are pulled again.
"""
import argparse, collections, json, os, re, time, urllib.parse, urllib.request

S = os.path.dirname(os.path.abspath(__file__))
API = "https://en.wikipedia.org/w/api.php"
UA = "KellyokeResearch/1.0 (https://github.com/ismayc/kellyoke)"


def get(params):
    params = dict(params, format="json", formatversion="2")
    url = API + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    for attempt in range(4):
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                return json.load(r)
        except Exception:
            time.sleep(2 * (attempt + 1))
    return {}


def fetch_wikitext(titles):
    """title -> wikitext, following redirects, 50 at a time."""
    out = {}
    for i in range(0, len(titles), 50):
        batch = titles[i:i+50]
        d = get({"action": "query", "prop": "revisions", "rvprop": "content",
                 "rvslots": "main", "redirects": 1, "titles": "|".join(batch)})
        q = d.get("query", {})
        # map redirected/normalized names back to what we asked for
        alias = {}
        for k in ("redirects", "normalized"):
            for m in q.get(k, []):
                alias[m["to"]] = m["from"]
        for p in q.get("pages", []):
            if "revisions" not in p:
                continue
            txt = p["revisions"][0]["slots"]["main"].get("content", "")
            name = p["title"]
            out[name] = txt
            seen = name
            while seen in alias:            # unwind chains back to the query title
                seen = alias[seen]
                out[seen] = txt
        print(f"  {min(i+50,len(titles))}/{len(titles)}", flush=True)
        time.sleep(0.2)
    return out


def fetch_categories(titles):
    """title -> [category names], following redirects, 50 at a time.

    Categories are a weaker signal than the infobox genre and are only ever
    used as a last resort in enrich.py, because they are free text: run the
    family rules over all of them and "Number-one singles in Bulgaria" files a
    song under Classical. enrich.py matches them against its own short
    allowlist instead of the general rules.
    """
    out = collections.defaultdict(list)
    for i in range(0, len(titles), 50):
        batch = titles[i:i+50]
        cont = {}
        while True:
            d = get({"action": "query", "prop": "categories", "cllimit": "max",
                     "clshow": "!hidden", "redirects": 1,
                     "titles": "|".join(batch), **cont})
            q = d.get("query", {})
            alias = {}
            for k in ("redirects", "normalized"):
                for m in q.get(k, []):
                    alias[m["to"]] = m["from"]
            for p in q.get("pages", []):
                names, seen = [p["title"]], p["title"]
                while seen in alias:
                    seen = alias[seen]
                    names.append(seen)
                for c in p.get("categories", []):
                    for n in names:
                        out[n].append(c["title"].replace("Category:", ""))
            if "continue" not in d:
                break
            cont = d["continue"]
        print(f"  {min(i+50,len(titles))}/{len(titles)}", flush=True)
        time.sleep(0.2)
    return out


def infobox_field(wt, field):
    """Value of |field = ... inside the first infobox, brace-aware."""
    m = re.search(r"\|\s*" + field + r"\s*=", wt, re.I)
    if not m:
        return ""
    i, depth, buf = m.end(), 0, []
    while i < len(wt):
        two = wt[i:i+2]
        if two in ("{{", "[["):
            depth += 1; buf.append(two); i += 2; continue
        if two in ("}}", "]]"):
            if depth == 0:
                break
            depth -= 1; buf.append(two); i += 2; continue
        if wt[i] == "|" and depth == 0:
            break
        if wt[i] == "\n" and re.match(r"\s*\|", wt[i:i+40]):
            break
        buf.append(wt[i]); i += 1
    return "".join(buf).strip()


def genre_list(raw):
    if not raw:
        return []
    t = re.sub(r"<ref[^>]*/>|<ref.*?</ref>", " ", raw, flags=re.S)
    t = re.sub(r"<!--.*?-->", " ", t, flags=re.S)
    # {{hlist|a|b}}, {{flatlist|...}}, {{ubl|a|b}} -> split on the pipes.
    # The space in "flat list" is not optional cosmetics: articles write both
    # {{flatlist}} and {{flat list}}, and an alias that is missed here does not
    # degrade to a partial answer. The next line deletes any {{...}} it does not
    # recognize, so the whole genre value disappears and the song reads as
    # having no genre at all. That is what hid New wave on "I Melt with You"
    # and Indie rock on "Lost on You" while their release years came through
    # fine from the same infobox.
    t = re.sub(r"\{\{\s*(hlist|flat ?list|ubl|unbulleted list|plain ?list"
               r"|bulleted list)\s*\|", "", t, flags=re.I)
    t = re.sub(r"\[\[([^\[\]|]*)\|([^\[\]]*)\]\]", r"\2", t)
    t = re.sub(r"\[\[([^\[\]]*)\]\]", r"\1", t)
    t = re.sub(r"\{\{[^{}]*\}\}", " ", t)
    t = re.sub(r"<[^>]+>", "|", t)
    t = t.replace("*", "|").replace("\n", "|")
    parts = re.split(r"[|,/]", t)
    out = []
    for p in parts:
        p = re.sub(r"[\[\]{}']", "", p).strip(" .;:-").strip()
        if not p or len(p) > 40:
            continue
        if re.fullmatch(r"(and|or|the)", p, re.I):
            continue
        out.append(p)
    return out


def year_of(raw):
    if not raw:
        return None
    m = re.search(r"\{\{\s*(?:start date|film date)\s*\|\s*(\d{4})", raw, re.I)
    if m:
        return int(m.group(1))
    yrs = [int(y) for y in re.findall(r"\b(19\d{2}|20\d{2})\b", raw)]
    return min(yrs) if yrs else None


# ---------------------------------------------------------------- collect links
song_links, artist_links = {}, {}
for n in range(1, 8):
    wt = json.load(open(os.path.join(S, f"s{n}.json")))["parse"]["wikitext"]
    for b in re.findall(r"\{\{Episode list(.*?)\n\}\}", wt, flags=re.S):
        m = re.search(r"\|\s*Aux4\s*=([^\n]*)", b)
        if not m:
            continue
        aux = m.group(1)
        for q in re.finditer(r'"(.*?)"', aux):
            inner = q.group(1)
            lm = re.match(r"\s*\[\[([^\[\]|]+)(?:\|([^\[\]]*))?\]\]", inner)
            if lm:
                disp = (lm.group(2) or lm.group(1)).strip()
                song_links[disp.lower()] = lm.group(1)
        tail = aux.split(" by ", 1)
        if len(tail) > 1:
            for am in re.finditer(r"\[\[([^\[\]|]+)(?:\|([^\[\]]*))?\]\]", tail[1]):
                disp = (am.group(2) or am.group(1)).strip()
                artist_links[disp.lower()] = am.group(1)

print(f"song articles {len(set(song_links.values()))}, artist articles {len(set(artist_links.values()))}")

cache_p = os.path.join(S, "wiki_meta.json")
cache = json.load(open(cache_p)) if os.path.exists(cache_p) else {"song": {}, "artist": {}}

args = argparse.ArgumentParser()
args.add_argument("--refresh", action="store_true",
                  help="re-fetch articles already in the cache")
args = args.parse_args()

if args.refresh:
    want_s = sorted(set(song_links.values()) | set(cache["song"]))
    want_a = sorted(set(artist_links.values()) | set(cache["artist"]))
else:
    want_s = sorted({v for v in song_links.values() if v not in cache["song"]})
    want_a = sorted({v for v in artist_links.values() if v not in cache["artist"]})
    # An article cached before categories were collected has no "cats" key.
    # Pick those up without disturbing anything else already resolved.
    want_s += sorted({v for v in song_links.values()
                      if v in cache["song"] and "cats" not in cache["song"][v]})
    want_a += sorted({v for v in artist_links.values()
                      if v in cache["artist"] and "cats" not in cache["artist"][v]})
    want_s, want_a = sorted(set(want_s)), sorted(set(want_a))

if want_s:
    print(f"fetching {len(want_s)} song articles")
    cats = fetch_categories(want_s)
    for title, wt in fetch_wikitext(want_s).items():
        cache["song"][title] = {
            "genres": genre_list(infobox_field(wt, "genre")),
            "year": year_of(infobox_field(wt, "released")),
            "cats": cats.get(title, []),
        }
if want_a:
    print(f"fetching {len(want_a)} artist articles")
    cats = fetch_categories(want_a)
    for title, wt in fetch_wikitext(want_a).items():
        cache["artist"][title] = {
            "genres": genre_list(infobox_field(wt, "genre")),
            "cats": cats.get(title, []),
        }

json.dump(cache, open(cache_p, "w"), indent=1)

# Merge, do not replace. fetch_unlinked_artists.py adds artist_links for
# credits the season wikitext names but never links, Bob Dylan and Thalía
# among them, and those keys cannot be regenerated from the wikitext. Writing
# this file from scratch silently deletes them and un-classifies their songs.
# Wikitext-derived links still win, so a link that genuinely moved is updated.
links_p = os.path.join(S, "links.json")
merged = json.load(open(links_p)) if os.path.exists(links_p) else {}
merged.setdefault("song_links", {}).update(song_links)
merged.setdefault("artist_links", {}).update(artist_links)
kept = len(merged["artist_links"]) - len(artist_links)
json.dump(merged, open(links_p, "w"), indent=1)
if kept:
    print(f"kept {kept} artist links that the wikitext does not carry")

sg = sum(1 for v in cache["song"].values() if v["genres"])
sy = sum(1 for v in cache["song"].values() if v["year"])
ag = sum(1 for v in cache["artist"].values() if v["genres"])
print(f"\nsong articles cached {len(cache['song'])}: {sg} with genre, {sy} with year")
print(f"artist articles cached {len(cache['artist'])}: {ag} with genre")
