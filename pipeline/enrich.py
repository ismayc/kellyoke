#!/usr/bin/env python3
"""Attach genre, original release year and popularity to every performance.

Genre and year come from the linked song's Wikipedia infobox, falling back to
the artist's infobox for genre when the song has no article. View counts come
from the channel dumps already on disk.
"""
import json, os, re, collections

S = os.path.dirname(os.path.abspath(__file__))
rows = json.load(open(os.path.join(S, "matched.json")))
meta = json.load(open(os.path.join(S, "wiki_meta.json")))
links = json.load(open(os.path.join(S, "links.json")))

JUNK = re.compile(r"^(cite|ref|http|www|isbn|p\.|pp\.|\d+)"
                  r"|^(hlist|flat ?list|ubl|plain ?list|unbulleted list"
                  r"|bulleted list|div col)$", re.I)

# ordered rules: first match wins, so "pop rock" lands in Rock and
# "country pop" in Country, which is how each is normally filed
FAMILY = [
    # Named "Holiday", not "Christmas": the pattern has always matched holiday
    # songs generally, and the narrower label was never what the rule did.
    ("Holiday",         r"christmas|holiday|noel|carol"),
    # Two families the rules genuinely lacked. Before these, family("tv theme")
    # and family("patriotic") both returned "", which is why the Mister Rogers
    # and Frasier themes and "America the Beautiful" had nowhere to go. Neither
    # pattern matches any genre string already in the archive, so adding them
    # moves nothing that was classified. Funk was deliberately NOT added: the
    # R&B / Soul rule below already contains "funk", and splitting it out would
    # have moved 14 performances, Superstition and Kiss among them.
    ("TV Themes",       r"tv theme|television theme|theme song|sitcom"),
    ("Patriotic",       r"patriotic|national anthem"),
    ("Gospel",          r"gospel|worship|contemporary christian|\bccm\b|spiritual"),
    ("Musical theatre", r"musical theat|show ?tune|broadway|west end|musical film|\bmusical\b"),
    ("Latin",           r"latin|reggaeton|salsa|bachata|cumbia|tejano|mariachi|ranchera|bossa nova"),
    ("Reggae",          r"reggae|ska\b|dancehall|rocksteady"),
    ("World",           r"calypso|mento|exotica|afrobeat|highlife|worldbeat|k-?pop"),
    ("Hip hop",         r"hip.?hop|\brap\b|trap\b|g-funk"),
    ("Metal",           r"metal"),
    ("Punk",            r"punk"),
    ("Country",         r"country|bluegrass|americana|honky.?tonk|western swing|nashville"),
    ("Rock",            r"rock"),
    ("Rock",            r"new wave|grunge|shoegaze|\bemo\b|alternative|britpop|psychedelia"),
    ("R&B / Soul",      r"r&b|rhythm and blues|soul|funk|motown|doo.?wop|new jack swing|quiet storm"),
    ("Pop",             r"pop"),
    ("Electronic",      r"disco|house|techno|\bedm\b|electronic|dance|trance|electro|synth|club|garage"),
    ("Jazz / Blues",    r"jazz|blues|swing|ragtime|big band|lounge|standard|torch song|vocal"),
    ("Folk",            r"folk|singer.?songwriter|celtic|bluesy folk|traditional"),
    # \baria\b, not bare "aria": unanchored it also matches inside Bulgaria,
    # vegetarianism and ARIA Award. No infobox genre string in the cache has
    # ever tripped that, but the rules are fed free text below, where it does.
    ("Classical",       r"classical|opera|\baria\b|orchestral|baroque|choral|hymn|light music|^light$|easy listening"),
]


def family(g):
    g = (g or "").lower()
    for name, pat in FAMILY:
        if re.search(pat, g):
            return name
    return ""


# Wikipedia categories, used only when no infobox genre exists anywhere. These
# are deliberately NOT the FAMILY rules: those assume a short genre string, and
# a category is a free-text sentence. Running FAMILY over categories files
# "Number-one singles in Bulgaria" and "American vegetarianism activists" under
# Classical (both contain "aria"), and sends every artist in "African-American
# male singer-songwriters" to Folk, which is how Durand Bernarr and Olivia Dean
# both came out wrong in testing. So: an explicit allowlist, phrases only.
#
# Order settles the pages that carry two at once. "America the Beautiful" is in
# both "American patriotic songs" and "American Christian hymns"; patriotic is
# the one that describes the song, so it is listed first. "What It Sounds Like"
# is in both "K-pop songs" and "Songs from KPop Demon Hunters", and k-pop wins
# for the same reason "Golden" files under World.
CATEGORY_FAMILY = [
    ("Patriotic",       r"\bpatriotic songs\b|\bnational anthems?\b"),
    ("Holiday",         r"\bchristmas (songs|carols|music)\b|\bholiday songs\b"),
    ("World",           r"\bk-?pop songs\b|\bsouth korean pop songs\b"),
    # "Songs from <work>" is the giveaway that a song belongs to a named show
    # or film: "Songs from Anything Goes" is what identifies "I Get a Kick Out
    # of You", whose infobox genre is an editor's comment telling people not to
    # add one.
    ("Musical theatre", r"\bshow tunes\b|\bsongs from \b|\bbroadway\b"
                        r"|\bsongs written for animated films\b|\bpixar songs\b"
                        r"|\bdisney songs\b"),
    ("Jazz / Blues",    r"\bjazz standards\b|\bjazz songs\b|\bblues songs\b"),
    ("Gospel",          r"\bchristian hymns\b|\bgospel songs\b|\bhymns\b"),
    ("Country",         r"\bcountry songs\b|\bcountry ballads\b"),
]


# "1982 songs" and "2017 singles" are near-universal on song articles and are
# often present when the infobox states no release date. Safe to read only
# because song_by_pair now resolves to the right article: on a shared title this
# would have handed one song another's year.
CAT_YEAR = re.compile(r"^(1[5-9]\d{2}|20\d{2}) (songs|singles)$", re.I)


def year_from_cats(cats):
    """Earliest year named by a "<year> songs/singles" category, or None. The
    earliest, because a song reissued as a single carries both its composition
    year and the later chart year, and the original release is what this
    archive means by orig_year."""
    yrs = [int(m.group(1)) for c in cats or [] if (m := CAT_YEAR.match(c))]
    return min(yrs) if yrs else None


def family_from_cats(cats):
    """First allowlisted category on the page, as (family, category) or ('','').

    The allowlist is scanned in order, not the category list, so precedence is
    the one declared above rather than whatever order Wikipedia happens to
    return the page's categories in.
    """
    for name, pat in CATEGORY_FAMILY:
        for c in cats or []:
            if re.search(pat, c, re.I):
                return name, c
    return "", ""


def clean_genres(gs):
    out = []
    for g in gs or []:
        g = g.strip()
        if not g or JUNK.match(g) or len(g) < 2:
            continue
        if g.lower() not in [o.lower() for o in out]:
            out.append(g)
    return out


# Years for songs with no Wikipedia article at all, from fetch_musicbrainz.py.
# Optional: the file only exists once that script has been run, and it is read
# as the last fallback so it can never displace a year Wikipedia stated.
mb_p = os.path.join(S, "mb_meta.json")
MB_YEAR = {}
if os.path.exists(mb_p):
    for k, v in json.load(open(mb_p)).items():
        if v.get("year"):
            song, _, artist = k.partition("\t")
            MB_YEAR[(song, artist)] = v["year"]

song_by_disp = {k: v for k, v in links["song_links"].items()}
art_by_disp = {k: v for k, v in links["artist_links"].items()}
# (song, artist) -> article. Prefer this over song_by_disp: a title alone picks
# whichever article was written last, so "Dreams" sent Fleetwood Mac and The
# Cranberries to Beck's article, and "Home" sent Edward Sharpe and Marc
# Broussard to Michael Buble's.
song_by_pair = {tuple(k.split("\t", 1)): v
                for k, v in (links.get("song_pairs") or {}).items()}


def song_article(song, artist):
    """The article for this performance, artist first, title only as fallback."""
    hit = song_by_pair.get((song.lower(), (artist or "").strip().lower()))
    return hit or song_by_disp.get(song.lower())


# Entries where the season wikitext credits the wrong work entirely, keyed on
# the credit as written so the wrong one is what matches. These carry the genre
# strings and year as well as the artist, because the correct article is not
# linked anywhere in the wikitext and so never gets fetched.
CREDIT_FIX = {
    # Two different songs are called "Bloom". The wikitext credits Aqyila,
    # whose "Bloom" is a 2021 R&B single. The clip title names The Paper Kites
    # and Chester confirmed by watching that the performance is folk, so this
    # is their 2010 song. Values from "Bloom (The Paper Kites song)".
    ("Bloom", "Aqyila"): {
        "artist": "The Paper Kites",
        "genres": ["Folk", "indie rock"],
        "year": 2010,
    },
}

# enrich.py writes matched.json back with the corrected credit, so on the next
# run the key above no longer matches its own output and the fix silently stops
# applying. Accept the corrected artist as well, which makes it idempotent.
# verify_dates.py has the same shape of trap for a different reason.
CREDIT_FIX = {**CREDIT_FIX,
              **{(song, v["artist"]): v for (song, _), v in CREDIT_FIX.items()}}


# Genres no article could supply, keyed on (song, artist) because a title alone
# cross-links different songs that share a name. Two sources feed this:
#
#   - songs the wiki listed with no artist to look up, identified from the clip
#     title, which names the source the wiki text did not
#   - the September 6, 2026 triage, where Chester classified by ear and by
#     research the entries Wikipedia states no genre for at all, most of them
#     independent or very recent artists with no infobox
#
# These supply genre *strings*, not families, so the FAMILY rules above classify
# them exactly as they classify everything fetched from Wikipedia. That is why
# "Golden" files under World: its k-pop string matches the World rule. Nothing
# here is a guess from a title.
HAND_GENRE = {
    # "Kellyoke | If I Only Had a Brain (Wizard of Oz)"
    # credited both ways in the wikitext, hence two keys
    ("If I Only Had a Brain", ''): ["show tune"],
    ("If I Only Had a Brain", 'Harold Arlen and Yip Harburg'): ["show tune"],
    # "Kellyoke | Sisters (From White Christmas)"
    ("Sisters", ''): ["show tune"],
    # "'Hopeless War' from 'The Outsiders'", a Broadway musical
    ("Hopeless War", ''): ["show tune"],
    # "'Golden' from Kpop Demon Hunters"
    ("Golden", ''): ["K-pop", "dance-pop"],
    # "Kellyoke | I Would've Loved You (Jake Hoot & Kelly Clarkson)", Hoot being
    # a country artist and the song a country duet
    ("I Would Have Loved You", ''): ["country"],
    # "Kellyoke | Just Sing", the Trolls World Tour ensemble single
    ("Just Sing", ''): ["pop"],
    # Kelly's own catalog. The wiki omits the artist on her own songs, so these
    # look artist-less rather than unknown; the clip titles confirm each one.
    ("Dance With Me", ''): ["pop"],
    # credited both ways in the wikitext, hence two keys
    ("Favorite Kind of High", ''): ["pop"],
    ("Favorite Kind of High", 'Kelly Clarkson'): ["pop"],
    ("People Like Us", ''): ["pop"],
    ("Sober", ''): ["pop"],
    ("Piece by Piece", ''): ["pop"],
    ("I'd Be Lyin'", ''): ["pop"],
    # --- from the September 6, 2026 triage ---
    ("Won't You Be My Neighbor", 'Fred Rogers'): ['tv theme'],   # TV Themes
    ('Classic Television theme songs', ''): ['tv theme'],   # TV Themes
    ('Cain', 'EXES'): ['pop'],   # Pop
    ('Liar', 'Davina Michelle'): ['pop'],   # Pop
    ('Paradise', 'Meduza'): ['electronic'],   # Electronic
    ("Step by Step/Whatta Man/Hangin' Tough", ''): ['R&B'],   # R&B / Soul
    ('Double Take', 'Dhruv'): ['pop'],   # Pop
    ("Take Yo' Praise", 'Camille Yarbrough'): ['R&B'],   # Funk
    ('Peacefully', 'GEMS'): ['pop'],   # Pop
    ('She Wants to Move', 'N.E.R.D'): ['rock'],   # Rock
    ('If He Wanted to He Would', 'Kylie Morgan'): ['country'],   # Country
    ('Mama, Dolly, Jesus', 'Madeline Edwards'): ['country'],   # Country
    ('Tossed Salad and Scrambled Eggs', 'Kelsey Grammer'): ['tv theme'],   # TV Themes
    ('Bloom', 'Aqyila'): ['folk'],   # Folk
    ('When My Fingers Find Your Strings', 'Jeff Daniels'): ['folk'],   # Folk
    ('Letting Go', 'Angie McMahon'): ['pop'],   # Pop
    ("Steppin' On Me", 'Fitz & The Tantrums'): ['pop'],   # Pop
    ('Flames', 'Will Swinton'): ['pop'],   # Pop
    ("Who's Sorry Now", 'Connie Francis'): ['pop'],   # Pop
    ('Boyfriend Forever', 'Abbey Romeo'): ['pop'],   # Pop
    ('7 Days of Weak', 'Ledisi'): ['R&B'],   # R&B / Soul
    ('What It Feels Like', 'Aly & AJ'): ['folk'],   # Folk
    ('Just Missed the Train', 'Trine Rein'): ['pop'],   # Pop
    ('I Got a New One', 'Elizabeth Nichols'): ['country'],   # Country
    ('Créme Brulée', 'David Archuleta'): ['pop'],   # Pop
    ('One Good Thing', ''): ['R&B'],   # R&B / Soul
    ('What It Sounds Like', 'KPop Demon Hunters'): ['k-pop'],   # World
    ('Complicated', 'Gabby Samone'): ['R&B'],   # R&B / Soul
    ('The Thing I Love', 'MAX'): ['pop'],   # Pop
    ('Yeehaw', 'Filmore'): ['country'],   # Country
    ('Eat Me Alive', 'Cami Petyn'): ['pop'],   # Pop
    ('Beg', 'Q Parker'): ['R&B'],   # R&B / Soul
    ('Put It On', 'Q Parker'): ['R&B'],   # R&B / Soul
    ('Painted You Pretty', 'Hudson Westbrook'): ['country'],   # Country
    ('Blues in the Night', 'Ella Fitzgerald'): ['jazz'],   # Jazz / Blues
    ('Bathroom Stall', 'Mikenley Brown'): ['folk'],   # Folk
    ('Day Late and a Buck Short', 'Julia Cole'): ['country'],   # Country
    ('Jesus Wept', 'JW Griffin'): ['country'],   # Country
    ('Suddenly Seymour', 'Lee Wilkof & Ellen Greene'): ['show tune'],   # Musical theatre
    ('Behind the Door', 'Liv Ciara'): ['R&B'],   # R&B / Soul
    ('Austin', 'Dasha'): ['country'],   # Country
}



def artist_candidates(artist):
    """The credit as written, then the ways it might name a real article.

    A credit is not always an article title. "Eve featuring Gwen Stefani" is a
    billing, and "JP Saxe and Julia Michaels" is two people; neither has a page,
    so an exact lookup found nothing and the genre came out blank. The full
    string is tried first and always, because "Fitz & The Tantrums" and
    "Aly & AJ" are band names that splitting would destroy.

    Falling back to one half of a collaboration is a deliberate approximation:
    the genre of the lead credit is a better guess for the song than no genre
    at all, and every family here is broad enough to survive it.
    """
    artist = (artist or "").strip()
    if not artist:
        return []
    out = [artist]
    lead = re.split(r"\s+(?:featuring|feat\.?|ft\.?|with)\s+", artist, flags=re.I)[0].strip()
    if lead and lead != artist:
        out.append(lead)
    for part in re.split(r"\s*(?:&|\band\b)\s*", lead, flags=re.I):
        part = part.strip()
        if part and part not in out:
            out.append(part)
    return out

# ---- view counts from whatever dump holds each video --------------------
views, durs = {}, {}
for fn in ("channel_videos.jsonl", "playlist_videos.jsonl", "kcvideos.jsonl",
           "courtney.jsonl", "xavier.jsonl"):
    p = os.path.join(S, fn)
    if not os.path.exists(p):
        continue
    for line in open(p):
        if not line.strip():
            continue
        v = json.loads(line)
        i = v.get("id")
        if not i:
            continue
        if v.get("view_count") and i not in views:
            views[i] = v["view_count"]
        if v.get("duration") and i not in durs:
            durs[i] = v["duration"]

# ---- duet partners -----------------------------------------------------------
# Wikipedia only sometimes records these. The archives mark many in the video
# title as "[with X]", and a few are known from reporting on the episode.
WITH_RE = re.compile(r"\[\s*with\s+([^\]]+)\]", re.I)
DUET_OVERRIDE = {
    # The Voice Hour: Kelly takes verse one, the other coaches join in
    ("2019-11-21", "Neon Moon"): "Blake Shelton, Gwen Stefani & John Legend",
}

stats = collections.Counter()
for r in rows:
    yr = int(r["date_iso"][:4])
    for p in r["perfs"]:
        # A wrong credit is corrected before anything is looked up, so the rest
        # of the resolution sees the work she actually sang.
        fix = CREDIT_FIX.get((p["song"], p.get("artist") or ""))
        if fix:
            p["artist"] = fix["artist"]
        sart = song_article(p["song"], p.get("artist"))
        sm = meta["song"].get(sart) if sart else None
        year = sm["year"] if sm else None
        year_src = "infobox" if year else ""
        if not year and sm:
            year = year_from_cats(sm.get("cats"))
            year_src = "category" if year else ""
        if not year:
            year = MB_YEAR.get((p["song"], (p.get("artist") or "").strip()))
            year_src = "musicbrainz" if year else year_src
        p["writers"] = (sm.get("writers") or [])[:4] if sm else []
        p["album"] = (sm.get("album") or "") if sm else ""
        p["orig_seconds"] = sm.get("seconds") if sm else None
        genres = []
        src = ""
        if fix:
            genres, year, src = list(fix["genres"]), fix["year"], "credit fix"
            year_src = "credit fix"
        if not genres:
            genres = clean_genres(sm["genres"]) if sm else []
            src = "song" if genres else ""
        if not genres:
            for cand in artist_candidates(p["artist"] or ""):
                am = meta["artist"].get(art_by_disp.get(cand.lower(), ""))
                if am:
                    genres = clean_genres(am["genres"])
                    if genres:
                        src = "artist"
                        break
        if not genres:
            genres = HAND_GENRE.get((p["song"], p.get("artist") or ""), [])
            if genres:
                src = "hand"
        fam = family(genres[0]) if genres else ""
        if not fam:
            for g in genres[1:]:
                fam = family(g)
                if fam:
                    break
        # Last resort, and only ever a last resort: the page's categories. This
        # runs after every genre source above has come up empty, so it can fill
        # a blank but can never overrule a genre an infobox actually stated.
        # The SONG's categories only. An artist's categories describe a career,
        # not this song: Johnny Mercer is in "Broadway composers and lyricists",
        # which filed "Come Rain or Come Shine" under Musical theatre and beat
        # the song's own "1940s jazz standards". Artist categories contributed
        # exactly one classification in testing and it was that wrong one.
        cat_used = ""
        if not fam:
            fam, cat_used = family_from_cats((sm or {}).get("cats"))
            if fam:
                src = "category"
        p["genre_cat"] = cat_used
        p["genres"] = genres[:4]
        p["genre"] = fam or "Not listed"
        p["genre_src"] = src
        p["orig_year"] = year
        p["year_src"] = year_src
        p["decade"] = (year // 10 * 10) if year else None
        p["age_at_cover"] = (yr - year) if year and year <= yr else None
        # performance-level duet: episode note, then the video title, then a known fix
        duet = r.get("duet") or ""
        if not duet and p.get("video_title"):
            m = WITH_RE.search(p["video_title"])
            if m:
                duet = m.group(1).strip()
        duet = DUET_OVERRIDE.get((r["date_iso"], p["song"]), duet)
        p["duet"] = duet
        p["views"] = views.get(p["video_id"]) if p["video_id"] else None
        if p["video_id"] and not p.get("duration"):
            p["duration"] = durs.get(p["video_id"])
        stats[fam or "Not listed"] += 1

json.dump(rows, open(os.path.join(S, "matched.json"), "w"), indent=1)

allp = [p for r in rows for p in r["perfs"]]
print(f"performances {len(allp)}")
print(f"  with a genre        : {sum(1 for p in allp if p['genre']!='Not listed')}"
      f"  ({sum(1 for p in allp if p['genre_src']=='song')} from the song article,"
      f" {sum(1 for p in allp if p['genre_src']=='artist')} from the artist)")
print(f"  with a release year : {sum(1 for p in allp if p['orig_year'])}")
print(f"  with a view count   : {sum(1 for p in allp if p['views'])}")
print(f"  with a duration     : {sum(1 for p in allp if p.get('duration'))}")
ndu = sum(1 for r in rows for q in r["perfs"] if q.get("duet"))
nfrom_ep = sum(1 for r in rows for q in r["perfs"] if q.get("duet") and r.get("duet"))
print(f"  duets identified    : {ndu}  ({nfrom_ep} from the episode note,"
      f" {ndu-nfrom_ep} recovered from video titles or known fixes)")
print("\ngenre spread:")
for g, n in stats.most_common():
    print(f"  {n:5d}  {g}")
yrs = [p["orig_year"] for p in allp if p["orig_year"]]
print(f"\noriginal release years: {min(yrs)} to {max(yrs)}")
dec = collections.Counter(p["decade"] for p in allp if p["decade"])
for d in sorted(dec):
    print(f"  {d}s: {dec[d]}")
