#!/usr/bin/env python3
"""
Coach-Mood-Scraper — Phase 2 of Hot-Seat-Prediction.

Powers Mood-Layer A: Google News RSS per active BL coach. Extracts headlines
of last N days, counts negative-keyword density, detects kiss-of-death phrases
(SD/CEO declines public endorsement, "vor dem Aus", etc.).

This catches the Riera-Pattern: Frankfurt #8 with PPG 1.0 looks "ruhig" by
form-metrics, but headlines show "Markus Krösche vermeidet Bekenntnis" and
"Atmosphäre ist vergiftet" — clear mood-trouble.

Output: data/coach_mood_signals.json
  {coach_tm_id: {
    "name": str,
    "club": str,
    "articles_n": int,
    "kiss_of_death_signals": [str],  # phrases found
    "wackel_signals": [str],
    "criticism_signals": [str],
    "mood_score": int,  # 0-20, fed into hot-seat as component 7
    "headlines_sample": [{"title", "source", "date"}],  # top 5 most-recent
    "scraped_at": iso str,
  }}

Usage:
  python3 execution/scrape_coach_mood.py
  python3 execution/scrape_coach_mood.py --days 14
  python3 execution/scrape_coach_mood.py --only-tm-id 75217
"""
import argparse
import json
import re
import sys
import time
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

BASE = Path(__file__).parent.parent
DATA = BASE / "data"
HOT_SEAT = DATA / "hot_seat_scores.json"
OUT = DATA / "coach_mood_signals.json"

GOOGLE_NEWS_RSS = (
    "https://news.google.com/rss/search?q={query}&hl=de&gl=DE&ceid=DE:de"
)

# ── Keyword-Listen (Hierarchie nach Stärke) ─────────────────────────

# Kiss-of-Death — SD/CEO öffentlich KEIN Bekenntnis = oft pre-firing-Signal
# Auch: starke Wackel-Verben in Schlagzeilen
KISS_OF_DEATH = [
    r"vermeidet\s+bekenntnis",
    r"keine\s+rückendeckung",
    r"vor\s+dem\s+aus",
    r"trainer\s*-?\s*aus",
    r"entlassung\s+droht",
    r"steht\s+vor\s+der\s+entlassung",
    r"wird\s+entlassen",
    r"freigestellt",
    r"trainerwechsel\s+(droht|steht\s+bevor)",
    r"abschied",
    r"trennung\s+(droht|nahe)",
    r"\?$|aus\?",  # "vor dem Aus?" pattern
]

# Wackel-Signale — Trainer in Diskussion, Status unklar
WACKEL_SIGNALS = [
    r"wackelt",
    r"infrage(\s+gestellt)?",
    r"trainerfrage",
    r"trainerdiskussion",
    r"zukunft\s+(offen|fraglich)",
    r"bangt\s+um",
    r"unter\s+druck",
    r"druck\s+(steigt|wächst)",
    r"alternativen\s+geprüft",
    r"krise(nsitzung)?",
    r"krisengespräch",
]

# Kritik-Signale — schwächer, aber Volumen ist Signal
CRITICISM_SIGNALS = [
    r"kritik(\s+wächst)?",
    r"vergiftet",
    r"chaos",
    r"debakel",
    r"blamage",
    r"fiasko",
    r"vor\s+die\s+wand\s+gefahren",
    r"krise",
    r"lügen!",
    r"bullshit",
    r"abstiegsangst",
    r"unzufrieden",
    r"enttäuschung",
]

# Positive-Signale (subtrahieren — Trainer sicher)
POSITIVE_SIGNALS = [
    r"vertragsverlängerung",
    r"verlängert\s+vertrag",
    r"gesetzt(er\s+trainer)?",
    r"trainer\s+der\s+saison",
]


def fetch(url: str, timeout: int = 15) -> str:
    """Fetch URL as text."""
    req = urllib.request.Request(url, headers={
        "User-Agent": "Mozilla/5.0 (compatible; projectFIVE-Mood/1.0)"
    })
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        raw = resp.read()
    # XML responses can be utf-8 or latin-1
    return raw.decode("utf-8", errors="replace")


def parse_rss(xml_text: str) -> list:
    """Lightweight RSS-item parser. Returns [{title, pub_date, source}, ...]."""
    items = []
    for raw_item in re.findall(r"<item>(.*?)</item>", xml_text, re.DOTALL):
        title_m = re.search(r"<title>(.*?)</title>", raw_item, re.DOTALL)
        pub_m = re.search(r"<pubDate>(.*?)</pubDate>", raw_item, re.DOTALL)
        src_m = re.search(r"<source[^>]*>(.*?)</source>", raw_item, re.DOTALL)

        title = ""
        if title_m:
            title = title_m.group(1).replace("<![CDATA[", "").replace("]]>", "").strip()

        pub = pub_m.group(1).strip() if pub_m else ""
        src = src_m.group(1).strip() if src_m else "?"

        items.append({"title": title, "pub_date": pub, "source": src})
    return items


def parse_pubdate(s: str):
    """RFC 822 → datetime; tolerant zu fehlerhaften Strings."""
    if not s:
        return None
    try:
        from email.utils import parsedate_to_datetime
        dt = parsedate_to_datetime(s)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except Exception:
        return None


def keyword_hits(text: str, patterns: list) -> list:
    """Return list of patterns that matched."""
    found = []
    text_lower = text.lower()
    for p in patterns:
        if re.search(p, text_lower, re.IGNORECASE):
            found.append(p)
    return found


def score_mood(headlines: list, days: int) -> dict:
    """0-20 mood score based on headline keyword density.

    Algorithm:
      +5 per kiss-of-death phrase (max 10)
      +2 per wackel-signal (max 6)
      +1 per criticism-signal (max 6)
      -3 per positive-signal (min 0)
      Volume bonus: log(n_articles) * 1.0 (more press = more attention)
    """
    kiss = []; wackel = []; crit = []; positive = []
    for h in headlines:
        title = h["title"]
        kiss.extend(keyword_hits(title, KISS_OF_DEATH))
        wackel.extend(keyword_hits(title, WACKEL_SIGNALS))
        crit.extend(keyword_hits(title, CRITICISM_SIGNALS))
        positive.extend(keyword_hits(title, POSITIVE_SIGNALS))

    # Dedupe (same phrase in multiple headlines counts once)
    kiss_u = list(set(kiss))
    wackel_u = list(set(wackel))
    crit_u = list(set(crit))

    mood = 0
    mood += min(len(kiss_u) * 5, 10)
    mood += min(len(wackel_u) * 2, 6)
    mood += min(len(crit_u), 6)
    mood -= min(len(set(positive)) * 3, 9)

    # Volume bonus (more press attention = higher signal strength)
    if len(headlines) >= 20:
        mood += 3
    elif len(headlines) >= 10:
        mood += 2
    elif len(headlines) >= 5:
        mood += 1

    return {
        "mood_score": max(0, min(20, mood)),
        "kiss_of_death_signals": kiss_u,
        "wackel_signals": wackel_u,
        "criticism_signals": crit_u,
        "positive_signals": list(set(positive)),
        "articles_n": len(headlines),
    }


def fetch_coach_news(coach_name: str, club_name: str, days: int = 14) -> list:
    """Google News RSS query for "{coach_name}" {club} → list of headlines
    in the last `days` days."""
    # Quote the coach name so multi-word names match exactly
    query = f'"{coach_name}" {club_name}'
    url = GOOGLE_NEWS_RSS.format(query=urllib.parse.quote(query))
    try:
        xml = fetch(url)
    except Exception as e:
        print(f"  ⚠ {coach_name}: fetch failed — {e}")
        return []

    items = parse_rss(xml)
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    recent = []
    for it in items:
        dt = parse_pubdate(it["pub_date"])
        if dt and dt >= cutoff:
            recent.append(it)
    return recent


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--days", type=int, default=14, help="Lookback window")
    parser.add_argument("--only-tm-id", type=int, help="Test single coach")
    parser.add_argument("--rate-limit", type=float, default=2.0,
                        help="Sekunden zwischen requests (rate-limit)")
    args = parser.parse_args()

    if not HOT_SEAT.exists():
        print(f"✗ Run calc_hot_seat_score.py first ({HOT_SEAT} not found)")
        sys.exit(1)

    hs = json.load(open(HOT_SEAT))
    coaches = hs["scores"]

    if args.only_tm_id:
        coaches = [c for c in coaches if c["coach_tm_id"] == args.only_tm_id]

    out = {}
    print(f"\n=== Mood-Scraper (last {args.days} days, {len(coaches)} coaches) ===\n")

    for i, c in enumerate(coaches, 1):
        name = c["coach_name"]
        club = c["club_name"]
        coach_tm_id = c["coach_tm_id"]

        sys.stdout.write(f"  [{i:>2}/{len(coaches)}] {name:<24} ({club:<24}) ... ")
        sys.stdout.flush()

        headlines = fetch_coach_news(name, club, days=args.days)
        scored = score_mood(headlines, args.days)

        # Sample 5 most recent for inspection / display
        sample = []
        for h in headlines[:5]:
            sample.append({
                "title": h["title"][:120],
                "source": h["source"][:30],
                "date": h["pub_date"][:16],
            })

        out[str(coach_tm_id)] = {
            "name": name,
            "club": club,
            "league": c["league"],
            **scored,
            "headlines_sample": sample,
            "scraped_at": datetime.now(timezone.utc).isoformat(),
        }

        # Compact terminal output
        m = scored["mood_score"]
        flags = (
            ("K" if scored["kiss_of_death_signals"] else "·") +
            ("W" if scored["wackel_signals"] else "·") +
            ("C" if scored["criticism_signals"] else "·")
        )
        print(f"mood={m:>2} {flags} ({scored['articles_n']} arts)")

        time.sleep(args.rate_limit)

    # Save
    with open(OUT, "w") as f:
        json.dump({
            "_meta": {
                "scraped_at": datetime.now(timezone.utc).isoformat(),
                "lookback_days": args.days,
                "coaches": len(out),
                "source": "Google News RSS",
            },
            "signals": out,
        }, f, ensure_ascii=False, indent=2)

    # Highlight top mood-flagged coaches
    sorted_coaches = sorted(out.items(), key=lambda kv: -kv[1]["mood_score"])
    print("\n=== Top Mood-Flagged ===")
    for tm_id, s in sorted_coaches[:8]:
        sigs = []
        if s["kiss_of_death_signals"]: sigs.append(f"KISS:{len(s['kiss_of_death_signals'])}")
        if s["wackel_signals"]: sigs.append(f"WACK:{len(s['wackel_signals'])}")
        if s["criticism_signals"]: sigs.append(f"CRIT:{len(s['criticism_signals'])}")
        sigs_str = ", ".join(sigs) or "—"
        print(f"  mood={s['mood_score']:>2}  {s['name']:<24} ({s['club']:<22}) [{sigs_str}]")
        for h in s["headlines_sample"][:2]:
            print(f"    [{h['date'][:11]}] {h['source']:<22} {h['title'][:80]}")

    print(f"\n  → {OUT}")


if __name__ == "__main__":
    main()
