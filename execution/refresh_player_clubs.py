#!/usr/bin/env python3
"""Transfer-window refresh of player current_club (resumable).

Re-fetches FRESH TM HTML (bypasses the 30-day HTML cache) for every spieler id in
/tmp/player_refresh_ids.json, re-parses the profile, overwrites
data/person_profiles/spieler_<id>.json, and logs club changes (Vereinswechsel) to
data/player_transfers_<stamp>.json.

Resumable: each completed id is appended to data/.player_refresh_done.txt; a restart
skips ids already in that file. Safe to kill/relaunch.

Usage:
  python3 execution/refresh_player_clubs.py
  python3 execution/refresh_player_clubs.py --ids-file /tmp/player_refresh_ids.json
"""
from __future__ import annotations
import argparse, json, sys, time
from pathlib import Path
import random

BASE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE / "execution"))

import scrape_person_profiles as SPP
from bs4 import BeautifulSoup

# Disable SPP's fixed internal sleep — we apply our OWN randomized delay instead
# (fixed intervals are a detectable pattern; community-confirmed block trigger).
SPP.REQUEST_DELAY = 0

PROF = BASE / "data" / "person_profiles"
DONE = BASE / "data" / ".player_refresh_done.txt"

DELAY_MIN, DELAY_MAX = 6.0, 12.0   # randomized politeness window
BLOCK_STREAK = 15                  # consecutive fails → assume IP block, abort run


def cc_name(cc):
    if isinstance(cc, dict):
        return cc.get("name", "")
    return cc or ""


def fetch_fresh(tm_id: int) -> str | None:
    """Force a fresh fetch, bypassing the HTML cache (delete cached file first)."""
    cache_key = f"spieler_{tm_id}"
    cache_path = SPP.CACHE_DIR / f"{cache_key}.html"
    try:
        if cache_path.exists():
            cache_path.unlink()
    except Exception:
        pass
    time.sleep(random.uniform(DELAY_MIN, DELAY_MAX))
    url = f"{SPP.TM_BASE}/x/profil/spieler/{tm_id}"
    return SPP.fetch_page(url, cache_key)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ids-file", default="/tmp/player_refresh_ids.json")
    ap.add_argument("--stamp", default="refresh", help="suffix for the transfers log")
    ap.add_argument("--max-per-run", type=int, default=8000,
                    help="stop after N successful scrapes this run (block-avoidance batch cap)")
    args = ap.parse_args()

    ids = json.load(open(args.ids_file))
    done = set()
    if DONE.exists():
        done = {int(x) for x in DONE.read_text().split() if x.strip().isdigit()}
    todo = [i for i in ids if i not in done]
    avg = (DELAY_MIN + DELAY_MAX) / 2
    batch = min(len(todo), args.max_per_run)
    print(f"Target: {len(ids)} | already done: {len(done)} | to scrape: {len(todo)}")
    print(f"This run: max {args.max_per_run} | delay {DELAY_MIN}-{DELAY_MAX}s | "
          f"est batch ~{batch*avg/3600:.1f}h")

    transfers = []
    ok = fail = unchanged = 0
    streak = 0  # consecutive failures → block detector
    t0 = time.time()
    # Append done ONLY on success — a failed/blocked id stays in the queue and is
    # retried on the next run (no more silently marking thousands of blocks as done).
    done_fh = open(DONE, "a")
    tlog = BASE / f"data/player_transfers_{args.stamp}.json"
    master = BASE / "data/player_transfers_master.json"

    def save_transfers():
        json.dump(transfers, open(tlog, "w"), ensure_ascii=False, indent=2)
        # Cumulative master across ALL runs — merge + dedupe by tm_id so batches
        # never overwrite each other's findings.
        prev = {}
        if master.exists():
            try:
                for t in json.load(open(master)):
                    prev[t["tm_id"]] = t
            except Exception:
                pass
        for t in transfers:
            prev[t["tm_id"]] = t
        json.dump(list(prev.values()), open(master, "w"), ensure_ascii=False, indent=2)

    for i, tm_id in enumerate(todo, 1):
        if ok >= args.max_per_run:
            print(f"  ↳ max-per-run ({args.max_per_run}) erreicht — sauberer Stopp.")
            break
        pf = PROF / f"spieler_{tm_id}.json"
        old_cc = ""
        if pf.exists():
            try:
                old_cc = cc_name(json.load(open(pf)).get("current_club"))
            except Exception:
                pass
        html = fetch_fresh(tm_id)
        if not html:
            fail += 1
            streak += 1
            if streak >= BLOCK_STREAK:
                print(f"  ⚠ {streak} Fehler in Folge → IP-Block vermutet. Stoppe Lauf "
                      f"(geblockte IDs bleiben in Queue für nächsten Lauf).")
                break
            continue
        try:
            profile = SPP.parse_profile(html, tm_id, "spieler")
            new_cc = cc_name(profile.get("current_club"))
            json.dump(profile, open(pf, "w"), ensure_ascii=False, indent=2)
            ok += 1
            streak = 0
            if old_cc and new_cc and old_cc != new_cc:
                transfers.append({"tm_id": tm_id, "name": profile.get("name", ""),
                                  "from": old_cc, "to": new_cc})
            else:
                unchanged += 1
            done_fh.write(f"{tm_id}\n"); done_fh.flush()
        except Exception:
            fail += 1  # parse error: do NOT mark done, do NOT count as block streak
            streak = 0

        if ok and ok % 200 == 0:
            eta = (time.time() - t0) / ok * (batch - ok) / 3600
            print(f"  [ok={ok}/{batch}] transfers={len(transfers)} fail={fail} "
                  f"ETA {eta:.1f}h", flush=True)
            save_transfers()

    save_transfers()
    print(f"\nDone: ok={ok} transfers={len(transfers)} unchanged={unchanged} "
          f"fail={fail} time={(time.time()-t0)/3600:.1f}h")
    print(f"Transfers → {tlog}")


if __name__ == "__main__":
    main()
