#!/usr/bin/env python3
"""The Kellyoke Archive - chronological log of every cover.

Design: the karaoke monitor. Rows are ruled lines, not cards; the only ornament
is the sung/unsung fill, and it always stands for a proportion.
"""
import json, os, re, html, unicodedata, collections
from design_tokens import SEASON_COLOR, FONTS, TOKENS

S = os.path.dirname(os.path.abspath(__file__))
REPO = "/Users/chesterismay/repos/kellyoke"
rows = json.load(open(os.path.join(S, "matched.json")))

MONTHS = ["January","February","March","April","May","June","July","August",
          "September","October","November","December"]
e = lambda t: html.escape(t or "", quote=True)


def key(*parts):
    t = " ".join(p for p in parts if p).lower()
    t = unicodedata.normalize("NFKD", t)
    t = "".join(c for c in t if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9 ]+", " ", t)).strip()


def dur(d):
    return f"{int(d)//60}:{int(d)%60:02d}" if d else ""


allp = [(r, p) for r in rows if r["perfs"] for p in r["perfs"]]
kelly = [(r, p) for r, p in allp if not r["cameo"]]
guest = [(r, p) for r, p in allp if r["cameo"]]
n_kelly, n_guest = len(kelly), len(guest)
n_play = sum(1 for _, p in kelly if p["video_id"])
n_songs = len({p["song"].lower() for _, p in kelly})
n_ver = sum(1 for _, p in allp if p.get("date_check") in ("verified", "corrected"))
n_classic = sum(1 for _, p in kelly if "kelly clarkson" in (p["artist"] or "").lower())
n_reprise = sum(1 for _, p in allp if p.get("date_check") == "reprise")
first, last = rows[0], rows[-1]
first_song = first["perfs"][0] if first["perfs"] else None
last_song = last["perfs"][0] if last["perfs"] else None

SRC_SHORT = {
    "The Kelly Clarkson Show (official)": "Show's own channel",
    "KC Videos archive": "KC Videos", "Courtney O'shea archive": "Courtney O'shea",
    "Xavier Del Cid archive": "Xavier Del Cid", "Other upload": "Another upload",
    "Weekly recap": "Inside a weekly recap",
}

# ------------------------------------------------------------------ the log
sections = []
by_season = collections.OrderedDict()
for r in rows:
    by_season.setdefault(r["season"], []).append(r)

for season, eps in by_season.items():
    colour = SEASON_COLOR[season]
    s_k = sum(1 for r in eps for p in r["perfs"] if not r["cameo"])
    s_v = sum(1 for r in eps for p in r["perfs"] if not r["cameo"] and p["video_id"])
    pct = round(s_v / s_k * 100) if s_k else 0
    months = collections.OrderedDict()
    for ep in eps:
        y, m, _ = ep["date_iso"].split("-")
        months.setdefault((int(y), int(m)), []).append(ep)

    mparts = []
    for (yy, mm), meps in months.items():
        rp = []
        for ep in meps:
            _, _, dd = (int(x) for x in ep["date_iso"].split("-"))
            if not ep["perfs"]:
                rp.append(
                    f'<li class="row row--quiet" data-k="{e(key(ep["date_iso"]))}" '
                    f'data-season="{season}" data-vid="0" data-cameo="0">'
                    f'<span class="day">{dd}</span>'
                    f'<span class="title">No Kellyoke this episode</span>'
                    f'<span class="right"></span></li>')
                continue
            for p in ep["perfs"]:
                cameo = ep["cameo"]
                classic = (not cameo) and "kelly clarkson" in (p["artist"] or "").lower()
                duet = p.get("duet") or ""
                vid = p["video_id"]

                notes = []
                if cameo:
                    who = f" &mdash; {e(ep['performer'])}" if ep["performer"] else ""
                    notes.append(f'<em class="n n--guest">Sung by a guest{who}</em>')
                if duet and not cameo:
                    notes.append(f'<em class="n">with {e(duet)}</em>')
                if classic:
                    notes.append('<em class="n n--own">Her own song</em>')
                if p.get("genre") and p["genre"] != "Not listed":
                    yr = f' {p["orig_year"]}' if p.get("orig_year") else ""
                    notes.append(f'<em class="n">{e(p["genre"])}{yr}</em>')
                elif p.get("orig_year"):
                    notes.append(f'<em class="n">{p["orig_year"]}</em>')
                if ep["version"]:
                    notes.append(f'<em class="n">{e(ep["version"])}</em>')
                if ep["rerun"]:
                    notes.append('<em class="n">Rerun</em>')

                if vid:
                    src = SRC_SHORT.get(p["source"], "Archive")
                    checked = p.get("date_check") in ("verified", "corrected")
                    mark = ('<span class="check" title="This clip states this air date">'
                            'date confirmed</span>' if checked else "")
                    d = dur(p.get("duration"))
                    right = (f'<a class="play" href="https://www.youtube.com/watch?v={vid}" '
                             f'target="_blank" rel="noopener noreferrer">Play'
                             f'{f"<b>{d}</b>" if d else ""}</a>'
                             f'<span class="src">{e(src)}{mark}</span>')
                else:
                    q = re.sub(r"\s+", "+", key("Kelly Clarkson Kellyoke", p["song"], p["artist"]))
                    right = (f'<a class="play play--none" '
                             f'href="https://www.youtube.com/results?search_query={q}" '
                             f'target="_blank" rel="noopener noreferrer">Look for it</a>'
                             f'<span class="src">No copy found</span>')

                facets = " ".join(f for f, on in (
                    ("cameo guest cameooke", cameo),
                    ("her own song classic", classic),
                    ("duet " + duet, bool(duet) and not cameo),
                    ("rerun", ep["rerun"]),
                    (p.get("genre", ""), p.get("genre", "") != "Not listed"),
                    (str(p.get("orig_year") or ""), bool(p.get("orig_year"))),
                ) if on)

                rp.append(
                    f'<li class="row{" row--guest" if cameo else ""}" '
                    f'data-k="{e(key(p["song"], p["artist"], ep["date_iso"], ep["performer"], facets))}" '
                    f'data-season="{season}" data-vid="{1 if vid else 0}" '
                    f'data-cameo="{1 if cameo else 0}">'
                    f'<span class="day">{dd}</span>'
                    f'<span class="title">{e(p["song"])}'
                    f'<span class="by">{e(p["artist"]) or "Traditional"}</span>'
                    f'{f"<span class=notes>{chr(32).join(notes)}</span>" if notes else ""}</span>'
                    f'<span class="right">{right}</span></li>')
        mparts.append(
            f'<div class="month"><h3>{MONTHS[mm-1]} <span>{yy}</span></h3>'
            f'<ul class="rows">{"".join(rp)}</ul></div>')

    sections.append(
        f'<section class="season" id="s{season}" data-season="{season}" style="--sc:{colour}">'
        f'<header class="sh">'
        f'<span class="sn">{season}</span>'
        f'<span class="st">Season {season}<b>{eps[0]["date_pretty"]} to {eps[-1]["date_pretty"]}</b></span>'
        f'<span class="sm"><span class="smn">{s_k} covers</span>'
        f'<span class="meter"><i style="width:{pct}%"></i></span>'
        f'<span class="smc">{s_v} playable</span></span>'
        f'</header>{"".join(mparts)}</section>')

chips = "".join(
    f'<button class="chip" data-f="{s}" style="--sc:{SEASON_COLOR[s]}" '
    f'aria-pressed="false"><i></i>{s}</button>' for s in by_season)

top = collections.Counter(
    p["artist"] for _, p in kelly
    if p["artist"] and "kelly clarkson" not in p["artist"].lower()).most_common(8)
top_list = "".join(
    f'<li><span>{e(a)}</span><b>{c}</b></li>' for a, c in top)

TOKENS_CSS = TOKENS.replace("{{", "{").replace("}}", "}")

HTML = f"""<meta charset="utf-8">
<title>The Kellyoke Archive</title>
<meta name="description" content="Every cover Kelly Clarkson opened The Kelly Clarkson Show with, from the 2019 premiere to the 2026 finale, in air-date order and linked to the best surviving copy.">
<meta property="og:type" content="website">
<meta property="og:site_name" content="The Kellyoke Archive">
<meta property="og:url" content="https://kellyokes.netlify.app/">
<meta property="og:title" content="Every song she opened with">
<meta property="og:description" content="Seven years of opening covers from The Kelly Clarkson Show, in air-date order and linked to the best surviving copy.">
<meta property="og:image" content="https://kellyokes.netlify.app/og-image.png">
<meta property="og:image:width" content="1200">
<meta property="og:image:height" content="630">
<meta property="og:image:alt" content="Every song she opened with. The Kelly Clarkson Show, 2019 to 2026.">
<meta name="twitter:card" content="summary_large_image">
{FONTS}
<style>{TOKENS_CSS}
.page {{ max-width:1000px; margin:0 auto; padding:0 22px 80px; }}

/* ---------- opening ---------- */
.hero {{ padding:64px 0 30px; border-bottom:2px solid var(--ink); }}
.hero h1 {{
  font-family:"Big Shoulders Display",Chivo,sans-serif; font-weight:800;
  font-size:clamp(52px,10.5vw,132px); line-height:.86; letter-spacing:-.01em;
  margin:0 0 22px; text-transform:none;
}}
.hero .sub {{ font-size:19px; line-height:1.45; max-width:56ch; margin:0 0 26px; color:var(--ink-2); }}
.hero .sub b {{ color:var(--ink); font-weight:700; }}
.bookends {{ display:flex; flex-wrap:wrap; gap:34px; }}
.bookend {{ max-width:30ch; }}
.bookend span {{ display:block; font-size:13px; color:var(--unsung); }}
.bookend b {{ display:block; font-size:17px; font-weight:700; line-height:1.25; }}
.bookend i {{ font-style:normal; font-size:13px; color:var(--ink-2); }}

/* ---------- counts ---------- */
.counts {{ display:flex; flex-wrap:wrap; gap:0; margin:0; padding:22px 0 0; list-style:none;
  border-bottom:1px solid var(--rule); }}
.counts li {{ flex:1 1 120px; padding:0 18px 20px 0; }}
.counts b {{ display:block; font-family:"Big Shoulders Display",Chivo,sans-serif;
  font-weight:700; font-size:38px; line-height:1; letter-spacing:-.01em; }}
.counts span {{ font-size:13px; color:var(--ink-2); }}

/* ---------- controls ---------- */
.controls {{ position:sticky; top:0; z-index:20; background:var(--ground);
  padding:12px 0 11px; border-bottom:1px solid var(--rule); }}
.cbar {{ display:flex; flex-wrap:wrap; gap:8px; align-items:center; }}
.find {{ flex:1 1 240px; min-width:190px; }}
.find input {{ width:100%; font:inherit; color:var(--ink); background:var(--panel);
  border:1px solid var(--rule); border-radius:var(--radius); padding:9px 13px; }}
.find input::placeholder {{ color:var(--unsung); }}
.chip, .tog {{ font:inherit; font-size:13.5px; font-weight:500; cursor:pointer; color:var(--ink-2);
  background:var(--panel); border:1px solid var(--rule); border-radius:var(--radius);
  padding:8px 12px; display:inline-flex; align-items:center; gap:7px; }}
.chip i {{ width:9px; height:9px; border-radius:2px; background:var(--sc); display:block; }}
.chip[aria-pressed="true"], .tog[aria-pressed="true"] {{
  background:var(--ink); color:var(--ground); border-color:var(--ink); }}
.tally {{ font-size:13px; color:var(--unsung); padding-top:9px; }}

/* ---------- season ---------- */
.season {{ margin:44px 0 0; }}
.sh {{ display:flex; align-items:center; gap:16px; padding:0 0 12px;
  border-bottom:2px solid var(--sc); }}
.sn {{ font-family:"Big Shoulders Display",Chivo,sans-serif; font-weight:800;
  font-size:60px; line-height:.8; color:var(--sc); }}
.st {{ flex:1 1 200px; font-size:17px; font-weight:700; }}
.st b {{ display:block; font-size:13px; font-weight:400; color:var(--ink-2); }}
.sm {{ min-width:160px; text-align:right; }}
.smn {{ display:block; font-size:14px; font-weight:700; }}
.sm .meter {{ margin:6px 0 4px; }}
.smc {{ font-size:12.5px; color:var(--unsung); }}

.month {{ margin:26px 0 0; }}
.month h3 {{ font-size:14px; font-weight:700; margin:0 0 4px; }}
.month h3 span {{ color:var(--unsung); font-weight:400; }}
.rows {{ list-style:none; margin:0; padding:0; }}

/* ---------- a row is a rule, not a card ---------- */
.row {{ display:grid; grid-template-columns:44px minmax(0,1fr) auto; gap:16px;
  align-items:baseline; padding:11px 0 12px; border-top:1px solid var(--rule-soft); }}
.row:hover {{ background:var(--panel-2); }}
.row--guest {{ color:var(--ink-2); }}
.day {{ font-size:14px; font-weight:700; color:var(--unsung); }}
.title {{ font-size:17px; font-weight:700; line-height:1.28; min-width:0; overflow-wrap:anywhere; }}
.by {{ display:block; font-size:14px; font-weight:400; color:var(--ink-2); }}
.notes {{ display:flex; flex-wrap:wrap; gap:5px 12px; margin-top:5px; }}
.n {{ font-style:normal; font-size:12.5px; color:var(--unsung); }}
.n--guest {{ color:var(--guest); }}
.n--own {{ color:var(--sung); }}
.right {{ text-align:right; white-space:nowrap; }}
.play {{ display:inline-flex; align-items:baseline; gap:8px; text-decoration:none;
  font-size:14px; font-weight:700; color:var(--sung); border-bottom:2px solid var(--sung);
  padding-bottom:1px; }}
.play:hover {{ background:var(--sung); color:var(--panel); border-color:var(--sung); }}
.play b {{ font-weight:400; font-size:12.5px; opacity:.75; }}
.play--none {{ color:var(--unsung); border-bottom-style:dotted; border-color:var(--unsung); }}
.play--none:hover {{ background:var(--unsung); color:var(--panel); }}
.src {{ display:block; font-size:12px; color:var(--unsung); margin-top:4px; }}
.check {{ color:var(--ok); }}
.check {{ margin-left:8px; }}
.row--quiet .title {{ font-weight:400; color:var(--unsung); font-size:15px; }}

.gone {{ display:none !important; }}
.nothing {{ padding:46px 0; color:var(--unsung); }}

/* ---------- closing notes ---------- */
.notes-foot {{ margin:60px 0 0; padding-top:26px; border-top:2px solid var(--ink); }}
.notes-foot h2 {{ font-family:"Big Shoulders Display",Chivo,sans-serif; font-weight:700;
  font-size:34px; margin:0 0 18px; }}
.cols {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(250px,1fr)); gap:30px; }}
.cols h4 {{ font-size:14px; margin:0 0 7px; }}
.cols p, .cols li {{ font-size:14px; color:var(--ink-2); max-width:60ch; }}
.cols ul {{ padding-left:17px; margin:0; }}
.cols li {{ margin-bottom:6px; }}
.rank {{ list-style:none; padding:0; margin:0; }}
.rank li {{ display:flex; justify-content:space-between; gap:12px; padding:5px 0;
  border-bottom:1px solid var(--rule-soft); font-size:14px; color:var(--ink); }}
.rank b {{ color:var(--unsung); font-weight:400; }}
.leave {{ display:inline-block; margin-top:16px; font-size:14px; font-weight:700;
  color:var(--sung); border-bottom:2px solid var(--sung); text-decoration:none; }}
.leave:hover {{ background:var(--sung); color:var(--panel); }}

@media (max-width:640px) {{
  .row {{ grid-template-columns:34px minmax(0,1fr); }}
  .right {{ grid-column:2; text-align:left; margin-top:6px; }}
  .sh {{ flex-wrap:wrap; }} .sm {{ text-align:left; }}
}}
</style>

<div class="page">
  <header class="hero">
    <h1><span class="wipe">Every song she<br>opened with</span></h1>
    <p class="sub">For seven years <b>Kelly Clarkson</b> started her show by covering somebody
      else's song, live, with the house band. This is all <b>{n_kelly:,}</b> of them, in the order
      they aired, each one linked to the best copy still online.</p>
    <div class="bookends">
      <div class="bookend">
        <span>It began</span>
        <b>{e(first_song["song"]) if first_song else ""}</b>
        <i>{e(first_song["artist"]) if first_song else ""} &nbsp;{first["date_pretty"]}</i>
      </div>
      <div class="bookend">
        <span>It ended</span>
        <b>{e(last_song["song"]) if last_song else ""}</b>
        <i>{last["date_pretty"]}, the series finale</i>
      </div>
    </div>
  </header>

  <ul class="counts">
    <li><b>{n_kelly:,}</b><span>covers by Kelly</span></li>
    <li><b>{n_songs:,}</b><span>different songs</span></li>
    <li><b>{n_play:,}</b><span>you can watch</span></li>
    <li><b>{n_ver:,}</b><span>date confirmed by the clip</span></li>
    <li><b>{n_guest}</b><span>sung by a guest</span></li>
  </ul>

  <div class="controls">
    <div class="cbar">
      <div class="find">
        <input id="q" type="search" placeholder="Find a song, an artist, a genre, a year"
               autocomplete="off" aria-label="Find a performance">
      </div>
      {chips}
      <button class="tog" id="onlyvid" aria-pressed="false">Only ones I can watch</button>
      <button class="tog" id="nocameo" aria-pressed="false">Hide guest turns</button>
      <button class="tog" id="rev" aria-pressed="false">Newest first</button>
    </div>
    <p class="tally" id="tally">All {len(allp):,} entries</p>
  </div>

  <main id="log">{"".join(sections)}
    <p class="nothing gone" id="nothing">Nothing here matches that. Try a shorter search.</p>
  </main>

  <footer class="notes-foot">
    <h2>How this was put together</h2>
    <div class="cols">
      <div>
        <h4>The dates</h4>
        <p>Every song, air date and episode number was read straight out of the wikitext of the
          seven Wikipedia season articles, which record the Kellyoke for all {len(rows):,} episodes.
          The totals reconcile exactly with the episode count each article declares.</p>
        <h4 style="margin-top:16px">The videos</h4>
        <p>Matched by title and artist against the show's own YouTube channel and three fan
          archives that mirror the segment. Most clips state their own air date in the
          description, so {n_ver:,} links are confirmed against the date shown here rather than
          inferred from the title.</p>
      </div>
      <div>
        <h4>What the labels mean</h4>
        <ul>
          <li><b>Sung by a guest</b> is the show's Cameo-oke: {n_guest} mornings someone else
            took the opening number. Hide them with the button above.</li>
          <li><b>Her own song</b> marks the {n_classic} times she covered her own catalog.</li>
          <li><b>with &hellip;</b> means she sang it as a duet.</li>
          <li>A note like <i>Reba McEntire version</i> means she sang that arrangement rather
            than the original.</li>
          <li><b>date confirmed</b> means the clip's own description states this air date.</li>
        </ul>
      </div>
      <div>
        <h4>Where it is thin</h4>
        <ul>
          <li>One cover has no findable copy: <i>Day-O</i>, October 31, 2024.</li>
          <li>Only {sum(1 for _, p in guest if p["video_id"])} of {n_guest} guest turns were
            ever posted.</li>
          <li>Where a song came back on a later morning and only one clip survives, every
            date points at that clip. That is {n_reprise} entries, each one identified by
            the clip dating itself to the other night.</li>
        </ul>
        <h4 style="margin-top:16px">Covered most</h4>
        <ul class="rank">{top_list}</ul>
        <a class="leave" id="toexplore" href="explore.html">Explore the data</a>
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
      tally=document.getElementById('tally'), nothing=document.getElementById('nothing'),
      log=document.getElementById('log'),
      seasons=[].slice.call(document.querySelectorAll('.season')),
      rows=[].slice.call(document.querySelectorAll('.row')),
      total=rows.length, pick=new Set(), order=[].slice.call(log.children);

  var ex=document.getElementById('toexplore');
  if (!(location.protocol==='file:'||/^(127\\.|localhost)/.test(location.hostname))) {{
    ex.setAttribute('href','__EXPLORE__');
  }}

  function norm(s) {{
    return s.toLowerCase().normalize('NFKD').replace(/[\\u0300-\\u036f]/g,'')
            .replace(/[^a-z0-9 ]+/g,' ').replace(/\\s+/g,' ').trim();
  }}
  function apply() {{
    var terms=norm(q.value).split(' ').filter(Boolean),
        v=onlyvid.getAttribute('aria-pressed')==='true',
        h=nocameo.getAttribute('aria-pressed')==='true', shown=0;
    rows.forEach(function (r) {{
      var ok=true;
      if (pick.size && !pick.has(r.dataset.season)) ok=false;
      if (ok && v && r.dataset.vid!=='1') ok=false;
      if (ok && h && r.dataset.cameo==='1') ok=false;
      if (ok && terms.length) {{
        var hay=r.dataset.k;
        for (var i=0;i<terms.length;i++) if (hay.indexOf(terms[i])===-1) {{ ok=false; break; }}
      }}
      r.classList.toggle('gone',!ok);
      if (ok) shown++;
    }});
    document.querySelectorAll('.month').forEach(function (m) {{
      m.classList.toggle('gone',!m.querySelector('.row:not(.gone)'));
    }});
    seasons.forEach(function (s) {{
      s.classList.toggle('gone',!s.querySelector('.row:not(.gone)'));
    }});
    nothing.classList.toggle('gone',shown!==0);
    tally.textContent = shown===total ? 'All '+total.toLocaleString()+' entries'
      : shown.toLocaleString()+' of '+total.toLocaleString()+' entries';
  }}
  function press(b) {{
    b.setAttribute('aria-pressed', b.getAttribute('aria-pressed')==='true'?'false':'true');
  }}
  q.addEventListener('input',apply);
  [onlyvid,nocameo].forEach(function (b) {{
    b.addEventListener('click',function(){{ press(b); apply(); }});
  }});
  chips.forEach(function (c) {{
    c.addEventListener('click',function () {{
      var s=c.dataset.f, on=c.getAttribute('aria-pressed')==='true';
      c.setAttribute('aria-pressed',on?'false':'true');
      if (on) pick.delete(s); else pick.add(s);
      apply();
    }});
  }});
  rev.addEventListener('click',function () {{
    var on=this.getAttribute('aria-pressed')==='true';
    this.setAttribute('aria-pressed',on?'false':'true');
    this.textContent = on ? 'Newest first' : 'Oldest first';
    (on?order:order.slice().reverse()).forEach(function(n){{ log.appendChild(n); }});
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

HTML = HTML.replace("__EXPLORE__",
                    "https://claude.ai/code/artifact/41950d92-c42a-434c-9f75-f214cc1b3dfd")

out = os.path.join(S, "kellyoke.html")
open(out, "w").write(HTML)
if os.path.isdir(REPO):
    open(os.path.join(REPO, "index.html"), "w").write(HTML)
print(f"archive: {os.path.getsize(out)/1024:.0f} KB | kelly {n_kelly} playable {n_play} "
      f"guest {n_guest} songs {n_songs} date-confirmed {n_ver}")
