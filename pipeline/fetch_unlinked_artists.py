#!/usr/bin/env python3
"""Fetch genre for artists the season wikitext named but never linked.

fetch_meta.py builds `artist_links` from the wikilinks in the season articles,
so an artist only gets an infobox lookup if some editor happened to write
[[Bob Dylan]] rather than plain "Bob Dylan". That is an editorial accident, not
a fact about the artist, and it left 51 artists unfetched, Bob Dylan, Ella
Fitzgerald and Cole Porter among them.

This script takes the artist names off the performances themselves, resolves
each as a Wikipedia title directly, and merges what it finds into the same two
caches fetch_meta.py writes. It only ever adds: an artist already in the cache
is left alone, so this can be re-run safely and cannot regress a genre that is
already resolved.

Two shapes of artist string need unpicking before a title lookup can work, both
the same class of bug as the alternate-title problem in match3.py:

  "Eve featuring Gwen Stefani"   -> the credit is not an article; "Eve" is
  "JP Saxe and Julia Michaels"   -> a joint credit; either half will do

The full string is always tried first, because "Fitz & The Tantrums" and
"Aly & AJ" are single band names that splitting would destroy.

Run after match3.py and before enrich.py. Needs network.

    python3 fetch_unlinked_artists.py [--dry-run]
"""
import argparse
import json
import os
import re
import time
import urllib.parse
import urllib.request

S = os.path.dirname(os.path.abspath(__file__))
API = "https://en.wikipedia.org/w/api.php"
UA = "KellyokeResearch/1.0 (https://github.com/ismayc/kellyoke)"

# Guard against resolving "Coco" to the film or "Still" to a song article. Only
# the FIRST infobox is the page's own: an artist article routinely contains
# {{Infobox album}} further down in a discography section, and testing the whole
# page rejected every musician on earth, Bob Dylan included.
NOT_A_MUSICIAN = re.compile(r"^(film|album|single|song|television|book|"
                            r"video game|musical|character)\b", re.I)


JUNK = re.compile(r"^(cite|ref|http|www|isbn|p\.|pp\.|\d+)"
                  r"|^(hlist|flatlist|ubl|plainlist|unbulleted list|div col)$", re.I)


def first_infobox(wt):
    """The name of the page's own infobox, lowercased, or ''."""
    m = re.search(r"\{\{\s*infobox\s+([^\n|}]+)", wt, re.I)
    return m.group(1).strip().lower() if m else ""


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
        batch = titles[i:i + 50]
        d = get({"action": "query", "prop": "revisions", "rvprop": "content",
                 "rvslots": "main", "redirects": 1, "titles": "|".join(batch)})
        q = d.get("query", {})
        alias = {}
        for k in ("redirects", "normalized"):
            for m in q.get(k, []):
                alias[m["to"]] = m["from"]
        for p in q.get("pages", []):
            if "revisions" not in p:
                continue
            txt = p["revisions"][0]["slots"]["main"].get("content", "")
            out[p["title"]] = txt
            seen = p["title"]
            while seen in alias:
                seen = alias[seen]
                out[seen] = txt
        time.sleep(0.2)
    return out


def infobox_field(wt, field):
    """Value of |field = ... inside the first infobox, brace-aware."""
    m = re.search(r"\|\s*" + field + r"\s*=", wt, re.I)
    if not m:
        return ""
    i, depth, buf = m.end(), 0, []
    while i < len(wt):
        two = wt[i:i + 2]
        if two in ("{{", "[["):
            depth += 1; buf.append(two); i += 2; continue
        if two in ("}}", "]]"):
            if depth == 0:
                break
            depth -= 1; buf.append(two); i += 2; continue
        if wt[i] == "|" and depth == 0:
            break
        if wt[i] == "\n" and re.match(r"\s*\|", wt[i:i + 40]):
            break
        buf.append(wt[i]); i += 1
    return "".join(buf).strip()


def genre_list(raw):
    if not raw:
        return []
    t = re.sub(r"<ref[^>]*/>|<ref.*?</ref>", " ", raw, flags=re.S)
    t = re.sub(r"<!--.*?-->", " ", t, flags=re.S)
    t = re.sub(r"\{\{\s*(hlist|flatlist|ubl|unbulleted list|plainlist)\s*\|", "", t, flags=re.I)
    t = re.sub(r"\[\[([^\[\]|]*)\|([^\[\]]*)\]\]", r"\2", t)
    t = re.sub(r"\[\[([^\[\]]*)\]\]", r"\1", t)
    t = re.sub(r"\{\{[^{}]*\}\}", " ", t)
    t = re.sub(r"<[^>]+>", "|", t)
    t = t.replace("*", "|").replace("\n", "|")
    out = []
    for p in re.split(r"[|,/]", t):
        p = re.sub(r"[\[\]{}']", "", p).strip(" .;:-").strip()
        if not p or len(p) > 40 or re.fullmatch(r"(and|or|the)", p, re.I):
            continue
        # Same junk list enrich.py filters on. Without it a field written
        # {{hlist |jazz |swing}} yields "hlist" as the first genre, which is
        # not wrong so much as meaningless, and it wins over the real one.
        if JUNK.match(p):
            continue
        out.append(p)
    return out


def candidates(artist):
    """Title guesses for one artist credit, most specific first."""
    out = [artist]
    primary = re.split(r"\s+(?:featuring|feat\.?|ft\.?|with)\s+", artist, flags=re.I)[0].strip()
    if primary and primary != artist:
        out.append(primary)
    for part in re.split(r"\s*(?:&|\band\b)\s*", primary, flags=re.I):
        part = part.strip()
        if part and part not in out:
            out.append(part)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true",
                    help="report what would be fetched and exit")
    args = ap.parse_args()

    rows = json.load(open(os.path.join(S, "matched.json")))
    cache_p = os.path.join(S, "wiki_meta.json")
    links_p = os.path.join(S, "links.json")
    cache = json.load(open(cache_p))
    links = json.load(open(links_p))
    known = {k.lower(): v for k, v in links["artist_links"].items()}

    def resolved(name):
        t = known.get(name.lower())
        return bool(t and cache["artist"].get(t, {}).get("genres"))

    # Only artists on performances that still have no genre. Anything already
    # resolved is left alone; this script must not be able to change a genre
    # that the song's own article supplied.
    wanted = {}
    for r in rows:
        for p in r["perfs"]:
            artist = (p.get("artist") or "").strip()
            if not artist or p.get("genre") not in (None, "", "Not listed"):
                continue
            if any(resolved(c) for c in candidates(artist)):
                continue
            wanted.setdefault(artist, candidates(artist))

    titles = sorted({c for cands in wanted.values() for c in cands
                     if c.lower() not in known})
    print(f"{len(wanted)} unresolved artist credits, {len(titles)} title guesses")
    if args.dry_run:
        for a, c in sorted(wanted.items())[:25]:
            print(f"   {a[:44]:<44} -> {c}")
        return

    wt = fetch_wikitext(titles)
    print(f"fetched {len(wt)} pages")

    added = 0
    for artist, cands in sorted(wanted.items()):
        for c in cands:
            text = wt.get(c)
            if not text or NOT_A_MUSICIAN.match(first_infobox(text)):
                continue
            genres = genre_list(infobox_field(text, "genre"))
            if not genres:
                continue
            # Key the link on the credit as written, so enrich.py's lookup on
            # the display name finds it without enrich.py having to change.
            links["artist_links"][artist.lower()] = c
            cache["artist"].setdefault(c, {"genres": genres})
            cache["artist"][c]["genres"] = genres
            print(f"  {artist[:40]:<40} -> {c}: {', '.join(genres[:3])}")
            added += 1
            break

    json.dump(cache, open(cache_p, "w"))
    json.dump(links, open(links_p, "w"))
    print(f"\nresolved {added} of {len(wanted)} artist credits")
    print(f"{len(wanted) - added} still unresolved; those need the song article "
          f"or a hand-assigned genre")


if __name__ == "__main__":
    main()
