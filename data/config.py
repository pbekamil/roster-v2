# =============================================================================
# data/config.py  —  Static configuration
# =============================================================================

DAYS            = ["Fri", "Sat", "Sun", "Mon", "Tue", "Wed", "Thu"]
FRI_BATCH_DAYS  = [0, 1, 2]
MON_BATCH_DAYS  = [3, 4, 5, 6]
CHANGEOVER_DAYS = [0, 3]
DEPARTURE_DAYS  = {0: "fri", 3: "mon"}

# ── CONTRACTS ─────────────────────────────────────────────────────────────────
CONTRACTED_HOURS        = 35.0
HOURS_PER_SHIFT         = 7.5
BREAK_THRESHOLD_H       = 6.0
BREAK_DURATION_H        = 0.5
PAID_LONG_SHIFT_H       = HOURS_PER_SHIFT - BREAK_DURATION_H   # 7.0h paid
MIN_REST_DAYS           = 1    # legal minimum
MAX_REST_DAYS           = 2    # maximum rest days
WORKING_DAYS            = 5    # target working days
HOLIDAY_PAID_H          = CONTRACTED_HOURS / 5   # 7.0h per holiday day
MIN_REST_BETWEEN_DAYS_H = 11

# ── ACCOMMODATION ─────────────────────────────────────────────────────────────
ACCOM_FORMULA = {
    "avg_family_size":   4,
    "rooms_per_staff":   3.9,  # rooms one staff cleans per changeover
    "normal_day_target": 40,
}
ACCOM_NORMAL_DAYS_TARGET = 40

ACCOM_SHIFTS = [
    {"id": "full",  "start": 900,  "end": 1600,
     "on_site_h": 7.0, "paid_h": 6.5, "label": "09:00-16:00"},
    {"id": "short", "start": 1100, "end": 1600,
     "on_site_h": 5.0, "paid_h": 5.0, "label": "11:00-16:00"},
]

# ── BUFFET ROLE OFFSETS ───────────────────────────────────────────────────────
BUFFET_ROLE_OFFSETS = {
    "host":         {"start": -15, "end": +15},
    "floor":        {"start": +30, "end": +60},
    "beverage":     {"start":   0, "end": +60},
    "bar":          {"start":   0, "end": +60},   # bar station within The Deck
    "bays":         {"start":   0, "end": +60},
    "setup":        {"start": -45, "end": +60},
    "fridges":      {"start": -60, "end": +60},
    "station_chef": {"start": -45, "end": +60},
}

DEPARTURE_BREAKFAST = {"open": "08:00", "close": "10:00"}

# ── BUFFET VENUES ─────────────────────────────────────────────────────────────
# Deck/YC share one team (same as OD/QS model)
# YC has zero dedicated staff — Deck team covers when open
BUFFET_VENUES = {
    "the_deck":    {"name": "The Deck",    "category": "premium",
                    "station_chef": True},
    "yacht_club":  {"name": "Yacht Club",  "category": "premium",
                    "station_chef": False, "staffed_by": "the_deck",
                    "excluded_roles": ["host", "bar", "station_chef"]},
    "ocean_drive": {"name": "Ocean Drive", "category": "food_court",
                    "station_chef": False},
    "quay_side":   {"name": "Quay Side",   "category": "food_court",
                    "station_chef": False, "staffed_by": "ocean_drive"},
}

BUFFET_OPENING_RULES = {
    "premium":    {
        (0, 799):    ["the_deck"],
        (800, 99999):["the_deck", "yacht_club"],
    },
    "food_court": {
        (0, 1099):    ["ocean_drive"],
        (1100, 99999):["ocean_drive", "quay_side"],
    },
}

# Venues that open from DINNER only on the day threshold is first crossed
# (subsequent days they run both services)
DINNER_ONLY_OPENING = {"quay_side", "yacht_club"}

# ── BUFFET STAGING BANDS ──────────────────────────────────────────────────────
PREMIUM_BANDS = {
    (0, 399):    {"host":1,"floor":6, "bar":1,"beverage":2,"bays":6,
                  "setup":2,"fridges":2,"station_chef":3},
    (400, 799):  {"host":1,"floor":8, "bar":1,"beverage":2,"bays":6,
                  "setup":2,"fridges":2,"station_chef":3},
    (800, 99999):{"host":1,"floor":12,"bar":1,"beverage":3,"bays":8,
                  "setup":3,"fridges":3,"station_chef":6},
}

FOOD_COURT_BANDS = {
    (0, 599):    {"host":1,"floor":6, "beverage":2,"bays":4,
                  "setup":2,"fridges":2},
    (600, 1099): {"host":1,"floor":10,"beverage":2,"bays":5,
                  "setup":2,"fridges":2},
    (1100,99999):{"host":2,"floor":16,"beverage":3,"bays":8,
                  "setup":2,"fridges":3},
}

# ── BAR VENUES + ROLES ────────────────────────────────────────────────────────
BAR_VENUES = {
    "centre_stage": {"name": "Centre Stage"},
    "reds":         {"name": "Reds"},
    "studio_36":    {"name": "Studio 36"},
    "bar_rosso":    {"name": "Bar Rosso"},
    "iotg":         {"name": "IOTG"},
    "hot_shots":    {"name": "Hot Shots"},
    "hwm":          {"name": "HWM"},
}
BAR_ROLES       = ["bartender"]
BAR_MIN_STAGING = {"bartender": 2}

# ── TM+ RULES ─────────────────────────────────────────────────────────────────
# tm_plus_1: home venue + accommodation Mon/Fri + can cover other bars
# tm_plus_2: from OTHER departments supporting bars (not built in Phase 1)
TM_RULES = {
    "tm_plus_1": {"can_work_bars": True,  "max_venues_per_day": 2},
    "tm_plus_2": {"can_work_bars": True,  "max_venues_per_day": 3},
}
