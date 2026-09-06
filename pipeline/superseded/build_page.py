#!/usr/bin/env python3
"""Build the Kellyoke Archive page from matched.json."""
import json, os, re, html, unicodedata, collections

S = os.path.dirname(os.path.abspath(__file__))
rows = json.load(open(os.path.join(S, "matched.json")))

# The show's own season colors, taken from each season's Wikipedia infobox bg_colour.
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
    if not d:
        return ""
    return f"{int(d)//60}:{int(d)%60:02d}"


perfs = [(r, p) for r in rows for p in r["perfs"]]
n_perf = len(perfs)
n_video = sum(1 for _, p in perfs if p["video_id"])
n_songs = len({p["song"].lower() for _, p in perfs})
n_eps = len(rows)

SRC_SHORT = {
    "The Kelly Clarkson Show (official)": ("official", "Official"),
    "KC Videos archive": ("archive", "Archive"),
    "Xavier Del Cid archive": ("archive2", "Archive"),
}

# ------------------------------------------------------------------ body rows
sections = []
by_season = collections.OrderedDict()
for r in rows:
    by_season.setdefault(r["season"], []).append(r)

for season, eps in by_season.items():
    color = SEASON_COLOR[season]
    s_perfs = sum(len(x["perfs"]) for x in eps)
    s_vid = sum(1 for x in eps for p in x["perfs"] if p["video_id"])
    first, last = eps[0], eps[-1]
    months = collections.OrderedDict()
    for ep in eps:
        y, m, _ = ep["date_iso"].split("-")
        months.setdefault(f"{MONTHS[int(m)-1]} {y}", []).append(ep)

    mparts = []
    for mlabel, meps in months.items():
        rowparts = []
        for ep in meps:
            y, m, d = (int(x) for x in ep["date_iso"].split("-"))
            datelabel = f"{MONTHS[m-1][:3]} {d}"
            if not ep["perfs"]:
                note = e(ep["aux_raw"]) or "No Kellyoke"
                rowparts.append(
                    f'<div class="row row--none" data-s="{e(searchkey(ep["aux_raw"], ep["date_iso"]))}" '
                    f'data-season="{season}" data-vid="0">'
                    f'<div class="cell-date"><span class="d">{datelabel}</span>'
                    f'<span class="y">{y}</span></div>'
                    f'<div class="cell-song"><span class="nosong">{note}</span></div>'
                    f'<div class="cell-meta"><span class="ep">Ep&nbsp;{e(ep["ep_overall"])}</span></div>'
                    f'<div class="cell-act"></div></div>')
                continue
            for p in ep["perfs"]:
                is_classic = "kelly clarkson" in (p["artist"] or "").lower()
                vid = p["video_id"]
                if vid:
                    href = f"https://www.youtube.com/watch?v={vid}"
                    key, label = SRC_SHORT.get(p["source"], ("archive", "Archive"))
                    dur = fmt_dur(p["duration"])
                    act = (f'<a class="watch" href="{href}" target="_blank" rel="noopener noreferrer">'
                           f'<span class="tri" aria-hidden="true"></span>Watch'
                           f'{f"<span class=dur>{dur}</span>" if dur else ""}</a>')
                    badge = f'<span class="src src--{key}">{label}</span>'
                else:
                    q = f"Kelly Clarkson Kellyoke {p['song']} {p['artist']}".strip()
                    href = "https://www.youtube.com/results?search_query=" + \
                           re.sub(r"\s+", "+", searchkey(q))
                    act = (f'<a class="watch watch--search" href="{href}" target="_blank" '
                           f'rel="noopener noreferrer">Search</a>')
                    badge = '<span class="src src--none">No copy found</span>'
                artist = e(p["artist"]) or "&mdash;"
                rowparts.append(
                    f'<div class="row" data-s="{e(searchkey(p["song"], p["artist"], ep["date_iso"], mlabel))}" '
                    f'data-season="{season}" data-vid="{1 if vid else 0}">'
                    f'<div class="cell-date"><span class="d">{datelabel}</span>'
                    f'<span class="y">{y}</span></div>'
                    f'<div class="cell-song"><span class="song">{e(p["song"])}</span>'
                    f'<span class="artist">{artist}</span>'
                    f'{"<span class=classic>Kellyoke Classic</span>" if is_classic else ""}</div>'
                    f'<div class="cell-meta">{badge}<span class="ep">Ep&nbsp;{e(ep["ep_overall"])}</span></div>'
                    f'<div class="cell-act">{act}</div></div>')
        mparts.append(f'<div class="month" data-month="{e(mlabel)}">'
                      f'<h3 class="month-h">{e(mlabel)}</h3>'
                      f'<div class="rows">{"".join(rowparts)}</div></div>')

    sections.append(
        f'<section class="season" id="s{season}" data-season="{season}" '
        f'style="--sc:{color}">'
        f'<header class="season-h">'
        f'<div class="season-n">S{season}</div>'
        f'<div class="season-t"><h2>Season&nbsp;{season}</h2>'
        f'<p>{first["date_pretty"]} &ndash; {last["date_pretty"]}</p></div>'
        f'<div class="season-k"><b>{s_perfs}</b><span>covers</span></div>'
        f'<div class="season-k"><b>{s_vid}</b><span>with video</span></div>'
        f'</header>{"".join(mparts)}</section>')

chips = "".join(
    f'<button class="chip" data-f="{s}" style="--sc:{SEASON_COLOR[s]}" '
    f'aria-pressed="false"><i></i>S{s}</button>' for s in by_season)

top_artists = collections.Counter(
    p["artist"] for _, p in perfs if p["artist"] and
    "kelly clarkson" not in p["artist"].lower()).most_common(10)
artist_list = "".join(
    f'<li><span class="an">{e(a)}</span><span class="ac">{c}</span></li>'
    for a, c in top_artists)

HTML = f"""<title>The Kellyoke Archive</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Bricolage+Grotesque:opsz,wght@12..96,400;12..96,600;12..96,800&family=Instrument+Sans:wght@400;500;600&family=JetBrains+Mono:wght@400;600&display=swap">
<style>
:root {{
  --bg:#F4F3F7; --surface:#FFFFFF; --surface-2:#EDEBF2; --line:#DCD8E4;
  --line-soft:#E8E5EE; --ink:#191622; --ink-2:#514B63; --ink-3:#7B7490;
  --accent:#7600ED; --accent-ink:#FFFFFF; --good:#0F7B5F; --shadow:0 1px 2px rgba(25,22,34,.06);
  --radius:9px;
}}
@media (prefers-color-scheme: dark) {{
  :root:not([data-theme="light"]) {{
    --bg:#131019; --surface:#1B1724; --surface-2:#241F30; --line:#332C42;
    --line-soft:#272134; --ink:#F2EFF7; --ink-2:#B4ACC6; --ink-3:#857D99;
    --accent:#B98BFF; --accent-ink:#1A1424; --good:#5FD9B4; --shadow:none;
  }}
}}
:root[data-theme="dark"] {{
  --bg:#131019; --surface:#1B1724; --surface-2:#241F30; --line:#332C42;
  --line-soft:#272134; --ink:#F2EFF7; --ink-2:#B4ACC6; --ink-3:#857D99;
  --accent:#B98BFF; --accent-ink:#1A1424; --good:#5FD9B4; --shadow:none;
}}

*,*::before,*::after {{ box-sizing:border-box; }}
body {{
  margin:0; background:var(--bg); color:var(--ink);
  font-family:"Instrument Sans",ui-sans-serif,system-ui,-apple-system,Segoe UI,sans-serif;
  font-size:15px; line-height:1.5; -webkit-font-smoothing:antialiased;
}}
a {{ color:inherit; }}
:focus-visible {{ outline:2px solid var(--accent); outline-offset:2px; border-radius:4px; }}
.wrap {{ max-width:1080px; margin:0 auto; padding:0 20px; }}

/* ---------- masthead ---------- */
.mast {{ padding:44px 0 20px; }}
.eyebrow {{
  font-family:"JetBrains Mono",ui-monospace,monospace; font-size:11px;
  letter-spacing:.14em; text-transform:uppercase; color:var(--ink-3); margin:0 0 14px;
}}
h1 {{
  font-family:"Bricolage Grotesque","Instrument Sans",sans-serif; font-weight:800;
  font-size:clamp(40px,7.5vw,76px); line-height:.95; letter-spacing:-.025em;
  margin:0 0 14px; text-wrap:balance;
}}
h1 .spark {{
  display:inline-block; background:linear-gradient(92deg,#FF52AF,#7600ED 34%,#1DD9FC 68%,#FF6929);
  -webkit-background-clip:text; background-clip:text; color:transparent;
}}
.lede {{ max-width:60ch; color:var(--ink-2); font-size:16.5px; margin:0 0 26px; }}
.lede b {{ color:var(--ink); font-weight:600; }}

.stats {{ display:flex; flex-wrap:wrap; gap:10px; margin:0 0 8px; padding:0; list-style:none; }}
.stats li {{
  background:var(--surface); border:1px solid var(--line); border-radius:var(--radius);
  padding:10px 14px; min-width:104px; box-shadow:var(--shadow);
}}
.stats b {{
  display:block; font-family:"JetBrains Mono",monospace; font-weight:600;
  font-size:21px; letter-spacing:-.02em; font-variant-numeric:tabular-nums;
}}
.stats span {{ font-size:11.5px; color:var(--ink-3); letter-spacing:.05em; text-transform:uppercase; }}

/* ---------- controls ---------- */
.controls {{
  position:sticky; top:0; z-index:20; background:var(--bg);
  border-bottom:1px solid var(--line); padding:12px 0; margin-bottom:8px;
}}
.cbar {{ display:flex; flex-wrap:wrap; gap:10px; align-items:center; }}
.search {{ position:relative; flex:1 1 260px; min-width:200px; }}
.search input {{
  width:100%; font:inherit; color:var(--ink); background:var(--surface);
  border:1px solid var(--line); border-radius:var(--radius); padding:9px 12px 9px 34px;
}}
.search input::placeholder {{ color:var(--ink-3); }}
.search svg {{ position:absolute; left:11px; top:50%; transform:translateY(-50%); color:var(--ink-3); }}
.chips {{ display:flex; flex-wrap:wrap; gap:6px; }}
.chip {{
  font:inherit; font-size:13px; font-weight:500; cursor:pointer; color:var(--ink-2);
  background:var(--surface); border:1px solid var(--line); border-radius:99px;
  padding:7px 12px; display:inline-flex; align-items:center; gap:6px;
}}
.chip i {{ width:8px; height:8px; border-radius:50%; background:var(--sc); display:block; }}
.chip[aria-pressed="true"] {{ background:var(--ink); color:var(--bg); border-color:var(--ink); }}
.toggle {{
  font:inherit; font-size:13px; font-weight:500; cursor:pointer; color:var(--ink-2);
  background:var(--surface); border:1px solid var(--line); border-radius:var(--radius);
  padding:7px 12px;
}}
.toggle[aria-pressed="true"] {{ background:var(--ink); color:var(--bg); border-color:var(--ink); }}
.count {{
  font-family:"JetBrains Mono",monospace; font-size:12px; color:var(--ink-3);
  padding:8px 0 0; font-variant-numeric:tabular-nums;
}}

/* ---------- season ---------- */
.season {{ margin:34px 0 0; }}
.season-h {{
  display:flex; align-items:center; gap:14px; padding:14px 16px;
  background:var(--surface); border:1px solid var(--line);
  border-left:5px solid var(--sc); border-radius:var(--radius); box-shadow:var(--shadow);
}}
.season-n {{
  font-family:"Bricolage Grotesque",sans-serif; font-weight:800; font-size:26px;
  letter-spacing:-.03em; color:var(--sc); min-width:44px;
}}
.season-t {{ flex:1 1 200px; }}
.season-t h2 {{ font-family:"Bricolage Grotesque",sans-serif; font-weight:600;
  font-size:19px; margin:0; letter-spacing:-.015em; }}
.season-t p {{ margin:1px 0 0; font-size:12.5px; color:var(--ink-3);
  font-family:"JetBrains Mono",monospace; }}
.season-k {{ text-align:right; min-width:74px; }}
.season-k b {{ display:block; font-family:"JetBrains Mono",monospace; font-weight:600;
  font-size:16px; font-variant-numeric:tabular-nums; }}
.season-k span {{ font-size:10.5px; color:var(--ink-3); text-transform:uppercase; letter-spacing:.05em; }}

.month {{ margin:18px 0 0; }}
.month-h {{
  font-family:"JetBrains Mono",monospace; font-size:11px; font-weight:600;
  letter-spacing:.13em; text-transform:uppercase; color:var(--ink-3);
  margin:0 0 6px; padding-left:2px;
}}
.rows {{ display:flex; flex-direction:column; gap:3px; }}

/* ---------- row ---------- */
.row {{
  display:grid; grid-template-columns:58px minmax(0,1fr) auto auto;
  gap:14px; align-items:center;
  background:var(--surface); border:1px solid var(--line-soft);
  border-radius:var(--radius); padding:9px 13px;
}}
.row:hover {{ border-color:var(--line); background:var(--surface-2); }}
.cell-date {{ font-family:"JetBrains Mono",monospace; font-variant-numeric:tabular-nums; line-height:1.15; }}
.cell-date .d {{ display:block; font-size:13px; font-weight:600; }}
.cell-date .y {{ display:block; font-size:10.5px; color:var(--ink-3); }}
.cell-song {{ min-width:0; }}
.cell-song .song {{
  font-family:"Bricolage Grotesque",sans-serif; font-weight:600; font-size:16px;
  letter-spacing:-.012em; display:block; overflow-wrap:anywhere;
}}
.cell-song .artist {{ font-size:13px; color:var(--ink-2); display:block; overflow-wrap:anywhere; }}
.cell-song .classic {{
  display:inline-block; margin-top:3px; font-size:10px; font-weight:600;
  letter-spacing:.07em; text-transform:uppercase; color:var(--accent);
  border:1px solid color-mix(in srgb, var(--accent) 38%, transparent);
  border-radius:99px; padding:1px 7px;
}}
.cell-song .nosong {{ color:var(--ink-3); font-style:italic; }}
.cell-meta {{ display:flex; flex-direction:column; align-items:flex-end; gap:3px; }}
.src {{
  font-size:10px; font-weight:600; letter-spacing:.06em; text-transform:uppercase;
  padding:2px 7px; border-radius:99px; white-space:nowrap;
}}
.src--official {{ color:var(--good); border:1px solid color-mix(in srgb, var(--good) 40%, transparent); }}
.src--archive, .src--archive2 {{ color:var(--ink-3); border:1px solid var(--line); }}
.src--none {{ color:var(--ink-3); border:1px dashed var(--line); }}
.ep {{ font-family:"JetBrains Mono",monospace; font-size:10.5px; color:var(--ink-3);
  font-variant-numeric:tabular-nums; }}
.watch {{
  display:inline-flex; align-items:center; gap:7px; text-decoration:none;
  font-size:13px; font-weight:600; white-space:nowrap;
  background:var(--ink); color:var(--bg); border-radius:99px; padding:7px 14px;
}}
.watch:hover {{ background:var(--accent); color:var(--accent-ink); }}
.watch .tri {{
  width:0; height:0; border-left:7px solid currentColor;
  border-top:4.5px solid transparent; border-bottom:4.5px solid transparent;
}}
.watch .dur {{ font-family:"JetBrains Mono",monospace; font-size:11px; opacity:.72; font-weight:400; }}
.watch--search {{ background:transparent; color:var(--ink-2); border:1px dashed var(--line); }}
.watch--search:hover {{ background:var(--surface-2); color:var(--ink); }}

.hidden {{ display:none !important; }}
.empty {{ padding:40px 4px; color:var(--ink-3); }}

/* ---------- notes ---------- */
.notes {{ margin:52px 0 60px; padding-top:26px; border-top:1px solid var(--line); }}
.notes h2 {{ font-family:"Bricolage Grotesque",sans-serif; font-weight:600; font-size:20px;
  margin:0 0 12px; letter-spacing:-.015em; }}
.grid2 {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(260px,1fr)); gap:26px; }}
.notes p {{ color:var(--ink-2); font-size:14px; max-width:62ch; }}
.notes h3 {{ font-family:"JetBrains Mono",monospace; font-size:11px; font-weight:600;
  letter-spacing:.13em; text-transform:uppercase; color:var(--ink-3); margin:0 0 8px; }}
.notes ol, .notes ul {{ padding-left:18px; color:var(--ink-2); font-size:14px; }}
.notes li {{ margin-bottom:5px; }}
.alist {{ list-style:none; padding:0; margin:0; }}
.alist li {{ display:flex; justify-content:space-between; gap:12px; padding:5px 0;
  border-bottom:1px solid var(--line-soft); font-size:14px; }}
.alist .an {{ color:var(--ink); }}
.alist .ac {{ font-family:"JetBrains Mono",monospace; color:var(--ink-3);
  font-variant-numeric:tabular-nums; }}

@media (max-width:640px) {{
  .row {{ grid-template-columns:50px minmax(0,1fr); grid-template-areas:"date song" ". meta" ". act";
    row-gap:7px; }}
  .cell-date {{ grid-area:date; }} .cell-song {{ grid-area:song; }}
  .cell-meta {{ grid-area:meta; flex-direction:row; align-items:center; justify-content:flex-start; gap:8px; }}
  .cell-act {{ grid-area:act; }}
  .season-h {{ flex-wrap:wrap; }}
}}
@media (prefers-reduced-motion:reduce) {{ * {{ animation:none !important; transition:none !important; }} }}
</style>

<div class="wrap">
  <header class="mast">
    <p class="eyebrow">The Kelly Clarkson Show &middot; September 2019 &ndash; August 2026</p>
    <h1>The <span class="spark">Kellyoke</span> Archive</h1>
    <p class="lede">Every cover Kelly Clarkson has opened her show with, in order of the date it
      first aired. <b>{n_perf:,} performances</b> across <b>{n_eps:,} episodes</b> and seven seasons,
      each linked to the best copy currently on YouTube.</p>
    <ul class="stats">
      <li><b>{n_perf:,}</b><span>Performances</span></li>
      <li><b>{n_songs:,}</b><span>Distinct songs</span></li>
      <li><b>7</b><span>Seasons</span></li>
      <li><b>{n_video:,}</b><span>Playable</span></li>
      <li><b>{n_video/n_perf*100:.0f}%</b><span>Coverage</span></li>
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
      <button class="toggle" id="rev" aria-pressed="false">Newest first</button>
    </div>
    <div class="count" id="count">Showing all {n_perf:,} performances</div>
  </div>

  <main id="list">{"".join(sections)}
    <p class="empty hidden" id="empty">No performance matches that search.</p>
  </main>

  <footer class="notes">
    <h2>How this list was built</h2>
    <div class="grid2">
      <div>
        <h3>Sources</h3>
        <p>The performances, air dates and episode numbers come from the Wikipedia season
          articles for <i>The Kelly Clarkson Show</i>, which log the Kellyoke cover for every
          episode. Those tables were parsed directly from the page wikitext rather than
          transcribed, so the dates here are the original broadcast dates.</p>
        <p>Video links were matched by title and artist against a full index of
          The Kelly Clarkson Show's YouTube channel plus the two standing fan archives that
          mirror the segment. The official upload is preferred wherever it still exists; the
          show does not keep every Kellyoke online, so most older entries resolve to an archive
          copy, typically 720p or 1080p.</p>
      </div>
      <div>
        <h3>Reading the list</h3>
        <ul>
          <li><b>Official</b> marks a video still on the show's own channel.</li>
          <li><b>Archive</b> marks a fan-maintained mirror, used where no official upload survives.</li>
          <li><b>Kellyoke Classic</b> marks the segments where Kelly covers her own catalog.</li>
          <li>{n_perf - n_video} performances have no copy online that could be identified; those
            rows link to a YouTube search instead.</li>
          <li>Season colors are the show's own, taken from each season's article.</li>
        </ul>
      </div>
      <div>
        <h3>Most covered artists</h3>
        <ul class="alist">{artist_list}</ul>
        <p style="font-size:13px;margin-top:10px">Kelly Clarkson's own songs account for a further
          {sum(1 for _, p in perfs if 'kelly clarkson' in (p['artist'] or '').lower())} performances,
          listed as Kellyoke Classics.</p>
      </div>
    </div>
  </footer>
</div>

<script>
(function () {{
  var q = document.getElementById('q'),
      chips = [].slice.call(document.querySelectorAll('.chip')),
      onlyvid = document.getElementById('onlyvid'),
      rev = document.getElementById('rev'),
      countEl = document.getElementById('count'),
      emptyEl = document.getElementById('empty'),
      list = document.getElementById('list'),
      seasons = [].slice.call(document.querySelectorAll('.season')),
      rows = [].slice.call(document.querySelectorAll('.row')),
      total = rows.length,
      seasonFilter = new Set(),
      order = [].slice.call(list.children);

  function norm(s) {{
    return s.toLowerCase().normalize('NFKD').replace(/[\\u0300-\\u036f]/g, '')
            .replace(/[^a-z0-9 ]+/g, ' ').replace(/\\s+/g, ' ').trim();
  }}

  function apply() {{
    var terms = norm(q.value).split(' ').filter(Boolean),
        vidOnly = onlyvid.getAttribute('aria-pressed') === 'true',
        shown = 0;

    rows.forEach(function (r) {{
      var ok = true;
      if (seasonFilter.size && !seasonFilter.has(r.dataset.season)) ok = false;
      if (ok && vidOnly && r.dataset.vid !== '1') ok = false;
      if (ok && terms.length) {{
        var hay = r.dataset.s;
        for (var i = 0; i < terms.length; i++) {{
          if (hay.indexOf(terms[i]) === -1) {{ ok = false; break; }}
        }}
      }}
      r.classList.toggle('hidden', !ok);
      if (ok) shown++;
    }});

    // collapse any month or season group left with nothing in it
    document.querySelectorAll('.month').forEach(function (m) {{
      m.classList.toggle('hidden', !m.querySelector('.row:not(.hidden)'));
    }});
    seasons.forEach(function (s) {{
      s.classList.toggle('hidden', !s.querySelector('.row:not(.hidden)'));
    }});

    emptyEl.classList.toggle('hidden', shown !== 0);
    countEl.textContent = shown === total
      ? 'Showing all ' + total.toLocaleString() + ' performances'
      : 'Showing ' + shown.toLocaleString() + ' of ' + total.toLocaleString() + ' performances';
  }}

  q.addEventListener('input', apply);
  onlyvid.addEventListener('click', function () {{
    this.setAttribute('aria-pressed', this.getAttribute('aria-pressed') === 'true' ? 'false' : 'true');
    apply();
  }});
  chips.forEach(function (c) {{
    c.addEventListener('click', function () {{
      var s = c.dataset.f, on = c.getAttribute('aria-pressed') === 'true';
      c.setAttribute('aria-pressed', on ? 'false' : 'true');
      if (on) seasonFilter.delete(s); else seasonFilter.add(s);
      apply();
    }});
  }});
  rev.addEventListener('click', function () {{
    var on = this.getAttribute('aria-pressed') === 'true';
    this.setAttribute('aria-pressed', on ? 'false' : 'true');
    this.textContent = on ? 'Newest first' : 'Oldest first';
    var seq = on ? order : order.slice().reverse();
    seq.forEach(function (n) {{ list.appendChild(n); }});
    seasons.forEach(function (s) {{
      var ms = [].slice.call(s.querySelectorAll('.month'));
      (on ? ms : ms.slice().reverse()).forEach(function (m) {{ s.appendChild(m); }});
      ms.forEach(function (m) {{
        var box = m.querySelector('.rows'),
            rs = [].slice.call(box.children);
        (on ? rs : rs.slice().reverse()).forEach(function (r) {{ box.appendChild(r); }});
      }});
    }});
  }});
}})();
</script>
"""

out = os.path.join(S, "kellyoke.html")
open(out, "w").write(HTML)
print(f"wrote {out}  ({os.path.getsize(out)/1024:.0f} KB)")
print(f"performances={n_perf} playable={n_video} songs={n_songs}")
