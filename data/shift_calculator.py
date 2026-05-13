# =============================================================================
# data/shift_calculator.py
# Derives shift times from opening/closing times + role offsets.
# Handles break deduction, overlap detection, 11h gap checks.
# Batch boundary logic: Fri/Mon each have BOTH departure breakfast
# (end of previous batch) AND opening dinner (start of new batch).
# =============================================================================

from data.config import (
    BUFFET_ROLE_OFFSETS, BUFFET_VENUES, BUFFET_OPENING_RULES,
    PREMIUM_BANDS, FOOD_COURT_BANDS, ACCOM_SHIFTS, ACCOM_FORMULA,
    CHANGEOVER_DAYS, FRI_BATCH_DAYS, MON_BATCH_DAYS,
    DEPARTURE_BREAKFAST, BREAK_THRESHOLD_H, BREAK_DURATION_H,
    BAR_ROLES, DINNER_ONLY_OPENING,
)


def t2m(time_str):
    h, m = map(int, time_str.split(":"))
    return h * 60 + m

def m2t(mins):
    h = (mins // 60) % 24
    return f"{h:02d}:{mins % 60:02d}"

def hhmm2m(hhmm):
    return (hhmm // 100) * 60 + (hhmm % 100)

def on_site_to_paid(on_site_h):
    if on_site_h > BREAK_THRESHOLD_H:
        return on_site_h - BREAK_DURATION_H
    return on_site_h

def shifts_overlap(a, b):
    as_, ae = a["start_min"], a["end_min"]
    bs_, be = b["start_min"], b["end_min"]
    if ae < as_: ae += 1440
    if be < bs_: be += 1440
    return as_ < be and bs_ < ae

def gap_ok(shift_today, shift_tomorrow, min_gap_h=11):
    end   = shift_today["end_min"]
    start = shift_tomorrow["start_min"]
    if start <= end:
        start += 1440
    return (start - end) >= min_gap_h * 60


def buffet_shifts_for_day(venue_id, service_schedule, day):
    """
    Return shift dicts for a buffet venue on a specific day.

    Batch boundary logic:
      Fri (day 0): breakfast = departure (Mon batch ending, 08:00-10:00)
                   dinner    = Fri batch opening service
      Mon (day 3): breakfast = departure (Fri batch ending, 08:00-10:00)
                   dinner    = Mon batch opening service

    Dinner-only venues (yacht_club, quay_side):
      First day they open → dinner only
      Subsequent days → both services
      We detect "first day open" by checking if previous day was also open.
    """
    venue_cfg  = BUFFET_VENUES.get(venue_id, {})
    has_chef   = venue_cfg.get("station_chef", False)
    is_overflow = bool(venue_cfg.get("staffed_by"))
    excluded_roles = set(venue_cfg.get("excluded_roles", []))

    # Get services scheduled for this day
    day_services = [s for s in service_schedule if s["day"] == day]
    shifts = []

    for svc in day_services:
        open_m  = t2m(svc["open"])
        close_m = t2m(svc["close"])

        # Determine which batch's guest numbers apply to this service
        # Departure breakfast uses PREVIOUS batch guests for staging
        # Opening dinner uses CURRENT batch guests for staging
        service_type = svc["service"]
        if day in [0, 3] and service_type == "breakfast":
            # Departure breakfast — previous batch
            batch_key = "mon_batch" if day == 0 else "fri_batch"
        elif day in FRI_BATCH_DAYS:
            batch_key = "fri_batch"
        else:
            batch_key = "mon_batch"

        for role, off in BUFFET_ROLE_OFFSETS.items():
            if role == "station_chef" and not has_chef:
                continue
            if role in excluded_roles:
                continue
            s_min  = open_m  + off["start"]
            e_min  = close_m + off["end"]
            on_h   = round((e_min - s_min) / 60, 4)
            paid_h = round(on_site_to_paid(on_h), 4)
            shifts.append({
                "role":      role,
                "service":   service_type,
                "day":       day,
                "start_min": s_min,
                "end_min":   e_min,
                "on_site_h": on_h,
                "paid_h":    paid_h,
                "label":     f"{m2t(s_min)}-{m2t(e_min)}",
                "task":      f"{role.replace('_',' ').title()} — {service_type.title()}",
                "batch_key": batch_key,
                "venue_id":  venue_id,
            })
    return shifts


def bar_shifts_for_day(venue_id, bar_schedule, day):
    day_sessions = [s for s in bar_schedule if s["day"] == day]
    shifts = []
    for svc in day_sessions:
        s_min = t2m(svc["open"])
        e_min = t2m(svc["close"])
        if e_min <= s_min:
            e_min += 1440
        on_h   = round((e_min - s_min) / 60, 4)
        paid_h = round(on_site_to_paid(on_h), 4)
        for role in BAR_ROLES:
            shifts.append({
                "role":      role,
                "service":   svc["session"],
                "day":       day,
                "start_min": s_min,
                "end_min":   e_min,
                "on_site_h": on_h,
                "paid_h":    paid_h,
                "label":     f"{svc['open']}-{svc['close']}",
                "task":      f"{role.replace('_',' ').title()} — {svc['session'].title()}",
                "venue_id":  venue_id,
            })
    return shifts


def accom_shifts_for_day(day, is_changeover):
    shifts = []
    options = ACCOM_SHIFTS if is_changeover else [ACCOM_SHIFTS[0]]
    for opt in options:
        s_min = hhmm2m(opt["start"])
        e_min = hhmm2m(opt["end"])
        shifts.append({
            "role":        "accommodation",
            "service":     "changeover" if is_changeover else "daily",
            "day":         day,
            "start_min":   s_min,
            "end_min":     e_min,
            "on_site_h":   opt["on_site_h"],
            "paid_h":      opt["paid_h"],
            "label":       opt["label"],
            "shift_id":    opt["id"],
            "task":        f"Accommodation — {'Changeover' if is_changeover else 'Daily'}",
            "venue_id":    "accommodation",
        })
    return shifts


def _get_batch_guests(week_config, day, service):
    """
    Return correct guest count for staging purposes.
    Departure breakfast uses previous batch.
    All other services use current batch.
    """
    if day == 0 and service == "breakfast":
        return week_config["mon_batch"]   # end of Mon batch
    if day == 3 and service == "breakfast":
        return week_config["fri_batch"]   # end of Fri batch
    if day in FRI_BATCH_DAYS:
        return week_config["fri_batch"]
    return week_config["mon_batch"]


def active_buffets_by_day(week_config):
    """
    Returns dict {day: {service: [venue_ids]}}
    Handles dinner-only opening for YC and QS on their first open day.
    """
    result = {}

    # First pass: determine which days each venue is open at all
    venue_open_days = {vid: [] for vid in BUFFET_VENUES}

    for day in range(7):
        fri_b = week_config["fri_batch"]
        mon_b = week_config["mon_batch"]

        # Premium
        pg = (fri_b if day in FRI_BATCH_DAYS else mon_b)["premium_guests"]
        for (lo, hi), venues in BUFFET_OPENING_RULES["premium"].items():
            if lo <= pg <= hi:
                for v in venues:
                    venue_open_days[v].append(day)
                break

        # Food court — use correct batch per service
        # For food court threshold, dinner on Fri/Mon uses new batch
        if day in [0, 3]:
            # Dinner uses new batch guests
            din_batch = fri_b if day == 0 else mon_b
            fg_din = din_batch["food_court_guests"]
            # Breakfast uses departing batch guests
            dep_batch = mon_b if day == 0 else fri_b
            fg_bkf = dep_batch["food_court_guests"]
        elif day in FRI_BATCH_DAYS:
            fg_din = fg_bkf = fri_b["food_court_guests"]
        else:
            fg_din = fg_bkf = mon_b["food_court_guests"]

        # Use dinner guests for overall open decision
        for (lo, hi), venues in BUFFET_OPENING_RULES["food_court"].items():
            if lo <= fg_din <= hi:
                for v in venues:
                    if day not in venue_open_days[v]:
                        venue_open_days[v].append(day)
                break

    # Second pass: build per-day per-service open list
    # Dinner-only venues open dinner-only on their FIRST open day
    for day in range(7):
        result[day] = {"breakfast": [], "dinner": []}

        for vid, open_days in venue_open_days.items():
            if day not in open_days:
                continue

            if vid in DINNER_ONLY_OPENING:
                # First day this venue opens → dinner only
                sorted_days = sorted(open_days)
                if day == sorted_days[0]:
                    result[day]["dinner"].append(vid)
                else:
                    result[day]["breakfast"].append(vid)
                    result[day]["dinner"].append(vid)
            else:
                result[day]["breakfast"].append(vid)
                result[day]["dinner"].append(vid)

    return result


def staging_for_venue_day_service(venue_id, week_config, day, service):
    """
    Return {role: exact_count} for a venue/day/service combo.
    For overflow venues (YC, QS): returns their share of the combined band.
    Returns None if venue closed for that service.
    """
    active = active_buffets_by_day(week_config)
    if venue_id not in active.get(day, {}).get(service, []):
        return None

    batch    = _get_batch_guests(week_config, day, service)
    category = BUFFET_VENUES[venue_id]["category"]
    guests   = (batch["premium_guests"] if category == "premium"
                else batch["food_court_guests"])
    bands    = PREMIUM_BANDS if category == "premium" else FOOD_COURT_BANDS

    # Find the source venue for overflow venues
    source_vid = BUFFET_VENUES.get(venue_id, {}).get("staffed_by")

    excluded = set(BUFFET_VENUES.get(venue_id, {}).get("excluded_roles", []))

    for (lo, hi), reqs in bands.items():
        if lo <= guests <= hi:
            if guests >= 1100 and category == "food_court":
                # Both food court venues open — split equally
                result = {role: max(1, cnt // 2) for role, cnt in reqs.items()}
            elif guests >= 800 and category == "premium":
                # Both premium venues open — split equally
                result = {role: max(1, cnt // 2) for role, cnt in reqs.items()}
            elif source_vid:
                # Single venue open — overflow venue shouldn't be open alone
                return None
            else:
                result = dict(reqs)
            return {role: cnt for role, cnt in result.items() if role not in excluded}
    return {}


def accom_target_for_day(week_config, day):
    """
    Changeover days: staff = arrivals ÷ rooms_per_staff
    Normal days: fixed 40.
    """
    if day not in CHANGEOVER_DAYS:
        return ACCOM_FORMULA["normal_day_target"]

    batch = (week_config["fri_batch"] if day in FRI_BATCH_DAYS
             else week_config["mon_batch"])

    override = week_config.get("accom_override", {})
    key      = "fri_arrivals" if day in FRI_BATCH_DAYS else "mon_arrivals"
    ov_val   = override.get(key) if override else None

    if ov_val is not None:
        return max(1, round(ov_val / ACCOM_FORMULA["rooms_per_staff"]))

    arrivals = batch["total_guests"] / ACCOM_FORMULA["avg_family_size"]
    return max(1, round(arrivals / ACCOM_FORMULA["rooms_per_staff"]))


def bar_staging_for_day(venue_id, day, daily_hours, day_shifts):
    """
    Derive bartender headcount target for a bar on a given day.
    Converts the payroll-model hours budget into a headcount by dividing by
    the average paid hours per session for that day.
    Returns {"bartender": n} or None if bar is closed / no budget.
    day_shifts: list of shift dicts for this venue/day (already have paid_h).
    """
    from data.config import BAR_MIN_STAGING
    if not day_shifts:
        return None
    weekly = daily_hours.get(venue_id)
    if weekly is None:
        return dict(BAR_MIN_STAGING)
    if day >= len(weekly) or weekly[day] <= 0:
        return None
    budget_h = weekly[day]
    # Unique sessions (one paid_h per session time window)
    seen, paid_hs = set(), []
    for sh in day_shifts:
        key = (sh["start_min"], sh["end_min"])
        if key not in seen:
            seen.add(key)
            paid_hs.append(sh["paid_h"])
    # Use SUM of all session paid_h (= one worker doing the full day) as the
    # divisor.  avg_paid_h would inflate targets when there are many short
    # sessions (e.g. Studio 36 with 4 × 1.75h sessions → avg=1.75h → ×33).
    total_daily_paid_h = sum(paid_hs) if paid_hs else 7.0
    target = max(BAR_MIN_STAGING["bartender"], round(budget_h / total_daily_paid_h))
    return {"bartender": target}
