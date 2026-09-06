#!/usr/bin/env python3
"""Parse Kellyoke performances from the Wikipedia season wikitext.

v2 adds: {{small|...}} version notes, Cameo-oke / duet / rerun classification,
and suppression of medley *labels* that are not themselves songs.
"""
import json, re, os

S = os.path.dirname(os.path.abspath(__file__))
MONTHS = ["January","February","March","April","May","June","July","August",
          "September","October","November","December"]


def strip_refs(t):
    t = re.sub(r"<ref[^>]*/>", "", t)
    t = re.sub(r"<ref.*?</ref>", "", t, flags=re.S)
    t = re.sub(r"<!--.*?-->", "", t, flags=re.S)
    return t


def unlink(t):
    t = re.sub(r"\[\[([^\[\]|]*)\|([^\[\]]*)\]\]", r"\2", t)
    t = re.sub(r"\[\[([^\[\]]*)\]\]", r"\1", t)
    return t


def clean(t, keep_small=False):
    t = strip_refs(t)
    t = unlink(t)
    t = re.sub(r"\{\{abbr\|([^|}]*)\|[^}]*\}\}", r"\1", t, flags=re.I)
    t = re.sub(r"\{\{TableTBA\|([^}]*)\}\}", r"\1", t, flags=re.I)
    t = re.sub(r"\{\{TableTBA\}\}", "TBA", t, flags=re.I)
    # {{small|(Reba McEntire version)}} -> keep or drop the inner text
    if keep_small:
        t = re.sub(r"\{\{\s*small\s*\|(.*?)\}\}", r"\1", t, flags=re.I | re.S)
    else:
        t = re.sub(r"\{\{\s*small\s*\|.*?\}\}", " ", t, flags=re.I | re.S)
    t = re.sub(r"\{\{'-\}\}", "'", t)
    t = re.sub(r"\{\{'\}\}", "'", t)
    t = re.sub(r"\{\{[^{}]*\}\}", " ", t)          # any leftover template
    t = re.sub(r"</?small>", "", t)
    t = re.sub(r"<br\s*/?>", " ", t, flags=re.I)
    t = re.sub(r"<[^>]+>", " ", t)
    t = re.sub(r"'''?", "", t)
    t = re.sub(r"&nbsp;", " ", t)
    t = t.replace("“", '"').replace("”", '"')
    t = t.replace("‘", "'").replace("’", "'")
    t = re.sub(r"\s+", " ", t)
    return t.strip()


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


# Quoted strings that are segment labels rather than song titles.
NOT_A_SONG = {"by request hour"}


def split_songs(aux, summary=""):
    src = aux
    if '"' not in aux and '"' in summary:
        src = summary
    if '"' in src and not re.search(r'"[^"]+"', src):
        src = '"' + src.lstrip('"')
    pairs = []
    for m in re.finditer(r'"([^"]+)"(\s*by\s+([^/,"]+))?', src):
        title = m.group(1).strip()
        if title.lower().rstrip(":") in NOT_A_SONG:
            continue
        artist = (m.group(3) or "").strip().rstrip(".;,")
        artist = re.sub(r"\s*\(.*?\)\s*$", "", artist).strip()
        pairs.append((title, artist))
    return pairs


CAMEO_RE = re.compile(r"cameo-?oke", re.I)
CAMEO_WHO = re.compile(r"cameo-?oke(?:\s+guest)?[:\s]+(?:guest\s+)?([^;.]+)", re.I)
DUET_RE = re.compile(r"performed with ([^;.(]+)", re.I)
RERUN_RE = re.compile(r"\(rerun\)", re.I)

rows = []
for season in range(1, 8):
    wt = json.load(open(os.path.join(S, f"s{season}.json")))["parse"]["wikitext"]
    for b in re.findall(r"\{\{Episode list(.*?)\n\}\}", wt, flags=re.S):
        f_ = fields(b)
        iso, pretty = parse_date(f_.get("originalairdate", ""))
        aux_full = clean(f_.get("aux4", ""), keep_small=True)
        aux = clean(f_.get("aux4", ""))
        summary = clean(f_.get("shortsummary", ""), keep_small=True)

        # "(Reba McEntire version)" style note describing the arrangement covered
        vm = re.search(r"\{\{\s*small\s*\|\s*\(?(.*?)\)?\s*\}\}",
                       strip_refs(unlink(f_.get("aux4", ""))), re.I | re.S)
        version = re.sub(r"\s+", " ", vm.group(1)).strip() if vm else ""

        blob = aux_full + " " + summary
        is_cameo = bool(CAMEO_RE.search(blob))
        performer = ""
        if is_cameo:
            m = CAMEO_WHO.search(summary) or CAMEO_WHO.search(aux_full)
            if m:
                performer = re.sub(r"^(guest|:)\s*", "", m.group(1).strip(), flags=re.I)
                performer = re.sub(r'^"[^"]*"\s*(by\s*)?', "", performer).strip()
        dm = DUET_RE.search(summary)
        duet = dm.group(1).strip() if dm else ""
        rerun = bool(RERUN_RE.search(blob))

        rows.append({
            "season": season,
            "ep_overall": clean(f_.get("episodenumber", "")).replace(",", ""),
            "ep_in_season": clean(f_.get("episodenumber2", "")),
            "date_iso": iso, "date_pretty": pretty,
            "aux_raw": aux, "version": version, "summary": summary,
            "guests": clean(f_.get("guests", "")),
            "cameo": is_cameo, "performer": performer,
            "duet": duet, "rerun": rerun,
            "songs": split_songs(aux, summary),
        })

json.dump(rows, open(os.path.join(S, "episodes.json"), "w"), indent=1)

nsong = sum(len(r["songs"]) for r in rows)
ncam = sum(len(r["songs"]) for r in rows if r["cameo"])
print(f"episodes {len(rows)}   song entries {nsong}")
print(f"  Kelly performances : {nsong - ncam}")
print(f"  Cameo-oke (guest)  : {ncam}   across {sum(1 for r in rows if r['cameo'])} episodes")
print(f"  duets              : {sum(1 for r in rows if r['duet'])}")
print(f"  reruns             : {sum(1 for r in rows if r['rerun'])}")
print(f"  version notes      : {sum(1 for r in rows if r['version'])}")
print(f"  no song parsed     : {sum(1 for r in rows if not r['songs'])}")
print("\nmarkup leaks remaining:",
      sum(1 for r in rows for s, a in r["songs"] if re.search(r"\{\{|\}\}|\[\[|<", s + a)))
print("\nsample cameo rows:")
for r in [r for r in rows if r["cameo"]][:6]:
    print(f'  {r["date_iso"]} {r["songs"]} performer={r["performer"]!r}')
print("\nsample version notes:")
for r in [r for r in rows if r["version"]][:6]:
    print(f'  {r["date_iso"]} {r["songs"][0] if r["songs"] else None} version={r["version"]!r}')
