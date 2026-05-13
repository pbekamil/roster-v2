# =============================================================================
# data/excel_reader.py
# Reads a weekly input Excel workbook and returns the five data structures
# expected by solve():  staff, week_config, buffet_schedule, bar_schedule,
# daily_hours.
#
# Sheet layout:
#   WeekConfig     — key/value pairs (guest counts, week dates)
#   Staff          — one row per person (or "Accom Team" placeholder row)
#   DaysOff        — long-format: name | day (Fri…Thu)
#   DailyHours     — venue | Fri | Sat | Sun | Mon | Tue | Wed | Thu
#   BarSchedule    — venue | day | session | open | close
#   BuffetSchedule — venue | day | service | open | close  (optional)
# =============================================================================

import pandas as pd

_DAY_IDX = {"Fri": 0, "Sat": 1, "Sun": 2, "Mon": 3,
            "Tue": 4, "Wed": 5, "Thu": 6}
_DAY_COLS = ["Fri", "Sat", "Sun", "Mon", "Tue", "Wed", "Thu"]

_ACCOM_ROLES = (["housekeeper"] * 140 + ["supervisor"] * 26 + ["porter"] * 20)


def _split(val):
    """Split a comma-separated cell value into a stripped list."""
    if pd.isna(val) or str(val).strip() == "":
        return []
    return [v.strip() for v in str(val).split(",") if v.strip()]


def _std_buffet(b_open="08:00", b_close="10:30",
                d_open="16:30", d_close="19:00"):
    """Default buffet schedule — same logic as sample_data.py."""
    svc = []
    for day in range(7):
        bc = "10:00" if day in [0, 3] else b_close
        svc.append({"day": day, "service": "breakfast",
                    "open": b_open, "close": bc})
        svc.append({"day": day, "service": "dinner",
                    "open": d_open, "close": d_close})
    return svc


# ── Sheet readers ─────────────────────────────────────────────────────────────

def _read_week_config(xls: pd.ExcelFile) -> dict:
    df = xls.parse("WeekConfig", header=None, names=["key", "value"])
    df = df.dropna(subset=["key"])
    kv = {str(r.key).strip(): r.value for _, r in df.iterrows()}

    def _int(k):
        v = kv.get(k)
        return int(v) if pd.notna(v) and str(v).strip() != "" else 0

    def _opt_int(k):
        v = kv.get(k)
        return int(v) if pd.notna(v) and str(v).strip() not in ("", "nan") else None

    return {
        "week_number": _int("week_number"),
        "week_start":  str(kv.get("week_start", "")).strip(),
        "fri_batch": {
            "premium_guests":    _int("fri_premium_guests"),
            "food_court_guests": _int("fri_food_court_guests"),
            "total_guests":      _int("fri_total_guests"),
        },
        "mon_batch": {
            "premium_guests":    _int("mon_premium_guests"),
            "food_court_guests": _int("mon_food_court_guests"),
            "total_guests":      _int("mon_total_guests"),
        },
        "accom_override": {
            "fri_arrivals": _opt_int("fri_arrivals_override"),
            "mon_arrivals": _opt_int("mon_arrivals_override"),
        },
    }


def _read_staff(xls: pd.ExcelFile) -> list:
    df = xls.parse("Staff")
    df.columns = [str(c).strip() for c in df.columns]
    df = df.dropna(subset=["name"])

    staff = []
    uid = 1

    for _, row in df.iterrows():
        name = str(row["name"]).strip()

        # Special placeholder row for generated accommodation team
        if name == "Accom Team":
            count = int(row.get("count", 186)) if pd.notna(row.get("count", 186)) else 186
            for i in range(count):
                staff.append({
                    "id":               f"S{uid:04d}",
                    "name":             f"Accom {i+1:03d}",
                    "contract_type":    "normal",
                    "tm_plus_type":     None,
                    "department":       "accommodation",
                    "home_venues":      ["accommodation"],
                    "eligible_venues":  ["accommodation"],
                    "contracted_hours": 35.0,
                    "hourly_rate":      11.00,
                    "holiday_remaining":10,
                    "skills":           [_ACCOM_ROLES[i % len(_ACCOM_ROLES)]],
                    "approved_days_off":[],
                })
                uid += 1
            continue

        contract    = str(row.get("contract_type", "normal")).strip() or "normal"
        tm_raw      = row.get("tm_plus_type", "")
        tm_type     = str(tm_raw).strip() if pd.notna(tm_raw) and str(tm_raw).strip() not in ("", "nan") else None
        department  = str(row.get("department", "")).strip()
        home        = _split(row.get("home_venues", ""))
        eligible    = _split(row.get("eligible_venues", "")) or home
        c_hours     = float(row.get("contracted_hours", 35.0) or 35.0)
        rate        = float(row.get("hourly_rate", 11.50) or 11.50)
        hol         = int(row.get("holiday_remaining", 10) or 10)
        skills      = _split(row.get("skills", ""))

        # TM+ also needs accommodation in eligible venues and skills
        if tm_type and "accommodation" not in eligible:
            eligible = list(eligible) + ["accommodation"]
        if tm_type and "accommodation" not in skills:
            skills = list(skills) + ["accommodation"]

        # Post-load skill expansions (mirrors sample_data.py)
        if "host" in skills and "floor" not in skills:
            skills.append("floor")
        if "bays" in skills and "setup" not in skills:
            skills.append("setup")

        staff.append({
            "id":               f"S{uid:04d}",
            "name":             name,
            "contract_type":    contract,
            "tm_plus_type":     tm_type,
            "department":       department,
            "home_venues":      home,
            "eligible_venues":  eligible,
            "contracted_hours": c_hours,
            "hourly_rate":      rate,
            "holiday_remaining":hol,
            "skills":           skills,
            "approved_days_off":[],
        })
        uid += 1

    return staff


def _apply_days_off(staff: list, xls: pd.ExcelFile):
    """Mutate staff records to set approved_days_off from the DaysOff sheet."""
    if "DaysOff" not in xls.sheet_names:
        return
    df = xls.parse("DaysOff")
    df.columns = [str(c).strip() for c in df.columns]
    df = df.dropna(subset=["name"])

    name_to_days: dict[str, list] = {}
    for _, row in df.iterrows():
        name = str(row["name"]).strip()
        day  = str(row.get("day", "")).strip()
        if day in _DAY_IDX:
            name_to_days.setdefault(name, []).append(_DAY_IDX[day])

    name_to_staff = {s["name"]: s for s in staff}
    for name, days in name_to_days.items():
        if name in name_to_staff:
            name_to_staff[name]["approved_days_off"] = sorted(set(days))


def _read_daily_hours(xls: pd.ExcelFile) -> dict:
    df = xls.parse("DailyHours")
    df.columns = [str(c).strip() for c in df.columns]
    df = df.dropna(subset=["venue"])
    result = {}
    for _, row in df.iterrows():
        venue = str(row["venue"]).strip()
        hours = []
        for col in _DAY_COLS:
            v = row.get(col, 0)
            hours.append(float(v) if pd.notna(v) else 0.0)
        result[venue] = hours
    return result


def _read_bar_schedule(xls: pd.ExcelFile) -> dict:
    df = xls.parse("BarSchedule")
    df.columns = [str(c).strip() for c in df.columns]
    df = df.dropna(subset=["venue", "day"])
    result: dict[str, list] = {}
    for _, row in df.iterrows():
        venue   = str(row["venue"]).strip()
        day_str = str(row["day"]).strip()
        if day_str not in _DAY_IDX:
            continue
        entry = {
            "day":     _DAY_IDX[day_str],
            "session": str(row.get("session", "session")).strip(),
            "open":    str(row["open"]).strip(),
            "close":   str(row["close"]).strip(),
        }
        result.setdefault(venue, []).append(entry)
    return result


def _read_buffet_schedule(xls: pd.ExcelFile) -> dict:
    """
    Parse BuffetSchedule sheet.  Any venue NOT listed falls back to _std_buffet().
    Any venue listed must have complete day coverage (all 7 days × 2 services).
    """
    buffet_venues = ["the_deck", "yacht_club", "ocean_drive", "quay_side"]
    result = {v: _std_buffet() for v in buffet_venues}

    if "BuffetSchedule" not in xls.sheet_names:
        return result

    df = xls.parse("BuffetSchedule")
    df.columns = [str(c).strip() for c in df.columns]
    df = df.dropna(subset=["venue", "day", "service"])

    overrides: dict[str, list] = {}
    for _, row in df.iterrows():
        venue   = str(row["venue"]).strip()
        day_str = str(row["day"]).strip()
        if day_str not in _DAY_IDX:
            continue
        overrides.setdefault(venue, []).append({
            "day":     _DAY_IDX[day_str],
            "service": str(row["service"]).strip(),
            "open":    str(row["open"]).strip(),
            "close":   str(row["close"]).strip(),
        })

    for venue, svc_list in overrides.items():
        result[venue] = svc_list

    return result


# ── Public API ────────────────────────────────────────────────────────────────

def load_from_excel(path: str):
    """
    Read a weekly input workbook and return:
        (staff, week_config, buffet_schedule, bar_schedule, daily_hours)

    These match the exact signatures expected by solve() in solver/core.py.
    """
    xls = pd.ExcelFile(path, engine="openpyxl")

    required = {"WeekConfig", "Staff", "DailyHours", "BarSchedule"}
    missing  = required - set(xls.sheet_names)
    if missing:
        raise ValueError(f"Excel workbook is missing required sheets: {missing}")

    week_config     = _read_week_config(xls)
    staff           = _read_staff(xls)
    _apply_days_off(staff, xls)
    daily_hours     = _read_daily_hours(xls)
    bar_schedule    = _read_bar_schedule(xls)
    buffet_schedule = _read_buffet_schedule(xls)

    return staff, week_config, buffet_schedule, bar_schedule, daily_hours
