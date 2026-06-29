# Football Coaches DB — Operator Runbook

Closes the **bus-factor=1** audit gap (AUDIT_2026-06-20). A second operator should
be able to keep the site healthy from this document alone, without prior context.

---

## Daily refresh (automated, 06:00)

LaunchAgent `com.footballdb.daily-refresh` runs `run_mvp.sh`:

1. **Staff scrape** (max-age 1d via `--max-age-days=1`)
2. **Network rebuild** for all coaches (BL1/2/3 + historical + SDs + NLZ)
3. **Dashboard regen** (`regenerate_dashboards.py --changed-only` — incremental;
   skips dashboards whose source `data/networks/{tm_id}.json` is older than the
   existing HTML)
4. **Club pages** (`generate_club_pages.py`)
5. **Quality gate (Step 4b)** — BLOCKS deploy on any defect:
   - `logic_audit.py` (LP/LC/LX checks)
   - `scoring_audit.py` (SC1–5: score range, strength, ordering)
   - `validate_pipeline.py` (artifact-count vs baseline, >5% drop fails)
6. **Vercel deploy** (`--archive=tgz`) + content-level smoke (≥50 coach rows live)

Verify/control:
```bash
bash setup_daily_refresh.sh --verify       # is plist loaded?
bash run_mvp.sh                            # manual run
bash run_mvp.sh --skip-deploy              # local-only test
SKIP_GATE=1 bash run_mvp.sh                # emergency bypass (use only when audit
                                           # itself is broken, not its findings)
```

---

## Other scheduled jobs

| LaunchAgent | When | Purpose | Setup |
|---|---|---|---|
| `com.footballdb.audit-loop` | 02:30 daily | Run `run_audit_loop.sh 500 3` + volume gate; logs drift overnight | `bash setup_audit_schedule.sh` |
| `com.footballdb.backup` | 03:30 daily | Snapshot `data/` to `$BACKUP_DEST` (default `~/coachdb-backups`) | `BACKUP_DEST=… bash setup_backup_schedule.sh` |
| `com.footballdb.daily-refresh` | 06:00 daily | `run_mvp.sh` full pipeline | `bash setup_daily_refresh.sh` |

For TRUE disaster recovery point `BACKUP_DEST` at an external drive or remote host.

---

## Common ops

### Add/swap a current coach (`coach_overrides.json`)

Append to `data/coach_overrides.json`:

- **Coach leaves**: add to `sacked` (`{club_tm_id, club, tm_id, name, note, added}`)
- **Coach arrives**: add to `appointed` (same shape + `replaces_tm_id` for the
  outgoing HC + `tm_url`). The index/status pick them up automatically.

Apply locally without full refresh:
```bash
python3 execution/check_coach_changes.py      # rebuilds output/api/check-coaches.json
python3 execution/generate_all_bl_coaches.py --skip-networks --all-networks --leagues BL1 BL2 BL3
cd output && npx vercel deploy --prod --yes --archive=tgz --scope cmk2299s-projects
```

### Update league memberships (Auf-/Abstiege at season turn)

Edit `data/club_registry.json` `leagues['YYYY/YYYY']` for each affected club
(verify against Wikipedia, **also for 3.Liga↔Regionalliga** churn). Then re-run
`run_mvp.sh` — default season already 2026.

### Hide a coach from index (e.g. departed but networks valuable)

Add `tm_id` to `data/index_exclude_ids.json`. Dashboards stay live for drilldown;
just removed from main index. ⚠ Index generator exempts `_league_hc` flag, so
current head coaches are never silently dropped — verify if a coach disappears.

### Disaster recovery

Pre-flight: confirm baseline.
```bash
bash setup_backup_schedule.sh --verify     # latest snapshots
ls -dt ~/coachdb-backups/* | head
```

Recovery (data/ wipe):
```bash
SNAP=$(ls -dt ~/coachdb-backups/* | head -1)
rsync -a "$SNAP/data/" data/
python3 execution/validate_pipeline.py     # ensure restored baseline OK
bash run_mvp.sh --skip-staff               # rebuild from restored data
```

If `data/networks/*.json` survived but dashboards didn't, just run
`regenerate_dashboards.py` (no `--changed-only`) and deploy.

---

## Diagnostic commands

```bash
bash run_audit_loop.sh 500 3               # logic + scoring + volume audit
python3 execution/validate_pipeline.py     # baseline vs current
python3 execution/logic_audit.py --json /tmp/x.json   # full report
python3 execution/scoring_audit.py --json /tmp/x.json # full report
python3 -m pytest tests/ -v                # unit tests (110+ as of 2026-06-29)
gh run list --limit 5                      # CI status
```

Curl smoke:
```bash
# Index alive + has rows
curl -s https://coach-network-explorer.vercel.app/ | grep -c 'class="row-club"'
# Status API current
curl -s https://coach-network-explorer.vercel.app/api/check-coaches.json | python3 -m json.tool | head -50
# Sample dashboard (thin-shell + external JSON since 2026-06-26)
curl -sI https://coach-network-explorer.vercel.app/dashboards/vincent_kompany_network | grep -i x-vercel-cache
```

---

## Failure modes & first response

| Symptom | First check | First fix |
|---|---|---|
| Daily refresh failed (ntfy push) | `tail -50 logs/mvp.log` | Re-run with `--skip-deploy` to isolate stage |
| Audit gate blocks deploy | `python3 execution/logic_audit.py --json /tmp/x.json` | Read `/tmp/x.json`; fix root cause OR `SKIP_GATE=1` (only if audit broken) |
| Index missing coaches | `python3 execution/check_coach_changes.py` | Add `appointed` override; check `index_exclude_ids.json` |
| Dashboards 404 | Did regenerate run? Check `output/dashboards/` count | Re-run regen WITHOUT `--changed-only` |
| Vercel deploy "Internal Server Error" | Output size? (`du -sh output/`) | Always use `--archive=tgz` flag (4054 files > Vercel Files-API limit) |
| TM scraper "blocked" | Check `tail logs/scrape_*.log` for 429/CF marker | Wait 1h, restart; `looks_like_block` sentinel prevents poison-caching |
| persons_master out of sync | Touch a profile newer than master | `preload_all_profiles` falls back to glob path automatically |

---

## Architecture quick-ref (operator-relevant)

- **Layer 1** `directives/*.md` = SOPs (read for "what to do")
- **Layer 2** Claude orchestration (read for "why")
- **Layer 3** `execution/*.py` deterministic scripts. Shared helpers in
  `execution/lib/` (`normalization.py`, `network_stages.py`, `scoring.py`,
  `dashboard_index.py`, `logging_setup.py`).
- **Data** `data/` (gitignored — backup is git's job here!): `club_registry.json`,
  `person_profiles/` (~99k files, 389MB), `persons_master.json` (~300MB, lazy +
  master-fast-path), `networks/` (3,323 per-coach), `staff/`, `squads/`,
  `coaches.db` (SQLite mirror, FK gate in build).
- **Output** `output/` (also gitignored): 4,054 dashboards as **thin-shell HTML
  + `{slug}_network.json`** (serve-from-DB), `index.html`, `clubs/*.html`,
  `api/check-coaches.json`, `vercel.json` (noindex + Cache-Control headers).
- **CI** GitHub Actions on every push: ruff (F,E9 hard gate, ignoring F841),
  compileall, pytest.

Reality check: **persons_master ~300MB / 99,211 profile files / 110+ tests / 0
FK violations** (the run_mvp gate enforces this — older docs listed wrong numbers).
