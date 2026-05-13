# RosterV2 — Resort Workforce Optimisation System

## Project Purpose

Automated weekly roster and workforce optimisation for a holiday resort (~308–323 staff).
Uses Google OR-Tools CP-SAT solver to generate shift assignments, then exports an Excel
report to SharePoint via Power Automate.

## Architecture

```
Dataverse (source of truth)
  ↓  Power Automate (weekly trigger, JSON payload)
Cloud Run — app.py (Flask API, this repo)
  ↓  Results JSON
Power Automate → Excel → SharePoint
```

**Module map:**

| File | Role |
|------|------|
| `main.py` | Local CLI entry point |
| `app.py` | Flask API (Cloud Run entry point) |
| `data/config.py` | All static config: staging bands, role offsets, penalties, rules |
| `data/sample_data.py` | Dummy staff + week data (Dataverse placeholder); imports real OD team from `ocean_drive_data.py` |
| `data/ocean_drive_data.py` | **Real** Ocean Drive team (33 staff, sourced from Excel rota) |
| `data/shift_calculator.py` | Derives shift times and coverage targets from schedules |
| `solver/core.py` | CP-SAT model: variables, constraints, penalties, extraction |
| `reporter/console.py` | Terminal summary output |
| `reporter/excel.py` | Excel workbook builder |

## Running Locally

```bash
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
python main.py
# Output: outputs/roster_report.xlsx
```

---

## Week Structure & Business Logic

### Day Indexing
```
0=Fri  1=Sat  2=Sun  3=Mon  4=Tue  5=Wed  6=Thu
```
- **Fri batch:** days 0–2 (Fri/Sat/Sun)
- **Mon batch:** days 3–6 (Mon–Thu)
- **Changeover days:** 0 (Fri) and 3 (Mon) — guests depart and arrive same day

### Changeover Logic
- **Departure breakfast** (Fri/Mon 08:00–10:00): uses the *previous* batch's guest count for staging
- **Opening dinner** (16:30–19:00): uses the *current* batch's guest count

### Staff Types
| Type | Home venue | Accommodation | Can cover bars |
|------|-----------|---------------|----------------|
| `normal` | Yes | No (except accom dept) | No |
| `tm_plus_1` | Yes | Mon/Fri changeover | Yes (≤2 venues/day) |
| `tm_plus_2` | Yes | Mon/Fri changeover | Yes (≤3 venues/day) |

TM+ **cannot rest on Mon or Fri** (hard constraint).

### Departments & Venue Pairs
- **Buffets:** The Deck ↔ Yacht Club (YC staffed from Deck pool); Ocean Drive ↔ Quay Side (QS staffed from OD pool)
- **Bars:** Centre Stage, Reds, Studio 36, Bar Rosso, IOTG
- **Accommodation:** 186 normal staff only; no TM+ in this dept

### Staff Counts (current sample data)
| Team | Normal | TM+1 | TM+2 | Total | Source |
|------|--------|------|------|-------|--------|
| The Deck | 15 | 21 | 5 | 41 | **real — `deck_data.py`** |
| Ocean Drive | 7 | 24 | 2 | 33 | **real — `ocean_drive_data.py`** |
| Bars | 15 | 30 | 0 | 45 | generated |
| Accommodation | 186 | 0 | 0 | 186 | generated |

### Venue Role Exclusions
Individual venues can opt out of specific roles via `"excluded_roles"` in `BUFFET_VENUES` (`data/config.py`).
Both `buffet_shifts_for_day` and `staging_for_venue_day_service` read this key and skip those roles automatically.

Current exclusions:
- **Yacht Club:** `excluded_roles: ["host"]` — YC does not need a dedicated host position

To exclude a role from a venue, add/edit `"excluded_roles": [...]` in the venue's dict in `BUFFET_VENUES`. No other files need changing.

### TM+ Changeover Patterns (enforced via `shifts_overlap`)
- **Pattern A:** buffet breakfast (ends 11:00) → accommodation 12:00–16:00
- **Pattern B:** accommodation 09:00–16:00 → buffet dinner (16:30+)

### Accommodation Target
- Changeover days: `ceil(total_guests / avg_family_size / rooms_per_staff)` → `rooms_per_staff = 3.9`
- Normal days: fixed 40 staff

---

## Solver Architecture (`solver/core.py`)

### Integer Scaling
All hours are multiplied by `SCALE = 100` before entering the solver to avoid floating-point arithmetic. Divide by 100 to recover human-readable hours.

### Penalty Hierarchy
```python
UNDER_PENALTY   = 500_000   # not covering a role slot  ← acts as near-hard
ACCOM_PENALTY   = 500_000   # accommodation under target ← acts as near-hard
OVER_PENALTY    =   1_000   # over-staffing a role (non-floor)
FLOOR_OVER_PEN  =  50_000   # floor over-staffing ← symmetry-breaker (see below)
```

Hours penalties (`HOURS_OVER_PEN`, `REST_DEMAND_PEN`) are **intentionally disabled**. When active they competed with staging penalties and caused coverage gaps — staff were being rested on high-demand days to save contract-hours cost. `UNDER_PENALTY = 500k` dominates for coverage.

A weak **one-sided under-hours penalty** (`_add_hours_under_penalty`, `CONTRACT_UNDER_PEN = 1`) is active. It costs 1 × scaled_shift_hours per unit of shortfall — about 300 per 3 h shift — well below `OVER_PENALTY (1 000)` so it never over-staffs a filled slot, and negligible vs `UNDER_PENALTY (500 000)` so it never trades coverage for hours. Its purpose is to pull under-contracted staff towards more shifts and balance hours between similar-skilled staff (e.g. Liubov/Steven on floor).

**Contracted hours = minimum, not maximum.** The business expectation is that staff work *at least* their contracted hours; exceeding them is acceptable. A weak one-sided under-hours penalty (`_add_hours_under_penalty`, `CONTRACT_UNDER_PEN = 1`) is active — see Hours penalties note above. The full `_add_hours_penalties` function must **not** be re-enabled — its `REST_DEMAND_PEN` (200,000) dominates staging and causes coverage gaps.

**Rule:** always prefer soft penalties over hard constraints. Hard constraints that can't be satisfied cause `INFEASIBLE` with no recovery path.

### Floor Distribution Symmetry Problem

**Root cause:** The floor role has 35+ eligible workers per service-day but only needs 6 (Deck) + 6 (YC) = 12. All breakfast roles at any venue overlap in time (07:00–11:30 window), so each worker can only fill ONE floor slot per breakfast. This creates many equivalent optimal solutions — the solver may concentrate 9 workers on Thu floor with 2 on Tue, or 6 on each day, with the same total penalty because the over/under offsets cancel.

**Why penalty offsetting happens:** With `OVER_PENALTY=1000` and `UNDER_PENALTY=500k`, concentrating workers on Thu (over=3 → 3k) while leaving Tue short (gap=4 → 2M) looks worse than balanced (0+0=0). But the workers doing both days ALSO fill non-floor roles elsewhere on the days they "skip" floor — so moving them between days shifts role gaps between days, keeping the total penalty the same.

**Fix: `FLOOR_OVER_PEN = 50_000`** (applied only to `role == "floor"` in `_add_staging_penalties`). Making floor over-staffing 50× more expensive than other roles breaks the symmetry — the solver now strongly prefers spreading floor workers evenly across days rather than concentrating them. Result: most days hit the 6-worker target exactly.

**Do NOT increase `FLOOR_OVER_PEN` above `UNDER_PENALTY / target` (~83k).** At that level, over-staffing 1 slot costs more than filling 1 gap, which could cause the solver to leave gaps unfilled just to avoid over-staffing.

**Do NOT use hard floor lower bounds (`_constrain_staging_hard` called in `solve()`).** This was tried repeatedly and causes FEASIBLE (slow, 600s+ runs) or INFEASIBLE. The `FLOOR_OVER_PEN` soft approach achieves the same distribution effect without feasibility risk.

### Hard Constraints
| Constraint | What it enforces |
|------------|-----------------|
| `_constrain_no_overlap` | At most one overlapping shift per staff per day |
| `_constrain_11h_gap` | ≥11h rest between shifts on consecutive days |
| `_constrain_rest_days` | Coverage-first: no min/max for buffet/bar staff; 2–4 rest days for accommodation; Mon/Fri never rest for TM+ |
| `_constrain_max_venues_per_day` | TM+1 ≤2 venues/day; TM+2 ≤3 venues/day |
| `_constrain_daily_hours` | Max 10h paid per day |
| `_constrain_accom_exact` | Normal accommodation staff must work changeover days |

### Contracted Hours = Minimum, Not Maximum
Contracted hours are the **floor**, not the ceiling. If 20 shifts are uncovered and 20 eligible staff exist, those staff MUST be assigned even if they are already at or over their contracted hours. Over-contract working is expected and acceptable — the "OVER CONTRACT" section in the console is informational only, not an alert.

### Coverage-First Scheduling
The solver operates in **coverage-first mode**: filling venue role-slots takes absolute priority. Staff may work up to 7 days/week and exceed contracted hours when coverage demands it.

- `_constrain_rest_days` applies **no lower or upper bound** on working days for buffet/bar staff. The `UNDER_PENALTY = 500k` drives the solver to fill every slot it can.
- Accommodation staff retain their 2–4 rest day bounds (186 staff for ~40 slots/normal day).
- Gaps that remain after full scheduling = **genuine staffing shortages** (not enough trained staff). These are flagged in the console as `!! MANAGER ACTION REQUIRED !!` and show eligible vs target counts per role/day/venue.
- Over-contract hours are expected and acceptable. The "OVER CONTRACT" section in the console is informational, not an alert.

### `solve()` Return Schema
```python
{
    "status": "OPTIMAL" | "FEASIBLE" | "NO_SOLUTION",
    "solve_time": float,          # seconds
    "assignments": [
        {
            "staff_id": str,
            "name": str,
            "contract_type": str,
            "department": str,
            "contracted_hours": float,
            "shift_hours": float,
            "holiday_hours": float,
            "allocated_hours": float,
            "hours_gap": float,
            "hours_over": float,
            "below_contracted": bool,
            "holiday_days": [int],
            "days": {int: [shift_dict]},  # day_idx → list of shifts
            "skills": [str]
        }
    ],
    "coverage": {
        venue_id: {
            day: {
                "open": bool,
                "services": {
                    service: {
                        role: {
                            "actual":   int,   # staff assigned
                            "target":   int,   # staff needed
                            "gap":      int,   # target − actual (0 = OK)
                            "ok":       bool,
                            "eligible": int,   # staff with variables for this slot
                            "shortage": int    # max(0, target − eligible)
                                               # > 0 = genuine training/hiring gap
                        }
                    }
                }
            }
        }
    },
    "summary": { ... }  # aggregated metrics
}
```

`shortage > 0` means even if every eligible person were scheduled, the target cannot be reached — a hiring or cross-training decision is required. `gap > 0` but `shortage == 0` means staff exist but the solver couldn't fit them (rare; check 11h-gap and overlap constraints).

---

## Data Structures

### Staff Record
```python
{
    "id": "SXXXX",
    "name": str,
    "contract_type": "normal" | "tm_plus",
    "tm_plus_type": "tm_plus_1" | "tm_plus_2" | None,
    "department": "buffets" | "bars" | "accommodation",
    "home_venues": [venue_id],
    "eligible_venues": [venue_id],
    "contracted_hours": 35.0,
    "hourly_rate": float,
    "holiday_remaining": int,
    "skills": [role_name],
    "approved_days_off": [day_idx]  # 0–6
}
```

### Week Config
```python
{
    "week_number": int,
    "week_start": "YYYY-MM-DD",
    "fri_batch": {
        "premium_guests": int,
        "food_court_guests": int,
        "total_guests": int
    },
    "mon_batch": {
        "premium_guests": int,
        "food_court_guests": int,
        "total_guests": int
    },
    "accom_override": {"fri_arrivals": int | None, "mon_arrivals": int | None}
}
```

### Shift Dict
```python
{
    "venue_id": str,
    "role": str,
    "service": "breakfast" | "dinner" | "full",
    "start": int,       # minutes since midnight
    "end": int,         # minutes since midnight
    "on_site_h": float,
    "paid_h": float,    # on_site_h minus 0.5h break
    "batch_key": "fri_batch" | "mon_batch"
}
```

### Time Representation
- **Internal (solver + shift_calculator):** minutes since midnight as integers
- **Config / display:** `"HH:MM"` strings
- **Helpers in `shift_calculator.py`:** `t2m("HH:MM")`, `m2t(mins)`, `hhmm2m(HHMM)`

---

## Coding Conventions

- **No floats in solver.** All hours → `int(hours * SCALE)`. Divide by `SCALE` only at extraction.
- **Solver errors → status strings, not exceptions.** Caller checks `result["status"]`.
- **Logging:** plain `print()` in `main.py`. No logging module. Keep it minimal.
- **Excel colors:** all via the `C` dict in `reporter/excel.py` — never hardcode hex strings.
- **Excel helpers:** always use `_f()`, `_fill()`, `_b()`, `_a()`, `_hdr_row()` — don't call openpyxl styles directly.
- **Time helpers:** always use `t2m` / `m2t` / `hhmm2m` — never parse time strings inline.

---

## Critical Rules When Editing

### `solver/core.py`
- **Never add a hard constraint without first verifying feasibility.** Run the solver and check for `INFEASIBLE` before committing.
- `shifts_overlap()` already enforces TM+ changeover patterns (A and B). Do not add manual pattern logic — it will conflict.
- Solver runs 8 parallel workers (`num_workers=8`). Don't reduce this without profiling.
- `_constrain_staging_hard()` exists in the file but is **not called**. Do not enable it — it causes FEASIBLE (600s+ time limit hit) due to the combined effect of no_overlap + 11h-gap reducing the effective feasible pool. The floor distribution problem it was meant to fix is now solved by `FLOOR_OVER_PEN = 50_000` instead.
- **Do not re-enable `_add_hours_penalties` as-is.** Its `REST_DEMAND_PEN` (200,000) competes with staging and causes coverage gaps. If a contracted-hours minimum is needed, add a new one-sided penalty with `HOURS_UNDER_PEN ≤ 1` (see Penalty Hierarchy notes above).
- **Do not add back a `min_work` lower bound to `_constrain_rest_days`** for buffet/bar staff. The previous version forced min 5 working days, which combined with single-service assignment left staff below contract while slots went unfilled. Coverage-first mode has no lower bound — `UNDER_PENALTY` drives working days naturally.

### `data/config.py`
- Single source of truth for staging bands, role offsets, and all penalty values.
- When changing staffing targets, edit the staging band dicts here first — the solver reads them dynamically.

### `data/sample_data.py`
- Placeholder only. Real data arrives as a JSON payload to `app.py` from Dataverse via Power Automate.
- Never reference sample staff IDs or hardcoded counts in production logic.
- The Ocean Drive section imports from `data/ocean_drive_data.py` and re-registers each person through `_s()` so IDs are sequential with the rest of the sample data.

### `data/ocean_drive_data.py`
- Contains the **real** Ocean Drive team (33 staff) sourced directly from the Excel weekly rota.
- Contract type mapping from rota: `b` → `normal`, `tm+1` → `tm_plus_1`, `TM+2` → `tm_plus_2`, blank → inferred `tm_plus_1` (staff run Accom shifts on changeover days).
- Skills reflect the rota's rightmost skill columns; contracted hours taken from the rota's last column (blank → 35 h).
- Post-load expansions at the bottom of this file mirror those in `sample_data.py` — keep them in sync.

### `reporter/excel.py`
- Follow the sheet-building pattern: title row → metadata block → table header → data rows → totals row → legend.
- Column widths and row heights are set explicitly — don't rely on auto-fit.

---

## Debugging

**Solver returns `INFEASIBLE`**
Relax or remove the most recently added hard constraint, or convert it to a soft penalty. Run a minimal repro with a small staff subset to isolate the conflicting constraint.

**Coverage gaps in output**
Check the `!! MANAGER ACTION REQUIRED !!` section first. If `shortage > 0` for a role, there are genuinely not enough trained staff — this cannot be fixed by the solver. If `gap > 0` but `shortage == 0`, eligible staff exist; call `staging_for_venue_day_service(venue_id, week_config, day, service)` and check the 11h-gap and overlap constraints to see why they weren't assigned.

**Wrong shift start/end times**
Trace through `buffet_shifts_for_day(venue_id, schedule, day)`. Check that the venue is open (`active_buffets_by_day`) and that the role offset in `config.py` is correct. Use `t2m` / `m2t` to convert.

**Hours look wrong**
Remember `SCALE=100`. All hours inside the solver are `×100`. Divide by 100 after extraction. Check `allocated_hours` vs `contracted_hours` in the assignment dict.

**Bar staging is wrong**
Bar headcount is sales-driven. Check `bar_staging_for_day(venue_id, day, daily_sales, bar_staff_count)`. The `daily_sales` dict in sample_data only covers Centre Stage and Reds — other bars default to zero if missing.

**Accommodation target is off**
Check `accom_target_for_day(week_config, day)`. On changeover days it uses `total_guests`, not `premium_guests`. Verify `accom_override` in the week config is `None` if not overriding.

---

## Adding Features

### New venue (buffet or bar)
1. Add staging bands and role offsets to `data/config.py`
2. If any roles don't apply to the venue, add `"excluded_roles": [...]` to its entry in `BUFFET_VENUES`
3. Add staff with correct `eligible_venues` to `data/sample_data.py`
4. Add a roster sheet in `reporter/excel.py` following the existing venue sheet pattern
5. Verify solver feasibility before adding any new hard constraints

### New solver constraint
1. Add it as a soft penalty first (model it as a deviation cost)
2. Run the solver and confirm `FEASIBLE` or `OPTIMAL`
3. Only then consider hardening it if the penalty is too weak

### New Excel sheet
Follow this structure in `excel.py`:
```
title row (merged cells)
metadata block (week, dates, status)
header row (_hdr_row)
data rows
totals row (SUM formulas)
legend
```

### Cross-training a role (e.g. hosts covering floor)
Apply the extra skill in the data layer, not in the solver. Post-load expansion loops run at the bottom of both `ocean_drive_data.py` and `sample_data.py`. When connecting real Dataverse data, apply the same expansions in `app.py`'s payload parser before passing staff to `solve()`.

Current expansions (applied in both files):
- `host` → also gets `floor`
- `bays` → also gets `setup` (bays team arrives early and preps the service)

### Connect real Dataverse data
- Replace the sample_data loads in `app.py`'s `/solve` endpoint with parsing of the incoming JSON payload
- The JSON schema must match the staff record and week config structures above
- Apply any cross-training expansions (e.g. host → floor) to each staff record after parsing, before calling `solve()`
- `sample_data.py` remains for local development only

---

## Known Issues / Roadmap

### Genuine Staffing Shortages (cannot be fixed by solver)

These gaps remain even when every eligible person is scheduled. They require hiring or cross-training decisions.

| Venue | Issue | Root Cause |
|-------|-------|------------|
| Accommodation (Mon) | Target ~327, max possible ~271 | 186 normal + ~85 TM+ < 327; structural 56-person shortfall on changeover day |
| Yacht Club (Mon–Thu evenings) | Low/zero coverage | Deck + YC share the same pool (all Deck normal + TM+ are eligible for both). When Deck demands consume the pool, YC goes short. |
| Bar normal staff hours | Max ~22h/week from 3–3.5h bar shifts | 35h contracts structurally unachievable from bar shifts alone |

**Resolution path:** for accommodation shortage — hire more changeover-day accommodation-eligible staff or reduce the Mon arrival target. For YC — gaps are genuine (same pool as Deck); only fix is more Deck/YC-eligible staff.

### Operational Constraints / Diagnostics

**Bar TM+ Mon accommodation assignment:**
- Mon accommodation (09:00–16:00) and Mon bar (16:45–22:00) do NOT overlap — a TM+1 can work both in one day.
- 11h gap from Sun bar (ends 22:00) to Mon accom (starts 09:00) = exactly 660 min = 11h ✓ (passes `gap_ok`).
- Mon accom → Tue bar gap = 26h 45m — well above 11h minimum. ✓
- If coverage gaps persist on "low priority" days (typically Thu = last day of week), the cause is **solver search order**: the solver tackles the biggest penalty reductions first (Fri/Mon changeover) and may not reach Thu before the time limit.
- `model.AddHint(v, 1)` warm-start: all buffet/bar shift variables are hinted to 1 (assigned). The solver starts from "everyone working" and only removes assignments where constraints force it, rather than building coverage up from zero. This ensures Thu (the last day explored) starts with full coverage and the solver only needs to remove infeasible overlaps/gaps. AddHint is safe — it never causes infeasibility.
- `num_search_workers = 8` (parallel search).
- `time_limit = 300s`. Console now shows `OPTIMAL` or `FEASIBLE ← coverage may be suboptimal` (the latter means hit time limit; raise further if needed).
- **Do NOT use hard floor lower bounds (`_constrain_staging_hard` called from `solve()`)** — causes FEASIBLE (600s+ time limit hit) even with `eligible >= 2 × target` guard. The correct fix for floor distribution is `FLOOR_OVER_PEN = 50_000` (see Floor Distribution Symmetry Problem above).
- **Do NOT use `_constrain_coverage_floors`** — causes INFEASIBLE in presolve. Same reason: hard lower bounds interact badly with no_overlap + 11h-gap constraints.
- `AddDecisionStrategy(SELECT_MAX_VALUE)` was tried and removed — caused one worker to waste all time backtracking from an over-assigned starting point.

### Display Clarification

**"REST" in venue roster sheet ≠ day off.** It means the staff member has no shift at *that specific venue* on that day. They may be working another venue (accommodation, different bar, etc.). Always cross-check the full row across all venue sheets.

### Roadmap

- [ ] Add Training Gap Report sheet to Excel reporter
- [ ] Add Changeover Readiness Score (needs Dataverse history table)
- [ ] Connect to real Dataverse data (replace `sample_data.py`)
- [ ] Deploy to Cloud Run (`Dockerfile` and `app.py` are ready)
- [ ] Phase 2: retail restaurants, QSR, leisure venues
- [ ] Power Apps manager interface (week config, absences, GM dashboard)

---

## Penalty Decisions Log

Decisions recorded here so future edits understand *why* penalties are set as they are.

| Date | Change | Reason |
|------|--------|--------|
| Apr 2025 | `_add_hours_under_penalty` added (`CONTRACT_UNDER_PEN=1`) | Balanced hours between same-skilled staff (e.g. Liubov/Stephen on OD floor); pulls under-contracted staff toward uncovered slots |
| Apr 2025 | `_add_normal_utilisation` split from 1×800/day to 2×400/service | Normal buffet staff were working dinner only; per-service penalty pushes them to cover both breakfast and dinner |
| Apr 2025 | `UNDER_PENALTY` doubled to 1M when only 1 eligible person for a role slot | Sole-eligible host was being reassigned to floor (bigger multi-gap saving); 2× multiplier makes the single host slot equally urgent |
| Apr 2025 | Accommodation normal excluded from `_add_hours_under_penalty` | Hours-under penalty pushed 186 accom staff to work extra non-changeover days → 155+/40 over-staffing on Tue–Thu; their rest days are already bounded by `_constrain_rest_days` |
| Apr 2025 | `FLOOR_OVER_PEN = 50_000` added for floor role in `_add_staging_penalties` | Floor workers are highly symmetric (35 eligible, 12 needed across Deck+YC) — solver found many equally-optimal solutions that concentrated 9–11 workers on Thu while leaving Tue/Wed with 1–2. High floor over-penalty breaks symmetry by making concentration expensive; spreads floor evenly across all open days. Value chosen: > `BUFFET_IDLE_PEN` (2000) so concentration is never preferred, < `UNDER_PENALTY / target` (~83k) so over-staffing is never preferred over filling a gap. Hard lower bounds were tried first (3 attempts) and caused FEASIBLE/INFEASIBLE. |
| Apr 2025 | `BAR_OVER_PEN = 25_000` added for bar roles in `_add_staging_penalties` | Bar venues (CS, Reds etc.) are symmetric — without a high over-penalty the solver would double-assign workers to one bar and leave others uncovered. Same symmetry-breaking logic as `FLOOR_OVER_PEN`. Value 25k chosen lower than `FLOOR_OVER_PEN` (50k) because bar venues have fewer eligible staff per slot; hard floor lower bounds were not used. |
| Apr 2025 | `BAR_IDLE_PEN = 20_000` added in `_add_bar_utilisation`; changeover days (Mon/Fri) skipped | Bar TM+ workers were idle on non-changeover days (Monday accommodation overlap prevented bar coverage). Per-day bar-idle penalty pushes them to work bar shifts when not on accommodation duty. Changeover day skip is critical: Mon/Fri accommodation is a hard-forced duty for TM+ — applying the idle penalty on those days caused the solver to skip accommodation (which has `ACCOM_PENALTY=500k`) in favour of avoiding the bar-idle cost. |
| Apr 2025 | `SC_SINGLE_SVC_PEN = 800` (< `OVER_PENALTY = 1000`) in `_add_sc_double_service`; changeover days exempted | Station chef slots require pairing (bkf + din sc each day). Without pairing penalty, solver assigned 1 sc worker to bkf only and left din sc unfilled. Value must be < `OVER_PENALTY` (1000): if higher, all 5 sc workers are forced to pair even on days when there are only 3 bkf sc slots (remaining 2 incur over-target cost of 800 < 1000 → forces double, causes gap in bays). Changeover day exemption: Mon/Fri bkf sc (07:15–11:30) overlaps accommodation (09:00–16:00); TM+ on accom cannot do bkf sc — symmetric mismatch penalty would then penalise them for doing din sc without bkf sc, causing them to skip din sc too. |
| Apr 2025 | `primary_bias` in `_add_staging_penalties` extended to cover `bays`, `setup`, and `fridges` roles (was floor only) | Same symmetry problem as floor: bays/setup/fridges workers are eligible for both Deck and YC but should default to Deck (primary venue). Without the bias the solver spread them across venues and both Deck and YC had partial coverage. `PRIMARY_FLOOR_BIAS = 1_000` applied to non-overflow venues for these roles. |
| Apr 2025 | `SETUP_PRIORITY = 70_000` and `FRIDGES_PRIORITY = 65_000` raised above `BAYS_PRIORITY = 50_000` | Setup and fridges slots (food safety, service readiness) are operationally more critical than bays. All three roles share the same time window (07:00–11:30 bkf, 15:30–20:00 din) so they compete for the same workers. With bays priority highest, workers always chose bays first and setup/fridges were consistently 0. Raising setup/fridges above bays fills those small critical slots first; bays has more workers eligible and can absorb the residual gaps. Trade-off: some bays slots are now unfilled where setup/fridges workers "take" a worker that would have been bays. |
| Apr 2025 | `min_rest = 1` enforced for all non-accommodation staff in `_constrain_rest_days` | Legal minimum: every worker must have at least 1 rest day per week. Previous implementation had no lower bound on rest for buffet/bar staff (coverage-first). Added `max_work = max(len(hard_no_rest), n_available − 1)` cap so every non-accom worker gets at least 1 rest day. TM+ hard-forced days (Mon/Fri) still count as working days; they must rest on at least 1 of the remaining 5 non-changeover days. |
| Apr 2025 | `SPEC_OVER_PEN = 5_000` added for setup/fridges/beverage/host/station_chef/bar roles | Without this, `OVER_PENALTY (1000) < BUFFET_IDLE_PEN (2000)` caused the solver to over-assign workers to already-filled small-target slots (e.g. setup=4/1 or beverage=6/1 on Thursday) rather than rest them. Setting `SPEC_OVER_PEN > BUFFET_IDLE_PEN` (2000) makes idling cheaper than over-stuffing these specialist roles. Value 5000 chosen well below `UNDER_PENALTY / target` to avoid creating gaps. Relationship to SC_SINGLE_SVC_PEN: 800 << 5000 still holds — SC workers won't over-assign just to avoid mismatch penalty. |
| Apr 2025 | 6 dedicated YC Bays workers + 10 dedicated YC Floor workers added to `sample_data.py` | YC bays showed GAP4 every day; YC floor showed GAP3–6 on Mon–Wed. Root cause: single Deck+YC pool with `PRIMARY_FLOOR_BIAS` routing all workers to Deck first; after Deck filled, workers hit `max_work=6` day cap leaving nothing for YC. Fix: add workers with `home=[yacht_club]` so PRIMARY_FLOOR_BIAS routes them to YC first, ensuring YC has its own dedicated coverage base. |
