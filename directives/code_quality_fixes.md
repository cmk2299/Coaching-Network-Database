# Directive: Code Quality Fixes

## Context
Full project audit (26.03.2026) identified code-level issues across 87 Python scripts. These don't affect production functionality but increase maintenance risk, especially before BL3 expansion (Sprint 7) adds complexity.

**Priority:** Complete before Sprint 7 (BL3 + NLZ + Historical coaches).

---

## Fix 1: Extract Shared `lib/normalization.py` (P0)

### Problem
`normalize_club()` is defined in `build_coach_network.py` with 22 mappings + registry lookup. Five other scripts define their own `normalize_club_name()` with partial/outdated mappings. When mappings change, only `build_coach_network.py` gets updated.

### Affected Files

| File | Function | Status |
|------|----------|--------|
| `build_coach_network.py:93` | `normalize_club()` ← canonical | Source of truth |
| `consolidate_network_data.py` | `normalize_club_name()` | Outdated copy |
| `identify_coach_connections.py` | `normalize_club_name()` | Outdated copy |
| `analyze_youth_executive_overlaps.py` | `normalize_club_name()` | Outdated copy |
| `analyze_sd_coach_overlaps.py` | `normalize_club_name()` | Outdated copy |
| `recompute_all_overlaps_fixed.py` | uses `normalize_club_name()` | Imports outdated |

Already importing correctly from `build_coach_network.py`:
- `build_sqlite.py:29`
- `scrape_foreign_staff.py:26`
- `test_data_integrity.py`

### Implementation

#### Step 1: Create shared module
```bash
mkdir -p execution/lib
touch execution/lib/__init__.py
```

#### Step 2: Create `execution/lib/normalization.py`
Move from `build_coach_network.py`:
- `CLUB_NAME_NORMALIZE` dict (22+ entries)
- `normalize_club(name, club_tm_id=None)` function
- `load_club_registry()` helper (if used by normalize_club)

Also add nationality resolution (currently duplicated between `build_coach_network.py` ~line 585 and `generate_all_bl_coaches.py` ~line 133):
- `resolve_nationality(nationality_list)` → returns single string
- Filter logic: exclude `' U'`, `'DDR'`, `'Jugoslawien'`, `'Sowjetunion'`, `'Tschechoslowakei'`
- If 2+ remain: return `[1]` (real nationality after Verbandsgebiet)
- If 1 remain: return `[0]`
- Else: return first original entry or ""

```python
# execution/lib/normalization.py

CLUB_NAME_NORMALIZE = {
    # Copy all 22+ entries from build_coach_network.py
}

DISSOLVED_STATES = ['Jugoslawien', 'Sowjetunion', 'DDR', 'Tschechoslowakei']

def normalize_club(name: str, club_tm_id: int = None) -> str:
    """Normalize club name to canonical form."""
    # Move full implementation from build_coach_network.py
    ...

def resolve_nationality(nationality) -> str:
    """Resolve TM nationality list to single display nationality."""
    if isinstance(nationality, str):
        return nationality
    if not isinstance(nationality, list) or not nationality:
        return ""
    real = [n for n in nationality if not any(x in n for x in DISSOLVED_STATES + [' U'])]
    if len(real) >= 2:
        return real[1]
    elif real:
        return real[0]
    return nationality[0]
```

#### Step 3: Update imports in ALL files

Replace in `build_coach_network.py`:
```python
# Remove: CLUB_NAME_NORMALIZE dict + normalize_club() function definition
from lib.normalization import normalize_club, resolve_nationality, CLUB_NAME_NORMALIZE
```

Replace in `build_sqlite.py`:
```python
# Change: from build_coach_network import normalize_club
from lib.normalization import normalize_club
```

Replace in 5 legacy files (delete their local `normalize_club_name()` definition):
```python
import sys, os
sys.path.insert(0, os.path.dirname(__file__))
from lib.normalization import normalize_club
# Then: replace all normalize_club_name(x) calls with normalize_club(x)
```

Replace in `generate_all_bl_coaches.py` (~line 133):
```python
from lib.normalization import resolve_nationality
# Then: replace inline nationality resolution with resolve_nationality(nat)
```

#### Step 4: Test
```bash
python -c "from execution.lib.normalization import normalize_club, resolve_nationality; print(normalize_club('Bor. Dortmund')); print(resolve_nationality(['Deutschland', 'Kroatien']))"
# Expected: Borussia Dortmund / Kroatien
```

---

## Fix 2: Replace Bare `except:` (P1)

### Problem
18 files use bare `except:` which catches ALL exceptions (including KeyboardInterrupt, SystemExit) and silently swallows errors.

### Affected Files

| File | Lines | Fix |
|------|-------|-----|
| `scrape_hiring_managers_websearch.py` | 46 | `except (ValueError, KeyError, requests.RequestException) as e:` |
| `enrich_decision_makers.py` | 61 | `except Exception as e:` + `logging.warning(f"...")` |
| `scrape_companions_bulk.py` | 65 | `except Exception as e:` |
| `integrate_coaches_with_matches.py` | 187 | `except (KeyError, IndexError) as e:` |
| `monitor_scraping_progress.py` | 49 | `except Exception as e:` |
| `auto_enrich_bundesliga_hiring_managers.py` | 47 | `except Exception as e:` |
| `analyze_sd_coach_overlaps.py` | 74 | `except (KeyError, ValueError) as e:` |
| `scrape_historical_staff.py` | 51, 184 | `except Exception as e:` |
| `analyze_youth_executive_overlaps.py` | 134 | `except (KeyError, ValueError) as e:` |
| `scrape_assistant_coaches.py` | 190, 238, 252 | `except Exception as e:` + log |
| `scrape_sporting_directors.py` | 194, 248, 263 | `except Exception as e:` + log |
| `scrape_transfermarkt_news.py` | 50 | `except Exception as e:` |
| `scrape_club_news.py` | 63 | `except Exception as e:` |

### Implementation
For each file:
1. Read the `except:` block to understand what it catches
2. Replace `except:` with the narrowest appropriate exception type
3. Add `as e:` and a `print(f"Warning: {e}")` or `logging.warning(...)` line
4. If the block just does `pass` or `continue`, add the warning before that

**Minimum fix:** Replace all `except:` with `except Exception as e:` and log. This still catches too broadly but at least doesn't swallow KeyboardInterrupt and logs the error.

### Test
```bash
grep -rn "except:" execution/*.py | grep -v "except " | grep -v "#"
# Expected: 0 results (no bare except remaining)
```

---

## Fix 3: Pytest Foundation (P1)

### Problem
87 Python scripts, 0 automated tests. Critical parsing logic (nationality resolution, club normalization, career parsing) has no test coverage.

### Implementation

#### Step 1: Create test structure
```bash
mkdir -p tests
touch tests/__init__.py
```

#### Step 2: Create `tests/test_normalization.py`
```python
"""Tests for club name normalization and nationality resolution."""
import pytest
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'execution'))
from lib.normalization import normalize_club, resolve_nationality

class TestNormalizeClub:
    def test_short_to_full(self):
        assert normalize_club("Bor. Dortmund") == "Borussia Dortmund"
        assert normalize_club("F. Düsseldorf") == "Fortuna Düsseldorf"
        assert normalize_club("TSG 1899 Hoffenheim") == "TSG Hoffenheim"

    def test_already_canonical(self):
        assert normalize_club("Borussia Dortmund") == "Borussia Dortmund"
        assert normalize_club("FC Bayern München") == "FC Bayern München"

    def test_empty_and_none(self):
        assert normalize_club("") == ""
        assert normalize_club("Unknown Club") == "Unknown Club"

class TestResolveNationality:
    def test_single_nationality(self):
        assert resolve_nationality(["Deutschland"]) == "Deutschland"

    def test_dual_nationality_prefers_second(self):
        assert resolve_nationality(["Deutschland", "Kroatien"]) == "Kroatien"

    def test_filters_dissolved_states(self):
        assert resolve_nationality(["Deutschland", "Jugoslawien (SFR)", "Österreich"]) == "Österreich"
        assert resolve_nationality(["DDR", "Deutschland"]) == "Deutschland"

    def test_filters_u_teams(self):
        assert resolve_nationality(["Deutschland U21", "Deutschland"]) == "Deutschland"

    def test_string_passthrough(self):
        assert resolve_nationality("Deutschland") == "Deutschland"

    def test_empty(self):
        assert resolve_nationality([]) == ""
        assert resolve_nationality("") == ""
```

#### Step 3: Create `tests/test_parsing.py`
```python
"""Tests for TM HTML parsing edge cases."""
import pytest
import re

def fix_concatenated_name(raw_name: str) -> str:
    """Replicate the name fix from scrape_person_profiles.py."""
    return re.sub(r"([a-zäöüß])([A-ZÄÖÜ])", r"\1 \2", raw_name)

class TestNameParsing:
    def test_concatenated_name(self):
        assert fix_concatenated_name("RainerBonhof") == "Rainer Bonhof"
        assert fix_concatenated_name("NikoKovac") == "Niko Kovac"

    def test_normal_name(self):
        assert fix_concatenated_name("Alexander Blessin") == "Alexander Blessin"

    def test_umlaut_name(self):
        assert fix_concatenated_name("ChristianTitz") == "Christian Titz"
```

#### Step 4: Add pytest to workflow
```bash
pip install pytest
pytest tests/ -v
```

Add to `run_mvp.sh` (after network build, before deploy):
```bash
pytest tests/ -v --tb=short || { echo "Tests failed!"; exit 1; }
```

---

## Fix 4: Update `expand_international_leagues.md` Phase 3 Status (P1)

### Problem
Directive still says Phase 3 is 🔄 — it's ✅ done.

### File
`directives/expand_international_leagues.md`, line 155-158

### Fix
```
### Phase 3: Profile Scraping ✅ (2026-03-26)
- **34,513 profiles** scraped (27,734 Spieler + 6,779 Coaches/Staff)
- **Master-Datei:** 51.9 MB
- Auto-resume mit `--limit` Batches funktionierte zuverlässig
```

---

## Fix 5: Correct Audit Report — Filter Finding Was Wrong (P0)

### Problem
`output/FULL_AUDIT_2026-03-26.md` reports that the dashboard filter hides 30-70% of contacts by default. This is **incorrect** — the template confirms:
- `proFilterActive = false` (line 285) — Pro filter OFF by default
- `activeFilters.stations.clear()` / `activeFilters.categories.clear()` — No station/category filters active
- All contacts are shown on load. Filter is opt-in (positive inclusion).

### Fix
Delete or correct the P0 finding in the audit report. The contact count differences the audit saw (91 vs 174 etc.) were likely from a different source — possibly the audit agent was reading stale data or comparing network JSON contact counts vs. dashboard filtered views during a previous session.

---

## Execution Order

1. **Fix 5** — Correct audit report (avoids acting on a false finding)
2. **Fix 4** — Update directive (10 seconds)
3. **Fix 1** — Extract `lib/normalization.py` (main effort, ~30 min)
4. **Fix 3** — Create pytest tests (depends on Fix 1)
5. **Fix 2** — Replace bare `except:` (mechanical, ~20 min)
6. **Verify:** `pytest tests/ -v` + spot-check `generate_all_bl_coaches.py` still works

### After code fixes, run dashboard regeneration:
```bash
python execution/generate_all_bl_coaches.py
cd output && npx vercel deploy --prod --yes --scope cmk2299s-projects
```

---

## Learnings
(Update as you go)
