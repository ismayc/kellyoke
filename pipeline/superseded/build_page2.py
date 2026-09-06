#!/usr/bin/env python3
"""Build the Kellyoke Archive page from matched.json (v2)."""
import json, os, re, html, unicodedata, collections

S = os.path.dirname(os.path.abspath(__file__))
rows = json.load(open(os.path.join(S, "matched.json")))

SEASON_COLOR = {1: "#FF52AF", 2: "#61CEBA", 3: "#7600ED", 4: "#FF6929",
                5: "#FCD959", 6: "#1DD9FC", 7: "#B60006"}
MONTHS = ["January","February","March","April","May","June","July","August",
          "September","October","November","December"]
e = lambda t: html.escape(t or "", quote=True)


def searchkey(*parts):
    t = " ".join(p for p in parts if p).lower()
    t = unicodedata.normalize("NFKD", t)
    t = "".join(c for c in t if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9 ]+", " ", t)).strip()


def fmt_dur(d):
    return f"{int(d)//60}:{int(d)%60:02d}" if d else ""


allp = [(r, p) for r in rows if r["perfs"] for p in r["perfs"]]
kelly = [(r, p) for r, p in allp if not r["cameo"]]
guest = [(r, p) for r, p in allp if r["cameo"]]
n_kelly, n_guest = len(kelly), len(guest)
n_play = sum(1 for _, p in kelly if p["video_id"])
n_songs = len({p["song"].lower() for _, p in kelly})
n_eps = len(rows)

SRC_KEY = {
    "The Kelly Clarkson Show (official)": ("official", "Official"),
    "KC Videos archive": ("archive", "Archive"),
    "Courtney O'shea archive": ("archive", "Archive"),
    "Xavier Del Cid archive": ("archive", "Archive"),
    "Other upload": ("other", "Other"),
    "Weekly recap": ("recap", "In recap"),
}

sections = []
by_season = collections.OrderedDict()
for r in rows:
    by_season.setdefault(r["season"], []).append(r)

for season, eps in by_season.items():
    color = SEASON_COLOR[season]
    s_k = sum(1 for r in eps for p in r["perfs"] if not r["cameo"])
    s_v = sum(1 for r in eps for p in r["perfs"] if not r["cameo"] and p["video_id"])
    months = collections.OrderedDict()
    for ep in eps:
        y, m, _ = ep["date_iso"].split("-")
        months.setdefault(f"{MONTHS[int(m)-1]} {y}", []).append(ep)

    mparts = []
    for mlabel, meps in months.items():
        rp = []
        for ep in meps:
            y, m, d = (int(x) for x in ep["date_iso"].split("-"))
            datelabel = f"{MONTHS[m-1][:3]} {d}"
            if not ep["perfs"]:
                rp.append(
                    f'<div class="row row--none" data-s="{e(searchkey(ep["aux_raw"], ep["date_iso"]))}" '
                    f'data-season="{season}" data-vid="0" data-cameo="0">'
                    f'<div class="cell-date"><span class="d">{datelabel}</span><span class="y">{y}</span></div>'
                    f'<div class="cell-song"><span class="nosong">No Kellyoke this episode</span></div>'
                    f'<div class="cell-meta"><span class="ep">Ep&nbsp;{e(ep["ep_overall"])}</span></div>'
                    f'<div class="cell-act"></div></div>')
                continue
            for p in ep["perfs"]:
                cameo = ep["cameo"]
                classic = (not cameo) and "kelly clarkson" in (p["artist"] or "").lower()
                vid = p["video_id"]
                if vid:
                    key, label = SRC_KEY.get(p["source"], ("archive", "Archive"))
                    dur = fmt_dur(p["duration"])
                    act = (f'<a class="watch" href="https://www.youtube.com/watch?v={vid}" '
                           f'target="_blank" rel="noopener noreferrer">'
                           f'<span class="tri" aria-hidden="true"></span>Watch'
                           f'{f"<span class=dur>{dur}</span>" if dur else ""}</a>')
                    badge = f'<span class="src src--{key}">{label}</span>'
                else:
                    q = re.sub(r"\s+", "+", searchkey(
                        f"Kelly Clarkson Kellyoke {p['song']} {p['artist']}"))
                    act = (f'<a class="watch watch--search" '
                           f'href="https://www.youtube.com/results?search_query={q}" '
                           f'target="_blank" rel="noopener noreferrer">Search</a>')
                    badge = '<span class="src src--none">No copy found</span>'

                tags = ""
                if cameo:
                    who = f" &middot; {e(ep['performer'])}" if ep["performer"] else ""
                    tags += f'<span class="tag tag--cameo">Cameo-oke{who}</span>'
                if classic:
                    tags += '<span class="tag tag--classic">Kellyoke Classic</span>'
                duet = p.get("duet") or ep["duet"]
                if duet and not cameo:
                    tags += f'<span class="tag tag--duet">with {e(duet)}</span>'
                if p.get("genre") and p["genre"] != "Not listed":
                    tags += f'<span class="tag tag--genre">{e(p["genre"])}</span>'
                if ep["version"]:
                    tags += f'<span class="tag tag--ver">{e(ep["version"])}</span>'
                if ep["rerun"]:
                    tags += '<span class="tag tag--rerun">Rerun</span>'
                if p.get("note"):
                    tags += f'<span class="tag tag--note">{e(p["note"])}</span>'

                # make the row facets searchable too ("cameo", "duet", "classic", "rerun")
                facets = " ".join(f for f, on in (
                    ("cameooke cameo guest", cameo),
                    ("kellyoke classic", classic),
                    ("duet with " + (p.get("duet") or ep["duet"] or ""),
                     bool(p.get("duet") or ep["duet"]) and not cameo),
                    (p.get("genre","") if p.get("genre")!="Not listed" else "",
                     bool(p.get("genre")) and p.get("genre")!="Not listed"),
                    ("rerun", ep["rerun"]),
                    (ep["version"], bool(ep["version"])),
                ) if on)
                artist = e(p["artist"]) or "&mdash;"
                rp.append(
                    f'<div class="row{" row--cameo" if cameo else ""}" '
                    f'data-s="{e(searchkey(p["song"], p["artist"], ep["date_iso"], mlabel, ep["performer"], facets))}" '
                    f'data-season="{season}" data-vid="{1 if vid else 0}" '
                    f'data-cameo="{1 if cameo else 0}">'
                    f'<div class="cell-date"><span class="d">{datelabel}</span><span class="y">{y}</span></div>'
                    f'<div class="cell-song"><span class="song">{e(p["song"])}</span>'
                    f'<span class="artist">{artist}</span>'
                    f'{f"<span class=tags>{tags}</span>" if tags else ""}</div>'
                    f'<div class="cell-meta">{badge}<span class="ep">Ep&nbsp;{e(ep["ep_overall"])}</span></div>'
                    f'<div class="cell-act">{act}</div></div>')
        mparts.append(f'<div class="month"><h3 class="month-h">{e(mlabel)}</h3>'
                      f'<div class="rows">{"".join(rp)}</div></div>')

    sections.append(
        f'<section class="season" id="s{season}" data-season="{season}" style="--sc:{color}">'
        f'<header class="season-h"><div class="season-n">S{season}</div>'
        f'<div class="season-t"><h2>Season&nbsp;{season}</h2>'
        f'<p>{eps[0]["date_pretty"]} &ndash; {eps[-1]["date_pretty"]}</p></div>'
        f'<div class="season-k"><b>{s_k}</b><span>Kelly covers</span></div>'
        f'<div class="season-k"><b>{s_v}</b><span>with video</span></div>'
        f'</header>{"".join(mparts)}</section>')

chips = "".join(f'<button class="chip" data-f="{s}" style="--sc:{SEASON_COLOR[s]}" '
                f'aria-pressed="false"><i></i>S{s}</button>' for s in by_season)

top = collections.Counter(p["artist"] for _, p in kelly if p["artist"]
                          and "kelly clarkson" not in p["artist"].lower()).most_common(10)
artist_list = "".join(f'<li><span class="an">{e(a)}</span><span class="ac">{c}</span></li>'
                      for a, c in top)
n_classic = sum(1 for _, p in kelly if "kelly clarkson" in (p["artist"] or "").lower())

PL = json.load(open(os.path.join(S, "playlists.json")))
n_uniq = sum(p["n"] for p in PL["all"])
pl_rows = ""
for s_, parts in PL["seasons"].items():
    links = "".join(
        f'<a class="pl" href="{p["url"]}" target="_blank" rel="noopener noreferrer">'
        f'<b>{p["part"]}</b><span>{p["n"]}</span></a>' for p in parts)
    pl_rows += (f'<div class="pl-row" style="--sc:{SEASON_COLOR[int(s_)]}">'
                f'<div class="pl-lab">Season&nbsp;{s_}'
                f'<em>{sum(p["n"] for p in parts)} videos</em></div>'
                f'<div class="pl-links">{links}</div></div>')
pl_all = "".join(
    f'<a class="pl pl--sm" href="{p["url"]}" target="_blank" rel="noopener noreferrer">'
    f'<b>{p["part"]}</b><span>{p["n"]}</span></a>' for p in PL["all"])
n_shared = 351

HTML = f"""<meta charset="utf-8">
<title>The Kellyoke Archive</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Bricolage+Grotesque:opsz,wght@12..96,400;12..96,600;12..96,800&family=Instrument+Sans:wght@400;500;600&family=JetBrains+Mono:wght@400;600&display=swap">
<style>
:root {{
  --bg:#F4F3F7; --surface:#FFFFFF; --surface-2:#EDEBF2; --line:#DCD8E4;
  --line-soft:#E8E5EE; --ink:#191622; --ink-2:#514B63; --ink-3:#7B7490;
  --accent:#7600ED; --accent-ink:#FFFFFF; --good:#0F7B5F; --warm:#B4531A;
  --shadow:0 1px 2px rgba(25,22,34,.06); --radius:9px;
}}
@media (prefers-color-scheme: dark) {{
  :root:not([data-theme="light"]) {{
    --bg:#131019; --surface:#1B1724; --surface-2:#241F30; --line:#332C42;
    --line-soft:#272134; --ink:#F2EFF7; --ink-2:#B4ACC6; --ink-3:#857D99;
    --accent:#B98BFF; --accent-ink:#1A1424; --good:#5FD9B4; --warm:#F0A56B; --shadow:none;
  }}
}}
:root[data-theme="dark"] {{
  --bg:#131019; --surface:#1B1724; --surface-2:#241F30; --line:#332C42;
  --line-soft:#272134; --ink:#F2EFF7; --ink-2:#B4ACC6; --ink-3:#857D99;
  --accent:#B98BFF; --accent-ink:#1A1424; --good:#5FD9B4; --warm:#F0A56B; --shadow:none;
}}
*,*::before,*::after {{ box-sizing:border-box; }}
body {{ margin:0; background:var(--bg); color:var(--ink);
  font-family:"Instrument Sans",ui-sans-serif,system-ui,-apple-system,sans-serif;
  font-size:15px; line-height:1.5; -webkit-font-smoothing:antialiased; }}
a {{ color:inherit; }}
:focus-visible {{ outline:2px solid var(--accent); outline-offset:2px; border-radius:4px; }}
.wrap {{ max-width:1080px; margin:0 auto; padding:0 20px; }}

.mast {{ padding:44px 0 20px; }}
.eyebrow {{ font-family:"JetBrains Mono",monospace; font-size:11px; letter-spacing:.14em;
  text-transform:uppercase; color:var(--ink-3); margin:0 0 14px; }}
h1 {{ font-family:"Bricolage Grotesque",sans-serif; font-weight:800;
  font-size:clamp(40px,7.5vw,76px); line-height:.95; letter-spacing:-.025em;
  margin:0 0 14px; text-wrap:balance; }}
h1 .spark {{ display:inline-block;
  background:linear-gradient(92deg,#FF52AF,#7600ED 34%,#1DD9FC 68%,#FF6929);
  -webkit-background-clip:text; background-clip:text; color:transparent; }}
.lede {{ max-width:62ch; color:var(--ink-2); font-size:16.5px; margin:0 0 26px; }}
.lede b {{ color:var(--ink); font-weight:600; }}
.stats {{ display:flex; flex-wrap:wrap; gap:10px; margin:0; padding:0; list-style:none; }}
.stats li {{ background:var(--surface); border:1px solid var(--line);
  border-radius:var(--radius); padding:10px 14px; min-width:104px; box-shadow:var(--shadow); }}
.stats b {{ display:block; font-family:"JetBrains Mono",monospace; font-weight:600;
  font-size:21px; letter-spacing:-.02em; font-variant-numeric:tabular-nums; }}
.stats span {{ font-size:11.5px; color:var(--ink-3); letter-spacing:.05em; text-transform:uppercase; }}

.controls {{ position:sticky; top:0; z-index:20; background:var(--bg);
  border-bottom:1px solid var(--line); padding:12px 0; margin-bottom:8px; }}
.cbar {{ display:flex; flex-wrap:wrap; gap:10px; align-items:center; }}
.search {{ position:relative; flex:1 1 240px; min-width:190px; }}
.search input {{ width:100%; font:inherit; color:var(--ink); background:var(--surface);
  border:1px solid var(--line); border-radius:var(--radius); padding:9px 12px 9px 34px; }}
.search input::placeholder {{ color:var(--ink-3); }}
.search svg {{ position:absolute; left:11px; top:50%; transform:translateY(-50%); color:var(--ink-3); }}
.chips {{ display:flex; flex-wrap:wrap; gap:6px; }}
.chip {{ font:inherit; font-size:13px; font-weight:500; cursor:pointer; color:var(--ink-2);
  background:var(--surface); border:1px solid var(--line); border-radius:99px;
  padding:7px 12px; display:inline-flex; align-items:center; gap:6px; }}
.chip i {{ width:8px; height:8px; border-radius:50%; background:var(--sc); display:block; }}
.chip[aria-pressed="true"] {{ background:var(--ink); color:var(--bg); border-color:var(--ink); }}
.toggle {{ font:inherit; font-size:13px; font-weight:500; cursor:pointer; color:var(--ink-2);
  background:var(--surface); border:1px solid var(--line); border-radius:var(--radius); padding:7px 12px; }}
.toggle[aria-pressed="true"] {{ background:var(--ink); color:var(--bg); border-color:var(--ink); }}
.count {{ font-family:"JetBrains Mono",monospace; font-size:12px; color:var(--ink-3);
  padding:8px 0 0; font-variant-numeric:tabular-nums; }}

.season {{ margin:34px 0 0; }}
.season-h {{ display:flex; align-items:center; gap:14px; padding:14px 16px;
  background:var(--surface); border:1px solid var(--line); border-left:5px solid var(--sc);
  border-radius:var(--radius); box-shadow:var(--shadow); }}
.season-n {{ font-family:"Bricolage Grotesque",sans-serif; font-weight:800; font-size:26px;
  letter-spacing:-.03em; color:var(--sc); min-width:44px; }}
.season-t {{ flex:1 1 200px; }}
.season-t h2 {{ font-family:"Bricolage Grotesque",sans-serif; font-weight:600; font-size:19px;
  margin:0; letter-spacing:-.015em; }}
.season-t p {{ margin:1px 0 0; font-size:12.5px; color:var(--ink-3); font-family:"JetBrains Mono",monospace; }}
.season-k {{ text-align:right; min-width:82px; }}
.season-k b {{ display:block; font-family:"JetBrains Mono",monospace; font-weight:600;
  font-size:16px; font-variant-numeric:tabular-nums; }}
.season-k span {{ font-size:10.5px; color:var(--ink-3); text-transform:uppercase; letter-spacing:.05em; }}
.month {{ margin:18px 0 0; }}
.month-h {{ font-family:"JetBrains Mono",monospace; font-size:11px; font-weight:600;
  letter-spacing:.13em; text-transform:uppercase; color:var(--ink-3); margin:0 0 6px; padding-left:2px; }}
.rows {{ display:flex; flex-direction:column; gap:3px; }}

.row {{ display:grid; grid-template-columns:58px minmax(0,1fr) auto auto; gap:14px;
  align-items:center; background:var(--surface); border:1px solid var(--line-soft);
  border-radius:var(--radius); padding:9px 13px; }}
.row:hover {{ border-color:var(--line); background:var(--surface-2); }}
.row--cameo {{ background:transparent; border-style:dashed; }}
.row--cameo:hover {{ background:var(--surface-2); }}
.cell-date {{ font-family:"JetBrains Mono",monospace; font-variant-numeric:tabular-nums; line-height:1.15; }}
.cell-date .d {{ display:block; font-size:13px; font-weight:600; }}
.cell-date .y {{ display:block; font-size:10.5px; color:var(--ink-3); }}
.cell-song {{ min-width:0; }}
.cell-song .song {{ font-family:"Bricolage Grotesque",sans-serif; font-weight:600;
  font-size:16px; letter-spacing:-.012em; display:block; overflow-wrap:anywhere; }}
.cell-song .artist {{ font-size:13px; color:var(--ink-2); display:block; overflow-wrap:anywhere; }}
.cell-song .nosong {{ color:var(--ink-3); font-style:italic; }}
.tags {{ display:flex; flex-wrap:wrap; gap:4px; margin-top:4px; }}
.tag {{ font-size:10px; font-weight:600; letter-spacing:.05em; text-transform:uppercase;
  border-radius:99px; padding:1px 7px; white-space:nowrap; }}
.tag--classic {{ color:var(--accent); border:1px solid color-mix(in srgb,var(--accent) 38%,transparent); }}
.tag--cameo {{ color:var(--warm); border:1px solid color-mix(in srgb,var(--warm) 42%,transparent); text-transform:none; }}
.tag--duet, .tag--ver, .tag--note {{ color:var(--ink-3); border:1px solid var(--line); text-transform:none; font-weight:500; }}
.tag--genre {{ color:var(--ink-2); border:1px solid var(--line);
  text-transform:none; letter-spacing:0; font-weight:500; }}
.tag--rerun {{ color:var(--ink-3); border:1px dashed var(--line); }}
.cell-meta {{ display:flex; flex-direction:column; align-items:flex-end; gap:3px; }}
.src {{ font-size:10px; font-weight:600; letter-spacing:.06em; text-transform:uppercase;
  padding:2px 7px; border-radius:99px; white-space:nowrap; }}
.src--official {{ color:var(--good); border:1px solid color-mix(in srgb,var(--good) 40%,transparent); }}
.src--archive, .src--other, .src--recap {{ color:var(--ink-3); border:1px solid var(--line); }}
.src--none {{ color:var(--ink-3); border:1px dashed var(--line); }}
.ep {{ font-family:"JetBrains Mono",monospace; font-size:10.5px; color:var(--ink-3);
  font-variant-numeric:tabular-nums; }}
.watch {{ display:inline-flex; align-items:center; gap:7px; text-decoration:none;
  font-size:13px; font-weight:600; white-space:nowrap; background:var(--ink); color:var(--bg);
  border-radius:99px; padding:7px 14px; }}
.watch:hover {{ background:var(--accent); color:var(--accent-ink); }}
.watch .tri {{ width:0; height:0; border-left:7px solid currentColor;
  border-top:4.5px solid transparent; border-bottom:4.5px solid transparent; }}
.watch .dur {{ font-family:"JetBrains Mono",monospace; font-size:11px; opacity:.72; font-weight:400; }}
.watch--search {{ background:transparent; color:var(--ink-2); border:1px dashed var(--line); }}
.watch--search:hover {{ background:var(--surface-2); color:var(--ink); }}
.playlists {{ margin:44px 0 0; padding:22px; background:var(--surface);
  border:1px solid var(--line); border-radius:var(--radius); box-shadow:var(--shadow); }}
.playlists h2 {{ font-family:"Bricolage Grotesque",sans-serif; font-weight:600;
  font-size:20px; margin:0 0 6px; letter-spacing:-.015em; }}
.playlists .sub {{ color:var(--ink-2); font-size:14px; margin:0 0 18px; max-width:66ch; }}
.pl-row {{ display:flex; flex-wrap:wrap; align-items:center; gap:12px;
  padding:9px 0; border-top:1px solid var(--line-soft); }}
.pl-row:first-of-type {{ border-top:0; }}
.pl-lab {{ flex:0 0 150px; font-weight:600; font-size:14px;
  border-left:3px solid var(--sc); padding-left:10px; }}
.pl-lab em {{ display:block; font-style:normal; font-weight:400; font-size:11.5px;
  color:var(--ink-3); font-family:"JetBrains Mono",monospace; }}
.pl-links {{ display:flex; flex-wrap:wrap; gap:6px; }}
.pl {{ display:inline-flex; align-items:baseline; gap:6px; text-decoration:none;
  border:1px solid var(--line); border-radius:99px; padding:6px 13px;
  background:var(--surface-2); }}
.pl:hover {{ background:var(--ink); color:var(--bg); border-color:var(--ink); }}
.pl b {{ font-family:"Bricolage Grotesque",sans-serif; font-size:14px; font-weight:600; }}
.pl span {{ font-family:"JetBrains Mono",monospace; font-size:10.5px; color:var(--ink-3); }}
.pl:hover span {{ color:inherit; opacity:.75; }}
.pl--sm {{ padding:5px 10px; }}
.pl-all {{ margin-top:16px; padding-top:14px; border-top:1px solid var(--line); }}
.pl-all h3 {{ font-family:"JetBrains Mono",monospace; font-size:11px; font-weight:600;
  letter-spacing:.13em; text-transform:uppercase; color:var(--ink-3); margin:0 0 8px; }}
.hidden {{ display:none !important; }}
.empty {{ padding:40px 4px; color:var(--ink-3); }}

.notes {{ margin:52px 0 60px; padding-top:26px; border-top:1px solid var(--line); }}
.notes h2 {{ font-family:"Bricolage Grotesque",sans-serif; font-weight:600; font-size:20px;
  margin:0 0 16px; letter-spacing:-.015em; }}
.grid2 {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(258px,1fr)); gap:26px; }}
.notes p {{ color:var(--ink-2); font-size:14px; max-width:62ch; }}
.notes h3 {{ font-family:"JetBrains Mono",monospace; font-size:11px; font-weight:600;
  letter-spacing:.13em; text-transform:uppercase; color:var(--ink-3); margin:0 0 8px; }}
.notes ul {{ padding-left:18px; color:var(--ink-2); font-size:14px; }}
.notes li {{ margin-bottom:6px; }}
.alist {{ list-style:none; padding:0; margin:0; }}
.alist li {{ display:flex; justify-content:space-between; gap:12px; padding:5px 0;
  border-bottom:1px solid var(--line-soft); font-size:14px; }}
.alist .ac {{ font-family:"JetBrains Mono",monospace; color:var(--ink-3); font-variant-numeric:tabular-nums; }}

@media (max-width:640px) {{
  .row {{ grid-template-columns:50px minmax(0,1fr); grid-template-areas:"date song" ". meta" ". act"; row-gap:7px; }}
  .cell-date {{ grid-area:date; }} .cell-song {{ grid-area:song; }}
  .cell-meta {{ grid-area:meta; flex-direction:row; align-items:center; justify-content:flex-start; gap:8px; }}
  .cell-act {{ grid-area:act; }}
  .season-h {{ flex-wrap:wrap; }}
}}
@media (prefers-reduced-motion:reduce) {{ * {{ animation:none !important; transition:none !important; }} }}
</style>

<div class="wrap">
  <header class="mast">
    <p class="eyebrow">The Kelly Clarkson Show &middot; September 9, 2019 &ndash; August 31, 2026</p>
    <h1>The <span class="spark">Kellyoke</span> Archive</h1>
    <p class="lede">Every cover Kelly Clarkson opened her show with, from the first episode to the
      series finale, in order of the date it first aired. <b>{n_kelly:,} performances</b> across
      {n_eps:,} episodes and seven seasons, each linked to the best copy still online.
      The <b>{n_guest}</b> nights a guest took the mic instead are kept in, and labeled.</p>
    <ul class="stats">
      <li><b>{n_kelly:,}</b><span>Kelly covers</span></li>
      <li><b>{n_songs:,}</b><span>Distinct songs</span></li>
      <li><b>7</b><span>Seasons</span></li>
      <li><b>{n_play:,}</b><span>Playable</span></li>
      <li><b>{n_play/n_kelly*100:.1f}%</b><span>Coverage</span></li>
      <li><b>{n_guest}</b><span>Cameo-oke</span></li>
    </ul>
  </header>

  <div class="controls">
    <div class="cbar">
      <div class="search">
        <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor"
             stroke-width="2.4" aria-hidden="true"><circle cx="11" cy="11" r="7"></circle>
          <path d="M20 20l-3.5-3.5"></path></svg>
        <input id="q" type="search" placeholder="Search a song, an artist, a year&hellip;"
               autocomplete="off" aria-label="Search performances">
      </div>
      <div class="chips" id="chips">{chips}</div>
      <button class="toggle" id="onlyvid" aria-pressed="false">Playable only</button>
      <button class="toggle" id="nocameo" aria-pressed="false">Kelly only</button>
      <button class="toggle" id="rev" aria-pressed="false">Newest first</button>
    </div>
    <div class="count" id="count">Showing all {len(allp):,} entries</div>
  </div>

  <main id="list">{"".join(sections)}
    <p class="empty hidden" id="empty">No performance matches that search.</p>
  </main>

  <section class="playlists">
    <h2>Watch them as playlists</h2>
    <p class="sub">Each button opens an instant YouTube playlist of Kelly's covers in air-date
      order. Nothing to sign in for; if you are signed in, YouTube offers a Save option that
      keeps it on your account. YouTube caps these instant playlists at 50 videos, so seasons
      are split into numbered parts. Deduplicated to {n_uniq:,} distinct videos, guest
      Cameo-okes left out.</p>
    {pl_rows}
    <div class="pl-all">
      <h3>Complete archive &middot; {n_uniq:,} videos in {len(PL["all"])} parts</h3>
      <div class="pl-links">{pl_all}</div>
    </div>
  </section>

  <footer class="notes">
    <h2>How this list was built</h2>
    <div class="grid2">
      <div>
        <h3>Where the dates come from</h3>
        <p>The songs, air dates and episode numbers were parsed straight out of the wikitext of
          the seven Wikipedia season articles for <i>The Kelly Clarkson Show</i>, which record the
          Kellyoke for every one of the {n_eps:,} episodes. Parsing the source rather than reading
          a summary means the dates here are the original broadcast dates, and the episode count
          reconciles exactly with the number each season's article declares.</p>
        <h3 style="margin-top:18px">Where the videos come from</h3>
        <p>Titles and artists were matched against a full index of the show's own YouTube channel
          (its video tab plus all 97 of its playlists) and three standing fan archives that mirror
          the segment. Official uploads are preferred, but the show keeps only about sixty
          Kellyokes online, so most entries resolve to an archive copy, typically 720p or 1080p.</p>
      </div>
      <div>
        <h3>Reading the list</h3>
        <ul>
          <li><b>Cameo-oke</b> is the show's name for the nights a guest sang the opening number
            instead of Kelly. Those {n_guest} rows are dashed and named; use <b>Kelly only</b> to hide them.</li>
          <li><b>Kellyoke Classic</b> marks the {n_classic} times Kelly covered her own catalog.</li>
          <li>A <b>with&nbsp;&hellip;</b> tag means she sang it as a duet with that guest.</li>
          <li>A tag like <i>Reba McEntire version</i> means she covered that artist's arrangement
            rather than the original.</li>
          <li><b>Official</b> is the show's channel; <b>Archive</b> a fan mirror; <b>In recap</b> a
            weekly compilation where the single clip no longer exists.</li>
        </ul>
      </div>
      <div>
        <h3>What is not exact</h3>
        <ul>
          <li>Two of Kelly's covers have no findable copy: <i>Day-O</i> (Oct 31, 2024) and
            <i>You're Beautiful</i> (Jun 5, 2025). Those rows link to a search instead.</li>
          <li>Most Cameo-oke nights were never posted, so only {sum(1 for _, p in guest if p["video_id"])}
            of {n_guest} have a video.</li>
          <li>About {n_shared} entries share a video with another date. Where a song was performed
            more than once and several copies exist, the copies were aligned to the air dates by
            upload date; where only one copy survives, every date points at it.</li>
          <li>Video quality is labeled by source, not measured per file.</li>
        </ul>
      </div>
      <div>
        <h3>Most covered artists</h3>
        <ul class="alist">{artist_list}</ul>
        <p style="font-size:13px;margin-top:10px">Kelly's own catalog accounts for a further
          {n_classic} performances.</p>
      </div>
    </div>
  </footer>
</div>

<script>
(function () {{
  var q=document.getElementById('q'),
      chips=[].slice.call(document.querySelectorAll('.chip')),
      onlyvid=document.getElementById('onlyvid'),
      nocameo=document.getElementById('nocameo'),
      rev=document.getElementById('rev'),
      countEl=document.getElementById('count'), emptyEl=document.getElementById('empty'),
      list=document.getElementById('list'),
      seasons=[].slice.call(document.querySelectorAll('.season')),
      rows=[].slice.call(document.querySelectorAll('.row')),
      total=rows.length, seasonFilter=new Set(), order=[].slice.call(list.children);

  function norm(s) {{
    return s.toLowerCase().normalize('NFKD').replace(/[\\u0300-\\u036f]/g,'')
            .replace(/[^a-z0-9 ]+/g,' ').replace(/\\s+/g,' ').trim();
  }}

  function apply() {{
    var terms=norm(q.value).split(' ').filter(Boolean),
        vidOnly=onlyvid.getAttribute('aria-pressed')==='true',
        hideCameo=nocameo.getAttribute('aria-pressed')==='true', shown=0;
    rows.forEach(function (r) {{
      var ok=true;
      if (seasonFilter.size && !seasonFilter.has(r.dataset.season)) ok=false;
      if (ok && vidOnly && r.dataset.vid!=='1') ok=false;
      if (ok && hideCameo && r.dataset.cameo==='1') ok=false;
      if (ok && terms.length) {{
        var hay=r.dataset.s;
        for (var i=0;i<terms.length;i++) if (hay.indexOf(terms[i])===-1) {{ ok=false; break; }}
      }}
      r.classList.toggle('hidden',!ok);
      if (ok) shown++;
    }});
    document.querySelectorAll('.month').forEach(function (m) {{
      m.classList.toggle('hidden',!m.querySelector('.row:not(.hidden)'));
    }});
    seasons.forEach(function (s) {{
      s.classList.toggle('hidden',!s.querySelector('.row:not(.hidden)'));
    }});
    emptyEl.classList.toggle('hidden',shown!==0);
    countEl.textContent = shown===total
      ? 'Showing all '+total.toLocaleString()+' entries'
      : 'Showing '+shown.toLocaleString()+' of '+total.toLocaleString()+' entries';
  }}

  function press(btn) {{
    btn.setAttribute('aria-pressed', btn.getAttribute('aria-pressed')==='true'?'false':'true');
  }}
  q.addEventListener('input',apply);
  [onlyvid,nocameo].forEach(function (b) {{
    b.addEventListener('click',function(){{ press(b); apply(); }});
  }});
  chips.forEach(function (c) {{
    c.addEventListener('click',function () {{
      var s=c.dataset.f, on=c.getAttribute('aria-pressed')==='true';
      c.setAttribute('aria-pressed',on?'false':'true');
      if (on) seasonFilter.delete(s); else seasonFilter.add(s);
      apply();
    }});
  }});
  rev.addEventListener('click',function () {{
    var on=this.getAttribute('aria-pressed')==='true';
    this.setAttribute('aria-pressed',on?'false':'true');
    this.textContent = on ? 'Newest first' : 'Oldest first';
    (on?order:order.slice().reverse()).forEach(function(n){{ list.appendChild(n); }});
    seasons.forEach(function (s) {{
      var ms=[].slice.call(s.querySelectorAll('.month'));
      (on?ms:ms.slice().reverse()).forEach(function(m){{ s.appendChild(m); }});
      ms.forEach(function (m) {{
        var box=m.querySelector('.rows'), rs=[].slice.call(box.children);
        (on?rs:rs.slice().reverse()).forEach(function(r){{ box.appendChild(r); }});
      }});
    }});
  }});
}})();
</script>
"""

out = os.path.join(S, "kellyoke.html")
open(out, "w").write(HTML)
# keep the copy in the repo folder in step; it is the entry page, so index.html
REPO = "/Users/chesterismay/repos/kellyoke"
if os.path.isdir(REPO):
    open(os.path.join(REPO, "index.html"), "w").write(HTML)
print(f"wrote {out} ({os.path.getsize(out)/1024:.0f} KB)")
print(f"Kelly {n_kelly}  playable {n_play}  guest {n_guest}  songs {n_songs}")
