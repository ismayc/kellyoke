#!/usr/bin/env python3
"""Parse Kellyoke performances from the Wikipedia season wikitext.

v3 fixes over v2:
  * "Cameoke" is an alternate Wikipedia spelling -> regex now cameo?-?oke
  * "performed by <someone>" (as opposed to "performed with") means the guest
    sang it, not Kelly - e.g. P!nk's guest-host week, Jewel, Keith Urban
  * repairs the unbalanced-paren typo in "Stay (I Missed You"
"""
import json, re, os

S = os.path.dirname(os.path.abspath(__file__))
MONTHS = ["January","February","March","April","May","June","July","August",
          "September","October","November","December"]


def strip_refs(t):
    t = re.sub(r"<ref[^>]*/>", "", t)
    t = re.sub(r"<ref.*?</ref>", "", t, flags=re.S)
    return re.sub(r"<!--.*?-->", "", t, flags=re.S)


def unlink(t):
    t = re.sub(r"\[\[([^\[\]|]*)\|([^\[\]]*)\]\]", r"\2", t)
    return re.sub(r"\[\[([^\[\]]*)\]\]", r"\1", t)


def clean(t, keep_small=False):
    t = unlink(strip_refs(t))
    t = re.sub(r"\{\{abbr\|([^|}]*)\|[^}]*\}\}", r"\1", t, flags=re.I)
    t = re.sub(r"\{\{TableTBA\|([^}]*)\}\}", r"\1", t, flags=re.I)
    t = re.sub(r"\{\{TableTBA\}\}", "TBA", t, flags=re.I)
    if keep_small:
        t = re.sub(r"\{\{\s*small\s*\|(.*?)\}\}", r"\1", t, flags=re.I | re.S)
    else:
        t = re.sub(r"\{\{\s*small\s*\|.*?\}\}", " ", t, flags=re.I | re.S)
    t = re.sub(r"\{\{'-\}\}", "'", t)
    t = re.sub(r"\{\{'\}\}", "'", t)
    t = re.sub(r"\{\{[^{}]*\}\}", " ", t)
    t = re.sub(r"</?small>", "", t)
    t = re.sub(r"<br\s*/?>", " ", t, flags=re.I)
    t = re.sub(r"<[^>]+>", " ", t)
    t = re.sub(r"'''?", "", t)
    t = t.replace("&nbsp;", " ").replace("“", '"').replace("”", '"')
    t = t.replace("‘", "'").replace("’", "'")
    return re.sub(r"\s+", " ", t).strip()


def parse_date(raw):
    m = re.search(r"\{\{\s*Start date\s*\|\s*(\d{4})\s*\|\s*(\d{1,2})\s*\|\s*(\d{1,2})", raw, re.I)
    if m:
        y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
        return f"{y:04d}-{mo:02d}-{d:02d}", f"{MONTHS[mo-1]} {d}, {y}"
    m = re.search(r"(" + "|".join(MONTHS) + r")\s+(\d{1,2}),\s*(\d{4})", clean(raw))
    if m:
        mo = MONTHS.index(m.group(1)) + 1
        return f"{int(m.group(3)):04d}-{mo:02d}-{int(m.group(2)):02d}", m.group(0)
    return None, clean(raw)


def fields(block):
    out, depth, key, buf, i = {}, 0, None, [], 0
    while i < len(block):
        two = block[i:i+2]
        if two in ("{{", "[["):
            depth += 1; buf.append(two); i += 2; continue
        if two in ("}}", "]]"):
            depth -= 1; buf.append(two); i += 2; continue
        if block[i] == "|" and depth == 0:
            if key:
                out[key.strip().lower()] = "".join(buf).strip()
            m = re.match(r"\s*([A-Za-z0-9_]+)\s*=", block[i+1:])
            if m:
                key, buf = m.group(1), []
                i += 1 + m.end(); continue
        buf.append(block[i]); i += 1
    if key:
        out[key.strip().lower()] = "".join(buf).strip()
    return out


NOT_A_SONG = {"by request hour"}
TYPO = {"Stay (I Missed You": "Stay (I Missed You)"}


def split_songs(aux, summary=""):
    src = aux
    if '"' not in aux and '"' in summary:
        src = summary
    if '"' in src and not re.search(r'"[^"]+"', src):
        src = '"' + src.lstrip('"')
    # An editor occasionally quotes a title that is already quoted and carries a
    # disambiguator: ""You Don't Know Me" (Cindy Walker song)" by Jann Arden.
    # The outer pair pushes the "by" clause out of reach of the title match, so
    # the song parses but the artist is silently lost. Unwrap it first.
    src = re.sub(r'""([^"]+)"\s*\([^)]*\)"', r'"\1"', src)
    pairs = []
    for m in re.finditer(r'"([^"]+)"(\s*by\s+([^/,"]+))?', src):
        title = m.group(1).strip()
        if title.lower().rstrip(":") in NOT_A_SONG:
            continue
        title = TYPO.get(title, title)
        artist = (m.group(3) or "").strip().rstrip(".;,")
        artist = re.sub(r"\s*\(.*?\)\s*$", "", artist).strip()
        pairs.append((title, artist))
    # "Beg" and "Put It On" by Q Parker: one credit covering both titles. Only
    # propagate when the titles are joined by "and" and exactly one credit was
    # found, on the last of them. A comma-separated list, or more than one
    # credit, means the wiki was naming them separately and guessing would be
    # worse than leaving a blank.
    if (len(pairs) > 1 and re.search(r'"\s+and\s+"', src)
            and sum(1 for _, a in pairs if a) == 1 and pairs[-1][1]):
        shared = pairs[-1][1]
        pairs = [(t, a or shared) for t, a in pairs]
    return pairs


CAMEO = re.compile(r"cameo?-?oke", re.I)
CAMEO_WHO = re.compile(r"cameo?-?oke(?:\s+guest)?[:\s]+(?:guest\s+)?([^;.]+)", re.I)
# "performed by X" = the guest sang it; "performed with X" = Kelly + guest duet
BY = re.compile(r"performed by\s+([^;.,(]+)", re.I)
WITH = re.compile(r"performed with\s+([^;.,(]+)", re.I)
RERUN = re.compile(r"\(rerun\)", re.I)


def tidy_name(s):
    s = re.sub(r"^(guest|:)\s*", "", s.strip(), flags=re.I)
    s = re.sub(r'^"[^"]*"\s*(by\s*)?', "", s).strip()
    s = re.sub(r"^cameo?-?oke\s*(guest)?[:\s]*", "", s, flags=re.I).strip()
    return s


rows = []
for season in range(1, 8):
    wt = json.load(open(os.path.join(S, f"s{season}.json")))["parse"]["wikitext"]
    for b in re.findall(r"\{\{Episode list(.*?)\n\}\}", wt, flags=re.S):
        f_ = fields(b)
        iso, pretty = parse_date(f_.get("originalairdate", ""))
        aux_full = clean(f_.get("aux4", ""), keep_small=True)
        aux = clean(f_.get("aux4", ""))
        summary = clean(f_.get("shortsummary", ""), keep_small=True)

        vm = re.search(r"\{\{\s*small\s*\|\s*\(?(.*?)\)?\s*\}\}",
                       unlink(strip_refs(f_.get("aux4", ""))), re.I | re.S)
        version = re.sub(r"\s+", " ", vm.group(1)).strip() if vm else ""

        blob = aux_full + " " + summary
        performer, is_guest = "", False
        if CAMEO.search(blob):
            is_guest = True
            m = CAMEO_WHO.search(summary) or CAMEO_WHO.search(aux_full)
            if m:
                performer = tidy_name(m.group(1))
        bm = BY.search(summary)
        if bm and "kelly" not in bm.group(1).lower():
            is_guest = True
            performer = performer or tidy_name(bm.group(1))
        wm = WITH.search(summary)
        duet = wm.group(1).strip() if wm else ""

        rows.append({
            "season": season,
            "ep_overall": clean(f_.get("episodenumber", "")).replace(",", ""),
            "ep_in_season": clean(f_.get("episodenumber2", "")),
            "date_iso": iso, "date_pretty": pretty,
            "aux_raw": aux, "version": version, "summary": summary,
            "guests": clean(f_.get("guests", "")),
            "cameo": is_guest, "performer": performer,
            "duet": duet, "rerun": bool(RERUN.search(blob)),
            "songs": split_songs(aux, summary),
        })

json.dump(rows, open(os.path.join(S, "episodes.json"), "w"), indent=1)

n = sum(len(r["songs"]) for r in rows)
g = sum(len(r["songs"]) for r in rows if r["cameo"])
print(f"episodes {len(rows)}  song entries {n}")
print(f"  sung by Kelly     : {n-g}")
print(f"  sung by a guest   : {g}  across {sum(1 for r in rows if r['cameo'])} episodes")
print(f"  duets (Kelly+guest): {sum(1 for r in rows if r['duet'] and not r['cameo'])}")
print(f"  reruns            : {sum(1 for r in rows if r['rerun'])}")
print(f"  markup leaks      : {sum(1 for r in rows for s,a in r['songs'] if re.search(r'\{\{|\}\}|\[\[|<', s+a))}")
print("\nnewly reclassified as guest-sung:")
for r in rows:
    if r["cameo"] and not CAMEO.search(r["aux_raw"] + " " + r["summary"]):
        print(f'   {r["date_iso"]} {r["songs"]} -> {r["performer"]!r}')
