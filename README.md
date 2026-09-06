# Kellyoke

Every cover Kelly Clarkson opened *The Kelly Clarkson Show* with, from the
premiere on September 9, 2019 to the series finale on August 31, 2026.

**1,178 performances by Kelly** across 1,233 episodes and seven seasons, plus
the **67** mornings a guest sang the opener instead (the show calls those
Cameo-oke). All 1,178 of Kelly's 1,178 are linked to a video, and **898 of those
links are confirmed** against the air date stated in the clip's own YouTube
description rather than inferred from its title.

The songs she reached for span **1930 to 2025** across **17 genre families**:
353 pop, 298 rock, 195 country, 165 R&B and soul, and a long tail down to a
single Latin track.

## Files

| File | What it is |
|---|---|
| `index.html` | The archive: every cover in air-date order, searchable, filterable by season. Open it in a browser. |
| `explore.html` | The data explorer: sort and filter by season, genre, decade, performer, with charts that follow the selection. |
| `playlists.html` | The playlists page: every instant YouTube playlist, by season or the whole run, rendered from the same data as `PLAYLISTS.md`. |
| `performances.csv` | All 1,245 entries, one row each, for spreadsheet work. |
| `PLAYLISTS.md` | Instant YouTube playlist links, per season and for the whole archive. |
| `video-urls.txt` | Plain video URLs grouped by season, for other tools. |

## Columns in `performances.csv`

`air_date`, `season`, `episode_overall`, `episode_in_season`, `song`,
`original_artist`, `genre`, `original_release_year`, `years_since_release`,
`performed_by`, `is_cameo`, `duet_with`, `version_covered`, `rerun`,
`video_id`, `video_url`, `video_source`, `video_title`, `video_views`,
`video_seconds`

`version_covered` records the arrangement she sang when it wasn't the original:
"Beggin'" is credited to The Four Seasons, but she did the Måneskin version.

## Where the data came from

- **Songs, air dates, episode numbers** — parsed from the wikitext of the seven
  Wikipedia season articles, which log the Kellyoke for 1,232 of the 1,233
  episodes (November 1, 2019 is listed as N/A: that morning she sang five
  shortened songs of her own, closing on *Invincible*, to announce the Las
  Vegas residency of the same name. None of them was a cover). The
  episode count reconciles exactly with the number each article declares.
- **Genre and original release year** — from each song's own Wikipedia infobox,
  falling back to the artist's infobox when the song has no article.
- **Videos** — matched by title and artist against a full index of the show's
  YouTube channel (its video tab plus all 97 playlists) and three fan archives
  that mirror the segment.
- **Air-date confirmation** — most archive uploads state "Original airdate" in
  the description. Those were fetched and compared against every assignment,
  which confirmed 898 links and corrected 10 that pointed at the wrong night.

## Known gaps

- Most Cameo-oke mornings were never posted, so only 13 of 67 have a video. A
  guest turn is linked only to a clip that shows the guest; where the sole
  surviving clip of that song is Kelly singing it on another night, the guest
  turn is left unlinked rather than pointed at the wrong performer.
- 98 of 1,245 entries have no genre, mostly newer or independent artists with
  no Wikipedia infobox. They show as "Not listed" rather than being guessed.
- Where a song came back on a later morning and only one clip survives, every
  date points at that clip. This covers 122 entries, and each one is labeled:
  either the clip states an air date belonging to another night on which the
  same song was sung (117), or it was uploaded before this episode aired (5).
  The yearly Christmas covers are the main case.
- Three clips state an air date falling on a Saturday or Sunday. The show never
  aired at the weekend, so those descriptions are wrong; the links themselves
  look right. One further link, *Trouble Blues* (Jun 19, 2024), states a date on
  which a different song was sung and is still unexplained.
- Video quality is labeled by source, not measured per file. The show keeps only
  about sixty Kellyokes online, so most links go to an archive copy.

## Checks

`tools/check_data.py` runs on every push and pull request. It needs no
dependencies and no network, because it checks the committed output files
against each other rather than rebuilding them. Most of its rules exist because
the thing they forbid actually happened once and nothing noticed:

- No clip is shared between a guest turn and one of Kelly's performances. A clip
  of Kelly singing a song is the wrong person for a Cameo-oke morning.
- No episode airs at the weekend. The show never did, across seven seasons, so a
  weekend date means something upstream mis-parsed.
- `video-urls.txt` and `PLAYLISTS.md` hold exactly the clips the CSV says they
  should, no playlist part exceeds the 50-video cap the YouTube endpoint honors,
  and each part declares its real length.
- The rendered pages carry a charset, no NUL bytes, and no unexpanded template
  braces.
- **The counts quoted in this README match the data.** They go stale silently
  otherwise, which is exactly what happened the first time this check ran.

`tools/check_prose.py` enforces American spellings and bans the em dash as
mid-sentence punctuation, while still allowing it to separate a list item from
its gloss.

Both pages deploy to [kellyokes.netlify.app](https://kellyokes.netlify.app) on
every push to `main`, through Netlify's Git integration. GitHub Pages would need
a paid plan for a private repo, which is why this goes through Netlify instead.
The build command in `netlify.toml` runs `tools/check_data.py` before assembling
the site, so a dataset that fails its own invariants fails the build rather than
reaching the page.

Netlify's Pretty URLs post-processing rewrites `explore.html` to `/explore` in
the served HTML, which the redirects in `netlify.toml` resolve.

The three pages share a nav defined once in `pipeline/design_tokens.py`. Its
links are relative, which is correct everywhere except `claude.ai`, where each
page is a separate Artifact with an unrelated URL; a few lines of JavaScript
swap in the Artifact URLs on that host only. Each link carries a `data-rel`
attribute because Pretty URLs rewrites the `href` itself, and the lookup has to
survive that.

`tools/check_links.py` runs monthly. It asks YouTube's oEmbed endpoint whether
each video still resolves and opens an issue listing any that have gone. Only a
clean 404, 403 or 401 counts as dead; a timeout or a rate-limit says something
about the runner's IP rather than the video, and if too much of a run comes back
unknown the script reports nothing rather than a list of false alarms.

Detecting rot does not undo it, so `tools/archive_videos.py` takes a local copy
of the footage. It reads `performances.csv` and fetches one file per distinct
video id, named `air-date__song__video-id`, with the `.info.json` beside it so a
clip stays identifiable even after the upload is gone. Runs are resumable: a
completed id is recorded and skipped, so the run can be interrupted freely.

```bash
python3 tools/archive_videos.py --out ~/kellyoke-archive --dry-run
python3 tools/archive_videos.py --out ~/kellyoke-archive
```

It needs `ffmpeg`, because YouTube serves these clips as separate video and
audio streams with no pre-muxed format, and `yt-dlp`. Measured over 341 real
downloads, the footage runs about **27 GB** at the default 720p, roughly
**8 GB** at `--height 360`, or about **2 GB** with `--audio-only`, which needs
no muxer. The `.info.json` files add about 0.2 GB. Nothing it writes belongs in
the repo.

**Expect to run it in batches.** YouTube starts answering "Sign in to confirm
you're not a bot" after a few hundred clips from one address, and the block
outlasts the run: slowing down mid-flight does not clear it, and neither does
retrying an hour later. It is a per-address cooldown, so the working pattern is
a few hundred clips, then wait, then resume. `--limit` counts what is still
outstanding rather than what exists, so `--limit 200` means "fetch 200 more",
and `--pause MIN-MAX` spaces the requests out.

H.264 is preferred over the AV1 and VP9 streams YouTube also offers. Those are
smaller at the same height, but this is a copy meant to outlive the uploads and
H.264 in mp4 is the one combination any player will open. `--any-codec` takes
the smaller files instead.

## Design

Both pages share one system, built around the karaoke monitor: a line sits
*unsung* and fills with a *sung* tone as it is performed. That fill is the only
ornament, and it always stands for a proportion. Type is Big Shoulders Display
for headlines and Chivo for everything else. The seven season colors are the
show's own, taken from each season's Wikipedia infobox. The chart palette was
checked for colorblind separation and contrast against both the light and dark
surfaces.
