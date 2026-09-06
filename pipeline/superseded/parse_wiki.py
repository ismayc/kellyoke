#!/usr/bin/env python3
"""Parse Kellyoke performances out of the Wikipedia season wikitext."""
import json, re, os, sys

S = os.path.dirname(os.path.abspath(__file__))

MONTHS = ["January","February","March","April","May","June","July","August",
          "September","October","November","December"]


def strip_refs(t):
    # drop <ref>...</ref> and <ref .../>
    t = re.sub(r"<ref[^>]*/>", "", t)
    t = re.sub(r"<ref.*?</ref>", "", t, flags=re.S)
    t = re.sub(r"<!--.*?-->", "", t, flags=re.S)
    return t


def unlink(t):
    """Resolve [[target|display]] -> display, [[target]] -> target."""
    t = re.sub(r"\[\[([^\[\]|]*)\|([^\[\]]*)\]\]", r"\2", t)
    t = re.sub(r"\[\[([^\[\]]*)\]\]", r"\1", t)
    return t


def clean(t):
    t = strip_refs(t)
    t = unlink(t)
    # {{abbr|N/A|Not applicable}} -> N/A ; {{TableTBA|N/A}} -> N/A
    t = re.sub(r"\{\{abbr\|([^|}]*)\|[^}]*\}\}", r"\1", t, flags=re.I)
    t = re.sub(r"\{\{TableTBA\|([^}]*)\}\}", r"\1", t, flags=re.I)
    t = re.sub(r"\{\{TableTBA\}\}", "TBA", t, flags=re.I)
    t = re.sub(r"</?small>", "", t)
    t = re.sub(r"<br\s*/?>", " ", t, flags=re.I)
    t = re.sub(r"\{\{'-\}\}", "'", t)          # {{'-}} -> apostrophe
    t = re.sub(r"\{\{'\}\}", "'", t)
    t = re.sub(r"'''?", "", t)
    t = re.sub(r"&nbsp;", " ", t)
    # normalize smart/curly quotes to straight double quotes
    t = t.replace("\u201c", '"').replace("\u201d", '"')
    t = t.replace("\u2018", "'").replace("\u2019", "'")
    t = re.sub(r"\s+", " ", t)
    return t.strip()


def parse_date(raw):
    m = re.search(r"\{\{\s*Start date\s*\|\s*(\d{4})\s*\|\s*(\d{1,2})\s*\|\s*(\d{1,2})", raw, re.I)
    if m:
        y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
        return f"{y:04d}-{mo:02d}-{d:02d}", f"{MONTHS[mo-1]} {d}, {y}"
    # fallback: plain "September 9, 2019"
    m = re.search(r"(" + "|".join(MONTHS) + r")\s+(\d{1,2}),\s*(\d{4})", clean(raw))
    if m:
        mo = MONTHS.index(m.group(1)) + 1
        return f"{int(m.group(3)):04d}-{mo:02d}-{int(m.group(2)):02d}", m.group(0)
    return None, clean(raw)


def fields(block):
    """Split an {{Episode list ...}} block into its named parameters."""
    out, depth, key, buf = {}, 0, None, []
    i = 0
    while i < len(block):
        c = block[i]
        nxt2 = block[i:i+2]
        if nxt2 in ("{{", "[["):
            depth += 1; buf.append(nxt2); i += 2; continue
        if nxt2 in ("}}", "]]"):
            depth -= 1; buf.append(nxt2); i += 2; continue
        if c == "|" and depth == 0:
            if key:
                out[key.strip().lower()] = "".join(buf).strip()
            rest = block[i+1:]
            m = re.match(r"\s*([A-Za-z0-9_]+)\s*=", rest)
            if m:
                key = m.group(1); buf = []
                i += 1 + m.end(); continue
            buf.append(c); i += 1; continue
        buf.append(c); i += 1
    if key:
        out[key.strip().lower()] = "".join(buf).strip()
    return out


SONG_RE = re.compile(r'"([^"]+)"\s*(?:by\s+(.*?))?(?=$|\s*/\s*"|,\s*"|\s+and\s+")', re.I)


def split_songs(aux, summary=""):
    """Return list of (title, artist) pairs found in the Aux4 / summary text."""
    src = aux
    # a medley/label with no quoted song: fall back to summary which lists them
    if '"' not in aux and '"' in summary:
        src = summary
    pairs = []
    if '"' in src and not re.search(r'"[^"]+"', src):
        # unbalanced single stray quote, e.g. 'Umbrella" by Rihanna (Rerun)'
        src = '"' + src.lstrip('"')
    pairs = []
    for m in re.finditer(r'"([^"]+)"(\s*by\s+([^/,"]+))?', src):
        title = m.group(1).strip()
        artist = (m.group(3) or "").strip().rstrip(".;,")
        artist = re.sub(r"\s*\(.*?\)\s*$", "", artist).strip()
        pairs.append((title, artist))
    return pairs


rows = []
for season in range(1, 8):
    with open(os.path.join(S, f"s{season}.json")) as f:
        wt = json.load(f)["parse"]["wikitext"]
    blocks = re.findall(r"\{\{Episode list(.*?)\n\}\}", wt, flags=re.S)
    for b in blocks:
        f_ = fields(b)
        iso, pretty = parse_date(f_.get("originalairdate", ""))
        aux_raw = f_.get("aux4", "")
        aux = clean(aux_raw)
        summary = clean(f_.get("shortsummary", ""))
        guests = clean(f_.get("guests", ""))
        mguests = clean(f_.get("musicalguests", ""))
        rows.append({
            "season": season,
            "ep_overall": clean(f_.get("episodenumber", "")).replace(",", ""),
            "ep_in_season": clean(f_.get("episodenumber2", "")),
            "date_iso": iso,
            "date_pretty": pretty,
            "aux_raw": aux,
            "summary": summary,
            "guests": guests,
            "musical_guests": mguests,
            "songs": split_songs(aux, summary),
        })

with open(os.path.join(S, "episodes.json"), "w") as f:
    json.dump(rows, f, indent=1)

print(f"episodes parsed: {len(rows)}")
print(f"with a date:     {sum(1 for r in rows if r['date_iso'])}")
print(f"with >=1 song:   {sum(1 for r in rows if r['songs'])}")
print(f"no song parsed:  {sum(1 for r in rows if not r['songs'])}")
print("\nper season:")
for s in range(1, 8):
    sub = [r for r in rows if r["season"] == s]
    print(f"  S{s}: {len(sub):3d} eps, {sum(len(r['songs']) for r in sub):3d} songs, "
          f"{sum(1 for r in sub if not r['songs']):3d} without a parsed song")
print("\nsample of unparsed Aux4 values:")
seen = set()
for r in rows:
    if not r["songs"] and r["aux_raw"] not in seen:
        seen.add(r["aux_raw"])
        print(f"  S{r['season']} {r['date_iso']}: {r['aux_raw'][:100]!r}")
    if len(seen) > 25:
        break
