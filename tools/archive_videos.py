#!/usr/bin/env python3
"""Download a local copy of every clip the archive links to.

The whole archive is links to fan uploads, and tools/check_links.py exists
because those uploads disappear. A link that has gone dead cannot be recovered
from this repo: the CSV records which video id was there, not what was in it.
This script is the answer to that, a local copy of the footage itself.

It reads performances.csv, so it downloads exactly what the archive points at
and nothing else. One file per distinct video id, not per performance: 177
mornings reuse a clip already queued, and downloading those again would waste
bandwidth to produce byte-identical files.

Resumability is the point, not a nicety. A full run is roughly 1,000 videos and
39 hours of footage, which will be interrupted. yt-dlp's --download-archive
records each completed id, so re-running skips what is already on disk and the
run can be stopped and restarted freely.

Every download also writes a .info.json beside the media. That is deliberate:
the title, description, uploader and upload date are the evidence the pipeline
uses to date a clip, and they vanish with the video. Keeping them means a dead
link stays identifiable even if the media file is later lost.

Requires ffmpeg. YouTube serves video and audio as separate streams for these
clips, with no pre-muxed format available, so without a muxer yt-dlp can fetch
one or the other but cannot produce a watchable file. The script checks for it
up front rather than failing 200 videos in.

    python3 tools/archive_videos.py --out ~/kellyoke-archive --limit 5
    python3 tools/archive_videos.py --out ~/kellyoke-archive
"""
import argparse
import csv
import json
import re
import shutil
import subprocess
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CSV = ROOT / "performances.csv"

# 720p is the practical default: most of these are fan re-uploads of broadcast
# video, so 1080p is usually an upscale of the same source at twice the bytes.
def video_format(height, codec="avc1"):
    """H.264 first, by default.

    YouTube also serves AV1 and VP9, which are smaller for the same height. For
    an archive meant to outlive the uploads, playability matters more than the
    saving: H.264 in mp4 is the one combination every player made in the last
    twenty years can open. The chain falls through to any codec rather than
    failing, so a clip offered only as AV1 is still fetched.
    """
    pref = f"[vcodec^={codec}]" if codec else ""
    return (f"bestvideo[height<=?{height}]{pref}+bestaudio[ext=m4a]/"
            f"bestvideo[height<=?{height}][ext=mp4]+bestaudio[ext=m4a]/"
            f"bestvideo[height<=?{height}]+bestaudio/best[height<=?{height}]/best")


def human(n):
    """Bytes as MB until it is genuinely gigabytes, so a small run reads right."""
    return f"{n / 1e9:.2f} GB" if n >= 1e9 else f"{n / 1e6:.0f} MB"


def slug(text, limit=60):
    """A filename fragment that survives every filesystem involved."""
    text = re.sub(r"[^\w\s-]", "", text or "", flags=re.UNICODE).strip()
    text = re.sub(r"[\s_]+", "_", text)
    return text[:limit].strip("_") or "untitled"


def load_targets():
    """Distinct video ids, each carrying the performances it stands for.

    A clip is named for its earliest airing, since that is the morning it was
    recorded on. The later dates it also covers are kept in the manifest so the
    mapping back to the archive stays complete.
    """
    by_id = defaultdict(list)
    with open(CSV, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            if row["video_id"]:
                by_id[row["video_id"]].append(row)
    targets = []
    for vid, rows in by_id.items():
        rows.sort(key=lambda r: r["air_date"])
        first = rows[0]
        targets.append({
            "video_id": vid,
            "air_date": first["air_date"],
            "song": first["song"],
            "is_cameo": first["is_cameo"] == "yes",
            "covers": [{"air_date": r["air_date"], "song": r["song"],
                        "performed_by": r["performed_by"]} for r in rows],
            "stem": f'{first["air_date"]}__{slug(first["song"])}__{vid}',
        })
    targets.sort(key=lambda t: t["air_date"])
    return targets


def find_yt_dlp(explicit=None):
    """Prefer an explicit path, then PATH, then the pipeline's own venv."""
    if explicit:
        return explicit
    found = shutil.which("yt-dlp")
    if found:
        return found
    for guess in ROOT.glob("**/venv/bin/yt-dlp"):
        return str(guess)
    return None


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", required=True, type=Path,
                    help="directory to write the archive into")
    ap.add_argument("--limit", type=int,
                    help="stop after this many videos, for a trial run")
    ap.add_argument("--kelly-only", action="store_true",
                    help="skip the 13 guest turns that have a clip")
    ap.add_argument("--audio-only", action="store_true",
                    help="m4a instead of video; no muxing, so ffmpeg is optional")
    ap.add_argument("--height", type=int, default=720,
                    help="max video height; 360 roughly thirds the total (default: 720)")
    ap.add_argument("--any-codec", action="store_true",
                    help="allow AV1/VP9, which are smaller but need a modern player")
    ap.add_argument("--yt-dlp", help="path to yt-dlp if it is not on PATH")
    ap.add_argument("--js-runtime", default="node",
                    help="JS runtime for YouTube extraction (default: node)")
    ap.add_argument("--sleep", type=float, default=2.0,
                    help="seconds between requests, to stay polite (default: 2)")
    ap.add_argument("--pause", default="4-12", metavar="MIN-MAX",
                    help="randomized seconds between downloads (default: 4-12). "
                         "This is the knob the rate limit responds to")
    ap.add_argument("--dry-run", action="store_true",
                    help="report what would be fetched and exit")
    args = ap.parse_args()

    yt_dlp = find_yt_dlp(args.yt_dlp)
    if not yt_dlp:
        sys.exit("yt-dlp not found. Pass --yt-dlp /path/to/yt-dlp.")

    # Fail here rather than after an hour of downloads that cannot be muxed.
    # A dry run touches the network for nothing, so it is exempt.
    if not args.dry_run and not args.audio_only and not shutil.which("ffmpeg"):
        sys.exit("ffmpeg not found, and these clips have no pre-muxed format, so "
                 "video and audio cannot be joined.\n"
                 "  Install it:   brew install ffmpeg\n"
                 "  Or run audio: --audio-only")

    pause_min, _, pause_max = args.pause.partition("-")
    pause_max = pause_max or pause_min

    targets = load_targets()
    if args.kelly_only:
        targets = [t for t in targets if not t["is_cameo"]]

    out = args.out.expanduser().resolve()
    media = out / "media"
    media.mkdir(parents=True, exist_ok=True)
    done_file = out / "downloaded.txt"

    already = set()
    if done_file.exists():
        already = {ln.split()[-1] for ln in done_file.read_text().splitlines() if ln.strip()}
    todo = [t for t in targets if t["video_id"] not in already]
    remaining = len(todo)
    # --limit counts what is still outstanding, not what exists. Slicing the
    # full list instead would re-select finished clips and fetch nothing, which
    # is exactly wrong for the batch-and-wait workflow the rate limit forces.
    if args.limit:
        todo = todo[:args.limit]

    print(f"{len(targets)} distinct clips -> {out}")
    print(f"{len(already)} already downloaded, {remaining} outstanding, "
          f"{len(todo)} this run\n")
    if args.dry_run:
        for t in todo[:10]:
            print(f"  {t['air_date']}  {t['song'][:48]:<48} {t['video_id']}")
        if len(todo) > 10:
            print(f"  ... and {len(todo) - 10} more")
        return

    failed = []
    for i, t in enumerate(todo, 1):
        url = f"https://www.youtube.com/watch?v={t['video_id']}"
        cmd = [yt_dlp, "--js-runtimes", args.js_runtime,
               "--download-archive", str(done_file),
               "--write-info-json", "--no-progress", "--no-warnings",
               "--sleep-requests", str(args.sleep),
               "--sleep-interval", pause_min, "--max-sleep-interval", pause_max,
               "-o", str(media / (t["stem"] + ".%(ext)s")),
               "-f", ("bestaudio[ext=m4a]/bestaudio" if args.audio_only
                      else video_format(args.height,
                                        "" if args.any_codec else "avc1")),
               url]
        print(f"[{i}/{len(todo)}] {t['air_date']}  {t['song'][:44]}")
        r = subprocess.run(cmd, capture_output=True, text=True)
        if r.returncode != 0:
            # A removed video is the expected failure and the reason this
            # script exists, so it is recorded and the run continues.
            why = (r.stderr or "").strip().splitlines()
            failed.append({**{k: t[k] for k in ("video_id", "air_date", "song")},
                           "error": why[-1] if why else f"exit {r.returncode}"})
            print(f"    FAILED  {failed[-1]['error'][:110]}")

    # The manifest maps every archive entry to its local file, so the download
    # is usable without re-deriving the mapping from filenames.
    manifest = []
    for t in targets:
        hits = sorted(media.glob(t["stem"] + ".*"))
        media_file = next((h for h in hits if h.suffix != ".json"), None)
        manifest.append({**t,
                         "file": media_file.name if media_file else None,
                         "bytes": media_file.stat().st_size if media_file else 0})
    (out / "manifest.json").write_text(json.dumps(manifest, indent=1))

    got = [m for m in manifest if m["file"]]
    total = sum(m["bytes"] for m in got)
    print(f"\n{len(got)} of {len(targets)} clips on disk, {human(total)}")
    if failed:
        (out / "failed.json").write_text(json.dumps(failed, indent=1))
        print(f"{len(failed)} failed, listed in {out / 'failed.json'}")
        print("Re-run to retry them; anything already downloaded is skipped.")


if __name__ == "__main__":
    main()
