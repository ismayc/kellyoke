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

# Same list enrich.py filters genres on. A field written {{hlist |a |b}} can
# leak the template name through as the first value, which is not wrong so much
# as meaningless, and it would sort ahead of the real one.
JUNK = re.compile(r"^(cite|ref|http|www|isbn|p\.|pp\.|\d+)"
                  r"|^(hlist|flat ?list|ubl|plain ?list|unbulleted list"
                  r"|bulleted list|div col)$", re.I)


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


def plain(raw):
    """An infobox value as readable text: links unwrapped, refs, templates and
    markup removed. Shared by the album field and the people fields below."""
    if not raw:
        return ""
    t = re.sub(r"<ref[^>]*/>|<ref.*?</ref>", " ", raw, flags=re.S)
    t = re.sub(r"<!--.*?-->", " ", t, flags=re.S)
    t = re.sub(r"\{\{\s*(hlist|flat ?list|ubl|unbulleted list|plain ?list"
               r"|bulleted list)\s*\|", "", t, flags=re.I)
    t = re.sub(r"\[\[([^\[\]|]*)\|([^\[\]]*)\]\]", r"\2", t)
    t = re.sub(r"\[\[([^\[\]]*)\]\]", r"\1", t)
    t = re.sub(r"\{\{[^{}]*\}\}", " ", t)
    t = re.sub(r"<[^>]+>", " ", t)
    return re.sub(r"\s+", " ", t.replace("*", " ")).strip(" .;:-|'\"")


def people(wt, *fields):
    """Names from the first non-empty of `fields`, split the way the infobox
    lists them. "writer" is absent on most pre-rock standards, where the credit
    is split across "composer" and "lyricist" instead, so those are the
    fallbacks rather than separate columns."""
    for f in fields:
        raw = infobox_field(wt, f)
        if not raw:
            continue
        t = re.sub(r"<ref[^>]*/>|<ref.*?</ref>", " ", raw, flags=re.S)
        t = re.sub(r"\{\{\s*(hlist|flat ?list|ubl|unbulleted list|plain ?list"
                   r"|bulleted list)\s*\|", "", t, flags=re.I)
        t = re.sub(r"\[\[([^\[\]|]*)\|([^\[\]]*)\]\]", r"\2", t)
        t = re.sub(r"\[\[([^\[\]]*)\]\]", r"\1", t)
        t = re.sub(r"\{\{[^{}]*\}\}", " ", t)
        t = re.sub(r"<[^>]+>", "|", t)
        t = t.replace("*", "|").replace("\n", "|")
        out = []
        for p in re.split(r"[|;]", t):
            p = re.sub(r"[\[\]{}]", "", p).strip(" .,;:-")
            p = re.sub(r"\s+", " ", p)
            if not p or len(p) > 60 or JUNK.match(p):
                continue
            if re.fullmatch(r"(and|or|the|with|feat\.?|featuring)", p, re.I):
                continue
            if p.lower() not in [o.lower() for o in out]:
                out.append(p)
        if out:
            return out
    return []


def seconds_of(raw):
    """Track length in seconds, from "3:48" or {{Duration|m=3|s=48}}."""
    if not raw:
        return None
    m = re.search(r"\{\{\s*duration\s*\|(.*?)\}\}", raw, re.I)
    if m:
        d = {k.lower(): int(v) for k, v in
             re.findall(r"([hms])\s*=\s*(\d+)", m.group(1), re.I)}
        total = d.get("h", 0) * 3600 + d.get("m", 0) * 60 + d.get("s", 0)
        if total:
            return total
    m = re.search(r"\b(\d{1,2}):([0-5]\d)(?::([0-5]\d))?\b", raw)
    if m:
        h, mi, s = m.groups()
        return (int(h) * 3600 + int(mi) * 60 + int(s)) if s else int(h) * 60 + int(mi)
    return None


def year_of(raw):
    if not raw:
        return None
    m = re.search(r"\{\{\s*(?:start date|film date)\s*\|\s*(\d{4})", raw, re.I)
    if m:
        return int(m.group(1))
    yrs = [int(y) for y in re.findall(r"\b(19\d{2}|20\d{2})\b", raw)]
    return min(yrs) if yrs else None


# ---------------------------------------------------------------- collect links
def unlink(t):
    """[[Page|Shown]] -> Shown, matching parse_wiki3.clean() so the artist text
    here is the same string that ends up on the performance."""
    t = re.sub(r"\[\[([^\[\]|]*)\|([^\[\]]*)\]\]", r"\2", t)
    return re.sub(r"\[\[([^\[\]]*)\]\]", r"\1", t)


def artist_text(raw):
    """The credit as parse_wiki3 records it: unlinked, small-tags dropped, and
    a trailing parenthetical removed."""
    t = re.sub(r"\{\{\s*small\s*\|.*?\}\}", " ", raw, flags=re.I | re.S)
    t = re.sub(r"</?small>", "", t)
    t = unlink(t).strip().rstrip(".;,")
    return re.sub(r"\s*\(.*?\)\s*$", "", t).strip()


# song_links is keyed on the title alone, which is wrong whenever two different
# songs share one: "Dreams" is credited to Beck, Fleetwood Mac and The
# Cranberries on different mornings, and the last write won. The wikitext
# already disambiguates each of them, so song_pairs keeps the artist in the key
# and song_links stays only as the fallback for a credit that did not parse.
song_links, artist_links, song_pairs = {}, {}, {}
for n in range(1, 8):
    wt = json.load(open(os.path.join(S, f"s{n}.json")))["parse"]["wikitext"]
    for b in re.findall(r"\{\{Episode list(.*?)\n\}\}", wt, flags=re.S):
        m = re.search(r"\|\s*Aux4\s*=([^\n]*)", b)
        if not m:
            continue
        aux = m.group(1)
        # one pass, so each quoted title keeps the credit that follows it
        for q in re.finditer(r'"([^"]+)"(\s*by\s+([^/,"]+))?', aux):
            lm = re.match(r"\s*\[\[([^\[\]|]+)(?:\|([^\[\]]*))?\]\]", q.group(1))
            if not lm:
                continue
            page = lm.group(1)
            disp = (lm.group(2) or lm.group(1)).strip()
            song_links[disp.lower()] = page
            who = artist_text(q.group(3) or "")
            if who:
                song_pairs[f"{disp.lower()}\t{who.lower()}"] = page
        tail = aux.split(" by ", 1)
        if len(tail) > 1:
            for am in re.finditer(r"\[\[([^\[\]|]+)(?:\|([^\[\]]*))?\]\]", tail[1]):
                disp = (am.group(2) or am.group(1)).strip()
                artist_links[disp.lower()] = am.group(1)

print(f"song articles {len(set(song_links.values()))}, "
      f"artist articles {len(set(artist_links.values()))}, "
      f"song+artist pairs {len(song_pairs)}")

cache_p = os.path.join(S, "wiki_meta.json")
cache = json.load(open(cache_p)) if os.path.exists(cache_p) else {"song": {}, "artist": {}}

args = argparse.ArgumentParser()
args.add_argument("--refresh", action="store_true",
                  help="re-fetch articles already in the cache")
args = args.parse_args()

# song_pairs points at articles song_links never named: where two songs share a
# title, only the last one written ever got fetched.
all_songs = set(song_links.values()) | set(song_pairs.values())

if args.refresh:
    want_s = sorted(all_songs | set(cache["song"]))
    want_a = sorted(set(artist_links.values()) | set(cache["artist"]))
else:
    want_s = sorted({v for v in all_songs if v not in cache["song"]})
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
            "writers": people(wt, "writer", "composer", "lyricist"),
            "album": plain(infobox_field(wt, "album")),
            "seconds": seconds_of(infobox_field(wt, "length")),
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
merged.setdefault("song_pairs", {}).update(song_pairs)
kept = len(merged["artist_links"]) - len(artist_links)
json.dump(merged, open(links_p, "w"), indent=1)
if kept:
    print(f"kept {kept} artist links that the wikitext does not carry")

sg = sum(1 for v in cache["song"].values() if v["genres"])
sy = sum(1 for v in cache["song"].values() if v["year"])
ag = sum(1 for v in cache["artist"].values() if v["genres"])
print(f"\nsong articles cached {len(cache['song'])}: {sg} with genre, {sy} with year")
print(f"artist articles cached {len(cache['artist'])}: {ag} with genre")
