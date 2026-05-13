# =============================================================================
# data/deck_data.py
# Real Deck team — extracted from weekly rota.
#
# Contract type mapping:
#   Normal  → contract_type="normal"
#   TM+1    → contract_type="tm_plus", tm_type="tm_plus_1"
#   tm+2    → contract_type="tm_plus", tm_type="tm_plus_2"
#
# 41 staff total:
#   Normal : 15  — home: the_deck, eligible: Deck + YC
#   TM+1   : 21  — eligible: Deck + YC + accommodation
#   TM+2   :  5  — eligible: Deck + YC + accommodation
#
# Skills read from rota columns:
#   floor, bays, bay setup (→ setup), fridges, host, beverage, bar, station_chef
#   "bar" = bar station within The Deck buffet (1 per service, Deck only; excluded from YC)
#
# Contracted hours: 35h unless stated in rota's last column.
# =============================================================================

import random
random.seed(55)

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


_DECK      = ["the_deck"]
_DECK_YC   = ["the_deck", "yacht_club"]
_DECK_YC_AC = ["the_deck", "yacht_club", "accommodation"]


# ── NORMAL STAFF ──────────────────────────────────────────────────────────────
# home: the_deck   eligible: Deck + YC

_s("Kayla Fletcher",     "normal", "buffets", _DECK, 35.0, 11.50, random.randint(5,15),
   ["floor", "host", "beverage", "bar"],        eligible_venues=_DECK_YC)

_s("Liam Hartley",       "normal", "buffets", _DECK, 16.0, 11.50, random.randint(5,15),
   ["floor"],                                   eligible_venues=_DECK_YC)

_s("Ralph Kovacs",   "normal", "buffets", _DECK, 35.0, 11.50, random.randint(5,15),
   ["floor", "beverage"],                       eligible_venues=_DECK_YC)

_s("Joedie",           "normal", "buffets", _DECK, 35.0, 11.50, random.randint(5,15),
   ["floor", "beverage"],                       eligible_venues=_DECK_YC)

_s("Paul Pearson",     "normal", "buffets", _DECK, 35.0, 11.50, random.randint(5,15),
   ["floor", "host", "beverage"],               eligible_venues=_DECK_YC)

_s("Simon Walsh",        "normal", "buffets", _DECK, 16.0, 11.50, random.randint(5,15),
   ["floor"],                                   eligible_venues=_DECK_YC)

_s("Dominic Thornton", "normal", "buffets", _DECK, 16.0, 11.50, random.randint(5,15),
   ["floor"],                                   eligible_venues=_DECK_YC)

# ── NORMAL — BAYS / BAY SETUP TEAM ───────────────────────────────────────────

_s("Viktor Vasquez",    "normal", "buffets", _DECK, 35.0, 11.50, random.randint(5,15),
   ["floor", "bays", "setup", "fridges"],       eligible_venues=_DECK_YC)

_s("Diana Andrade", "normal", "buffets", _DECK, 35.0, 11.50, random.randint(5,15),
   ["floor", "bays", "setup", "fridges"],       eligible_venues=_DECK_YC)

_s("Gabriela Novak", "normal", "buffets", _DECK, 35.0, 11.50, random.randint(5,15),
   ["floor", "bays", "setup", "fridges"],       eligible_venues=_DECK_YC)

_s("Ihor Petrov",      "normal", "buffets", _DECK, 35.0, 11.50, random.randint(5,15),
   ["floor", "bays", "setup"],                  eligible_venues=_DECK_YC)

# ── NORMAL — STATION CHEF / BAYS ─────────────────────────────────────────────

_s("Sushant Sharma","normal", "buffets", _DECK, 35.0, 11.50, random.randint(5,15),
   ["bays", "station_chef"],                    eligible_venues=_DECK_YC)

_s("Said Al-Rashid", "normal", "buffets", _DECK, 35.0, 11.50, random.randint(5,15),
   ["bays", "station_chef"],                    eligible_venues=_DECK_YC)

_s("Anoop Patel",   "normal", "buffets", _DECK, 35.0, 11.50, random.randint(5,15),
   ["bays", "station_chef"],                    eligible_venues=_DECK_YC)

_s("Lorena Ferreira",   "normal", "buffets", _DECK, 35.0, 11.50, random.randint(5,15),
   ["bays", "station_chef"],                    eligible_venues=_DECK_YC)


# ── TM+1 STAFF ────────────────────────────────────────────────────────────────
# home: the_deck   eligible: Deck + YC + accommodation

_s("Lada Ivanova",   "tm_plus", "buffets", _DECK, 35.0, 12.50, random.randint(5,15),
   ["floor", "beverage", "accommodation"],
                                               eligible_venues=_DECK_YC_AC, tm_type="tm_plus_1")

_s("Mikhailo Bondarenko",    "tm_plus", "buffets", _DECK, 35.0, 12.50, random.randint(5,15),
   ["floor", "beverage", "bar", "accommodation"],
                                               eligible_venues=_DECK_YC_AC, tm_type="tm_plus_1")

_s("Ildiko Fekete",       "tm_plus", "buffets", _DECK, 35.0, 12.50, random.randint(5,15),
   ["floor", "accommodation"],                 eligible_venues=_DECK_YC_AC, tm_type="tm_plus_1")

_s("Csaba Molnar",          "tm_plus", "buffets", _DECK, 35.0, 12.50, random.randint(5,15),
   ["floor", "accommodation"],                 eligible_venues=_DECK_YC_AC, tm_type="tm_plus_1")

_s("Alona Sokolova",    "tm_plus", "buffets", _DECK, 35.0, 12.50, random.randint(5,15),
   ["floor", "beverage", "accommodation"],
                                               eligible_venues=_DECK_YC_AC, tm_type="tm_plus_1")

_s("Alla Kovalenko",       "tm_plus", "buffets", _DECK, 35.0, 12.50, random.randint(5,15),
   ["floor", "accommodation"],                 eligible_venues=_DECK_YC_AC, tm_type="tm_plus_1")

_s("Piedad Ferreira",      "tm_plus", "buffets", _DECK, 35.0, 12.50, random.randint(5,15),
   ["floor", "accommodation"],                 eligible_venues=_DECK_YC_AC, tm_type="tm_plus_1")

_s("Joe Sullivan",         "tm_plus", "buffets", _DECK, 35.0, 12.50, random.randint(5,15),
   ["floor", "host", "beverage", "accommodation"],
                                               eligible_venues=_DECK_YC_AC, tm_type="tm_plus_1")

_s("Ruslana Kovalchuk",     "tm_plus", "buffets", _DECK, 35.0, 12.50, random.randint(5,15),
   ["floor", "beverage", "accommodation"],
                                               eligible_venues=_DECK_YC_AC, tm_type="tm_plus_1")

_s("Hanna Marchenko",     "tm_plus", "buffets", _DECK, 35.0, 12.50, random.randint(5,15),
   ["floor", "accommodation"],                 eligible_venues=_DECK_YC_AC, tm_type="tm_plus_1")

_s("Halyna Lysenko",  "tm_plus", "buffets", _DECK, 35.0, 12.50, random.randint(5,15),
   ["floor", "accommodation"],                 eligible_venues=_DECK_YC_AC, tm_type="tm_plus_1")

_s("Natalia Moreau",   "tm_plus", "buffets", _DECK, 35.0, 12.50, random.randint(5,15),
   ["floor", "accommodation"],                 eligible_venues=_DECK_YC_AC, tm_type="tm_plus_1")

_s("Alla Tkachuk",        "tm_plus", "buffets", _DECK, 35.0, 12.50, random.randint(5,15),
   ["floor", "accommodation"],                 eligible_venues=_DECK_YC_AC, tm_type="tm_plus_1")

_s("Millie Sterling",       "tm_plus", "buffets", _DECK, 35.0, 12.50, random.randint(5,15),
   ["floor", "host", "beverage", "accommodation"],
                                               eligible_venues=_DECK_YC_AC, tm_type="tm_plus_1")

_s("Olena Melnik",       "tm_plus", "buffets", _DECK, 35.0, 12.50, random.randint(5,15),
   ["floor", "accommodation"],                 eligible_venues=_DECK_YC_AC, tm_type="tm_plus_1")

# ── TM+1 — BAYS / BAY SETUP TEAM ─────────────────────────────────────────────

_s("Albina Savchenko",   "tm_plus", "buffets", _DECK, 35.0, 12.50, random.randint(5,15),
   ["floor", "bays", "setup", "fridges", "accommodation"],
                                               eligible_venues=_DECK_YC_AC, tm_type="tm_plus_1")

_s("Olha Petrenko",       "tm_plus", "buffets", _DECK, 35.0, 12.50, random.randint(5,15),
   ["floor", "bays", "setup", "fridges", "accommodation"],
                                               eligible_venues=_DECK_YC_AC, tm_type="tm_plus_1")

_s("Iryna Boyko",      "tm_plus", "buffets", _DECK, 35.0, 12.50, random.randint(5,15),
   ["floor", "bays", "setup", "fridges", "accommodation"],
                                               eligible_venues=_DECK_YC_AC, tm_type="tm_plus_1")

_s("Halyna Lysenko Jr","tm_plus", "buffets", _DECK, 35.0, 12.50, random.randint(5,15),
   ["floor", "bays", "setup", "accommodation"],
                                               eligible_venues=_DECK_YC_AC, tm_type="tm_plus_1")

_s("Ruben Shevchenko",     "tm_plus", "buffets", _DECK, 35.0, 12.50, random.randint(5,15),
   ["floor", "bays", "setup", "fridges", "accommodation"],
                                               eligible_venues=_DECK_YC_AC, tm_type="tm_plus_1")

_s("Oksana Moroz",     "tm_plus", "buffets", _DECK, 35.0, 12.50, random.randint(5,15),
   ["floor", "bays", "setup", "fridges", "accommodation"],
                                               eligible_venues=_DECK_YC_AC, tm_type="tm_plus_1")


# ── TM+2 STAFF ────────────────────────────────────────────────────────────────
# home: the_deck   eligible: Deck + YC + accommodation

_s("Oleksandr Bilenky",  "tm_plus", "buffets", _DECK, 35.0, 13.50, random.randint(5,15),
   ["floor", "bar", "accommodation"],          eligible_venues=_DECK_YC_AC, tm_type="tm_plus_2")

_s("Chimzie Okafor",       "tm_plus", "buffets", _DECK, 35.0, 13.50, random.randint(5,15),
   ["floor", "accommodation"],                 eligible_venues=_DECK_YC_AC, tm_type="tm_plus_2")

_s("Natalia Boiko",     "tm_plus", "buffets", _DECK, 35.0, 13.50, random.randint(5,15),
   ["floor", "accommodation"],                 eligible_venues=_DECK_YC_AC, tm_type="tm_plus_2")

_s("Volodymr Karpenko",   "tm_plus", "buffets", _DECK, 35.0, 13.50, random.randint(5,15),
   ["floor", "accommodation"],                 eligible_venues=_DECK_YC_AC, tm_type="tm_plus_2")

_s("Princewill Okonkwo",   "tm_plus", "buffets", _DECK, 35.0, 13.50, random.randint(5,15),
   ["bays", "station_chef", "accommodation"],  eligible_venues=_DECK_YC_AC, tm_type="tm_plus_2")


# ── POST-LOAD SKILL EXPANSIONS ────────────────────────────────────────────────
for s in STAFF:
    if "host" in s["skills"] and "floor" not in s["skills"]:
        s["skills"].append("floor")
for s in STAFF:
    if "bays" in s["skills"] and "setup" not in s["skills"]:
        s["skills"].append("setup")
