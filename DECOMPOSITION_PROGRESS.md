# build_network() Decomposition — Progress & Plan

Goal: break the monolithic `build_network()` in `execution/build_coach_network.py`
(was ~2,123 lines / ~3,000-line file) into named, individually-testable stages in
`execution/lib/`, **without changing output**.

## Method (safety net — use this for every future step)

1. **Golden harness** `/tmp/golden_harness.py` builds 5 diverse networks
   (Kompany 69681, Klos-SD 60956, Hütter 5018, Flick 67, Rapp 24235) with
   `json.dumps(..., sort_keys=True)`. Snapshot a baseline before changing code:
   `python3 /tmp/golden_harness.py /tmp/golden_BASE`
2. Extract a stage → `lib/`, replace the inline block with a call.
3. Re-run harness to a new dir, **byte-diff vs baseline — must be identical**:
   `for id in 69681 60956 5018 67 24235; do diff -q /tmp/golden_BASE/$id.json /tmp/golden_NEW/$id.json; done`
4. Add unit tests in `tests/`, `python3 -m pytest tests/`.
5. Commit + push → CI (`.github/workflows/ci.yml`) gates pytest + compile.

> ⚠ `build_network()` was non-deterministic before this work — if golden diffs
> show churn unrelated to your change, it's a latent ordering/`id()` bug; fix that
> first (see step 1 below) rather than masking it.

## Done (6 steps, all golden-verified + CI-green, 78 tests)

| Step | Commit | Extracted → `lib/` | Notes |
|------|--------|--------------------|-------|
| 1 | `0db9c15` | `enrich_cross_references` → network_stages | + fixed 2 non-determinism bugs: `_merged_aliases` persisted `id(c)` (memory address); unsorted set iteration in notes/stations |
| 2 | `32681be` | `normalize_contact_urls`, `remove_connection_self_loops` → network_stages | PATTERN 27 + 26b |
| 3 | `c245e9f` | 7 pure scoring-math fns → scoring.py | role_weights, score_relationship/league/recency, category_floor, gs_bonus, multi_station_multiplier |
| 4 | `83e545a` | `is_still_active_player`, `determine_today_role` → scoring | former-teammate role detection (Marco-Bode dual-namespace area) |
| 5 | `72c19f5` | `score_former_teammate` → scoring | ~145-line promotion **mutator** (rewrites category/role/tm_id/etc.); inputs now explicit params |
| 6 | `1d02e0c` | `parse_coach_stations` → network_stages | coach career → stations defaultdict |

`build_coach_network.py`: ~3,000 → **2,592 lines**. New modules:
`lib/network_stages.py`, `lib/scoring.py` (+ `tests/test_network_stages.py`,
`tests/test_scoring.py`).

## Remaining inline stages (candidates, in build order)

These are **data-gathering** stages that read external files / indexes and append
to `contacts_map`. More coupled than the post-processing/scoring stages already
done — each needs several closure inputs threaded as explicit params. Extract the
same way (golden-diff each). Approx. line ranges in current file:

| Block | ~lines | Coupling / inputs to thread | Risk |
|-------|--------|------------------------------|------|
| Current-staff colleagues (Step 1) | ~714–762 | staff files, coach_stations, CURRENT_SEASON grace window | med |
| Shared-career-stations (Step 2, inverted index) | ~808–908 | inverted persons index, coach_club_seasons, profiles | **high** (the hot path) |
| Former-teammates from playing career (Step 2b) | ~908–1008 | playing-career squads, profiles | med |
| GemeinsameSpiele integration (Step 2c) | ~1008–1088 | data/gemeinsame_spiele/*, existing contacts | med |
| Players-coached (Step 3) | ~1088–1247 | squad files, real_players_used | med |
| Lehrgang colleagues (Step 4) | ~1247–1361 | coaching_licenses.json | low–med |
| Profile-enrichment loop | ~1361–1396 | profiles, F1 dual-namespace guard | med |

Suggested order: **Lehrgang** (most self-contained) → **GemeinsameSpiele** →
**players-coached** → **former-teammates** → **current-staff** → **shared-stations**
last (highest-risk, hottest path). Each should return its new contacts (or mutate
`contacts_map`) and keep the golden diff clean.

## To resume
```
python3 /tmp/golden_harness.py /tmp/golden_BASE      # re-baseline (harness is in /tmp; recreate if lost)
# ...extract one block to lib/, wire the call...
python3 /tmp/golden_harness.py /tmp/golden_NEW && diff per-id   # must be identical
python3 -m pytest tests/ && git commit && git push   # CI gates the rest
```
Harness source (recreate if `/tmp` was cleared): preload once via
`build_coach_network.preload_all_profiles()` + `build_profile_index()`, then
`build_network(id, profiles, idx)` for the 5 ids, dump sort_keys=True.
