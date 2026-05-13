# =============================================================================
# data/sample_data.py
# Correct staff structure:
#   Deck:        5 normal + 25 TM+1 + 4 TM+2  = 34  (eligible Deck+YC)
#   YC:          0 staff  (covered by Deck team)
#   OceanDrive:  7 normal + 24 TM+1 + 2 TM+2  = 33  (real team, ocean_drive_data.py)
#   QuaySide:    0 staff  (covered by OD team)
#   Bars:        11 normal+ 30 TM+1             = 41  (TM+1 covers bars+accom)
#                NO TM+2 in bars dept — TM+2 from other depts support bars
#   Accom:       186 normal only
# =============================================================================

import random
random.seed(42)

_uid = 1
STAFF = []

def _s(name, contract, dept, home_venues, contracted_h,
       rate, hol_remaining, skills, eligible_venues=None, tm_type=None):
    global _uid
    rec = {
        "id":               f"S{_uid:04d}",
        "name":             name,
        "contract_type":    contract,
        "tm_plus_type":     tm_type,
        "department":       dept,
        "home_venues":      list(home_venues),
        "contracted_hours": contracted_h,
        "hourly_rate":      rate,
        "holiday_remaining":hol_remaining,
        "skills":           list(skills),
        "eligible_venues":  list(eligible_venues or home_venues),
        "approved_days_off":[],
    }
    _uid += 1
    STAFF.append(rec)
    return rec

# ── THE DECK  (real team — 15 normal + 21 TM+1 + 5 TM+2 = 41 staff) ──────────
from data.deck_data import STAFF as _DECK_REAL
for _dk in _DECK_REAL:
    _s(_dk["name"], _dk["contract_type"], _dk["department"],
       _dk["home_venues"], _dk["contracted_hours"], _dk["hourly_rate"],
       _dk["holiday_remaining"], _dk["skills"],
       eligible_venues=_dk["eligible_venues"], tm_type=_dk["tm_plus_type"])
del _DECK_REAL, _dk

# ── OCEAN DRIVE  (real team — 7 normal + 24 TM+1 + 2 TM+2 = 33 staff) ────────
# Staff defined in data/ocean_drive_data.py; re-registered here so IDs are
# sequential with the rest of the sample data.
from data.ocean_drive_data import STAFF as _OD_REAL
for _od in _OD_REAL:
    _s(_od["name"], _od["contract_type"], _od["department"],
       _od["home_venues"], _od["contracted_hours"], _od["hourly_rate"],
       _od["holiday_remaining"], _od["skills"],
       eligible_venues=_od["eligible_venues"], tm_type=_od["tm_plus_type"])
del _OD_REAL, _od

# ── BARS  (real staff from data/bars_data.py) ─────────────────────────────────
from data.bars_data import STAFF as _BARS_REAL
for _br in _BARS_REAL:
    _s(_br["name"], _br["contract_type"], _br["department"],
       _br["home_venues"], _br["contracted_hours"], _br["hourly_rate"],
       _br["holiday_remaining"], _br["skills"],
       eligible_venues=_br["eligible_venues"],
       tm_type=_br.get("tm_plus_type"))
del _BARS_REAL, _br

# ── ACCOMMODATION NORMAL TEAM  (186 staff, no TM+) ────────────────────────────
_ACCOM_ROLES = (["housekeeper"]*140+["supervisor"]*26+["porter"]*20)
for i in range(186):
    _s(f"Accom {i+1:03d}", "normal", "accommodation",
       ["accommodation"], 35.0, 11.00, random.randint(3,18),
       [_ACCOM_ROLES[i % len(_ACCOM_ROLES)]],
       eligible_venues=["accommodation"])

# ── WEEK CONFIG ───────────────────────────────────────────────────────────────
WEEK_CONFIG = {
    "week_number": 12,
    "week_start":  "2025-04-18",
    "fri_batch": {
        "premium_guests":    650,
        "food_court_guests": 950,
        "total_guests":      3800,
    },
    "mon_batch": {
        "premium_guests":    850,
        "food_court_guests": 1000,
        "total_guests":      5100,
    },
    "accom_override": {
        "fri_arrivals": None,
        "mon_arrivals": None,
    },
}

# ── BUFFET SERVICE SCHEDULE ───────────────────────────────────────────────────
# Fri and Mon have BOTH departure breakfast AND opening dinner
def _std_buffet(b_open="08:00", b_close="10:30",
                d_open="16:30", d_close="19:00"):
    svc = []
    for day in range(7):
        # Departure breakfast (shorter) on Fri(0) and Mon(3)
        bc = "10:00" if day in [0,3] else b_close
        svc.append({"day":day,"service":"breakfast",
                    "open":b_open,"close":bc})
        svc.append({"day":day,"service":"dinner",
                    "open":d_open,"close":d_close})
    return svc

BUFFET_SCHEDULE = {
    "the_deck":    _std_buffet(),
    "yacht_club":  _std_buffet(),
    "ocean_drive": _std_buffet(),
    "quay_side":   _std_buffet(),
}

# ── BAR SCHEDULE + DAILY SALES  (from data/bars_data.py) ─────────────────────
from data.bars_data import BAR_SCHEDULE, DAILY_HOURS

# ── APPROVED HOLIDAYS ─────────────────────────────────────────────────────────
APPROVED_HOLIDAYS = [
    {"staff_id":"S0001","days_off":[1,2]},
    {"staff_id":"S0007","days_off":[4,5]},
    {"staff_id":"S0042","days_off":[1,2]},
    {"staff_id":"S0080","days_off":[5,6]},
    {"staff_id":"S0120","days_off":[4,6]},
    {"staff_id":"S0200","days_off":[1,2]},
    {"staff_id":"S0250","days_off":[4,5]},
    {"staff_id":"S0300","days_off":[2,5]},
]
_hmap = {h["staff_id"]:h["days_off"] for h in APPROVED_HOLIDAYS}
for s in STAFF:
    s["approved_days_off"] = _hmap.get(s["id"],[])
    # Hosts can also cover floor
    if "host" in s["skills"] and "floor" not in s["skills"]:
        s["skills"].append("floor")
    # Bays team also does setup (they arrive early and prep the service)
    if "bays" in s["skills"] and "setup" not in s["skills"]:
        s["skills"].append("setup")

# ── ADDITIONAL DECK BAYS WORKERS (dedicated — no setup cross-training) ─────────
# Added AFTER expansion so bays→setup does not fire.
# These workers have only ["bays"] and can fill bays slots without being stolen
# by setup/fridges priority on the same time window.
for _i in range(6):
    _s(f"Deck Bays {_i+1:02d}", "normal", "buffets",
       ["the_deck"], 35.0, 11.50, random.randint(5, 15),
       ["bays"],
       eligible_venues=["the_deck", "yacht_club"])

# ── ADDITIONAL YC BAYS WORKERS (dedicated — home=yacht_club) ─────────────────
# Added AFTER expansion so bays→setup does not fire. Home venue = yacht_club so
# PRIMARY_FLOOR_BIAS pushes them to YC (their primary venue) rather than Deck,
# splitting the bays pool between the two venues.
for _i in range(6):
    _s(f"YC Bays {_i+1:02d}", "normal", "buffets",
       ["yacht_club"], 35.0, 11.50, random.randint(5, 15),
       ["bays"],
       eligible_venues=["the_deck", "yacht_club"])

# ── ADDITIONAL YC FLOOR WORKERS (dedicated — home=yacht_club) ─────────────────
# Home venue = yacht_club so PRIMARY_FLOOR_BIAS pushes them to YC floor first.
# They also cover Deck floor as overflow, ensuring both venues are staffed.
for _i in range(10):
    _s(f"YC Floor {_i+1:02d}", "normal", "buffets",
       ["yacht_club"], 35.0, 11.50, random.randint(5, 15),
       ["floor"],
       eligible_venues=["the_deck", "yacht_club"])

# ── ADDITIONAL OD FLOOR WORKERS (floor-only TM+1) ────────────────────────────
# Added AFTER expansion. Skills = floor + accommodation only — no bays/setup/
# fridges competing roles. These workers fill floor on non-changeover days and
# can do full-accommodation + Mon/Fri dinner floor on changeover days.
for _i in range(10):
    _s(f"OD Floor TM1 {_i+1:02d}", "tm_plus", "buffets",
       ["ocean_drive"], 35.0, 12.50, random.randint(5, 15),
       ["floor", "accommodation"],
       eligible_venues=["ocean_drive", "quay_side", "accommodation"],
       tm_type="tm_plus_1")
del _i
