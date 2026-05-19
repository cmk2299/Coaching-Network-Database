# Directive: Sprint 1 — Drill-Down Sub-Networks

## Goal
Enable recursive drill-down in all 36 coach dashboards. When a user clicks a contact in the network graph, that contact becomes the center and their own network is displayed. The dashboard JS already supports this via the `DRILLDOWN` constant — we just need to generate the data.

## Prerequisites
- [x] 35 coach dashboards generated (output/dashboards/)
- [ ] Uwe Rösler (TM-ID 1766, VfL Bochum) profile scraped and dashboard generated
- [ ] All dashboards deployed on Vercel

## Immediate Fixes (Before Drill-Down)

### Fix 1: Scrape Rösler
```bash
python execution/scrape_person_profiles.py --tm-id 1766
```
Then regenerate his dashboard:
```bash
python execution/generate_all_bl_coaches.py --only 1766
```

### Fix 2: Deploy to Vercel
```bash
cd output && npx vercel deploy --prod --yes
```
`vercel.json` already exists in `output/`.

---

## Drill-Down Architecture

### How it works in the dashboard
The template (`blessin_network_v3.html`) has two data constants:
- `const NETWORK = {...}` — the center coach's network (what we already generate)
- `const DRILLDOWN = {...}` — a map of contact names → their sub-networks

When a contact has `has_drilldown: true`, clicking them loads `DRILLDOWN[contact_name]` and renders it as the new center. Breadcrumbs let you navigate back.

### DRILLDOWN data structure
```json
{
  "Contact Name": {
    "center": "Contact Name",
    "center_info": { ... },
    "total_contacts": N,
    "stations": [...],
    "categories": [...],
    "contacts": [...]
  },
  "Another Contact": { ... }
}
```
Each entry is a full network object (same format as NETWORK).

### Which contacts get drill-down?
Not every contact needs a sub-network. Prioritize:
1. **All contacts that have a scraped profile** (i.e., `person_profiles/{tm_id}.json` exists) — these are coaches/staff with career history, so we can compute their network
2. **Skip players** — they don't have career history in our data (no profile scraped for most)
3. **Skip contacts without tm_url** — we can't link them anyway

### Implementation Plan

#### Step 1: Add `build_drilldown()` to `build_coach_network.py`

```python
def build_drilldown(center_network: dict, profiles: Dict[int, dict],
                    profile_index: Dict[Tuple[int, int], List[int]],
                    max_contacts: int = 50) -> dict:
    """
    Build DRILLDOWN dict for all drill-downable contacts in a network.

    Args:
        center_network: The main coach's network (output of build_network())
        profiles: Pre-loaded profiles
        profile_index: Pre-built inverted index
        max_contacts: Max contacts per sub-network (keep file size manageable)

    Returns:
        {contact_name: sub_network_dict, ...}
    """
    drilldown = {}

    for contact in center_network["contacts"]:
        # Skip players (no profile data)
        if contact.get("category") == "player_coached":
            continue

        # Check if we have a profile for this contact
        # We need to find their tm_id — it was removed in build_network() cleanup
        # FIX: preserve tm_id in contacts (see Step 2)
        tm_id = contact.get("_tm_id")
        if not tm_id or tm_id not in profiles:
            continue

        # Build their network
        sub_network = build_network(tm_id, profiles, profile_index)
        if not sub_network:
            continue

        sub_network = generate_background_summaries(sub_network)

        # Trim to max_contacts (keep top contacts by strength)
        if len(sub_network["contacts"]) > max_contacts:
            sub_network["contacts"] = sub_network["contacts"][:max_contacts]
            sub_network["total_contacts"] = len(sub_network["contacts"])

        # Sub-networks don't get their own drill-down (no recursion beyond 1 level)
        for c in sub_network["contacts"]:
            c["has_drilldown"] = False

        drilldown[contact["name"]] = sub_network
        contact["has_drilldown"] = True

    return drilldown
```

#### Step 2: Preserve tm_id in contacts (currently removed in cleanup)

In `build_network()`, the line `c.pop("tm_id", None)` removes the tm_id we need for drill-down. Change to:
```python
# Instead of removing tm_id completely, rename to _tm_id for internal use
c["_tm_id"] = c.pop("tm_id", None)
```

Then in the final output cleanup (after drill-down is computed), remove `_tm_id`:
```python
for c in contacts_list:
    c.pop("_tm_id", None)
```

#### Step 3: Update `generate_dashboard.py`

Change the drilldown injection from hardcoded `{}` to actual data:
```python
drilldown_json = json.dumps(drilldown_data, ensure_ascii=False, separators=(',', ':'))
```

The `generate_dashboard()` function signature changes to accept drilldown:
```python
def generate_dashboard(network: dict, output_path: Path, drilldown: dict = None):
    drilldown_json = json.dumps(drilldown or {}, ensure_ascii=False, separators=(',', ':'))
```

#### Step 4: Update `generate_all_bl_coaches.py`

After `build_network()` and `generate_background_summaries()`, add:
```python
drilldown = build_drilldown(network, profiles, profile_index)
# Then pass to generate_dashboard:
generate_dashboard(network, dashboard_path, drilldown=drilldown)
```

#### Step 5: Redeploy
```bash
python execution/generate_all_bl_coaches.py
cd output && npx vercel deploy --prod --yes
```

---

## Performance Considerations

- Each drill-downable contact requires a `build_network()` call (~2-5s each)
- If a coach has ~50 drill-downable contacts, that's ~100-250s per coach
- For 36 coaches: ~60-150 minutes total (significant but one-time)
- **Optimization**: Cache network JSONs in `data/networks/` — if already computed for another coach, reuse
- **File size**: Each dashboard HTML could grow to 5-15 MB with full drilldown data. Monitor this.
  - If too large: limit to top 20 contacts by strength, or lazy-load drilldown from separate JSON files

## Testing
1. Generate drill-down for Blessin first: `python execution/generate_all_bl_coaches.py --only 26099`
2. Open the dashboard, click on known contacts (e.g. a Co-Trainer), verify sub-network loads
3. Check breadcrumb navigation works (back to center)
4. Verify file size is reasonable (<20 MB per dashboard)
5. Then run full batch

## Learnings
- [2026-03-21] Drilldown generation is fast: 29s for all 36 coaches (0.8s per coach avg)
- [2026-03-21] File sizes: 518K (smallest, Schmidt) to 5.2M (largest, Kovac). Total output: 109MB. All under 20MB threshold.
- [2026-03-21] Blessin: 70 contacts → 53 drill-down sub-networks (76% drilldown coverage for non-player contacts)
- [2026-03-21] scrape_person_profiles.py needed --tm-id flag added (was missing). Also --type=trainer/spieler.
- [2026-03-21] strip_internal_fields() needed to clean _tm_id from serialized network JSON
- [2026-03-21] Performance much better than estimated (29s vs 60-150min) because profile_index is in memory
