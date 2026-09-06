# The pipeline

These are the generators that produce everything in the repo root. They are kept
here because for a long time they existed only in a temporary directory, which
made the published data impossible to rebuild or audit.

## What is not here

The scraped caches, about 41 MB of them, are gitignored: the two large ones are
a full index of the show's YouTube channel and of its 97 playlists. They are
re-derivable and are not the source of truth. Nothing in this directory will run
without them, so a fresh checkout has to re-scrape (roughly 90 minutes) before
the pipeline works.

Also needed: `yt-dlp` on the path, and network access.

| Cache | What it holds |
|---|---|
| `s1.json` to `s7.json` | wikitext of the seven Wikipedia season articles |
| `channel_videos.jsonl` | the show's channel, every video |
| `playlist_videos.jsonl` | every video across its 97 playlists |
| `kcvideos.jsonl`, `courtney.jsonl`, `xavier.jsonl` | the three fan archives |
| `wiki_meta.json` | genre and original release year per song |
| `video_airdates.json` | the air date each upload states in its description |
| `upload_dates.json`, `date_assign.json` | disambiguation for songs sung more than once |

## Run order

```
python fetch_meta.py      # genre and release year        (network, cached)
python fetch_dates.py     # -> date_assign.json           (network, cached)
python parse_wiki3.py     # wikitext   -> episodes.json
python match3.py          # episodes   -> matched.json
python verify_dates.py    # labels and corrections, in place
python enrich.py          # genre, year, views, duration
python playlists.py       # -> performances.csv, video-urls.txt, PLAYLISTS.md
python build_archive.py   # -> ../index.html
python build_explorer.py  # -> explore.html, copy to ../explore.html by hand
```

Two things about that order are load-bearing:

- **`verify_dates.py` is not idempotent** across repeated runs on its own output.
  Its `corrected` entries get relinked to a clip that states the episode date, so
  a second run reclassifies them as `verified` and the corrected count silently
  falls to zero. Always re-run `match3.py` immediately before it.
- **`enrich.py` must follow `verify_dates.py`**, so that view counts and durations
  follow the corrected video ids rather than the ones they replaced.

`build_archive.py` writes the repo's `index.html` itself. `build_explorer.py`
does not copy its output; do that by hand.

## Changing the matcher

Every link is a claim about which video shows which morning, and a wrong one
still looks plausible. Two checks are worth more than reading the diff:

1. **No entry whose `date_check` was `verified` may change.** That label means the
   clip's own description states that air date, which is evidence independent of
   the matcher. A fix that moves a verified link is a fix that is wrong.
2. Run `python ../tools/check_data.py`. It enforces the invariants that have
   actually been broken here, including that no clip is shared between a guest
   turn and a Kelly performance.

`superseded/` holds earlier versions kept only for reference. Do not run them.
