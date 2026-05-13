# =============================================================================
# data/ocean_drive_data.py
# Real Ocean Drive team — extracted directly from the weekly Excel rota.
#
# Contract type mapping from rota:
#   "b"    → contract_type="normal"
#   tm+1   → contract_type="tm_plus", tm_type="tm_plus_1"
#   TM+2   → contract_type="tm_plus", tm_type="tm_plus_2"
#   blank  → inferred tm_plus_1 (staff run Accom shifts on changeover days)
#
# 33 staff total:
#   Normal  (b):  7  — home: ocean_drive, eligible: OD + QS
#   TM+1:        24  — eligible: OD + QS + accommodation
#   TM+2:         2  — eligible: OD + QS + accommodation
#
# Skills read from rota's rightmost columns.
# Contracted hours = last column value; blank → 35.0 h.
# Valentyna Petrov's "fridges (set up)" note → skills include setup + fridges.
# =============================================================================

import random
random.seed(99)

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


_OD = ["ocean_drive"]
_OD_QS = ["ocean_drive", "quay_side"]
_OD_QS_AC = ["ocean_drive", "quay_side", "accommodation"]


# ── NORMAL STAFF  (contract "b") ──────────────────────────────────────────────
# home: ocean_drive   eligible: OD + QS

_s("Liubov Zinchenko",     "normal", "buffets", _OD, 16.0,  11.50, random.randint(5,15),
   ["floor", "fridges"],               eligible_venues=_OD_QS)

_s("Stephen Nicholls",    "normal", "buffets", _OD, 35.0,  11.50, random.randint(5,15),
   ["floor"],                           eligible_venues=_OD_QS)

_s("Lynda Bailey",        "normal", "buffets", _OD, 20.0,  11.50, random.randint(5,15),
   ["floor", "host"],                   eligible_venues=_OD_QS)

_s("Valentyna Petrov",    "normal", "buffets", _OD, 35.0,  11.50, random.randint(5,15),
   ["floor", "fridges", "setup"],       eligible_venues=_OD_QS)

_s("Marko Melnychenko",        "normal", "buffets", _OD, 35.0,  11.50, random.randint(5,15),
   ["floor", "bays", "fridges"],        eligible_venues=_OD_QS)

_s("Natalia Havryluk",     "normal", "buffets", _OD, 35.0,  11.50, random.randint(5,15),
   ["floor", "bays", "fridges"],        eligible_venues=_OD_QS)

_s("Valentyna Radchenko", "normal", "buffets", _OD, 35.0,  11.50, random.randint(5,15),
   ["floor", "bays", "fridges"],        eligible_venues=_OD_QS)


# ── TM+1 STAFF ────────────────────────────────────────────────────────────────
# home: ocean_drive   eligible: OD + QS + accommodation

_s("Zoia Fedorenko",       "tm_plus", "buffets", _OD, 35.0, 12.50, random.randint(5,15),
   ["floor", "accommodation"],          eligible_venues=_OD_QS_AC, tm_type="tm_plus_1")

_s("Oksana Savitska",          "tm_plus", "buffets", _OD, 35.0, 12.50, random.randint(5,15),
   ["floor", "accommodation"],          eligible_venues=_OD_QS_AC, tm_type="tm_plus_1")

_s("Vira Bieliaieva","tm_plus", "buffets", _OD, 20.0, 12.50, random.randint(5,15),
   ["floor", "accommodation"],          eligible_venues=_OD_QS_AC, tm_type="tm_plus_1")

_s("Nataliia Havrylenko",     "tm_plus", "buffets", _OD, 35.0, 12.50, random.randint(5,15),
   ["floor", "accommodation"],          eligible_venues=_OD_QS_AC, tm_type="tm_plus_1")

_s("Jennifer Adeyemi",  "tm_plus", "buffets", _OD, 35.0, 12.50, random.randint(5,15),
   ["floor", "host", "beverage", "accommodation"],
                                        eligible_venues=_OD_QS_AC, tm_type="tm_plus_1")

_s("Halyna Morozenko",     "tm_plus", "buffets", _OD, 35.0, 12.50, random.randint(5,15),
   ["floor", "accommodation"],          eligible_venues=_OD_QS_AC, tm_type="tm_plus_1")

_s("Svitlana Serhienko", "tm_plus", "buffets", _OD, 35.0, 12.50, random.randint(5,15),
   ["floor", "fridges", "beverage", "accommodation"],
                                        eligible_venues=_OD_QS_AC, tm_type="tm_plus_1")

_s("Oksana Yakovenko",    "tm_plus", "buffets", _OD, 35.0, 12.50, random.randint(5,15),
   ["floor", "beverage", "accommodation"],
                                        eligible_venues=_OD_QS_AC, tm_type="tm_plus_1")

_s("Anna Stefanenko",    "tm_plus", "buffets", _OD, 35.0, 12.50, random.randint(5,15),
   ["floor", "accommodation"],          eligible_venues=_OD_QS_AC, tm_type="tm_plus_1")

_s("Svitlana Yartseva",    "tm_plus", "buffets", _OD, 35.0, 12.50, random.randint(5,15),
   ["floor", "fridges", "accommodation"],
                                        eligible_venues=_OD_QS_AC, tm_type="tm_plus_1")

_s("Halyna Klymenko",       "tm_plus", "buffets", _OD, 35.0, 12.50, random.randint(5,15),
   ["floor", "fridges", "beverage", "accommodation"],
                                        eligible_venues=_OD_QS_AC, tm_type="tm_plus_1")

_s("Matida Jallow",       "tm_plus", "buffets", _OD, 35.0, 12.50, random.randint(5,15),
   ["floor", "accommodation"],          eligible_venues=_OD_QS_AC, tm_type="tm_plus_1")

_s("Vitalii Vasylenko",     "tm_plus", "buffets", _OD, 35.0, 12.50, random.randint(5,15),
   ["floor", "accommodation"],          eligible_venues=_OD_QS_AC, tm_type="tm_plus_1")

_s("Ashot Hakobyan",       "tm_plus", "buffets", _OD, 35.0, 12.50, random.randint(5,15),
   ["floor", "accommodation"],          eligible_venues=_OD_QS_AC, tm_type="tm_plus_1")

_s("Tamila Kovalova",    "tm_plus", "buffets", _OD, 35.0, 12.50, random.randint(5,15),
   ["floor", "beverage", "accommodation"],
                                        eligible_venues=_OD_QS_AC, tm_type="tm_plus_1")

# Contract blank in rota — inferred tm_plus_1 (both run Accom on changeover days)
_s("Stepan Halenko",      "tm_plus", "buffets", _OD, 35.0, 12.50, random.randint(5,15),
   ["floor", "bays", "fridges", "accommodation"],
                                        eligible_venues=_OD_QS_AC, tm_type="tm_plus_1")

_s("Volodymr Marchuk", "tm_plus", "buffets", _OD, 35.0, 12.50, random.randint(5,15),
   ["floor", "bays", "fridges", "accommodation"],
                                        eligible_venues=_OD_QS_AC, tm_type="tm_plus_1")

# ── BAY / FLOOR TEAM (TM+1) ───────────────────────────────────────────────────

_s("Hanna Khudoba",     "tm_plus", "buffets", _OD, 35.0, 12.50, random.randint(5,15),
   ["floor", "bays", "fridges", "beverage", "accommodation"],
                                        eligible_venues=_OD_QS_AC, tm_type="tm_plus_1")

_s("Kateryna Mykolaienko",  "tm_plus", "buffets", _OD, 35.0, 12.50, random.randint(5,15),
   ["floor", "bays", "fridges", "beverage", "accommodation"],
                                        eligible_venues=_OD_QS_AC, tm_type="tm_plus_1")

_s("Viecheslav Burmylo", "tm_plus", "buffets", _OD, 35.0, 12.50, random.randint(5,15),
   ["floor", "bays", "fridges", "accommodation"],
                                        eligible_venues=_OD_QS_AC, tm_type="tm_plus_1")

_s("Ivanna Vynohradova",       "tm_plus", "buffets", _OD, 35.0, 12.50, random.randint(5,15),
   ["floor", "bays", "fridges", "beverage", "accommodation"],
                                        eligible_venues=_OD_QS_AC, tm_type="tm_plus_1")

_s("Janek Kowalski",   "tm_plus", "buffets", _OD, 35.0, 12.50, random.randint(5,15),
   ["floor", "bays", "accommodation"],  eligible_venues=_OD_QS_AC, tm_type="tm_plus_1")

_s("Daria Zhuravleva",      "tm_plus", "buffets", _OD, 35.0, 12.50, random.randint(5,15),
   ["floor", "bays", "fridges", "beverage", "accommodation"],
                                        eligible_venues=_OD_QS_AC, tm_type="tm_plus_1")

_s("Iryna Luchko",       "tm_plus", "buffets", _OD, 35.0, 12.50, random.randint(5,15),
   ["floor", "fridges", "beverage", "accommodation"],
                                        eligible_venues=_OD_QS_AC, tm_type="tm_plus_1")


# ── TM+2 STAFF ────────────────────────────────────────────────────────────────

_s("Samantha Reid",       "tm_plus", "buffets", _OD, 35.0, 13.50, random.randint(5,15),
   ["floor", "host", "accommodation"],  eligible_venues=_OD_QS_AC, tm_type="tm_plus_2")

_s("Ivan Petrychenko",      "tm_plus", "buffets", _OD, 35.0, 13.50, random.randint(5,15),
   ["floor", "bays", "fridges", "accommodation"],
                                        eligible_venues=_OD_QS_AC, tm_type="tm_plus_2")


# ── POST-LOAD SKILL EXPANSIONS ─────────────────────────────────────────────────
# Hosts can also cover floor.
for s in STAFF:
    if "host" in s["skills"] and "floor" not in s["skills"]:
        s["skills"].append("floor")
# Bays team also does setup (they arrive early and prep the service).
for s in STAFF:
    if "bays" in s["skills"] and "setup" not in s["skills"]:
        s["skills"].append("setup")
