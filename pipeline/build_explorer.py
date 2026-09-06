#!/usr/bin/env python3
"""Build the Kellyoke Data Explorer: faceted table + charts over the dataset."""
import json, os, collections
from design_tokens import SEASON_COLOR, FONTS, TOKENS

S = os.path.dirname(os.path.abspath(__file__))
REPO = "/Users/chesterismay/repos/kellyoke"
rows = json.load(open(os.path.join(S, "matched.json")))

SRC_LABEL = {
    "The Kelly Clarkson Show (official)": "Official channel",
    "KC Videos archive": "KC Videos archive",
    "Courtney O'shea archive": "Courtney O'shea archive",
    "Xavier Del Cid archive": "Xavier Del Cid archive",
    "Other upload": "Other upload",
    "Weekly recap": "Weekly recap",
}
sources = list(SRC_LABEL.values())

# ---- compact record array ---------------------------------------------------
# [date, season, ep, song, artist, performer, cameo, duet, version, rerun,
#  vid, srcIdx, genre, origYear, views, duration]
recs = []
genres_seen = collections.Counter()
for r in rows:
    for p in r["perfs"]:
        src = SRC_LABEL.get(p["source"] or "", "")
        genres_seen[p.get("genre") or "Not listed"] += 1
        recs.append([
            r["date_iso"], r["season"], r["ep_overall"], p["song"], p["artist"] or "",
            (r["performer"] or "A guest") if r["cameo"] else "Kelly Clarkson",
            1 if r["cameo"] else 0, p.get("duet") or r["duet"] or "", r["version"] or "",
            1 if r["rerun"] else 0, p["video_id"] or "",
            sources.index(src) if src in sources else -1,
            p.get("genre") or "Not listed", p.get("orig_year") or 0,
            p.get("views") or 0, p.get("duration") or 0,
        ])
GENRES = [g for g, _ in genres_seen.most_common()]
DECADES = sorted({(p.get("orig_year") or 0)//10*10
                  for r in rows for p in r["perfs"] if p.get("orig_year")})

DATA = json.dumps(recs, separators=(",", ":"), ensure_ascii=False)
GENRES_JSON = json.dumps(GENRES, ensure_ascii=False)
DECADES_JSON = json.dumps(DECADES)
SRC_JSON = json.dumps(sources, ensure_ascii=False)
SC_JSON = json.dumps(SEASON_COLOR)
ARCHIVE_URL = "https://claude.ai/code/artifact/5e11c4ba-11e2-4128-a1ad-31af1f13afea"

HTML = """<meta charset="utf-8">
<title>Kellyoke Data Explorer</title>
<meta name="description" content="Filter, sort and chart every Kellyoke performance by season, genre, decade and performer.">
<meta property="og:type" content="website">
<meta property="og:site_name" content="The Kellyoke Archive">
<meta property="og:url" content="https://kellyokes.netlify.app/explore">
<meta property="og:title" content="Kellyoke Data Explorer">
<meta property="og:description" content="Filter, sort and chart every Kellyoke performance by season, genre, decade and performer.">
<meta property="og:image" content="https://kellyokes.netlify.app/og-image.png">
<meta property="og:image:width" content="1200">
<meta property="og:image:height" content="630">
<meta property="og:image:alt" content="Every song she opened with. The Kelly Clarkson Show, 2019 to 2026.">
<meta name="twitter:card" content="summary_large_image">
__FONTS__
<style>__TOKENS__
.wrap { max-width:1200px; margin:0 auto; padding:0 22px 70px; }

.top { display:flex; flex-wrap:wrap; gap:18px; align-items:flex-end;
  justify-content:space-between; padding:52px 0 20px; border-bottom:2px solid var(--ink); }
h1 { font-family:"Big Shoulders Display",Chivo,sans-serif; font-weight:800;
  font-size:clamp(42px,7vw,86px); line-height:.86; margin:0; }
.top p { margin:10px 0 0; color:var(--ink-2); max-width:56ch; font-size:16px; }
.back { font-size:14px; font-weight:700; text-decoration:none; color:var(--sung);
  border-bottom:2px solid var(--sung); white-space:nowrap; }
.back:hover { background:var(--sung); color:var(--panel); }

.tiles { display:flex; flex-wrap:wrap; gap:0; margin:0; padding:20px 0 0; list-style:none;
  border-bottom:1px solid var(--rule); }
.tile { flex:1 1 118px; padding:0 16px 18px 0; }
.tile b { display:block; font-family:"Big Shoulders Display",Chivo,sans-serif;
  font-weight:700; font-size:32px; line-height:1; }
.tile span { font-size:12.5px; color:var(--ink-2); }

.filters { position:sticky; top:0; z-index:30; background:var(--ground);
  padding:12px 0 11px; border-bottom:1px solid var(--rule); margin-bottom:22px; }
.frow { display:flex; flex-wrap:wrap; gap:8px; align-items:center; }
.frow + .frow { margin-top:8px; }
.flabel { font-size:13px; color:var(--unsung); margin-right:2px; }
.search { flex:1 1 220px; min-width:180px; }
.search input { width:100%; font:inherit; color:var(--ink); background:var(--panel);
  border:1px solid var(--rule); border-radius:var(--radius); padding:8px 12px; }
.search input::placeholder { color:var(--unsung); }
.search svg { display:none; }
.chip, .seg button, .sel, .ghost { font:inherit; font-size:13px; font-weight:500;
  cursor:pointer; color:var(--ink-2); background:var(--panel);
  border:1px solid var(--rule); border-radius:var(--radius); padding:7px 11px;
  display:inline-flex; align-items:center; gap:6px; }
.chip i { width:9px; height:9px; border-radius:2px; background:var(--sc); display:block; }
.chip[aria-pressed="true"] { background:var(--ink); color:var(--ground); border-color:var(--ink); }
.seg { display:inline-flex; border:1px solid var(--rule); border-radius:var(--radius);
  overflow:hidden; background:var(--panel); }
.seg button { border:0; border-radius:0; }
.seg button + button { border-left:1px solid var(--rule); }
.seg button[aria-pressed="true"] { background:var(--ink); color:var(--ground); }
.ghost { border-style:dashed; background:transparent; }
.ghost:hover { background:var(--panel-2); color:var(--ink); }
.status { font-size:13px; color:var(--unsung); margin-top:9px; }

.charts { display:grid; grid-template-columns:repeat(auto-fit,minmax(330px,1fr));
  gap:16px; margin-bottom:24px; }
.card { background:var(--panel); border:1px solid var(--rule);
  border-top:3px solid var(--sung); border-radius:0 0 var(--radius) var(--radius);
  padding:16px 18px 18px; min-width:0; }
.card.wide { grid-column:1 / -1; }
.card h2 { font-size:16px; font-weight:700; margin:0 0 2px; }
.card .sub { font-size:12.5px; color:var(--unsung); margin:0 0 14px; }
.legend { display:flex; gap:16px; margin:0 0 10px; font-size:12.5px; color:var(--ink-2); }
.legend span { display:inline-flex; align-items:center; gap:6px; }
.legend i { width:11px; height:11px; border-radius:2px; display:block; }
svg { display:block; width:100%; height:auto; overflow:visible; }
.axis { fill:var(--unsung); font-family:Chivo,sans-serif; font-size:10.5px; }
.vlab { fill:var(--ink-2); font-family:Chivo,sans-serif; font-size:10.5px;
  font-variant-numeric:tabular-nums; }
.gridline { stroke:var(--rule-soft); stroke-width:1; }
.mark { cursor:default; }
.mark:hover { opacity:.8; }

#tip { position:fixed; z-index:60; pointer-events:none; opacity:0; transition:opacity .09s;
  background:var(--ink); color:var(--ground); font-size:12.5px; line-height:1.35;
  padding:7px 10px; border-radius:var(--radius); max-width:250px; }
#tip b { font-weight:700; }

.tablecard { background:var(--panel); border:1px solid var(--rule);
  border-top:3px solid var(--sung); }
.tscroll { overflow-x:auto; max-height:74vh; overflow-y:auto; }
table { border-collapse:collapse; width:100%; font-size:13.5px; }
thead th { position:sticky; top:0; z-index:2; background:var(--panel);
  text-align:left; font-weight:700; font-size:12.5px; color:var(--ink);
  padding:10px 13px; border-bottom:2px solid var(--rule); white-space:nowrap;
  cursor:pointer; user-select:none; }
thead th:hover { color:var(--sung); }
thead th .arw { color:var(--unsung); font-size:9px; }
thead th[aria-sort] { color:var(--sung); }
tbody td { padding:9px 13px; border-bottom:1px solid var(--rule-soft); vertical-align:top; }
tbody tr:hover { background:var(--panel-2); }
td.num, th.num { font-variant-numeric:tabular-nums; white-space:nowrap; }
td.song { font-weight:700; min-width:165px; }
td.who { white-space:nowrap; }
.sdot { display:inline-block; width:9px; height:9px; border-radius:2px; margin-right:7px; }
.pill { display:inline-block; font-size:12px; color:var(--unsung); white-space:nowrap; }
.pill + .pill { margin-left:9px; }
.pill--cameo { color:var(--guest); }
.pill--classic { color:var(--sung); }
.pill--genre { color:var(--ink-2); }
.yt { display:inline-block; text-decoration:none; font-weight:700; font-size:13px;
  color:var(--sung); border-bottom:2px solid var(--sung); white-space:nowrap; }
.yt:hover { background:var(--sung); color:var(--panel); }
.yt .tri { display:none; }
.none { color:var(--unsung); font-size:12.5px; }
.tfoot { padding:12px 15px; border-top:1px solid var(--rule); font-size:13px;
  color:var(--unsung); display:flex; flex-wrap:wrap; gap:12px; align-items:center; }
.csvbox { width:100%; height:170px; margin-top:10px; font-family:ui-monospace,monospace;
  font-size:11.5px; background:var(--panel-2); color:var(--ink);
  border:1px solid var(--rule); border-radius:var(--radius); padding:10px; }
.empty { padding:44px 15px; color:var(--unsung); }
</style>

<div class="wrap">
  <header class="top">
    <div>
      <h1>Kellyoke Data Explorer</h1>
      <p>Slice the full record of every Kellyoke: 1,245 performances over seven seasons.
         Filter and sort below; the charts follow whatever you have selected.</p>
    </div>
    <a class="backlink" id="backlink" href="__ARCHIVE__">Back to the archive &rarr;</a>
  </header>

  <div class="tiles" id="tiles"></div>

  <div class="filters">
    <div class="frow">
      <div class="search">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor"
             stroke-width="2.4" aria-hidden="true"><circle cx="11" cy="11" r="7"></circle>
          <path d="M20 20l-3.5-3.5"></path></svg>
        <input id="q" type="search" placeholder="Song, artist, performer, year&hellip;"
               autocomplete="off" aria-label="Search the dataset">
      </div>
      <span class="flabel">Season</span>
      <div id="chips" style="display:flex;flex-wrap:wrap;gap:6px"></div>
    </div>
    <div class="frow">
      <span class="flabel">Sung by</span>
      <div class="seg" id="segWho" role="group" aria-label="Filter by performer">
        <button data-v="all" aria-pressed="true">Everyone</button>
        <button data-v="kelly" aria-pressed="false">Kelly</button>
        <button data-v="guest" aria-pressed="false">Guest</button>
      </div>
      <span class="flabel">Video</span>
      <div class="seg" id="segVid" role="group" aria-label="Filter by video availability">
        <button data-v="all" aria-pressed="true">Any</button>
        <button data-v="yes" aria-pressed="false">Linked</button>
        <button data-v="no" aria-pressed="false">Missing</button>
      </div>
      <span class="flabel">Genre</span>
      <select id="selGenre" class="sel" aria-label="Filter by genre"></select>
      <span class="flabel">Original</span>
      <select id="selDecade" class="sel" aria-label="Filter by decade of the original"></select>
      <button class="chip" id="fDuet" aria-pressed="false">Duets</button>
      <button class="chip" id="fRerun" aria-pressed="false">Reruns</button>
      <button class="chip" id="fClassic" aria-pressed="false">Kelly's own songs</button>
      <button class="ghost" id="reset">Reset</button>
    </div>
    <div class="status" id="status"></div>
  </div>

  <div class="charts">
    <div class="card wide">
      <h2>Performances per season</h2>
      <p class="sub">Guest Cameo-oke only becomes a regular feature in season 6.</p>
      <div class="legend">
        <span><i style="background:var(--sung)"></i>Kelly</span>
        <span><i style="background:var(--guest)"></i>A guest</span>
      </div>
      <div id="chSeason"></div>
    </div>
    <div class="card wide">
      <h2>Covers per month</h2>
      <p class="sub">The run of the show, hiatus gaps and all.</p>
      <div id="chTime"></div>
    </div>
    <div class="card">
      <h2>Genre of the original</h2>
      <p class="sub">From each song's Wikipedia infobox, folded into families.</p>
      <div id="chGenre"></div>
    </div>
    <div class="card">
      <h2>When the original came out</h2>
      <p class="sub">How far back each cover reaches.</p>
      <div id="chDecade"></div>
    </div>
    <div class="card">
      <h2>Most covered artists</h2>
      <p class="sub">Excludes Kelly's own catalog.</p>
      <div id="chArtists"></div>
    </div>
    <div class="card">
      <h2>Where the video comes from</h2>
      <p class="sub">The show keeps only a fraction of the segment online.</p>
      <div id="chSource"></div>
    </div>
  </div>

  <div class="tablecard">
    <div class="tscroll">
      <table id="tbl">
        <thead><tr id="thead"></tr></thead>
        <tbody id="tbody"></tbody>
      </table>
      <p class="empty hidden" id="empty" hidden>Nothing matches those filters.</p>
    </div>
    <div class="tfoot">
      <span id="tcount"></span>
      <button class="ghost" id="csvBtn">Copy these rows as CSV</button>
      <span id="csvMsg"></span>
    </div>
    <div style="padding:0 14px 14px" id="csvWrap" hidden>
      <textarea class="csvbox" id="csvBox" readonly></textarea>
    </div>
  </div>
</div>
<div id="tip" role="status" aria-live="polite"></div>

<script>
(function () {
  var DATA = __DATA__;
  var SOURCES = __SOURCES__;
  var SC = __SEASONCOLORS__;
  var D_DATE=0,D_S=1,D_EP=2,D_SONG=3,D_ART=4,D_WHO=5,D_CAMEO=6,D_DUET=7,
      D_VER=8,D_RERUN=9,D_VID=10,D_SRC=11,D_GEN=12,D_YEAR=13,D_VIEWS=14,D_DUR=15;
  var GENRES = __GENRES__, DECADES = __DECADES__;

  // The archive is a sibling file everywhere except the Claude artifact host,
  // where the two pages are separate artifacts with unrelated URLs. So default
  // to the relative link and keep the absolute one only on claude.ai. This
  // covers file://, localhost, and kellyokes.netlify.app alike.
  var bl=document.getElementById('backlink');
  if (!/(^|\\.)claude\\.ai$/.test(location.hostname)) {
    bl.setAttribute('href','index.html');
  }

  function norm(s){ return (s||'').toLowerCase().normalize('NFKD')
    .replace(/[\\u0300-\\u036f]/g,'').replace(/[^a-z0-9 ]+/g,' ').replace(/\\s+/g,' ').trim(); }

  DATA.forEach(function (r) {
    r.key = norm([r[D_DATE],r[D_SONG],r[D_ART],r[D_WHO],r[D_DUET],r[D_VER],
                  r[D_GEN],r[D_YEAR]||''].join(' '));
    r.classic = r[D_CAMEO]===0 && /kelly clarkson/i.test(r[D_ART]);
  });

  var state={q:'',seasons:new Set(),who:'all',vid:'all',duet:false,rerun:false,classic:false,
             genre:'',decade:'',sort:'date',dir:1};

  function filtered() {
    var terms=norm(state.q).split(' ').filter(Boolean);
    return DATA.filter(function (r) {
      if (state.seasons.size && !state.seasons.has(r[D_S])) return false;
      if (state.who==='kelly' && r[D_CAMEO]) return false;
      if (state.who==='guest' && !r[D_CAMEO]) return false;
      if (state.vid==='yes' && !r[D_VID]) return false;
      if (state.vid==='no' && r[D_VID]) return false;
      if (state.duet && !r[D_DUET]) return false;
      if (state.rerun && !r[D_RERUN]) return false;
      if (state.classic && !r.classic) return false;
      if (state.genre && r[D_GEN]!==state.genre) return false;
      if (state.decade && Math.floor((r[D_YEAR]||0)/10)*10 !== +state.decade) return false;
      for (var i=0;i<terms.length;i++) if (r.key.indexOf(terms[i])===-1) return false;
      return true;
    });
  }

  // ---------- tooltip ----------
  var tip=document.getElementById('tip');
  function showTip(html,ev){ tip.innerHTML=html; tip.style.opacity='1';
    var x=ev.clientX+13, y=ev.clientY+13;
    if (x+250>window.innerWidth) x=ev.clientX-250;
    if (y+70>window.innerHeight) y=ev.clientY-64;
    tip.style.left=x+'px'; tip.style.top=y+'px'; }
  function hideTip(){ tip.style.opacity='0'; }
  function bindTip(el,html){
    el.addEventListener('mousemove',function(ev){ showTip(html,ev); });
    el.addEventListener('mouseleave',hideTip);
  }
  var svgNS='http://www.w3.org/2000/svg';
  function el(n,at){ var e=document.createElementNS(svgNS,n);
    for (var k in at) e.setAttribute(k,at[k]); return e; }

  // ---------- chart: stacked bars per season ----------
  function chartSeason(rows) {
    var host=document.getElementById('chSeason'); host.textContent='';
    var by={}; for (var s=1;s<=7;s++) by[s]={k:0,g:0};
    rows.forEach(function(r){ by[r[D_S]][r[D_CAMEO]?'g':'k']++; });
    var max=0; for (s=1;s<=7;s++) max=Math.max(max,by[s].k+by[s].g);
    if (!max) max=1;
    var W=1000,H=210,PL=34,PR=8,PT=14,PB=26,n=7;
    var iw=W-PL-PR, ih=H-PT-PB, band=iw/n, bw=Math.min(84,band*0.56);
    var svg=el('svg',{viewBox:'0 0 '+W+' '+H,role:'img',
      'aria-label':'Performances per season, split by who sang'});
    [0,.25,.5,.75,1].forEach(function(f){
      var y=PT+ih-ih*f;
      svg.appendChild(el('line',{x1:PL,x2:W-PR,y1:y,y2:y,class:'gridline'}));
      var t=el('text',{x:PL-7,y:y+3,class:'axis','text-anchor':'end'});
      t.textContent=Math.round(max*f); svg.appendChild(t);
    });
    for (s=1;s<=7;s++) {
      var d=by[s], cx=PL+band*(s-1)+band/2, tot=d.k+d.g;
      var hk=ih*(d.k/max), hg=ih*(d.g/max);
      var yk=PT+ih-hk;
      if (d.k>0) {
        var rk=el('rect',{x:cx-bw/2,y:yk,width:bw,height:Math.max(hk,1),rx:4,
          fill:'var(--sung)',class:'mark'});
        bindTip(rk,'<b>Season '+s+'</b><br>'+d.k+' sung by Kelly'); svg.appendChild(rk);
      }
      if (d.g>0) {
        // 2px surface gap between stacked segments
        var rg=el('rect',{x:cx-bw/2,y:yk-hg-2,width:bw,height:Math.max(hg,1),rx:4,
          fill:'var(--guest)',class:'mark'});
        bindTip(rg,'<b>Season '+s+'</b><br>'+d.g+' sung by a guest'); svg.appendChild(rg);
      }
      var lt=el('text',{x:cx,y:PT+ih+16,class:'axis','text-anchor':'middle'});
      lt.textContent='S'+s; svg.appendChild(lt);
      var vt=el('text',{x:cx,y:yk-hg-(d.g?8:4),class:'vlab','text-anchor':'middle'});
      vt.textContent=tot; svg.appendChild(vt);
    }
    host.appendChild(svg);
  }

  // ---------- chart: monthly line ----------
  function chartTime(rows) {
    var host=document.getElementById('chTime'); host.textContent='';
    var by={}, keys=[];
    // full month spine so hiatus gaps read as zero, not as missing
    var start=new Date(2019,8,1), end=new Date(2026,7,1);
    for (var d=new Date(start); d<=end; d.setMonth(d.getMonth()+1)) {
      var k=d.getFullYear()+'-'+String(d.getMonth()+1).padStart(2,'0');
      by[k]=0; keys.push(k);
    }
    rows.forEach(function(r){ var k=r[D_DATE].slice(0,7); if (k in by) by[k]++; });
    var max=Math.max.apply(null,keys.map(function(k){return by[k];})) || 1;
    var W=1000,H=190,PL=34,PR=8,PT=12,PB=28;
    var iw=W-PL-PR, ih=H-PT-PB, step=iw/(keys.length-1);
    var svg=el('svg',{viewBox:'0 0 '+W+' '+H,role:'img','aria-label':'Covers per month'});
    [0,.5,1].forEach(function(f){
      var y=PT+ih-ih*f;
      svg.appendChild(el('line',{x1:PL,x2:W-PR,y1:y,y2:y,class:'gridline'}));
      var t=el('text',{x:PL-7,y:y+3,class:'axis','text-anchor':'end'});
      t.textContent=Math.round(max*f); svg.appendChild(t);
    });
    var pts=keys.map(function(k,i){ return [PL+step*i, PT+ih-ih*(by[k]/max)]; });
    var area='M'+PL+','+(PT+ih)+' '+pts.map(function(p){return p[0]+','+p[1];}).join(' ')+
             ' '+(PL+step*(keys.length-1))+','+(PT+ih)+'Z';
    svg.appendChild(el('path',{d:area,fill:'var(--sung)','fill-opacity':'.16',stroke:'none'}));
    svg.appendChild(el('path',{d:'M'+pts.map(function(p){return p[0]+','+p[1];}).join(' L'),
      fill:'none',stroke:'var(--sung)','stroke-width':2,'stroke-linejoin':'round'}));
    keys.forEach(function(k,i){
      if (k.slice(5)==='01') {
        var t=el('text',{x:pts[i][0],y:PT+ih+16,class:'axis','text-anchor':'middle'});
        t.textContent=k.slice(0,4); svg.appendChild(t);
      }
      var hit=el('rect',{x:pts[i][0]-step/2,y:PT,width:step,height:ih,fill:'transparent',class:'mark'});
      var dt=new Date(k+'-01T00:00:00');
      bindTip(hit,'<b>'+dt.toLocaleString('en-US',{month:'long',year:'numeric'})+'</b><br>'+
        by[k]+(by[k]===1?' cover':' covers'));
      svg.appendChild(hit);
    });
    host.appendChild(svg);
  }

  // ---------- chart: top artists ----------
  function chartArtists(rows) {
    var host=document.getElementById('chArtists'); host.textContent='';
    var c={};
    rows.forEach(function(r){
      var a=r[D_ART]; if (!a || /kelly clarkson/i.test(a)) return;
      c[a]=(c[a]||0)+1;
    });
    var top=Object.keys(c).map(function(k){return [k,c[k]];})
      .sort(function(x,y){ return y[1]-x[1] || x[0].localeCompare(y[0]); }).slice(0,10);
    if (!top.length) { host.innerHTML='<p class="none">No artists in this selection.</p>'; return; }
    var max=top[0][1], rowH=25, W=520, H=top.length*rowH+8, LW=136;
    var svg=el('svg',{viewBox:'0 0 '+W+' '+H,role:'img','aria-label':'Most covered artists'});
    top.forEach(function(t,i){
      var y=i*rowH+4, bw=(W-LW-34)*(t[1]/max);
      var lab=el('text',{x:LW-8,y:y+13,class:'axis','text-anchor':'end'});
      lab.textContent=t[0].length>20?t[0].slice(0,19)+'\\u2026':t[0];
      svg.appendChild(lab);
      var b=el('rect',{x:LW,y:y+2,width:Math.max(bw,2),height:14,rx:4,
        fill:'var(--sung)',class:'mark'});
      bindTip(b,'<b>'+t[0]+'</b><br>'+t[1]+(t[1]===1?' cover':' covers'));
      svg.appendChild(b);
      var v=el('text',{x:LW+Math.max(bw,2)+7,y:y+13,class:'vlab'});
      v.textContent=t[1]; svg.appendChild(v);
    });
    host.appendChild(svg);
  }

  // ---------- chart: source breakdown ----------
  function chartSource(rows) {
    var host=document.getElementById('chSource'); host.textContent='';
    var c={}, none=0;
    rows.forEach(function(r){
      if (r[D_SRC]<0 || !r[D_VID]) { none++; return; }
      var s=SOURCES[r[D_SRC]]; c[s]=(c[s]||0)+1;
    });
    var list=Object.keys(c).map(function(k){return [k,c[k]];}).sort(function(x,y){return y[1]-x[1];});
    if (none) list.push(['No copy found',none]);
    if (!list.length) { host.innerHTML='<p class="none">Nothing in this selection.</p>'; return; }
    var max=list[0][1], rowH=25, W=520, H=list.length*rowH+8, LW=168;
    var svg=el('svg',{viewBox:'0 0 '+W+' '+H,role:'img','aria-label':'Video source breakdown'});
    list.forEach(function(t,i){
      var y=i*rowH+4, bw=(W-LW-34)*(t[1]/max), isNone=t[0]==='No copy found';
      var lab=el('text',{x:LW-8,y:y+13,class:'axis','text-anchor':'end'});
      lab.textContent=t[0].length>22?t[0].slice(0,21)+'\\u2026':t[0];
      svg.appendChild(lab);
      var b=el('rect',{x:LW,y:y+2,width:Math.max(bw,2),height:14,rx:4,
        fill:isNone?'var(--unsung)':'var(--sung)','fill-opacity':isNone?'.45':'1',class:'mark'});
      bindTip(b,'<b>'+t[0]+'</b><br>'+t[1]+' of '+rows.length);
      svg.appendChild(b);
      var v=el('text',{x:LW+Math.max(bw,2)+7,y:y+13,class:'vlab'});
      v.textContent=t[1]; svg.appendChild(v);
    });
    host.appendChild(svg);
  }

  // ---------- chart: genre families ----------
  function chartGenre(rows) {
    var host=document.getElementById('chGenre'); host.textContent='';
    var c={};
    rows.forEach(function(r){ c[r[D_GEN]]=(c[r[D_GEN]]||0)+1; });
    var list=Object.keys(c).map(function(k){return [k,c[k]];})
      .sort(function(x,y){ return y[1]-x[1] || x[0].localeCompare(y[0]); });
    if (!list.length) { host.innerHTML='<p class="none">Nothing in this selection.</p>'; return; }
    if (list.length>12) {
      var tail=list.slice(11).reduce(function(a,b){return a+b[1];},0);
      list=list.slice(0,11); list.push(['Other genres',tail]);
    }
    var max=list[0][1], rowH=23, W=520, H=list.length*rowH+8, LW=112;
    var svg=el('svg',{viewBox:'0 0 '+W+' '+H,role:'img','aria-label':'Genre of the original'});
    list.forEach(function(t,i){
      var y=i*rowH+4, bw=(W-LW-38)*(t[1]/max), quiet=(t[0]==='Not listed');
      var lab=el('text',{x:LW-8,y:y+12,class:'axis','text-anchor':'end'});
      lab.textContent=t[0]; svg.appendChild(lab);
      var b=el('rect',{x:LW,y:y+2,width:Math.max(bw,2),height:13,rx:4,
        fill:quiet?'var(--unsung)':'var(--sung)','fill-opacity':quiet?'.45':'1',class:'mark'});
      bindTip(b,'<b>'+t[0]+'</b><br>'+t[1]+' of '+rows.length+
        ' ('+Math.round(t[1]/rows.length*100)+'%)');
      svg.appendChild(b);
      var v=el('text',{x:LW+Math.max(bw,2)+7,y:y+12,class:'vlab'});
      v.textContent=t[1]; svg.appendChild(v);
    });
    host.appendChild(svg);
  }

  // ---------- chart: decade of the original ----------
  function chartDecade(rows) {
    var host=document.getElementById('chDecade'); host.textContent='';
    var by={}; DECADES.forEach(function(d){ by[d]=0; });
    var known=0;
    rows.forEach(function(r){
      var y=r[D_YEAR]; if (!y) return;
      var d=Math.floor(y/10)*10; if (d in by) { by[d]++; known++; }
    });
    if (!known) { host.innerHTML='<p class="none">No release years in this selection.</p>'; return; }
    var ks=DECADES, max=Math.max.apply(null,ks.map(function(d){return by[d];}))||1;
    var W=520,H=200,PL=30,PR=8,PT=14,PB=42;
    var iw=W-PL-PR, ih=H-PT-PB, band=iw/ks.length, bw=Math.min(38,band*0.62);
    var svg=el('svg',{viewBox:'0 0 '+W+' '+H,role:'img','aria-label':'Decade of the original release'});
    [0,.5,1].forEach(function(f){
      var y=PT+ih-ih*f;
      svg.appendChild(el('line',{x1:PL,x2:W-PR,y1:y,y2:y,class:'gridline'}));
      var t=el('text',{x:PL-6,y:y+3,class:'axis','text-anchor':'end'});
      t.textContent=Math.round(max*f); svg.appendChild(t);
    });
    ks.forEach(function(d,i){
      var cx=PL+band*i+band/2, h=ih*(by[d]/max), y=PT+ih-h;
      var b=el('rect',{x:cx-bw/2,y:y,width:bw,height:Math.max(h,1),rx:4,
        fill:'var(--sung)',class:'mark'});
      bindTip(b,'<b>'+d+'s</b><br>'+by[d]+(by[d]===1?' cover':' covers'));
      svg.appendChild(b);
      var lt=el('text',{x:cx,y:PT+ih+15,class:'axis','text-anchor':'middle'});
      lt.textContent="'"+String(d).slice(2); svg.appendChild(lt);
      if (by[d]) {
        var v=el('text',{x:cx,y:y-5,class:'vlab','text-anchor':'middle'});
        v.textContent=by[d]; svg.appendChild(v);
      }
    });
    var note=el('text',{x:PL,y:H-8,class:'axis'});
    note.textContent=known+' of '+rows.length+' have a known release year';
    svg.appendChild(note);
    host.appendChild(svg);
  }

  // ---------- tiles ----------
  function tiles(rows) {
    var kelly=rows.filter(function(r){return !r[D_CAMEO];}).length,
        guest=rows.length-kelly,
        vid=rows.filter(function(r){return r[D_VID];}).length,
        songs=new Set(rows.map(function(r){return r[D_SONG].toLowerCase();})).size,
        arts=new Set(rows.filter(function(r){return r[D_ART];})
                         .map(function(r){return r[D_ART].toLowerCase();})).size,
        eps=new Set(rows.map(function(r){return r[D_DATE];})).size;
    var pct=rows.length?Math.round(vid/rows.length*1000)/10:0;
    var yrs=rows.map(function(r){return r[D_YEAR];}).filter(Boolean).sort();
    var gens=new Set(rows.map(function(r){return r[D_GEN];})
                         .filter(function(g){return g!=='Not listed';})).size;
    var span=yrs.length?(yrs[0]+'\u2013'+yrs[yrs.length-1]):'\u2014';
    var t=[['Performances',rows.length],['By Kelly',kelly],['By a guest',guest],
           ['Distinct songs',songs],['Distinct artists',arts],['Genres',gens],
           ['Originals span',span],['Episodes',eps],
           ['Linked to video',vid],['Coverage',pct+'%']];
    document.getElementById('tiles').innerHTML=t.map(function(x){
      return '<div class="tile"><b>'+(typeof x[1]==='number'?x[1].toLocaleString():x[1])+
             '</b><span>'+x[0]+'</span></div>'; }).join('');
  }

  // ---------- table ----------
  var COLS=[
    {k:'date', t:'Air date', cls:'num'},
    {k:'season', t:'S', cls:'num'},
    {k:'ep', t:'Ep', cls:'num'},
    {k:'song', t:'Song', cls:'song'},
    {k:'artist', t:'Original artist'},
    {k:'genre', t:'Genre'},
    {k:'year', t:'Orig.', cls:'num'},
    {k:'who', t:'Sung by', cls:'who'},
    {k:'tags', t:'Notes', sortable:false},
    {k:'source', t:'Video source'},
    {k:'views', t:'Views', cls:'num'},
    {k:'link', t:'', sortable:false}
  ];
  function val(r,k){
    switch(k){
      case 'date': return r[D_DATE];
      case 'season': return r[D_S];
      case 'ep': return parseInt(r[D_EP],10)||0;
      case 'song': return r[D_SONG].toLowerCase();
      case 'artist': return r[D_ART].toLowerCase();
      case 'who': return r[D_WHO].toLowerCase();
      case 'genre': return r[D_GEN]==='Not listed'?'zzz':r[D_GEN].toLowerCase();
      case 'year': return r[D_YEAR]||99999;
      case 'views': return -(r[D_VIEWS]||0);
      case 'source': return r[D_SRC]<0?'zzz':SOURCES[r[D_SRC]].toLowerCase();
      default: return '';
    }
  }
  function head(){
    document.getElementById('thead').innerHTML=COLS.map(function(c){
      var on=state.sort===c.k;
      return '<th class="'+(c.cls==='num'?'num':'')+'" data-k="'+c.k+'"'+
        (c.sortable===false?' style="cursor:default"':'')+
        (on?' aria-sort="'+(state.dir>0?'ascending':'descending')+'"':'')+'>'+
        c.t+(c.sortable===false?'':' <span class="arw">'+(on?(state.dir>0?'\\u25b2':'\\u25bc'):'\\u25b4\\u25be')+'</span>')+'</th>';
    }).join('');
    [].forEach.call(document.querySelectorAll('#thead th'),function(th){
      var k=th.dataset.k, col=COLS.filter(function(c){return c.k===k;})[0];
      if (!col || col.sortable===false) return;
      th.addEventListener('click',function(){
        if (state.sort===k) state.dir=-state.dir; else { state.sort=k; state.dir=1; }
        render();
      });
    });
  }
  function fmtViews(n){
    if (n>=1e6) return (n/1e6).toFixed(n>=1e7?0:1)+'M';
    if (n>=1e3) return Math.round(n/1e3)+'K';
    return String(n);
  }
  function esc(s){ return (s||'').replace(/[&<>"]/g,function(c){
    return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]; }); }

  function rowHTML(r){
    var tags='';
    if (r[D_CAMEO]) tags+='<span class="pill pill--cameo">Cameo-oke</span> ';
    if (r.classic) tags+='<span class="pill pill--classic">Classic</span> ';
    if (r[D_DUET]) tags+='<span class="pill">with '+esc(r[D_DUET])+'</span> ';
    if (r[D_VER]) tags+='<span class="pill">'+esc(r[D_VER])+'</span> ';
    if (r[D_RERUN]) tags+='<span class="pill">Rerun</span> ';
    var src=r[D_SRC]>=0&&r[D_VID]?esc(SOURCES[r[D_SRC]]):'<span class="none">none found</span>';
    var link=r[D_VID]
      ? '<a class="yt" href="https://www.youtube.com/watch?v='+r[D_VID]+
        '" target="_blank" rel="noopener noreferrer"><span class="tri"></span>Watch</a>' : '';
    return '<tr><td class="num">'+r[D_DATE]+'</td>'+
      '<td class="num"><span class="sdot" style="background:'+SC[r[D_S]]+'"></span>'+r[D_S]+'</td>'+
      '<td class="num">'+esc(r[D_EP])+'</td>'+
      '<td class="song">'+esc(r[D_SONG])+'</td>'+
      '<td>'+(esc(r[D_ART])||'<span class="none">&mdash;</span>')+'</td>'+
      '<td>'+(r[D_GEN]==='Not listed'?'<span class="none">not listed</span>':
              '<span class="pill pill--genre">'+esc(r[D_GEN])+'</span>')+'</td>'+
      '<td class="num">'+(r[D_YEAR]||'<span class="none">&mdash;</span>')+'</td>'+
      '<td class="who">'+esc(r[D_WHO])+'</td>'+
      '<td>'+(tags||'')+'</td><td>'+src+'</td>'+
      '<td class="num">'+(r[D_VIEWS]?fmtViews(r[D_VIEWS]):'<span class="none">&mdash;</span>')+'</td>'+
      '<td>'+link+'</td></tr>';
  }

  var current=[];
  function render() {
    var rows=filtered();
    rows.sort(function(a,b){
      var x=val(a,state.sort), y=val(b,state.sort);
      if (x<y) return -state.dir; if (x>y) return state.dir;
      return a[D_DATE]<b[D_DATE]?-1:1;
    });
    current=rows;
    tiles(rows); chartSeason(rows); chartTime(rows); chartGenre(rows);
    chartDecade(rows); chartArtists(rows); chartSource(rows);
    head();
    document.getElementById('tbody').innerHTML=rows.map(rowHTML).join('');
    document.getElementById('empty').hidden=rows.length>0;
    document.getElementById('tcount').textContent=
      rows.length.toLocaleString()+' of '+DATA.length.toLocaleString()+' rows';
    document.getElementById('status').textContent = rows.length===DATA.length
      ? 'Showing the whole dataset \\u2014 '+DATA.length.toLocaleString()+' performances'
      : 'Filtered to '+rows.length.toLocaleString()+' of '+DATA.length.toLocaleString()+' performances';
  }

  // ---------- controls ----------
  var chips=document.getElementById('chips');
  chips.innerHTML=[1,2,3,4,5,6,7].map(function(s){
    return '<button class="chip" data-s="'+s+'" style="--sc:'+SC[s]+'" aria-pressed="false"><i></i>S'+s+'</button>';
  }).join('');
  [].forEach.call(chips.children,function(b){
    b.addEventListener('click',function(){
      var s=+b.dataset.s, on=b.getAttribute('aria-pressed')==='true';
      b.setAttribute('aria-pressed',on?'false':'true');
      if (on) state.seasons.delete(s); else state.seasons.add(s);
      render();
    });
  });
  var gsel=document.getElementById('selGenre');
  gsel.innerHTML='<option value="">All genres</option>'+
    GENRES.map(function(g){ return '<option value="'+g.replace(/"/g,'&quot;')+'">'+g+'</option>'; }).join('');
  gsel.addEventListener('change',function(){ state.genre=gsel.value; render(); });
  var dsel=document.getElementById('selDecade');
  dsel.innerHTML='<option value="">Any decade</option>'+
    DECADES.map(function(d){ return '<option value="'+d+'">'+d+'s</option>'; }).join('');
  dsel.addEventListener('change',function(){ state.decade=dsel.value; render(); });

  function seg(id,key){
    var g=document.getElementById(id);
    [].forEach.call(g.children,function(b){
      b.addEventListener('click',function(){
        [].forEach.call(g.children,function(o){ o.setAttribute('aria-pressed','false'); });
        b.setAttribute('aria-pressed','true'); state[key]=b.dataset.v; render();
      });
    });
  }
  seg('segWho','who'); seg('segVid','vid');
  function tog(id,key){
    var b=document.getElementById(id);
    b.addEventListener('click',function(){
      state[key]=!state[key]; b.setAttribute('aria-pressed',state[key]?'true':'false'); render();
    });
  }
  tog('fDuet','duet'); tog('fRerun','rerun'); tog('fClassic','classic');
  var qi=document.getElementById('q'), t=null;
  qi.addEventListener('input',function(){ clearTimeout(t);
    t=setTimeout(function(){ state.q=qi.value; render(); },140); });
  document.getElementById('reset').addEventListener('click',function(){
    state={q:'',seasons:new Set(),who:'all',vid:'all',duet:false,rerun:false,classic:false,
           genre:'',decade:'',sort:'date',dir:1};
    qi.value=''; gsel.value=''; dsel.value='';
    [].forEach.call(document.querySelectorAll('.chip'),function(b){ b.setAttribute('aria-pressed','false'); });
    ['segWho','segVid'].forEach(function(id){
      [].forEach.call(document.getElementById(id).children,function(b,i){
        b.setAttribute('aria-pressed',i===0?'true':'false'); });
    });
    document.getElementById('csvWrap').hidden=true;
    document.getElementById('csvMsg').textContent='';
    render();
  });

  // ---------- CSV ----------
  document.getElementById('csvBtn').addEventListener('click',function(){
    var head=['air_date','season','episode','song','original_artist','genre',
              'original_release_year','sung_by','is_cameo','duet_with','version_covered',
              'rerun','video_url','video_source','video_views','video_seconds'];
    var lines=[head.join(',')].concat(current.map(function(r){
      return [r[D_DATE],r[D_S],r[D_EP],r[D_SONG],r[D_ART],
              r[D_GEN]==='Not listed'?'':r[D_GEN], r[D_YEAR]||'', r[D_WHO],
              r[D_CAMEO]?'yes':'no',r[D_DUET],r[D_VER],r[D_RERUN]?'yes':'no',
              r[D_VID]?'https://www.youtube.com/watch?v='+r[D_VID]:'',
              r[D_SRC]>=0&&r[D_VID]?SOURCES[r[D_SRC]]:'', r[D_VIEWS]||'', r[D_DUR]||'']
        .map(function(v){ v=String(v==null?'':v);
          return /[",\\n]/.test(v)?'"'+v.replace(/"/g,'""')+'"':v; }).join(',');
    }));
    var csv=lines.join('\\n');
    var box=document.getElementById('csvBox'), msg=document.getElementById('csvMsg');
    document.getElementById('csvWrap').hidden=false;
    box.value=csv; box.focus(); box.select();
    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(csv).then(
        function(){ msg.textContent=current.length.toLocaleString()+' rows copied to your clipboard.'; },
        function(){ msg.textContent='Select the text below and copy it.'; });
    } else { msg.textContent='Select the text below and copy it.'; }
  });

  render();
})();
</script>
"""

HTML = (HTML.replace("__DATA__", DATA)
            .replace("__SOURCES__", SRC_JSON)
            .replace("__SEASONCOLORS__", SC_JSON)
            .replace("__GENRES__", GENRES_JSON)
            .replace("__DECADES__", DECADES_JSON)
            .replace("__ARCHIVE__", ARCHIVE_URL)
            .replace("__FONTS__", FONTS)
            .replace("__TOKENS__", TOKENS.replace("{{","{").replace("}}","}")))

out = os.path.join(S, "explore.html")
open(out, "w").write(HTML)
if os.path.isdir(REPO):
    open(os.path.join(REPO, "explore.html"), "w").write(HTML)
print(f"wrote explore.html ({os.path.getsize(out)/1024:.0f} KB), {len(recs)} records")
