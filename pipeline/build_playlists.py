#!/usr/bin/env python3
"""The Kellyoke Playlists page.

Renders the instant-playlist links that playlists.py generates. These are
watch_videos URLs rather than real YouTube playlists: building real ones needs
OAuth and would cost roughly 59k quota units against a 10k daily default, so the
URL form is what makes this possible at all. YouTube honors at most 50 ids per
URL, which is why every season arrives in numbered parts.

Design follows the archive: ruled lines rather than cards, and the sung/unsung
fill wherever a proportion is being shown.
"""
import collections
import html
import json
import os

from design_tokens import SEASON_COLOR, FONTS, TOKENS, nav, nav_css, nav_js

S = os.path.dirname(os.path.abspath(__file__))
REPO = "/Users/chesterismay/repos/kellyoke"

pl = json.load(open(os.path.join(S, "playlists.json")))
rows = json.load(open(os.path.join(S, "matched.json")))
e = lambda t: html.escape(str(t or ""), quote=True)

TOKENS_CSS = TOKENS.replace("{{", "{").replace("}}", "}")

# season context, so a part is not just a number with no sense of when it was
by_season = collections.OrderedDict()
for r in rows:
    by_season.setdefault(r["season"], []).append(r)

season_meta = {}
for s, eps in by_season.items():
    playable = sum(1 for r in eps for p in r["perfs"]
                   if not r["cameo"] and p["video_id"])
    season_meta[s] = {
        "from": eps[0]["date_pretty"], "to": eps[-1]["date_pretty"],
        "playable": playable,
    }

total_videos = sum(p["n"] for p in pl["all"])


def parts_list(parts, label):
    """One row per playlist part: what it holds, and a link that opens it."""
    out = []
    for p in parts:
        out.append(
            f'<li class="row">'
            f'<span class="pn">Part {p["part"]}<b> of {p["of"]}</b></span>'
            f'<span class="pc">{p["n"]} videos</span>'
            f'<span class="right">'
            f'<a class="play" href="{e(p["url"])}" target="_blank" '
            f'rel="noopener noreferrer">Open in YouTube</a></span>'
            f'</li>')
    return f'<ul class="rows" aria-label="{e(label)}">{"".join(out)}</ul>'


seasons_html = []
for s, parts in sorted(pl["seasons"].items(), key=lambda kv: int(kv[0])):
    m = season_meta[int(s)]
    n = sum(p["n"] for p in parts)
    seasons_html.append(
        f'<section class="season" style="--sc:{SEASON_COLOR[int(s)]}">'
        f'<header class="sh">'
        f'<span class="sn">{e(s)}</span>'
        f'<span class="st">Season {e(s)}<b>{e(m["from"])} to {e(m["to"])}</b></span>'
        f'<span class="sm"><span class="smn">{n} videos</span>'
        f'<span class="smc">{len(parts)} parts</span></span>'
        f'</header>{parts_list(parts, f"Season {s} playlists")}</section>')

HTML = f"""<meta charset="utf-8">
<title>Kellyoke Playlists</title>
<meta name="description" content="Every Kellyoke as an instant YouTube playlist, by season or the whole run end to end.">
<meta property="og:type" content="website">
<meta property="og:site_name" content="The Kellyoke Archive">
<meta property="og:url" content="https://kellyokes.netlify.app/playlists">
<meta property="og:title" content="Kellyoke Playlists">
<meta property="og:description" content="Every Kellyoke as an instant YouTube playlist, by season or the whole run end to end.">
<meta property="og:image" content="https://kellyokes.netlify.app/og-image.png">
<meta property="og:image:width" content="1200">
<meta property="og:image:height" content="630">
<meta property="og:image:alt" content="Every song she opened with. The Kelly Clarkson Show, 2019 to 2026.">
<meta name="twitter:card" content="summary_large_image">
<meta name="viewport" content="width=device-width,initial-scale=1">
{FONTS}
<style>{TOKENS_CSS}
{nav_css()}
*,*::before,*::after {{ box-sizing:border-box; }}
body {{
  margin:0; background:var(--ground); color:var(--ink);
  font-family:Chivo,ui-sans-serif,system-ui,-apple-system,sans-serif;
  font-size:15px; line-height:1.5; font-variant-numeric:tabular-nums;
  -webkit-font-smoothing:antialiased;
}}
a {{ color:inherit; }}
:focus-visible {{ outline:2px solid var(--sung); outline-offset:2px; border-radius:3px; }}
::selection {{ background:var(--sung); color:var(--panel); }}
.page {{ max-width:1000px; margin:0 auto; padding:0 22px 80px; }}

.hero {{ padding:26px 0 30px; border-bottom:2px solid var(--ink); }}
.hero h1 {{
  font-family:"Big Shoulders Display",Chivo,sans-serif; font-weight:800;
  font-size:clamp(46px,9vw,104px); line-height:.86; margin:0 0 18px;
}}
.hero .sub {{ font-size:18px; line-height:1.45; max-width:60ch; margin:0; color:var(--ink-2); }}
.hero .sub b {{ color:var(--ink); font-weight:700; }}

.season {{ margin:44px 0 0; }}
.sh {{ display:flex; align-items:center; gap:16px; padding:0 0 12px;
  border-bottom:2px solid var(--sc); }}
.sn {{ font-family:"Big Shoulders Display",Chivo,sans-serif; font-weight:800;
  font-size:60px; line-height:.8; color:var(--sc); }}
.st {{ flex:1 1 200px; font-size:17px; font-weight:700; }}
.st b {{ display:block; font-size:13px; font-weight:400; color:var(--ink-2); }}
.sm {{ min-width:120px; text-align:right; }}
.smn {{ display:block; font-size:14px; font-weight:700; }}
.smc {{ font-size:12.5px; color:var(--unsung); }}

.rows {{ list-style:none; margin:0; padding:0; }}
.row {{ display:grid; grid-template-columns:150px 1fr auto; gap:16px;
  align-items:baseline; padding:11px 0 12px; border-top:1px solid var(--rule-soft); }}
.row:hover {{ background:var(--panel-2); }}
.pn {{ font-size:16px; font-weight:700; }}
.pn b {{ font-weight:400; color:var(--unsung); }}
.pc {{ font-size:14px; color:var(--ink-2); }}
.right {{ text-align:right; white-space:nowrap; }}
.play {{ display:inline-flex; align-items:baseline; gap:8px; text-decoration:none;
  font-size:14px; font-weight:700; color:var(--sung); border-bottom:2px solid var(--sung);
  padding-bottom:1px; }}
.play:hover {{ background:var(--sung); color:var(--panel); }}

.whole {{ margin:34px 0 0; padding:22px 24px 8px; background:var(--panel);
  border:1px solid var(--rule); border-top:3px solid var(--sung);
  border-radius:0 0 var(--radius) var(--radius); }}
.whole h2 {{ font-family:"Big Shoulders Display",Chivo,sans-serif; font-weight:700;
  font-size:30px; margin:0 0 4px; }}
.whole p {{ margin:0 0 8px; font-size:14px; color:var(--ink-2); max-width:64ch; }}

.notes-foot {{ margin:60px 0 0; padding-top:26px; border-top:2px solid var(--ink); }}
.notes-foot h2 {{ font-family:"Big Shoulders Display",Chivo,sans-serif; font-weight:700;
  font-size:30px; margin:0 0 14px; }}
.notes-foot p {{ font-size:14px; color:var(--ink-2); max-width:66ch; }}

@media (max-width:640px) {{
  .row {{ grid-template-columns:1fr auto; }}
  .pc {{ grid-column:1; color:var(--unsung); font-size:13px; }}
  .sh {{ flex-wrap:wrap; }} .sm {{ text-align:left; }}
}}
</style>

<div class="page">
  {nav("playlists.html")}
  <header class="hero">
    <h1>Playlists</h1>
    <p class="sub">Every Kellyoke that still has a copy online, queued up and ready to
      play: <b>{total_videos:,} videos</b> by season, or the whole run end to end.
      Each link opens straight in YouTube, no account needed.</p>
  </header>

  <section class="whole">
    <h2>The whole archive</h2>
    <p>All {total_videos:,} in air-date order, from the September 2019 premiere to the
      series finale, in {len(pl["all"])} parts.</p>
    {parts_list(pl["all"], "Complete archive playlists")}
  </section>

  {"".join(seasons_html)}

  <footer class="notes-foot">
    <h2>How these work</h2>
    <p>These are YouTube <i>watch_videos</i> links rather than saved playlists. YouTube
      builds a temporary queue from the video ids in the URL, so nothing needs an
      account and nothing is stored anywhere. It accepts at most 50 ids at a time,
      which is the only reason a season arrives in parts rather than one link.</p>
    <p>A part will occasionally play short. These point at fan-uploaded copies, and
      when one is taken down the queue simply skips it. The
      <a class="play" href="index.html" data-rel="index.html">archive</a> always has the
      current link for a given morning.</p>
  </footer>
</div>

<script>
(function () {{
{nav_js()}
}})();
</script>
"""

out = os.path.join(REPO, "playlists.html")
with open(out, "w", encoding="utf-8") as f:
    f.write(HTML)
print(f"playlists: {len(HTML)//1024} KB | {total_videos} videos | "
      f"{len(pl['all'])} whole-archive parts | {len(pl['seasons'])} seasons")
