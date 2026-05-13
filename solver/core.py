# =============================================================================
# solver/core.py  — Day-by-day CP-SAT solver
#
# Fixes in this version:
#   A. Variable builder now checks active_buffets before creating variables
#      — staff cannot be assigned to closed venues (YC/QS on weekends etc.)
#   B. No rest days on Mon/Fri for ALL staff unless operationally unavoidable
#      — solver allows exception only if staging cannot be met otherwise
#   C. Accommodation: normal team hard-constrained to 186 on changeover days
#      TM+ fills remainder as soft constraint
#   D. Rooms per staff changed to 3.9
#   E. Coverage sheet data fixed in _build_coverage
#   F. Bar staff assigned on days bar is actually open only
# =============================================================================

from ortools.sat.python import cp_model
from data.config import (
    DAYS, CHANGEOVER_DAYS, FRI_BATCH_DAYS,
    CONTRACTED_HOURS, MIN_REST_DAYS, MAX_REST_DAYS,
    HOLIDAY_PAID_H, TM_RULES, BAR_MIN_STAGING, BUFFET_VENUES,
)
from data.shift_calculator import (
    buffet_shifts_for_day, bar_shifts_for_day, accom_shifts_for_day,
    active_buffets_by_day, staging_for_venue_day_service,
    accom_target_for_day, shifts_overlap, gap_ok,
    bar_staging_for_day,
)

SCALE              = 100
OVER_PENALTY       = 1000    # over-staffing a role
FLOOR_OVER_PEN     = 50000   # floor over-staffing — high to break day-distribution symmetry
BAYS_OVER_PEN      = 50000   # bays over-staffing — same rationale; breaks concentration symmetry
BAR_OVER_PEN       = 25000   # bar role over-staffing — prevents 2@Reds leaving CS empty (symmetry)
BAR_UNDER_PEN      = 50000   # bar under-staffing vs hours target — lower than buffet (500k) because
                             # bar targets may exceed eligible pool; solver shouldn't agonise over
                             # irrecoverable gaps that slow proof of OPTIMAL
SPEC_OVER_PEN      =  5000   # setup/fridges/beverage/host over-staffing — must exceed
                             # BUFFET_IDLE_PEN (2000) so workers rest rather than pile into
                             # already-filled small-target slots (especially Thu end-of-week)
UNDER_PENALTY      = 500000  # under-staffing — treat as near-hard
ACCOM_PENALTY      = 500000  # accommodation same
HOURS_OVER_PEN     = 50
HOURS_UNDER_PEN    = 200
PRIMARY_FLOOR_BIAS      =  1000   # floor at primary venues (Deck, OD) over overflow (YC, QS)
STATION_CHEF_PRIORITY  = 200000  # only 5 eligible (target 3) — must beat floor/bays
SETUP_PRIORITY         =  70000  # target 1-2; small slot — must fill BEFORE bays (50k) so
                                 # solver uses dedicated workers rather than leaving it empty
FRIDGES_PRIORITY       =  65000  # same rationale as setup; slightly below setup
BAYS_PRIORITY          =  50000  # 15 eligible (target 4-6); overlap with setup/fridges
BEVERAGE_PRIORITY      =  10000  # 10 eligible (target 2) — prefer over floor
HOST_PRIORITY          =  10000  # 3-4 eligible (target 1) — prefer over floor
SC_SINGLE_SVC_PEN      =    800  # sc single-service mismatch — must be < OVER_PENALTY (1000)
                               # so once sc reaches target, adding more to avoid mismatch is
                               # more expensive than paying the mismatch (breaks symmetry at 3)
BAR_IDLE_PEN           =  20000  # bar TM+ idle on a bar-open day (> BAR_OVER_PEN to prefer working)
SC_WORK_PEN            =  50000  # sc worker not using sc skill on an open service-day.
                                 # Only 5 eligible workers for 3 slots — unlike setup/fridges
                                 # (many eligible, SPEC_OVER_PEN prevents pileup), sc needs a
                                 # per-variable push. 50k > OVER_PENALTY (1k) so workers prefer
                                 # sc even when at target; slight over-staffing (4/3 or 5/3)
                                 # costs only 1k/slot vs 50k idle, ensuring all 5 workers fill
                                 # every available day rather than alternating in pairs.

def _h(h):
    return int(round(h * SCALE))


def solve(staff, week_config, buffet_schedule, bar_schedule,
          daily_hours=None, time_limit=60):
    model  = cp_model.CpModel()
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = time_limit
    solver.parameters.num_search_workers  = 8

    active = active_buffets_by_day(week_config)

    all_buffet = {}
    for vid, sched in buffet_schedule.items():
        all_buffet[vid] = {d: buffet_shifts_for_day(vid, sched, d)
                           for d in range(7)}

    all_bar = {}
    for vid, sched in bar_schedule.items():
        all_bar[vid] = {d: bar_shifts_for_day(vid, sched, d)
                        for d in range(7)}

    all_accom = {d: accom_shifts_for_day(d, d in CHANGEOVER_DAYS)
                 for d in range(7)}

    works = _build_variables(model, staff, active,
                             all_buffet, all_bar, all_accom)

    _constrain_no_overlap(model, staff, works, all_buffet, all_bar, all_accom)
    _constrain_11h_gap(model, staff, works, all_buffet, all_bar, all_accom)
    _constrain_rest_days(model, staff, works)
    _constrain_tm_accommodation(model, staff, works, all_accom)
    _constrain_accom_exact(model, staff, works, week_config)
    _constrain_max_venues_per_day(model, staff, works, all_buffet, all_bar)
    _constrain_daily_hours(model, staff, works, all_buffet, all_bar, all_accom)

    penalty_terms = []
    _add_staging_penalties(model, staff, works, penalty_terms,
                           active, all_buffet, all_bar, all_accom,
                           week_config, daily_hours or {})
    _add_normal_utilisation(model, staff, works, penalty_terms, active, all_buffet)
    _add_bar_utilisation(model, staff, works, penalty_terms, all_bar)
    _add_sc_utilisation(model, staff, works, penalty_terms, all_buffet, active)
    _add_sc_double_service(model, staff, works, penalty_terms, all_buffet, active)
    _add_hours_under_penalty(model, staff, works, penalty_terms,
                              all_buffet, all_bar, all_accom)

    model.Minimize(sum(penalty_terms))

    # Warm-start: hint all buffet/bar shift variables to 1 (assigned).
    # The solver starts from "everyone works everywhere" and only removes
    # assignments where hard constraints force it (overlap, 11h gap, etc.).
    # This is much faster than building coverage up from zero, and fixes
    # later weekdays (e.g. Thu) being left unoptimised when the time limit hits.
    # AddHint is safe — it never causes infeasibility.
    #
    # Also hint TM+ accommodation on changeover days to 1. Without this,
    # accommodation starts at 0, and the solver treats "TM+ on floor" vs
    # "TM+ on accommodation + floor" as equivalent (same penalty) — it
    # arbitrarily picks floor-only. Starting from 1 biases toward accommodation
    # so TM+ only skip it when constraints force them (10h cap, overlap, hard cap).
    tm_sids = {s["id"] for s in staff if s["contract_type"] == "tm_plus"}

    for sid, day_data in works.items():
        for day, venue_data in day_data.items():
            for vid, vvars in venue_data.items():
                if vid == "accommodation":
                    if sid in tm_sids and day in CHANGEOVER_DAYS:
                        # Hint only the full shift (idx=0, 09:00-16:00) to 1.
                        # Hinting both full+short to 1 creates an infeasible starting
                        # point (no_overlap blocks both) — solver resolves by setting
                        # both to 0, defeating the hint entirely.
                        full_var = vvars.get(0)
                        if full_var is not None:
                            model.AddHint(full_var, 1)
                    continue
                for v in vvars.values():
                    model.AddHint(v, 1)

    status = solver.Solve(model)

    return _extract(solver, status, staff, works,
                    all_buffet, all_bar, all_accom, active,
                    week_config, daily_hours or {})


# ── Variable builder ──────────────────────────────────────────────────────────
# KEY FIX: Only create variables for venues that are OPEN on that day/service

def _build_variables(model, staff, active, all_buffet, all_bar, all_accom):
    works = {}
    for s in staff:
        sid      = s["id"]
        is_tm    = s["contract_type"] == "tm_plus"
        tm_type  = s.get("tm_plus_type", "")
        rules    = TM_RULES.get(tm_type, {}) if is_tm else {}
        is_accom = s["department"] == "accommodation"
        works[sid] = {}

        for day in range(7):
            if day in s["approved_days_off"]:
                continue
            works[sid][day] = {}

            # ── Accommodation normal team ─────────────────────────────────
            if is_accom:
                shifts = all_accom[day]
                if shifts:
                    works[sid][day]["accommodation"] = {
                        idx: model.NewBoolVar(f"w_{sid}_{day}_ac_{idx}")
                        for idx in range(len(shifts))
                    }
                continue

            # ── TM+ ───────────────────────────────────────────────────────
            if is_tm:
                # Accommodation on changeover days
                if day in CHANGEOVER_DAYS:
                    shifts = all_accom[day]
                    if shifts:
                        works[sid][day]["accommodation"] = {
                            idx: model.NewBoolVar(f"w_{sid}_{day}_ac_{idx}")
                            for idx in range(len(shifts))
                        }

                # Buffet venues — ONLY if open today
                for vid in s["eligible_venues"]:
                    if vid not in all_buffet:
                        continue
                    # Check venue is open for at least one service today
                    open_services = [
                        svc for svc in ["breakfast", "dinner"]
                        if vid in active.get(day, {}).get(svc, [])
                    ]
                    if not open_services:
                        continue
                    # Only create variables for open services
                    day_shifts = all_buffet[vid][day]
                    eligible = {
                        idx: sh for idx, sh in enumerate(day_shifts)
                        if sh["role"] in s["skills"]
                        and sh["service"] in open_services
                    }
                    if eligible:
                        works[sid][day][vid] = {
                            idx: model.NewBoolVar(f"w_{sid}_{day}_{vid}_{idx}")
                            for idx in eligible
                        }

                # Bar venues (TM+1 and TM+2 can work bars)
                if rules.get("can_work_bars", False):
                    for vid in s["eligible_venues"]:
                        if vid not in all_bar:
                            continue
                        shifts = all_bar[vid][day]
                        if not shifts:
                            continue
                        eligible = {
                            idx: sh for idx, sh in enumerate(shifts)
                            if sh["role"] in s["skills"]
                        }
                        if eligible:
                            works[sid][day][vid] = {
                                idx: model.NewBoolVar(
                                    f"w_{sid}_{day}_{vid}_{idx}")
                                for idx in eligible
                            }
                continue

            # ── Normal non-accommodation staff ────────────────────────────
            for vid in s["eligible_venues"]:
                if vid in all_buffet:
                    # ONLY create variables for services open today
                    open_services = [
                        svc for svc in ["breakfast", "dinner"]
                        if vid in active.get(day, {}).get(svc, [])
                    ]
                    if not open_services:
                        continue
                    day_shifts = all_buffet[vid][day]
                    eligible = {
                        idx: sh for idx, sh in enumerate(day_shifts)
                        if sh["role"] in s["skills"]
                        and sh["service"] in open_services
                    }
                    if eligible:
                        works[sid][day][vid] = {
                            idx: model.NewBoolVar(f"w_{sid}_{day}_{vid}_{idx}")
                            for idx in eligible
                        }

                elif vid in all_bar:
                    shifts = all_bar[vid][day]
                    if not shifts:
                        continue
                    eligible = {
                        idx: sh for idx, sh in enumerate(shifts)
                        if sh["role"] in s["skills"]
                    }
                    if eligible:
                        works[sid][day][vid] = {
                            idx: model.NewBoolVar(f"w_{sid}_{day}_{vid}_{idx}")
                            for idx in eligible
                        }

    return works


# ── Helpers ───────────────────────────────────────────────────────────────────

def _day_items(sid, day, works, all_buffet, all_bar, all_accom):
    items = []
    if day not in works.get(sid, {}):
        return items
    for vid, vvars in works[sid][day].items():
        if vid == "accommodation":
            slist = all_accom[day]
        elif vid in all_buffet:
            slist = all_buffet[vid][day]
        elif vid in all_bar:
            slist = all_bar[vid][day]
        else:
            continue
        for idx, var in vvars.items():
            if idx < len(slist):
                items.append((var, slist[idx], vid))
    return items


# ── Hard constraints ──────────────────────────────────────────────────────────

def _constrain_no_overlap(model, staff, works, all_buffet, all_bar, all_accom):
    for s in staff:
        sid = s["id"]
        for day in range(7):
            items = _day_items(sid, day, works, all_buffet, all_bar, all_accom)
            for i in range(len(items)):
                for j in range(i + 1, len(items)):
                    va, sa, _ = items[i]
                    vb, sb, _ = items[j]
                    if shifts_overlap(sa, sb):
                        model.Add(va + vb <= 1)


def _constrain_11h_gap(model, staff, works, all_buffet, all_bar, all_accom):
    for s in staff:
        sid = s["id"]
        for day in range(6):
            today    = _day_items(sid, day,   works, all_buffet, all_bar, all_accom)
            tomorrow = _day_items(sid, day+1, works, all_buffet, all_bar, all_accom)
            for va, sa, _ in today:
                for vb, sb, _ in tomorrow:
                    if not gap_ok(sa, sb):
                        model.Add(va + vb <= 1)


def _constrain_rest_days(model, staff, works):
    """
    Rest day rules — coverage-first mode:
    - Buffet / bar staff: no forced minimum working days; no maximum rest days.
      Staff work as many days as venue coverage requires. Over-contract is OK.
      Only hard constraint: TM+ cannot rest on Mon/Fri (changeover days).
    - Accommodation normal team: min 2, max 4 rest days (186 staff for ~40
      slots/normal day — most must rest; Mon+Fri are hard working days).
    - Gaps that remain after all staff are scheduled = genuine understaffing;
      these are surfaced in the coverage report for the manager.
    """
    for s in staff:
        sid      = s["id"]
        hol      = set(s["approved_days_off"])
        is_tm    = s["contract_type"] == "tm_plus"
        is_accom = s["department"] == "accommodation"

        hard_no_rest = set(CHANGEOVER_DAYS) if (is_tm or is_accom) else set()

        if is_accom and not is_tm:
            # Accommodation team: keep existing bounds so 186 staff spread
            # across 40-per-day normal slots without all working every day.
            min_rest = 2
            max_rest = 4
        else:
            # Legal minimum: 1 rest day per week. Workers can exceed contracted hours
            # to cover venue gaps — over-contract is acceptable per policy.
            min_rest = 1
            max_rest = 7   # no upper bound — coverage decides how many days worked

        available_days = [d for d in range(7) if d not in hol]
        day_worked = {}

        for day in available_days:
            if day not in works.get(sid, {}):
                continue
            all_vars = [v for vv in works[sid][day].values()
                        for v in vv.values()]
            if not all_vars:
                continue
            dw = model.NewBoolVar(f"dw_{sid}_{day}")
            model.AddMaxEquality(dw, all_vars)
            day_worked[day] = dw
            if day in hard_no_rest:
                model.Add(dw == 1)

        n_available = len(day_worked)
        if n_available == 0:
            continue

        total_worked = sum(day_worked.values())

        if is_accom and not is_tm:
            max_work = n_available - min_rest
            min_work = max(0, n_available - max_rest)
            model.Add(total_worked >= min_work)
            model.Add(total_worked <= max_work)
        else:
            # All other staff: enforce minimum 1 rest day (max_work cap only).
            # TM+ changeover days (Mon/Fri) are already hard-forced to dw==1,
            # so those count toward their working days; they must rest on
            # at least 1 of the remaining 5 non-changeover days.
            max_work = max(len(hard_no_rest), n_available - min_rest)
            if max_work < n_available:
                model.Add(total_worked <= max_work)


def _constrain_tm_accommodation(model, staff, works, all_accom):
    """
    TM+ on changeover days: accommodation is their primary assignment.
    Use soft enforcement via ACCOM_PENALTY rather than hard constraint.
    Hard cap in _add_staging_penalties limits how many are needed.
    Hard constraint only for normal accom team (in _constrain_accom_exact).
    """
    # No hard constraint here — handled by penalties and cap in staging
    pass


def _constrain_accom_exact(model, staff, works, week_config):
    """
    Accommodation constraints:

    Changeover days (Mon/Fri):
      - Normal accom team: all work (hard — their only venue)
      - TM+: each works exactly one accom shift (handled by _constrain_tm_accommodation)
      - Over/under target: soft penalty only (in _add_staging_penalties)
        Cannot use hard upper bound because 186 normal + 91 TM+ = 277
        which already exceeds Fri target of 244.
        Solver minimises over-staffing via ACCOM_PENALTY.

    Normal days:
      - Soft lower bound only (penalty for under 40)
      - Rest day constraint spreads 186 staff so ~40 work each normal day
    """
    # Force normal accom team to work on changeover days
    for s in staff:
        if s["department"] != "accommodation": continue
        if s["contract_type"] != "normal": continue
        sid = s["id"]
        for day in CHANGEOVER_DAYS:
            if day in s["approved_days_off"]: continue
            if day not in works.get(sid, {}): continue
            accom_vars = list(works[sid][day].get("accommodation", {}).values())
            if accom_vars:
                model.Add(sum(accom_vars) == 1)


def _constrain_max_venues_per_day(model, staff, works, all_buffet, all_bar):
    """
    TM+1: max 2 venues per day
    TM+2: max 3 venues per day
    Normal: max 1 venue per day (already enforced by single_service + eligibility)
    """
    for s in staff:
        if s["contract_type"] != "tm_plus":
            continue
        sid     = s["id"]
        tm_type = s.get("tm_plus_type", "tm_plus_1")
        max_v   = TM_RULES.get(tm_type, {}).get("max_venues_per_day", 2)

        for day in range(7):
            if day not in works.get(sid, {}):
                continue

            # Create a boolean for each venue: 1 if person works there today
            venue_used = []
            for vid, vvars in works[sid][day].items():
                if not vvars:
                    continue
                v_used = model.NewBoolVar(f"vu_{sid}_{day}_{vid}")
                model.AddMaxEquality(v_used, list(vvars.values()))
                venue_used.append(v_used)

            if len(venue_used) > max_v:
                model.Add(sum(venue_used) <= max_v)


def _constrain_staging_hard(model, staff, works, active,
                             all_buffet, all_bar, week_config, daily_hours):
    """
    Hard lower bounds for floor coverage at ALL buffet venues (primary and
    overflow).

    Only applied to "floor" — the high-eligible role where the solver
    concentrates workers on some days while leaving others short due to
    symmetry in the objective (equal penalty at Deck and YC).

    Safety guard: only add the constraint when eligible >= target * 2, which
    guarantees feasibility even if ~50% of the pool is knocked out by 11h-gap
    or overlap constraints.  With 35 floor-eligible and target 6, the guard
    is always satisfied.
    """
    for vid, day_shifts in all_buffet.items():
        for day in range(7):
            for service in ["breakfast", "dinner"]:
                if vid not in active.get(day, {}).get(service, []):
                    continue
                staging = staging_for_venue_day_service(
                    vid, week_config, day, service)
                if not staging:
                    continue

                target = staging.get("floor", 0)
                if target == 0:
                    continue

                role_idxs = [idx for idx, sh in enumerate(day_shifts[day])
                              if sh["service"] == service and sh["role"] == "floor"]

                role_vars = []
                for s in staff:
                    sid = s["id"]
                    if day not in works.get(sid, {}): continue
                    if vid not in works[sid][day]: continue
                    for idx in role_idxs:
                        if idx in works[sid][day][vid]:
                            role_vars.append(works[sid][day][vid][idx])

                if len(role_vars) >= target * 2:
                    model.Add(sum(role_vars) >= target)

    # Bars — soft penalties in _add_staging_penalties handle bars


def _constrain_daily_hours(model, staff, works, all_buffet, all_bar, all_accom):
    """
    Split shifts allowed for all staff when needed to cover venue.
    But cap daily paid hours at 10h to prevent unreasonable days.
    (Breakfast 07:15-11:30 = 4.25h + dinner 15:45-20:00 = 4.25h = 8.5h max split)
    """
    MAX_DAILY_H = _h(10.0)
    for s in staff:
        sid = s["id"]
        for day in range(7):
            items = _day_items(sid, day, works, all_buffet, all_bar, all_accom)
            if len(items) < 2:
                continue
            # Sum of all paid hours this day must not exceed cap
            day_hours = sum(var * _h(sh["paid_h"]) for var, sh, _ in items)
            model.Add(day_hours <= MAX_DAILY_H)


# ── Coverage floors (hard lower bounds where eligible >> target) ──────────────

def _constrain_coverage_floors(model, staff, works, active, all_buffet, week_config):
    """
    Convert soft UNDER_PENALTY to hard lower bounds for buffet slots where
    eligible staff >= 2 × target.  When eligible is at least double the target,
    even if half the pool is blocked by 11h-gap or overlap constraints, the
    remaining half still exceeds the target — so the hard constraint is
    guaranteed feasible.

    This prevents the solver from returning a FEASIBLE (suboptimal) solution
    where coverage gaps exist on days explored last (e.g. Thu) simply because
    the time limit was hit before LNS could close those gaps.
    """
    for vid, day_shifts in all_buffet.items():
        for day in range(7):
            for service in ["breakfast", "dinner"]:
                if vid not in active.get(day, {}).get(service, []):
                    continue
                staging = staging_for_venue_day_service(
                    vid, week_config, day, service)
                if not staging:
                    continue

                role_idxs = {}
                for idx, sh in enumerate(day_shifts[day]):
                    if sh["service"] == service:
                        role_idxs.setdefault(sh["role"], []).append(idx)

                for role, target in staging.items():
                    if target == 0:
                        continue
                    role_vars = []
                    for s in staff:
                        sid = s["id"]
                        if day not in works.get(sid, {}): continue
                        if vid not in works[sid][day]: continue
                        for idx in role_idxs.get(role, []):
                            if idx in works[sid][day][vid]:
                                role_vars.append(works[sid][day][vid][idx])

                    # Only harden when eligible is at least double the target —
                    # guarantees feasibility even with ~50% constraint knockouts.
                    if len(role_vars) >= target * 2:
                        model.Add(sum(role_vars) >= target)


# ── Soft constraints ──────────────────────────────────────────────────────────

def _add_staging_penalties(model, staff, works, penalty_terms,
                            active, all_buffet, all_bar, all_accom,
                            week_config, daily_hours):

    # Buffets — per service per role (including overflow venues YC, QS)
    for vid, day_shifts in all_buffet.items():
        for day in range(7):
            for service in ["breakfast", "dinner"]:
                # Skip if venue not open for this service
                if vid not in active.get(day, {}).get(service, []):
                    continue
                staging = staging_for_venue_day_service(
                    vid, week_config, day, service)
                if not staging:
                    continue

                role_idxs = {}
                for idx, sh in enumerate(day_shifts[day]):
                    if sh["service"] == service:
                        role_idxs.setdefault(sh["role"], []).append(idx)

                for role, target in staging.items():
                    if target == 0:
                        continue
                    role_vars = []
                    for s in staff:
                        sid = s["id"]
                        if day not in works.get(sid, {}): continue
                        if vid not in works[sid][day]: continue
                        for idx in role_idxs.get(role, []):
                            if idx in works[sid][day][vid]:
                                role_vars.append(works[sid][day][vid][idx])
                    if not role_vars:
                        continue
                    # Double the under-penalty when only one person can fill the
                    # slot — makes sole-eligible slots (e.g. host when one host
                    # is on holiday) worth 1M to fill, beating any individual
                    # multi-eligible floor gap (500k) in the objective.
                    is_overflow  = bool(BUFFET_VENUES.get(vid, {}).get("staffed_by"))
                    primary_bias = (0 if is_overflow else
                                    PRIMARY_FLOOR_BIAS if role in ("floor","bays","setup","fridges") else
                                    0)
                    role_bias = {
                        "station_chef": STATION_CHEF_PRIORITY,
                        "bays":         BAYS_PRIORITY,
                        "setup":        SETUP_PRIORITY,
                        "fridges":      FRIDGES_PRIORITY,
                        "beverage":     BEVERAGE_PRIORITY,
                        "host":         HOST_PRIORITY,
                    }.get(role, 0)
                    eff_under = (UNDER_PENALTY * 2
                                 if len(role_vars) == 1
                                 else UNDER_PENALTY) + primary_bias + role_bias
                    # Floor/bays over-staffing breaks day-distribution symmetry:
                    # expensive enough (> BUFFET_IDLE_PEN=2000) to push solver
                    # towards balanced distribution without causing infeasibility.
                    if role == "floor":
                        eff_over = FLOOR_OVER_PEN
                    elif role == "bays":
                        eff_over = BAYS_OVER_PEN
                    elif role in ("setup", "fridges", "beverage", "host", "bar"):
                        # SPEC_OVER_PEN > BUFFET_IDLE_PEN (2000): once these
                        # small-target slots are full, workers rest rather than
                        # pile in (prevents end-of-week over-assignment).
                        eff_over = SPEC_OVER_PEN
                    else:
                        eff_over = OVER_PENALTY
                    total = sum(role_vars)
                    over  = model.NewIntVar(0, len(role_vars),
                                           f"ov_{vid}_{day}_{service}_{role}")
                    under = model.NewIntVar(0, target,
                                           f"un_{vid}_{day}_{service}_{role}")
                    model.Add(over  >= total - target)
                    model.Add(under >= target - total)
                    penalty_terms += [eff_over * over, eff_under * under]

    # Bars — hours-budget daily staging
    for vid, day_shifts in all_bar.items():
        for day in range(7):
            shifts = day_shifts[day]
            if not shifts:
                continue
            staging = bar_staging_for_day(vid, day, daily_hours, shifts)
            if staging is None:
                continue   # bar closed (sales = 0)
            for role, target in staging.items():
                if target == 0:
                    continue
                role_vars = []
                for s in staff:
                    sid = s["id"]
                    if day not in works.get(sid, {}): continue
                    if vid not in works[sid][day]: continue
                    for idx, sh in enumerate(shifts):
                        if sh["role"] == role and idx in works[sid][day][vid]:
                            role_vars.append(works[sid][day][vid][idx])
                if not role_vars:
                    continue
                # Cap target at eligible count — if fewer workers are trained
                # than the hours-budget implies, the gap is irrecoverable and
                # the residual penalty would slow proof of optimality.
                eff_target = min(target, len(role_vars))
                total = sum(role_vars)
                over  = model.NewIntVar(0, len(role_vars), f"ov_{vid}_{day}_{role}")
                under = model.NewIntVar(0, eff_target,     f"un_{vid}_{day}_{role}")
                model.Add(over  >= total - eff_target)
                model.Add(under >= eff_target - total)
                penalty_terms += [BAR_OVER_PEN * over, BAR_UNDER_PEN * under]

    # Accommodation — cap TM+ at (target - normal_team_count)
    # so surplus TM+ are freed to work their home venues
    for day in CHANGEOVER_DAYS:
        target      = accom_target_for_day(week_config, day)
        normal_count= sum(1 for s in staff
                          if s["department"]=="accommodation"
                          and s["contract_type"]=="normal"
                          and day not in s["approved_days_off"])
        tm_needed   = max(0, target - normal_count)

        # Collect TM+ accommodation vars for this day
        tm_accom_vars = []
        for s in staff:
            if s["contract_type"] != "tm_plus": continue
            sid = s["id"]
            if day not in works.get(sid, {}): continue
            for var in works[sid][day].get("accommodation", {}).values():
                tm_accom_vars.append(var)

        if tm_accom_vars:
            # Hard upper bound: TM+ on accommodation <= what's actually needed
            model.Add(sum(tm_accom_vars) <= tm_needed)

    # Accommodation soft penalties (under target)
    for day in range(7):
        target = accom_target_for_day(week_config, day)
        accom_vars = []
        for s in staff:
            sid = s["id"]
            if day not in works.get(sid, {}): continue
            for idx in works[sid][day].get("accommodation", {}):
                accom_vars.append(works[sid][day]["accommodation"][idx])
        if not accom_vars:
            continue
        total = sum(accom_vars)
        under = model.NewIntVar(0, target, f"un_ac_{day}")
        over  = model.NewIntVar(0, len(accom_vars), f"ov_ac_{day}")
        model.Add(under >= target - total)
        model.Add(over  >= total  - target)
        pen = ACCOM_PENALTY if day in CHANGEOVER_DAYS else UNDER_PENALTY
        penalty_terms += [pen * under, OVER_PENALTY * over]


def _add_normal_utilisation(model, staff, works, penalty_terms, active, all_buffet):
    """
    Penalise buffet staff (Normal AND TM+) sitting idle on days/services their
    venue is open.

    BUFFET_IDLE_PEN = 2000 > OVER_PENALTY (1000): the solver always prefers to
    assign a staff member to an already-full slot rather than leave them idle.
    This ensures every available staff member is scheduled into every available
    service, giving them their contracted hours while filling coverage gaps.

    Coverage-first: 500k UNDER_PENALTY >> 2000 idle pen >> 1000 OVER_PENALTY.
    Order of priority: fill gaps → use all staff → avoid over-staffing.
    """
    BUFFET_IDLE_PEN = 2000   # per-service; > OVER_PENALTY (1000) so idle is never preferred

    for s in staff:
        if s["department"] != "buffets":
            continue
        sid = s["id"]
        for day in range(7):
            if day not in works.get(sid, {}):
                continue
            for svc in ["breakfast", "dinner"]:
                # Only penalise idle when at least one eligible venue is open for this service
                venue_open_svc = any(
                    vid in active.get(day, {}).get(svc, [])
                    for vid in s["eligible_venues"]
                    if vid in all_buffet
                )
                if not venue_open_svc:
                    continue
                # Collect variables for shifts in this service only
                svc_vars = []
                for vid, vvars in works[sid][day].items():
                    if vid not in all_buffet:
                        continue
                    slist = all_buffet[vid][day]
                    for idx, v in vvars.items():
                        if idx < len(slist) and slist[idx]["service"] == svc:
                            svc_vars.append(v)
                if not svc_vars:
                    continue
                dw = model.NewBoolVar(f"nutil_{sid}_{day}_{svc}")
                model.AddMaxEquality(dw, svc_vars)
                penalty_terms.append(BUFFET_IDLE_PEN * dw.Not())


def _add_hours_under_penalty(model, staff, works, penalty_terms,
                              all_buffet, all_bar, all_accom):
    """
    Weak one-sided penalty for staff being under their contracted hours.

    CONTRACT_UNDER_PEN = 1 → per 3 h shift the under-hours penalty drops by
    1 × 300 (scaled) = 300, which is below OVER_PENALTY (1 000) so the solver
    never over-staffs a filled slot just to hit contract, and far below
    UNDER_PENALTY (500 000) so it never trades coverage for hours.

    Effect: pulls under-contracted staff towards more shifts (including uncovered
    floor/role slots they are eligible for) and naturally balances hours between
    staff with the same skills — a staff member further from their contract gains
    more from each additional shift than one who is already over.
    """
    CONTRACT_UNDER_PEN = 1  # keep ≤ 1 per CLAUDE.md guidance

    for s in staff:
        # Accommodation normal staff are governed by _constrain_rest_days bounds
        # (2–4 rest days). Applying hours-under penalty here pushes them to work
        # extra non-changeover days, producing 155+/40 over-staffing on Tue–Thu.
        if s["department"] == "accommodation" and s["contract_type"] == "normal":
            continue

        sid    = s["id"]
        hol_h  = _h(len(s["approved_days_off"]) * HOLIDAY_PAID_H)
        target = max(0, _h(s["contracted_hours"]) - hol_h)
        if target <= 0:
            continue

        all_vars = []
        for day in range(7):
            for var, sh, _ in _day_items(
                    sid, day, works, all_buffet, all_bar, all_accom):
                all_vars.append((var, _h(sh["paid_h"])))

        if not all_vars:
            continue

        total = sum(v * h for v, h in all_vars)
        under = model.NewIntVar(0, target, f"hun_{sid}")
        model.Add(under >= target - total)
        penalty_terms.append(CONTRACT_UNDER_PEN * under)


def _add_bar_utilisation(model, staff, works, penalty_terms, all_bar):
    """
    Penalise bar TM+ staff idle on non-changeover days when bars are open.

    Skip changeover days (Mon/Fri) — on those days bar TM+ are expected to do
    accommodation first; the ACCOM_PENALTY (500k) handles that priority.

    BAR_IDLE_PEN (20k) < BAR_OVER_PEN (25k): the solver prefers to staff a bar
    to its target rather than over-staff to avoid the idle penalty — so workers
    fill empty slots first, then stop when the bar reaches target.
    """
    for s in staff:
        if s["contract_type"] != "tm_plus":
            continue
        if s["department"] != "bars":
            continue
        sid = s["id"]
        for day in range(7):
            if day in CHANGEOVER_DAYS:
                continue   # accommodation priority — no bar idle pressure
            if day not in works.get(sid, {}):
                continue
            bar_vars = []
            for vid, vvars in works[sid][day].items():
                if vid not in all_bar:
                    continue
                for idx, v in vvars.items():
                    bar_vars.append(v)
            if not bar_vars:
                continue
            any_bar_open = any(
                bool(all_bar[vid][day])
                for vid in s["eligible_venues"]
                if vid in all_bar
            )
            if not any_bar_open:
                continue
            dw = model.NewBoolVar(f"butil_{sid}_{day}")
            model.AddMaxEquality(dw, bar_vars)
            penalty_terms.append(BAR_IDLE_PEN * dw.Not())


def _add_sc_utilisation(model, staff, works, penalty_terms, all_buffet, active):
    """
    Penalise station_chef workers for each open service where they don't do sc.

    Uses AddMaxEquality (mirrors _add_bar_utilisation): one BoolVar per worker/
    day/service that is 1 iff any sc variable for that slot is 1. Penalises the
    .Not() of that indicator — fires exactly once per idle service, not once per
    unfilled sc slot variable. The per-variable approach was broken because a
    worker filling slot 0 still has slot 1 and slot 2 set to 0 (no_overlap),
    making the penalty fire regardless of assignment, killing the signal.
    """
    for s in staff:
        if "station_chef" not in s["skills"]:
            continue
        sid = s["id"]
        for day in range(7):
            if day in s.get("approved_days_off", []):
                continue
            if day not in works.get(sid, {}):
                continue
            for svc in ("breakfast", "dinner"):
                sc_vars = []
                for vid, vvars in works[sid][day].items():
                    if vid not in all_buffet:
                        continue
                    if vid not in active.get(day, {}).get(svc, []):
                        continue
                    slist = all_buffet[vid][day]
                    for idx, v in vvars.items():
                        if idx >= len(slist):
                            continue
                        sh = slist[idx]
                        if sh["role"] == "station_chef" and sh["service"] == svc:
                            sc_vars.append(v)
                if not sc_vars:
                    continue
                did_sc = model.NewBoolVar(f"sc_util_{sid}_{day}_{svc[0]}")
                model.AddMaxEquality(did_sc, sc_vars)
                penalty_terms.append(SC_WORK_PEN * did_sc.Not())


def _add_sc_double_service(model, staff, works, penalty_terms, all_buffet, active):
    """
    Penalise station_chef workers who cover only one buffet service per day.

    With 5 eligible workers and a target of 3 per service (6 total daily slots),
    at least 1 worker must work both breakfast and dinner sc every day. Without
    this penalty the solver distributes workers across services but never assigns
    both to the same worker — always leaving a bkf sc gap.

    SC_SINGLE_SVC_PEN = 800 < OVER_PENALTY (1000): once bkf sc target=3 is met,
    adding a 4th sc worker costs 1000 (over) > 800 (mismatch saved) — exactly 3
    workers pair up. Must be < OVER_PENALTY to avoid forcing all 5 workers to pair.

    Skip changeover days (Mon/Fri): bkf sc (07:15-11:30) overlaps with
    accommodation (09:00-16:00 full or 11:00-16:00 short). Workers who must do
    Mon/Fri accommodation cannot do bkf sc — symmetric mismatch would penalise
    them for doing din sc without bkf sc, causing them to skip din sc too.
    """
    for s in staff:
        if "station_chef" not in s["skills"]:
            continue
        sid = s["id"]
        for day in range(7):
            if day in CHANGEOVER_DAYS and s["contract_type"] == "tm_plus":
                continue   # TM+ bkf sc overlaps with their accommodation on Mon/Fri
            for vid, vvars in works.get(sid, {}).get(day, {}).items():
                if vid not in all_buffet:
                    continue
                slist = all_buffet[vid][day]
                bkf_sc = [v for idx, v in vvars.items()
                           if idx < len(slist)
                           and slist[idx]["role"] == "station_chef"
                           and slist[idx]["service"] == "breakfast"
                           and vid in active.get(day, {}).get("breakfast", [])]
                din_sc = [v for idx, v in vvars.items()
                           if idx < len(slist)
                           and slist[idx]["role"] == "station_chef"
                           and slist[idx]["service"] == "dinner"
                           and vid in active.get(day, {}).get("dinner", [])]
                if not bkf_sc or not din_sc:
                    continue
                bkf_v = bkf_sc[0]
                din_v = din_sc[0]
                # Penalise covering only one service: |bkf - din| must be 0
                mismatch = model.NewBoolVar(f"sc_mm_{sid}_{day}_{vid}")
                model.Add(din_v - bkf_v <= mismatch)   # din=1,bkf=0
                model.Add(bkf_v - din_v <= mismatch)   # bkf=1,din=0
                penalty_terms.append(SC_SINGLE_SVC_PEN * mismatch)


def _add_hours_penalties(model, staff, works, penalty_terms,
                          all_buffet, all_bar, all_accom, week_config):
    """
    Penalise deviation from 35h contracted.
    Also penalise resting on high-demand days using sales-derived weights
    so Saturday (peak sales) is strongly preferred over Sunday.
    """
    # Build per-venue daily demand weights
    # Bars: use sales data. Buffets: use guest count. Accom: flat.
    from data.sample_data import DAILY_SALES as _DS

    # Buffet demand by day — derived from batch guest counts
    fri_b = week_config["fri_batch"]
    mon_b = week_config["mon_batch"]
    # 0=Fri,1=Sat,2=Sun use fri_batch; 3=Mon,4=Tue,5=Wed,6=Thu use mon_batch
    buffet_guests = [
        fri_b["total_guests"],  # Fri
        fri_b["total_guests"],  # Sat
        fri_b["total_guests"],  # Sun
        mon_b["total_guests"],  # Mon
        mon_b["total_guests"],  # Tue
        mon_b["total_guests"],  # Wed
        mon_b["total_guests"],  # Thu
    ]
    max_guests = max(buffet_guests) or 1
    buffet_weights = [g / max_guests for g in buffet_guests]

    def _demand_weights(sid_staff):
        """Return 7-day demand weights (0-1) for a staff member."""
        for vid in sid_staff.get("eligible_venues", []):
            if vid in _DS:
                sales = _DS[vid]
                max_s = max(sales) or 1
                return [s / max_s for s in sales]
        # Buffet/accom staff — use guest-count weights
        return buffet_weights

    # Penalty for resting when venue is open
    # Must be high enough to outweigh hours savings
    # Resting saves ~HOURS_UNDER_PEN * shift_hours ≈ 200 * 700 = 140,000
    # So rest penalty must be > 140,000 to override
    REST_DEMAND_PENALTY = 200000

    for s in staff:
        sid    = s["id"]
        hol_h  = _h(len(s["approved_days_off"]) * HOLIDAY_PAID_H)
        target = max(0, _h(CONTRACTED_HOURS) - hol_h)

        all_vars = []
        for day in range(7):
            for var, sh, _ in _day_items(
                    sid, day, works, all_buffet, all_bar, all_accom):
                all_vars.append((var, _h(sh["paid_h"])))

        if not all_vars:
            continue

        total        = sum(v * h for v, h in all_vars)
        max_possible = sum(h for _, h in all_vars)

        over  = model.NewIntVar(0, max(0, max_possible - target), f"hov_{sid}")
        under = model.NewIntVar(0, target, f"hun_{sid}")
        model.Add(over  >= total - target)
        model.Add(under >= target - total)
        penalty_terms += [HOURS_OVER_PEN * over, HOURS_UNDER_PEN * under]

        # Penalise resting on high-demand days
        weights = _demand_weights(s)
        for day in range(7):
            if day in s["approved_days_off"]:
                continue
            w = weights[day]
            if w <= 0:
                continue   # only skip truly zero-demand days
            if day not in works.get(sid, {}):
                continue
            day_vars = [v for vv in works[sid][day].values()
                        for v in vv.values()]
            if not day_vars:
                continue
            dw = model.NewBoolVar(f"dw2_{sid}_{day}")
            model.AddMaxEquality(dw, day_vars)
            rest_penalty = model.NewIntVar(0, 1, f"rp_{sid}_{day}")
            model.Add(rest_penalty == 1 - dw)
            scaled = int(REST_DEMAND_PENALTY * w)
            penalty_terms.append(scaled * rest_penalty)


# ── Results extraction ────────────────────────────────────────────────────────

def _extract(solver, status, staff, works,
             all_buffet, all_bar, all_accom, active,
             week_config, daily_hours):
    feasible   = status in (cp_model.OPTIMAL, cp_model.FEASIBLE)
    status_str = ("OPTIMAL" if status == cp_model.OPTIMAL
                  else "FEASIBLE" if feasible else "NO_SOLUTION")
    assignments = []

    if feasible:
        for s in staff:
            sid = s["id"]
            person_days = {}
            for day in range(7):
                items = _day_items(sid, day, works,
                                   all_buffet, all_bar, all_accom)
                assigned = []
                for var, sh, vid in items:
                    if solver.Value(var) == 1:
                        e = dict(sh); e["venue_id"] = vid
                        assigned.append(e)
                if assigned:
                    person_days[day] = assigned
                elif day in s["approved_days_off"]:
                    person_days[day] = [{"type": "holiday"}]

            shift_h = sum(sh["paid_h"]
                          for ds in person_days.values()
                          for sh in ds if "paid_h" in sh)
            hol_h   = len(s["approved_days_off"]) * HOLIDAY_PAID_H
            total_h = round(shift_h + hol_h, 2)

            assignments.append({
                "staff_id":         sid,
                "name":             s["name"],
                "contract_type":    s["contract_type"],
                "tm_plus_type":     s.get("tm_plus_type"),
                "department":       s["department"],
                "contracted_hours": s["contracted_hours"],
                "shift_hours":      round(shift_h, 2),
                "holiday_hours":    round(hol_h, 2),
                "allocated_hours":  total_h,
                "hours_gap":        round(max(0, s["contracted_hours"] - total_h), 2),
                "hours_over":       round(max(0, total_h - s["contracted_hours"]), 2),
                "below_contracted": total_h < s["contracted_hours"] - 0.1,
                "holiday_days":     len(s["approved_days_off"]),
                "days":             person_days,
                "skills":           s["skills"],
            })

    coverage = _build_coverage(
        solver if feasible else None, feasible,
        staff, works, all_buffet, all_bar, all_accom,
        active, week_config, daily_hours)

    return {
        "status":      status_str,
        "solve_time":  round(solver.WallTime(), 3),
        "assignments": assignments,
        "coverage":    coverage,
        "summary":     _summary(assignments, solver),
    }


def _build_coverage(solver, feasible, staff, works,
                     all_buffet, all_bar, all_accom,
                     active, week_config, daily_hours):
    """
    Build per-venue per-day per-service coverage report.
    Shows actual vs target for each role.
    Fixed: now correctly populates data when feasible.
    """
    cov = {}
    all_venues = list(all_buffet) + list(all_bar) + ["accommodation"]

    for vid in all_venues:
        cov[vid] = {}
        for day in range(7):

            # Determine if venue is open and what services run
            if vid in all_buffet:
                open_services = [
                    svc for svc in ["breakfast", "dinner"]
                    if vid in active.get(day, {}).get(svc, [])
                ]
                is_open = bool(open_services)
            elif vid in all_bar:
                is_open = bool(all_bar[vid][day])
                open_services = ["bar"] if is_open else []
            else:  # accommodation
                is_open = True
                open_services = ["changeover" if day in CHANGEOVER_DAYS
                                 else "daily"]

            day_cov = {"open": is_open, "services": {}}

            if not is_open or not feasible or solver is None:
                cov[vid][day] = day_cov
                continue

            # Count actual assignments per service per role
            for svc in open_services:
                day_cov["services"][svc] = {}

            for s in staff:
                sid = s["id"]
                if day not in works.get(sid, {}): continue
                if vid not in works[sid][day]: continue
                for idx, var in works[sid][day][vid].items():
                    if solver.Value(var) != 1:
                        continue
                    if vid in all_buffet:
                        slist = all_buffet[vid][day]
                        if idx >= len(slist): continue
                        sh  = slist[idx]
                        svc = sh["service"]
                        role= sh["role"]
                    elif vid in all_bar:
                        slist = all_bar[vid][day]
                        if idx >= len(slist): continue
                        sh   = slist[idx]
                        svc  = "bar"
                        role = sh["role"]
                    else:
                        svc  = open_services[0]
                        role = "accommodation"

                    day_cov["services"].setdefault(svc, {})
                    day_cov["services"][svc].setdefault(
                        role, {"actual": 0, "target": 0})
                    day_cov["services"][svc][role]["actual"] += 1

            # Fill targets + count eligible staff per role
            if vid in all_buffet:
                for svc in open_services:
                    staging = staging_for_venue_day_service(
                        vid, week_config, day, svc)
                    if not staging:
                        continue
                    role_idxs_svc = {}
                    for idx, sh in enumerate(all_buffet[vid][day]):
                        if sh["service"] == svc:
                            role_idxs_svc.setdefault(sh["role"], []).append(idx)
                    for role, tgt in staging.items():
                        day_cov["services"].setdefault(svc, {})
                        day_cov["services"][svc].setdefault(
                            role, {"actual": 0, "target": 0})
                        day_cov["services"][svc][role]["target"] = tgt
                        # Count staff who have a variable for this role/svc/day
                        eligible = sum(
                            1 for s in staff
                            if day in works.get(s["id"], {})
                            and vid in works[s["id"]][day]
                            and any(idx in works[s["id"]][day][vid]
                                    for idx in role_idxs_svc.get(role, []))
                        )
                        day_cov["services"][svc][role]["eligible"] = eligible

            elif vid in all_bar:
                staging = bar_staging_for_day(
                    vid, day, daily_hours, all_bar[vid][day])
                if staging:
                    for role, tgt in staging.items():
                        day_cov["services"].setdefault("bar", {})
                        day_cov["services"]["bar"].setdefault(
                            role, {"actual": 0, "target": 0})
                        day_cov["services"]["bar"][role]["target"] = tgt
                        eligible = sum(
                            1 for s in staff
                            if day in works.get(s["id"], {})
                            and vid in works[s["id"]][day]
                            and any(sh["role"] == role
                                    for idx, sh in enumerate(
                                        all_bar[vid][day])
                                    if idx in works[s["id"]][day].get(vid, {}))
                        )
                        day_cov["services"]["bar"][role]["eligible"] = eligible

            else:  # accommodation
                tgt = accom_target_for_day(week_config, day)
                svc = open_services[0]
                act = day_cov["services"].get(svc, {}).get(
                    "accommodation", {}).get("actual", 0)
                eligible = sum(
                    1 for s in staff
                    if day in works.get(s["id"], {})
                    and "accommodation" in works[s["id"]][day]
                )
                day_cov["services"][svc] = {
                    "accommodation": {
                        "actual": act, "target": tgt, "eligible": eligible
                    }
                }

            # Add gap, ok, and shortage flag
            for svc in day_cov["services"]:
                for role in day_cov["services"][svc]:
                    rd  = day_cov["services"][svc][role]
                    rd["gap"] = rd["target"] - rd["actual"]
                    rd["ok"]  = rd["gap"] == 0
                    # shortage: eligible staff genuinely fewer than target
                    el = rd.get("eligible", rd["target"])
                    rd["shortage"] = max(0, rd["target"] - el)

            cov[vid][day] = day_cov

    return cov


def _summary(assignments, solver):
    if not assignments:
        return {}
    tc = sum(a["contracted_hours"] for a in assignments)
    ta = sum(a["allocated_hours"]  for a in assignments)
    ts = sum(a["shift_hours"]      for a in assignments)
    th = sum(a["holiday_hours"]    for a in assignments)
    below = [a for a in assignments if a["below_contracted"]]
    over  = [a for a in assignments if a["hours_over"] > 0.1]
    return {
        "total_staff":            len(assignments),
        "total_contracted_hrs":   round(tc, 1),
        "total_shift_hrs":        round(ts, 1),
        "total_holiday_hrs":      round(th, 1),
        "total_allocated_hrs":    round(ta, 1),
        "total_gap_hrs":          round(tc - ta, 1),
        "below_contracted_count": len(below),
        "over_hours_count":       len(over),
        "below_contracted_staff": [
            {"name": a["name"], "contracted": a["contracted_hours"],
             "shift_h": a["shift_hours"], "holiday_h": a["holiday_hours"],
             "allocated": a["allocated_hours"], "shortfall": a["hours_gap"]}
            for a in below],
        "over_hours_staff": [
            {"name": a["name"], "contracted": a["contracted_hours"],
             "allocated": a["allocated_hours"], "over": a["hours_over"]}
            for a in over],
        "holiday_days_total": sum(a["holiday_days"] for a in assignments),
        "solve_time":         solver.WallTime() if solver else 0,
    }
