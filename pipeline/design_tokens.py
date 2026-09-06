"""Shared visual system for both Kellyoke pages.

Concept: the karaoke monitor. A line sits "unsung" and fills with a "sung" tone
as it is performed; that fill is the only ornament and always encodes a
proportion. Palette validated with the dataviz validator against both surfaces.
"""

SEASON_COLOR = {1: "#FF52AF", 2: "#61CEBA", 3: "#7600ED", 4: "#FF6929",
                5: "#FCD959", 6: "#1DD9FC", 7: "#B60006"}

FONTS = (
    '<link rel="preconnect" href="https://fonts.googleapis.com">\n'
    '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>\n'
    '<link rel="stylesheet" href="https://fonts.googleapis.com/css2?'
    'family=Big+Shoulders+Display:wght@500;700;800&'
    'family=Chivo:ital,wght@0,400;0,500;0,700;1,400&display=swap">'
)

# Written with doubled braces so it can drop straight into an f-string template.
TOKENS = """
:root {{
  --ground:#E7EEF4; --panel:#FFFFFF; --panel-2:#F1F5F9;
  --ink:#08243B; --ink-2:#3D5C75; --unsung:#6B8399;
  --rule:#CBD8E3; --rule-soft:#DFE8F0;
  --sung:#E11D74; --sung-soft:#FCE4EF; --guest:#2a78d6;
  --ok:#0F7B5F;
  --radius:6px;
  color-scheme:light;
}}
@media (prefers-color-scheme: dark) {{
  :root:not([data-theme="light"]) {{
    --ground:#081B2D; --panel:#0F2A42; --panel-2:#143351;
    --ink:#E8F1F8; --ink-2:#A9C0D2; --unsung:#6E8AA3;
    --rule:#22456A; --rule-soft:#17364F;
    --sung:#E84691; --sung-soft:#33162A; --guest:#3987e5;
    --ok:#5FD9B4;
    color-scheme:dark;
  }}
}}
:root[data-theme="dark"] {{
  --ground:#081B2D; --panel:#0F2A42; --panel-2:#143351;
  --ink:#E8F1F8; --ink-2:#A9C0D2; --unsung:#6E8AA3;
  --rule:#22456A; --rule-soft:#17364F;
  --sung:#E84691; --sung-soft:#33162A; --guest:#3987e5;
  --ok:#5FD9B4;
  color-scheme:dark;
}}

*,*::before,*::after {{ box-sizing:border-box; }}
body {{
  margin:0; background:var(--ground); color:var(--ink);
  font-family:Chivo,ui-sans-serif,system-ui,-apple-system,"Helvetica Neue",sans-serif;
  font-size:15px; line-height:1.5; font-variant-numeric:tabular-nums;
  -webkit-font-smoothing:antialiased;
}}
a {{ color:inherit; }}
:focus-visible {{ outline:2px solid var(--sung); outline-offset:2px; border-radius:3px; }}
::selection {{ background:var(--sung); color:var(--panel); }}

/* the wipe: text rests unsung and fills once, like a lyric being sung */
.wipe {{
  background-image:linear-gradient(90deg,var(--sung) 50%,var(--unsung) 50%);
  background-size:200% 100%; background-position:100% 0;
  -webkit-background-clip:text; background-clip:text; color:transparent;
  animation:sing 1.5s cubic-bezier(.33,0,.2,1) .2s forwards;
}}
@keyframes sing {{ to {{ background-position:0 0; }} }}
@media (prefers-reduced-motion:reduce) {{
  .wipe {{ animation:none; background-position:0 0; }}
  * {{ animation-duration:.001ms !important; transition-duration:.001ms !important; }}
}}

/* a proportion, drawn as a fill against its own track */
.meter {{ display:block; height:3px; background:var(--rule-soft); border-radius:2px; overflow:hidden; }}
.meter i {{ display:block; height:100%; background:var(--sung); border-radius:2px; }}
"""

# ---------------------------------------------------------------- the nav
# Three pages that should feel like one site. Unlike TOKENS above, these are
# functions returning ready-to-use text with single braces: they are always
# interpolated as a value, never inlined into an f-string literal, so there is
# no doubling to remember.

PAGES = [
    ("index.html", "The Archive"),
    ("explore.html", "Data Explorer"),
    ("playlists.html", "Playlists"),
]

# Each page is also published as a separate Claude Artifact, where the others
# are not sibling files. Relative links are the default because they are right
# on every other host; claude.ai is the exception, patched at runtime.
ARTIFACT = {
    "index.html": "https://claude.ai/code/artifact/5e11c4ba-11e2-4128-a1ad-31af1f13afea",
    "explore.html": "https://claude.ai/code/artifact/41950d92-c42a-434c-9f75-f214cc1b3dfd",
    "playlists.html": "https://claude.ai/code/artifact/31e56e13-f295-4a33-b7b5-07cc30151d41",
}


def nav(current):
    """The page switcher. `current` is a filename from PAGES."""
    links = []
    for href, label in PAGES:
        here = ' aria-current="page"' if href == current else ""
        # data-rel survives host rewriting; Netlify's Pretty URLs turns the
        # href into "/explore", which would no longer match the lookup table
        links.append(f'<a href="{href}" data-rel="{href}"{here}>{label}</a>')
    return f'<nav class="nav" aria-label="Pages">{"".join(links)}</nav>'


def nav_css():
    return """
.nav { display:flex; flex-wrap:wrap; gap:2px; align-items:center;
  padding:16px 0 0; margin:0 0 -6px; }
.nav a { font-size:14px; font-weight:700; text-decoration:none; color:var(--unsung);
  padding:7px 12px 6px; border-bottom:2px solid transparent; white-space:nowrap; }
.nav a:hover { color:var(--ink); border-bottom-color:var(--rule); }
.nav a[aria-current="page"] { color:var(--ink); border-bottom-color:var(--sung); }
"""


def nav_js():
    import json
    return ("""
  // On claude.ai the three pages are separate artifacts, so the relative
  // hrefs cannot resolve; everywhere else they are siblings and already right.
  var ARTIFACT = %s;
  if (/(^|\\.)claude\\.ai$/.test(location.hostname)) {
    var navlinks = document.querySelectorAll('.nav a[data-rel]');
    for (var i = 0; i < navlinks.length; i++) {
      var target = ARTIFACT[navlinks[i].getAttribute('data-rel')];
      if (target && target.indexOf('__') !== 0) {
        navlinks[i].setAttribute('href', target);
      }
    }
  }
""" % json.dumps(ARTIFACT))
