#!/usr/bin/env python3
"""Targeted YouTube search for the handful of performances left without a video."""
import json, os, re, subprocess, sys

S = os.path.dirname(os.path.abspath(__file__))
YTDLP = os.path.join(S, "venv", "bin", "yt-dlp")

rows = json.load(open(os.path.join(S, "matched.json")))
miss = [(r, p) for r in rows for p in r["perfs"] if not p["video_id"] and not r["cameo"]]

out = {}
for i, (r, p) in enumerate(miss, 1):
    q = f"Kellyoke {p['song']} {p['artist']}".strip()
    q = re.sub(r"\s+", " ", q)
    try:
        res = subprocess.run(
            [YTDLP, "--flat-playlist", "--dump-json", f"ytsearch6:{q}"],
            capture_output=True, text=True, timeout=120)
        cands = []
        for line in res.stdout.splitlines():
            if not line.strip():
                continue
            v = json.loads(line)
            cands.append({"id": v.get("id"), "title": v.get("title"),
                          "channel": v.get("channel"), "duration": v.get("duration")})
        out[f'{r["date_iso"]}|{p["song"]}'] = {
            "song": p["song"], "artist": p["artist"], "date": r["date_iso"],
            "query": q, "cands": cands}
        print(f'[{i}/{len(miss)}] {p["song"][:40]:42s} -> {len(cands)} hits', flush=True)
    except Exception as ex:
        print(f'[{i}/{len(miss)}] {p["song"][:40]:42s} -> ERROR {ex}', flush=True)

json.dump(out, open(os.path.join(S, "hunt.json"), "w"), indent=1)
print("saved hunt.json")
