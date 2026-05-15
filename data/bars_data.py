# =============================================================================
# data/bars_data.py  —  Real bar staff and venue schedules
# Week of 22–29 May 2026 (sourced from the bars schedule CSV)
#
# Roles: everyone is bartender for now (roles confirmed later).
# TM+1 staff also carry "accommodation" skill and are eligible for the
# accommodation venue on Fri/Mon changeover days.
# Sessions for long-open venues are split to stay within the 10h daily paid max.
# =============================================================================

import random
random.seed(99)

# ── BAR SCHEDULE ──────────────────────────────────────────────────────────────
# Day index: 0=Fri 1=Sat 2=Sun 3=Mon 4=Tue 5=Wed 6=Thu
BAR_SCHEDULE = {
    "centre_stage": [
        {"day":0,"session":"evening",  "open":"18:45","close":"22:00"},
        {"day":1,"session":"afternoon","open":"15:15","close":"17:00"},
        {"day":1,"session":"evening",  "open":"18:45","close":"22:00"},
        {"day":2,"session":"afternoon","open":"15:30","close":"17:15"},
        {"day":2,"session":"evening",  "open":"18:45","close":"22:00"},
        {"day":3,"session":"evening",  "open":"18:45","close":"22:00"},
        {"day":4,"session":"evening",  "open":"18:45","close":"22:00"},
        {"day":5,"session":"afternoon","open":"15:15","close":"17:00"},
        {"day":5,"session":"evening",  "open":"18:45","close":"22:00"},
        {"day":6,"session":"morning",  "open":"09:45","close":"13:45"},
        {"day":6,"session":"evening",  "open":"18:45","close":"22:00"},
    ],
    "reds": [
        {"day":0,"session":"evening","open":"18:15","close":"23:00"},
        {"day":1,"session":"lunch",  "open":"11:30","close":"13:00"},
        {"day":1,"session":"evening","open":"18:15","close":"23:00"},
        {"day":2,"session":"evening","open":"18:15","close":"23:00"},
        {"day":3,"session":"evening","open":"18:15","close":"23:00"},
        {"day":4,"session":"evening","open":"18:15","close":"23:00"},
        {"day":5,"session":"evening","open":"18:15","close":"23:00"},
        {"day":6,"session":"lunch",  "open":"11:30","close":"13:00"},
        {"day":6,"session":"evening","open":"18:15","close":"23:00"},
    ],
    # IOTG 12:00–00:00 split into two ≤6h sessions (daily paid cap = 10h)
    "iotg": [
        *[{"day":d,"session":"afternoon","open":"12:00","close":"18:00"} for d in range(7)],
        *[{"day":d,"session":"evening",  "open":"18:00","close":"00:00"} for d in range(7)],
    ],
    "studio_36": [
        {"day":0,"session":"evening",   "open":"17:15","close":"22:00"},
        {"day":1,"session":"session_1", "open":"13:15","close":"15:00"},
        {"day":1,"session":"session_2", "open":"18:15","close":"22:30"},
        {"day":2,"session":"session_1", "open":"13:15","close":"15:15"},
        {"day":2,"session":"session_2", "open":"16:15","close":"18:15"},
        {"day":2,"session":"session_3", "open":"19:15","close":"21:15"},
        {"day":3,"session":"session_1", "open":"16:15","close":"18:00"},
        {"day":3,"session":"session_2", "open":"19:15","close":"21:00"},
        {"day":4,"session":"session_1", "open":"13:15","close":"15:15"},
        {"day":4,"session":"session_2", "open":"16:15","close":"18:15"},
        {"day":4,"session":"session_3", "open":"19:15","close":"21:15"},
        {"day":5,"session":"session_1", "open":"10:15","close":"12:00"},
        {"day":5,"session":"session_2", "open":"13:15","close":"15:00"},
        {"day":5,"session":"session_3", "open":"18:15","close":"20:00"},
        {"day":5,"session":"session_4", "open":"20:45","close":"22:30"},
        {"day":6,"session":"evening",   "open":"17:15","close":"22:00"},
    ],
    # Bar Rosso: Fri/Mon open 08:00–23:00; other days 10:00–23:00
    # Both split into two sessions to stay within 10h daily paid cap
    "bar_rosso": [
        {"day":0,"session":"morning","open":"08:00","close":"15:00"},
        {"day":0,"session":"evening","open":"15:00","close":"23:00"},
        *[{"day":d,"session":"day",    "open":"10:00","close":"17:00"} for d in [1,2,4,5,6]],
        *[{"day":d,"session":"evening","open":"17:00","close":"23:00"} for d in [1,2,4,5,6]],
        {"day":3,"session":"morning","open":"08:00","close":"15:00"},
        {"day":3,"session":"evening","open":"15:00","close":"23:00"},
    ],
    # Hot Shots: 10:00–22:30 every day — split into day + evening
    "hot_shots": [
        *[{"day":d,"session":"day",    "open":"10:00","close":"17:00"} for d in range(7)],
        *[{"day":d,"session":"evening","open":"17:00","close":"22:30"} for d in range(7)],
    ],
    "hwm": [],  # no sessions until HWM is staffed
}

# ── DAILY HOURS (payroll model — allowed spend per venue per day) ──────────────
# Source: payroll model week 22–29 May 2026. Day index: 0=Fri … 6=Thu
#                        Fri    Sat    Sun    Mon    Tue    Wed    Thu
DAILY_HOURS = {
    "bar_rosso":    [ 66.5,  78.2,  61.5,  55.0,  55.0,  55.0,  55.0],
    "hot_shots":    [ 50.0,  70.0,  67.5,  54.5,  65.2,  55.7,  59.1],
    "iotg":         [ 34.6,  38.9,  38.8,  38.6,  39.2,  36.1,  35.2],
    "studio_36":    [ 66.1,  69.4,  66.1,  60.4,  69.7,  57.3,  49.7],
    "centre_stage": [ 36.6,  44.7,  57.8,  50.6,  67.9,  37.8,  37.4],
    "reds":         [ 67.1,  81.4,  41.6,  43.2,  72.7,  71.2,  86.1],
    "hwm":          [  5.7,   5.7,   5.6,   8.7,   5.7,   5.7,   5.7],
}

# ── REAL BAR STAFF ─────────────────────────────────────────────────────────────
# Tuple: (name, home_venues, eligible_bar_venues, contracted_hours, tm_type)
# tm_type=None → normal; tm_type="tm_plus_1" → TM+1 (also works accommodation)
# Removed: managers with separate roster (10 staff — managed via separate system)

_BAR_STAFF = [
    # ── Centre Stage primary ─────────────────────────────────────────────────
    ("Cameron O'Brien",         ["centre_stage"],           ["centre_stage","reds","iotg"],                                35.0, "tm_plus_1"),
    ("Daniel Horvath",            ["centre_stage"],           ["centre_stage","reds"],                                       35.0, None),
    ("Joshua Brennan",        ["centre_stage"],           ["centre_stage"],                                              35.0, "tm_plus_1"),
    ("Katie Hadley",          ["centre_stage"],           ["centre_stage","reds","iotg"],                                35.0, None),
    ("Keir Donovan",          ["centre_stage"],           ["centre_stage","reds","bar_rosso","studio_36"],               35.0, None),
    ("Martin Ribeiro",       ["centre_stage"],           ["centre_stage","iotg"],                                       35.0, "tm_plus_1"),
    ("Piran Flynn",         ["centre_stage"],           ["centre_stage","hot_shots"],                                  35.0, "tm_plus_1"),
    ("Tamas Balint",             ["centre_stage"],           ["centre_stage","bar_rosso"],                                  35.0, None),
    ("Victoria Schwartz",         ["centre_stage"],           ["centre_stage"],                                              35.0, "tm_plus_1"),
    # ── Reds primary ─────────────────────────────────────────────────────────
    ("Christie Donovan",      ["reds"],                   ["reds","studio_36"],                                          35.0, None),
    ("Coral Whitmore",        ["reds"],                   ["reds","bar_rosso"],                                          35.0, None),
    ("Dawn Bailey",            ["reds"],                   ["reds","bar_rosso"],                                          35.0, "tm_plus_1"),
    ("Elsie Ewing",             ["reds"],                   ["reds","studio_36","hot_shots"],                              35.0, "tm_plus_1"),
    ("Georgia Schulz",          ["studio_36"],              ["studio_36","reds","centre_stage"],                           35.0, "tm_plus_1"),
    ("Logan Hammond",          ["reds"],                   ["reds"],                                                       35.0, "tm_plus_1"),
    ("Michael Brambilla",       ["reds"],                   ["reds","iotg"],                                               35.0, "tm_plus_1"),
    ("Nathan Coulter",          ["reds"],                   ["reds","centre_stage","hot_shots"],                           35.0, "tm_plus_1"),
    ("Nicholas Morgan",        ["reds"],                   ["reds","studio_36"],                                          35.0, None),
    ("Oliver Edmonds",          ["reds"],                   ["reds","centre_stage","bar_rosso","hot_shots"],               35.0, "tm_plus_1"),
    ("Oliver Simmons",             ["reds"],                   ["reds","centre_stage","hot_shots"],                           35.0, "tm_plus_1"),
    ("Oliver Blake-Harding",    ["reds"],                   ["reds","centre_stage"],                                       35.0, "tm_plus_1"),
    ("Volodymyr Karpenko",     ["reds"],                   ["reds","centre_stage","bar_rosso","iotg"],                    35.0, "tm_plus_1"),
    # ── IOTG primary ─────────────────────────────────────────────────────────
    ("Charli Campbell",         ["iotg"],                   ["iotg","hot_shots","reds"],                                   35.0, None),
    ("Ellie Griffiths",            ["iotg"],                   ["iotg","studio_36","bar_rosso"],                              35.0, None),
    ("Kevin Dawson",              ["iotg"],                   ["iotg","centre_stage","bar_rosso"],                           35.0, "tm_plus_1"),
    ("Lauren Chambers",           ["iotg"],                   ["iotg","hot_shots"],                                          35.0, "tm_plus_1"),
    ("Ryan Bevan",             ["iotg"],                   ["iotg","bar_rosso","hot_shots"],                              35.0, None),
    ("Samuel Sinclair",       ["iotg"],                   ["iotg","centre_stage","studio_36","bar_rosso"],               35.0, None),
    # ── Bar Rosso primary ────────────────────────────────────────────────────
    ("Charlotte Brentwood",      ["bar_rosso"],              ["bar_rosso","iotg","studio_36","hot_shots","centre_stage"],   40.0, None),
    ("Chloe Norris",            ["bar_rosso"],              ["bar_rosso","reds","studio_36","centre_stage"],               35.0, None),
    ("Chloe Jackson",            ["bar_rosso"],              ["bar_rosso","studio_36"],                                     35.0, None),
    ("Emily Lawson",           ["bar_rosso"],              ["bar_rosso","studio_36"],                                     35.0, None),
    ("Grace Barker",          ["bar_rosso"],              ["bar_rosso","studio_36","iotg"],                              35.0, None),
    ("Iryna Vasylchuk",       ["bar_rosso"],              ["bar_rosso","studio_36"],                                     35.0, None),
    ("Oleksandr Bilenky",     ["bar_rosso"],              ["bar_rosso","studio_36","hot_shots"],                         35.0, "tm_plus_1"),
    ("Samuel Blackwood",          ["bar_rosso"],              ["bar_rosso","centre_stage","studio_36"],                      35.0, None),
    # ── Studio 36 primary ────────────────────────────────────────────────────
    ("Alan Caldwell",         ["studio_36"],              ["studio_36","bar_rosso","hot_shots"],                         35.0, None),
    ("Aleksandrs Bertoni",      ["studio_36"],              ["studio_36","bar_rosso","hot_shots"],                         35.0, None),
    ("Demi Foster",           ["studio_36"],              ["studio_36","reds","centre_stage","bar_rosso","iotg"],        35.0, "tm_plus_1"),
    ("Jessie Stone-Perry",      ["studio_36"],              ["studio_36","centre_stage"],                                  35.0, "tm_plus_1"),
    ("Jonathan Webb-Gradwell", ["studio_36"],              ["studio_36","centre_stage","bar_rosso"],                      35.0, "tm_plus_1"),
    ("Oluwatosin Osei",     ["studio_36"],              ["studio_36","reds","bar_rosso","iotg"],                       35.0, "tm_plus_1"),
    # ── Hot Shots primary ────────────────────────────────────────────────────
    ("Andrzej Nowak",         ["hot_shots"],              ["hot_shots","studio_36","bar_rosso"],                         35.0, "tm_plus_1"),
    ("Dakota Chandler",           ["hot_shots"],              ["hot_shots","studio_36"],                                     35.0, None),
    ("Jess Shelton",             ["hot_shots"],              ["hot_shots","studio_36"],                                     35.0, "tm_plus_1"),
    ("Joshua Cavendish",          ["hot_shots"],              ["hot_shots","bar_rosso","centre_stage","iotg"],               35.0, "tm_plus_1"),
    ("Marcin Wisniewski",          ["hot_shots"],              ["hot_shots"],                                                  35.0, None),
    ("Melissa Parrish",          ["hot_shots"],              ["hot_shots","iotg","centre_stage","studio_36"],               35.0, "tm_plus_1"),
    ("Oliver Eaton",          ["hot_shots"],              ["hot_shots"],                                                  35.0, None),
    ("Seren Beaumont",           ["hot_shots"],              ["hot_shots","reds","bar_rosso"],                              35.0, None),
    # ── HWM ─────────────────────────────────────────────────────────────────
    ("Cheryl Forsythe",          ["hwm"],                    ["hwm"],                                                        35.0, None),
]

STAFF = [
    {
        "name":             name,
        "contract_type":    "tm_plus" if tm_type else "normal",
        "tm_plus_type":     tm_type,
        "department":       "bars",
        "home_venues":      list(home),
        "contracted_hours": contracted_h,
        "hourly_rate":      12.00,
        "holiday_remaining":random.randint(5, 15),
        "skills":           ["bartender", "accommodation"] if tm_type else ["bartender"],
        "eligible_venues":  list(eligible) + ["accommodation"] if tm_type else list(eligible),
        "approved_days_off":[],
    }
    for name, home, eligible, contracted_h, tm_type in _BAR_STAFF
]
