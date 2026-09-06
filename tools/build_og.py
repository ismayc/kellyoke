#!/usr/bin/env python3
"""Render og-image.png, the card that appears when the site is shared.

The card carries no counts. An earlier version showed "1,177 of 1,178 are linked
to a copy you can still watch", which is true and reads as a near miss: it points
at the one that gets away rather than at the seven years that are here. Counts
also date the card the moment the data moves. The page itself is the place for
figures.

Typography comes from Google Fonts, which means this needs network access and
headless Chrome. Chrome renders at 2x and the result is downsampled, because
social cards get shown small and the text has to survive it.

Usage: python tools/build_og.py
"""
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "og-image.png"
W, H = 1200, 630
SCALE = 2

CHROME_CANDIDATES = [
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "/Applications/Chromium.app/Contents/MacOS/Chromium",
    shutil.which("google-chrome") or "",
    shutil.which("chromium") or "",
]

# The dark half of the site's palette. A social feed is mostly white, so the
# card reads as a held note against it rather than another pale rectangle.
TOKENS = {
    "ground": "#081B2D", "panel": "#0F2A42",
    "ink": "#E8F1F8", "ink2": "#A9C0D2", "unsung": "#6E8AA3",
    "rule": "#22456A", "rule_soft": "#17364F", "sung": "#E84691",
}


def html():
    t = TOKENS
    return f"""<!doctype html>
<meta charset="utf-8">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Big+Shoulders+Display:wght@600;800&family=Chivo:wght@400;700&display=swap">
<style>
  * {{ box-sizing: border-box; margin: 0; }}
  html, body {{ width: {W}px; height: {H}px; }}
  body {{
    background: {t['ground']}; color: {t['ink']};
    font-family: Chivo, sans-serif; font-variant-numeric: tabular-nums;
    padding: 58px 64px 54px; display: flex; flex-direction: column;
    justify-content: space-between; overflow: hidden;
    -webkit-font-smoothing: antialiased;
    position: relative;
  }}
  /* The type carries the card; the mic fills the right third and sits behind it,
     drawn in the same near-ground tones so it reads as depth rather than
     clip art. The one pink band ties it to the rest of the system. */
  .mic {{
    position: absolute; right: 74px; bottom: 122px; height: 438px; width: auto;
    transform: rotate(13deg); transform-origin: 50% 62%;
  }}
  body > div, body > footer {{ position: relative; z-index: 1; }}
  .eyebrow {{
    font-size: 21px; font-weight: 700; letter-spacing: .13em;
    text-transform: uppercase; color: {t['unsung']};
  }}
  h1 {{
    font-family: "Big Shoulders Display", Chivo, sans-serif;
    font-weight: 800; font-size: 124px; line-height: .84;
    letter-spacing: -.015em; margin: 22px 0 0;
  }}
  .rule {{
    width: 218px; height: 7px; background: {t['sung']};
    border-radius: 4px; margin: 34px 0 22px;
  }}
  /* wide enough that the bold phrase stays on one line */
  .lede {{
    font-size: 29px; line-height: 1.36; color: {t['ink2']}; max-width: 34ch;
  }}
  .lede b {{ color: {t['ink']}; font-weight: 700; }}
  footer {{
    display: flex; align-items: flex-end; justify-content: space-between;
    border-top: 1px solid {t['rule']}; padding-top: 22px; gap: 30px;
  }}
  .who {{ font-size: 21px; color: {t['unsung']}; }}
  .by {{ font-size: 19px; color: {t['unsung']}; opacity: .8; margin-top: 7px; }}
  .by b {{ color: {t['ink2']}; font-weight: 700; }}
  .site {{
    font-size: 22px; font-weight: 700; color: {t['sung']};
    border-bottom: 3px solid {t['sung']}; padding-bottom: 3px; white-space: nowrap;
  }}
</style>
<svg class="mic" viewBox="0 0 220 500" fill="none" aria-hidden="true">
  <defs>
    <pattern id="mesh" width="15" height="15" patternUnits="userSpaceOnUse">
      <circle cx="7.5" cy="7.5" r="2.7" fill="{t['unsung']}" opacity=".5"></circle>
    </pattern>
    <clipPath id="ball"><circle cx="110" cy="104" r="82"></circle></clipPath>
  </defs>

  <!-- handle, tapering slightly toward a rounded base -->
  <path d="M 68,192 L 152,192 L 145,438 Q 145,462 122,462 L 98,462 Q 75,462 75,438 Z"
        fill="{t['panel']}" stroke="{t['rule']}" stroke-width="3"></path>
  <!-- a single highlight so the handle reads as round, not flat -->
  <path d="M 88,206 L 84,436" stroke="{t['rule']}" stroke-width="5"
        stroke-linecap="round" opacity=".85"></path>

  <!-- grille -->
  <circle cx="110" cy="104" r="82" fill="#12314C" stroke="{t['rule']}" stroke-width="3"></circle>
  <g clip-path="url(#ball)">
    <rect x="0" y="0" width="220" height="220" fill="url(#mesh)"></rect>
    <path d="M 46,150 A 82,82 0 0 1 60,44" stroke="{t['unsung']}" stroke-width="4"
          stroke-linecap="round" opacity=".45"></path>
  </g>

  <!-- the band: the one place the card's pink appears twice -->
  <rect x="62" y="176" width="96" height="26" rx="9" fill="{t['sung']}"></rect>
</svg>

<div>
  <p class="eyebrow">The Kelly Clarkson Show &nbsp;&middot;&nbsp; 2019 to 2026</p>
  <h1>Every<br>Kellyoke</h1>
  <div class="rule"></div>
  <p class="lede">Seven years of the song that opened the show, each one linked
     to <b>a clip on YouTube</b>.</p>
</div>
<footer>
  <div>
    <p class="who">Searchable by song, artist, season and genre</p>
    <p class="by">Designed by <b>Chester Ismay</b></p>
  </div>
  <div class="site">kellyokes.netlify.app</div>
</footer>
"""


def main():
    chrome = next((c for c in CHROME_CANDIDATES if c and Path(c).exists()), None)
    if not chrome:
        print("No Chrome or Chromium found; cannot render.", file=sys.stderr)
        return 1

    with tempfile.TemporaryDirectory() as tmp:
        page = Path(tmp) / "og.html"
        page.write_text(html(), encoding="utf-8")
        shot = Path(tmp) / "shot.png"
        cmd = [chrome, "--headless=new", "--disable-gpu", "--hide-scrollbars",
               f"--force-device-scale-factor={SCALE}",
               f"--window-size={W},{H}",
               # give the webfonts time to arrive before the shutter
               "--virtual-time-budget=8000",
               f"--screenshot={shot}", page.as_uri()]
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
        if not shot.exists():
            print("Chrome did not produce a screenshot.", file=sys.stderr)
            print(r.stderr[-1500:], file=sys.stderr)
            return 1

        from PIL import Image
        im = Image.open(shot).convert("RGB")
        if im.size != (W, H):
            im = im.resize((W, H), Image.LANCZOS)
        im.save(OUT, "PNG", optimize=True)

    kb = OUT.stat().st_size / 1024
    print(f"wrote {OUT.name}  {W}x{H}  {kb:.0f} KB")
    return 0


if __name__ == "__main__":
    sys.exit(main())
