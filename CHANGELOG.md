# Changelog

Notable engineering changes since the AUDIT_2026-06-20 hardening track started.
Older history lives in git directly; this file curates the architectural shifts.

---

## 2026-06 — Phase-2 engineering loop (in progress)

Sustained alternation between **`build_network()` decomposition** and
**complementary safety/perf wins**, each step golden-verified byte-identical
on 5 diverse coach networks (Kompany / Klos / Hütter / Flick / Rapp) and
gated by CI (ruff F,E9 + compile + pytest).

### `build_network()` decomposition: 2941 → 2366 lines (–575, 17 stages)

All extracted into `execution/lib/network_stages.py` (or `lib/scoring.py`),
with dependencies injected so the lib stays decoupled from build_coach_network
internals:

| Stage | Lib symbol |
|---|---|
| 1 | `enrich_cross_references` |
| 2 | `normalize_contact_urls` / `remove_connection_self_loops` |
| 3 | `lib/scoring.py` (full relevance-score math) |
| 4 | `score_former_teammate` (~145 LOC promotion logic) |
| 5 | `score_former_teammate` (mutator-form fit) |
| 6 | `parse_coach_stations` |
| 7 | `drop_low_value_categories` |
| 8 | `resolve_post_career_roles` |
| 9 | `scoring_finalizer` (single chokepoint: strength + canonical sort) |
| 10 | `sanitize_id_integrity` (TM namespace-collision guard) |
| 11 | `dedupe_same_profile_contacts` (LX2 same-URL merger) |
| 12 | `current_career_first` + `is_future_career_entry` (PATTERN 15) |
| 13 | `compute_playing_career_window` |
| 14 | `CAT_ORDER` constant deduplication |
| 15 | `refine_executive_tier` |
| 16 | `add_current_staff_colleagues` (Section 1) |
| 17 | `add_staff_at_career_stations` (Section 1b) |

### Determinism / correctness fixes uncovered en route

- **`_merged_aliases` id() leak**: persisted Python memory addresses on
  contacts without a parseable tm_url → non-deterministic output. Now only
  real tm_ids.
- **Unsorted set iteration**: `player_coached` notes + cross-ref stations
  produced random club order across rebuilds. Now sorted.
- **Stale `is_future_career_entry`**: dropped orphan `re as _re_module`
  import after move.

### Performance wins (production)

- **`preload_all_profiles` fast-path**: 40.8 s → 8.5 s (**5×**) by reading
  the pre-built `persons_master.json` when newer than every individual
  profile; cheap mtime safety auto-falls-back to glob otherwise.
  Strict-superset output (74 enrichments / 5 networks, 0 regressions).
- **`dashboard_index` lazy master + shared scan**: OOM-killed (exit 137) →
  14.0 s + 0.20 s; `persons_master` no longer eagerly loaded twice; both
  functions share one memoized network scan.
- **`regenerate_dashboards --changed-only`**: incremental mode — daily
  refresh skips dashboards whose source `data/networks/{tm_id}.json` is
  older than the existing HTML. Cuts a daily run from ~800 s to seconds.
- **Serve-from-DB**: all 4054 dashboards converted to thin-shell HTML +
  external `{slug}_network.json` (single canonical data file per dashboard;
  data-only changes re-upload only the JSON; HTML cacheable).

### Safety / operability wins

- **Deploy quality-gate** (`run_mvp.sh` Step 4b): blocking gate on
  `logic_audit.py` + `scoring_audit.py` + `validate_pipeline.py` +
  `validate_coach_overrides.py` before any Vercel deploy. `SKIP_GATE=1`
  override only for emergencies.
- **`validate_pipeline.py`**: artifact-count vs baseline; >5 % drop fails
  the deploy. `--max-baseline-age-days` warns on fossilized baselines.
- **`validate_coach_overrides.py`**: catches typos in
  `data/coach_overrides.json` (zero tm_id, missing required, duplicate
  appointed) before they ship.
- **Scraper block-detection**: `scrape_person_profiles.looks_like_block`
  prevents caching anti-bot/interstitial pages as profiles for 30 days
  (closes the documented data-corruption vector). 14 unit tests.
- **Structured logging** (`lib/logging_setup.py`): configured logger + JSON
  run-summaries in `logs/runs/<day>.jsonl` for drift detection. Wired into
  pipeline entry points.
- **Backups**: `backup_data.sh` + `setup_backup_schedule.sh` (nightly
  03:30 LaunchAgent, offsite via `$BACKUP_DEST`). Closes the
  May-21 wipe vector.
- **Nightly audit**: `setup_audit_schedule.sh` (02:30 LaunchAgent) runs
  `run_audit_loop.sh` continuously, catches drift overnight before refresh.
- **Operator runbook** (`RUNBOOK.md`): single-page playbook covering
  daily refresh, scheduled jobs, common ops (override a coach, season
  turn, hide a contact-coach), disaster recovery, failure modes.

### Reproducibility

- **CI**: GitHub Actions runs ruff (F,E9 hard gate excluding F841),
  compileall, pytest on every push. Test suite **143 → growing** as
  each extraction adds coverage.
- **`requirements.txt`** pinned to exact versions (was all `>=`).
- **`scoring_finalizer`**: single chokepoint guarantees every contact has
  `strength` and `contacts_list` is in canonical score order — caught
  by `scoring_audit.py` post-build.

### Documentation cleanup

- CLAUDE.md doc-drift: `persons_master` "51.9 MB" → "~300 MB ~99k entries"
  (66× off); "47 tests" → "143+ tests".

---

## Audit-driven hardening (AUDIT_2026-06-20)

See `AUDIT_2026-06-20.md` for the three-perspective audit (Data Eng / CTO /
CIO) that initiated this hardening. Open P0/P1 items remaining are owner-
gated (legal/DSGVO + Vercel auth-gate enable; not engineering).
