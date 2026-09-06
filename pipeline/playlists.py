#!/usr/bin/env python3
"""Build YouTube playlist links, a CSV export, and a plain URL list.

YouTube's /watch_videos?video_ids=... endpoint builds an ad-hoc playlist with
no sign-in and no API quota. It accepts at most 50 ids, so each season is split
into parts. Opening one while signed in offers a Save option to keep it.
"""
import json, os, csv, collections

S = os.path.dirname(os.path.abspath(__file__))
OUT = "/Users/chesterismay/repos/kellyoke"
CHUNK = 50
rows = json.load(open(os.path.join(S, "matched.json")))

MONTHS = ["January","February","March","April","May","June","July","August",
          "September","October","November","December"]


def url(ids):
    return "https://www.youtube.com/watch_videos?video_ids=" + ",".join(ids)


# ---- per-season unique video ids, in first-air order ------------------------
per = collections.OrderedDict()
order_all = []
for r in rows:
    if r["cameo"]:
        continue
    for p in r["perfs"]:
        if not p["video_id"]:
            continue
        per.setdefault(r["season"], [])
        if p["video_id"] not in per[r["season"]]:
            per[r["season"]].append(p["video_id"])
        order_all.append(p["video_id"])
uniq_all = list(dict.fromkeys(order_all))

playlists = collections.OrderedDict()
for s, ids in per.items():
    parts = [ids[i:i+CHUNK] for i in range(0, len(ids), CHUNK)]
    playlists[s] = [{"part": i+1, "of": len(parts), "n": len(c), "url": url(c)}
                    for i, c in enumerate(parts)]

whole = [uniq_all[i:i+CHUNK] for i in range(0, len(uniq_all), CHUNK)]
whole_pl = [{"part": i+1, "of": len(whole), "n": len(c), "url": url(c)}
            for i, c in enumerate(whole)]

json.dump({"seasons": playlists, "all": whole_pl},
          open(os.path.join(S, "playlists.json"), "w"), indent=1)

# ---- CSV of every performance ----------------------------------------------
os.makedirs(OUT, exist_ok=True)
with open(os.path.join(OUT, "performances.csv"), "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["air_date", "season", "episode_overall", "episode_in_season",
                "song", "original_artist", "genre", "original_release_year",
                "years_since_release", "performed_by", "is_cameo",
                "duet_with", "version_covered", "rerun",
                "video_id", "video_url", "video_source", "video_title",
                "video_views", "video_seconds"])
    for r in rows:
        for p in r["perfs"]:
            w.writerow([
                r["date_iso"], r["season"], r["ep_overall"], r["ep_in_season"],
                p["song"], p["artist"],
                "" if p.get("genre") in (None, "Not listed") else p["genre"],
                p.get("orig_year") or "", p.get("age_at_cover") if p.get("age_at_cover") is not None else "",
                (r["performer"] or "guest") if r["cameo"] else "Kelly Clarkson",
                "yes" if r["cameo"] else "no",
                p.get("duet") or r["duet"], r["version"], "yes" if r["rerun"] else "no",
                p["video_id"] or "",
                f"https://www.youtube.com/watch?v={p['video_id']}" if p["video_id"] else "",
                p["source"] or "", p["video_title"] or "",
                p.get("views") or "", p.get("duration") or "",
            ])

# ---- plain list of unique video URLs ---------------------------------------
with open(os.path.join(OUT, "video-urls.txt"), "w") as f:
    for s, ids in per.items():
        f.write(f"# Season {s} ({len(ids)} videos)\n")
        for i in ids:
            f.write(f"https://www.youtube.com/watch?v={i}\n")
        f.write("\n")

# ---- markdown index of the playlist links ----------------------------------
with open(os.path.join(OUT, "PLAYLISTS.md"), "w") as f:
    f.write("# Kellyoke playlists\n\n")
    f.write("Each link opens an instant YouTube playlist. No sign-in is needed to "
            "watch; if you are signed in, use the playlist's Save option to keep it "
            "on your account. YouTube caps these ad-hoc playlists at 50 videos, so "
            "longer seasons are split into parts.\n\n")
    f.write("Guest Cameo-oke performances are excluded; these are Kelly's covers only.\n\n")
    for s, parts in playlists.items():
        eps = [r for r in rows if r["season"] == s]
        f.write(f"## Season {s}  ({eps[0]['date_pretty']} - {eps[-1]['date_pretty']})\n\n")
        for p in parts:
            f.write(f"- [Season {s}, part {p['part']} of {p['of']} "
                    f"({p['n']} videos)]({p['url']})\n")
        f.write("\n")
    f.write(f"## Complete archive ({len(uniq_all)} videos)\n\n")
    for p in whole_pl:
        f.write(f"- [All Kellyokes, part {p['part']} of {p['of']} "
                f"({p['n']} videos)]({p['url']})\n")

print(f"unique videos: {len(uniq_all)}")
for s, parts in playlists.items():
    print(f"  S{s}: {sum(p['n'] for p in parts)} videos in {len(parts)} parts")
print(f"  complete: {len(whole_pl)} parts")
print("wrote performances.csv, video-urls.txt, PLAYLISTS.md ->", OUT)
