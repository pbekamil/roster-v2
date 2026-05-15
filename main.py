# =============================================================================
# main.py  —  Run locally: python main.py
# =============================================================================
from data.sample_data import (
    STAFF, WEEK_CONFIG, BUFFET_SCHEDULE,
    BAR_SCHEDULE, DAILY_HOURS,
)

from solver.core import solve
from reporter.console import print_summary
from reporter.excel import export_to_excel


DAYS = ["Fri", "Sat", "Sun", "Mon", "Tue", "Wed", "Thu"]

WATCH_NAMES = {"Lada Ivanova", "Alla Tkachuk", "Millie Sterling", "Olena Melnik",
               "Albina Savchenko", "Olha Petrenko", "Chimzie Okafor", "Diana Andrade"}

def _diag_week_grid(results):
    """Full week schedule for the resting TM+ workers."""
    print("\n  FULL WEEK SCHEDULE — resting TM+ workers")
    print("  " + "-"*80)
    for a in results["assignments"]:
        if a["name"] not in WATCH_NAMES:
            continue
        print(f"\n  {a['name']} ({a['allocated_hours']}h):")
        for day in range(7):
            shifts = a["days"].get(day, [])
            if not shifts:
                print(f"    {DAYS[day]}: REST")
            else:
                for sh in shifts:
                    if "type" in sh:
                        print(f"    {DAYS[day]}: HOLIDAY")
                    else:
                        print(f"    {DAYS[day]}: {sh.get('role','?'):<14} {sh.get('service',''):<10} "
                              f"at {sh.get('venue_id','?'):<14} {sh.get('label','')}")
    print()


def _diag_tue_breakdown(results):
    """Show what every Deck/YC-eligible staff member is doing on Tue breakfast."""
    DAYS = ["Fri", "Sat", "Sun", "Mon", "Tue", "Wed", "Thu"]
    print("\n  TUE (day 4) BREAKFAST ASSIGNMENTS — Deck+YC eligible staff")
    print("  " + "-"*70)
    for a in results["assignments"]:
        # only Deck/YC staff
        if not any(v in ["the_deck","yacht_club"]
                   for v in [sh.get("venue_id","") for day_shifts in a["days"].values()
                              for sh in day_shifts]):
            if "floor" not in a["skills"]:
                continue
        day_shifts = a["days"].get(4, [])  # Tue = day 4
        if not day_shifts:
            # no shifts at all on Tue
            bkf = [sh for sh in a["days"].get(3,[]) if sh.get("service")=="dinner"]  # Mon dinner
            mon_end = bkf[-1]["end_min"] if bkf else None
            print(f"  {a['name']:<26} Tue: REST  (Mon dinner end={mon_end})")
            continue
        bkf = [sh for sh in day_shifts if sh.get("service") == "breakfast"]
        if not bkf:
            other = day_shifts[0]
            print(f"  {a['name']:<26} Tue bkf: NONE  "
                  f"(doing {other.get('service','')} {other.get('role','')} "
                  f"at {other.get('venue_id','')})")
        else:
            for sh in bkf:
                print(f"  {a['name']:<26} Tue bkf: {sh['role']:<14} "
                      f"at {sh.get('venue_id',''):<12} "
                      f"{sh.get('label','')}")
    print()


def _diag_floor(results):
    """Print floor assignment counts per day for The Deck and Yacht Club."""
    cov = results.get("coverage", {})
    print("\n  FLOOR DIAGNOSTIC — breakfast/dinner per venue")
    print("  " + "-"*55)
    for vid in ["the_deck", "yacht_club"]:
        if vid not in cov:
            continue
        print(f"\n  {vid.replace('_',' ').title()}")
        for day in range(7):
            ddata = cov[vid].get(day, {})
            if not ddata.get("open"):
                continue
            for svc in ["breakfast", "dinner"]:
                rd = ddata["services"].get(svc, {}).get("floor")
                if rd is None:
                    continue
                gap = rd["target"] - rd["actual"]
                flag = " ✓" if gap == 0 else (f" !! GAP {gap}" if gap > 0 else f" ++ OVER {-gap}")
                print(f"    {DAYS[day]:<6} {svc:<10} "
                      f"actual={rd['actual']:>2}  target={rd['target']:>2}  "
                      f"eligible={rd['eligible']:>2}{flag}")
    print()


def _diag_specialized_roles(results):
    """Print setup/fridges/bays/station_chef coverage per service at Deck."""
    cov = results.get("coverage", {})
    vid = "the_deck"
    roles = ["station_chef", "bays", "setup", "fridges", "beverage", "host"]
    print(f"\n  SPECIALIZED ROLES — {vid}")
    print("  " + "-"*110)
    for day in range(7):
        ddata = cov.get(vid, {}).get(day, {})
        if not ddata.get("open"):
            continue
        for svc in ["breakfast", "dinner"]:
            svcd = ddata["services"].get(svc, {})
            if not svcd:
                continue
            parts = []
            for role in roles:
                rd = svcd.get(role)
                if rd is None:
                    continue
                flag = "✓" if rd["gap"] == 0 else f"GAP{rd['gap']}"
                parts.append(f"{role}={rd['actual']}/{rd['target']}[e={rd['eligible']}]({flag})")
            print(f"    {DAYS[day]:<6} {svc:<10}  " + "  ".join(parts))
    print()


def _diag_absent_sat_bkf(results):
    """Print what absent Sat bkf workers are doing instead."""
    absent = {"Viktor Vasquez","Diana Andrade","Gabriela Novak","Albina Savchenko",
              "Olha Petrenko","Sushant Sharma","Said Al-Rashid","Anoop Patel","Lorena Ferreira"}
    present_sat_bkf = set()
    for a in results["assignments"]:
        for sh in a["days"].get(1, []):
            if sh.get("venue_id") == "the_deck" and sh.get("service") == "breakfast":
                present_sat_bkf.add(a["name"])
    print("\n  ABSENT SAT BKF — what are they doing?")
    print("  " + "-"*80)
    for a in results["assignments"]:
        if a["name"] not in absent or a["name"] in present_sat_bkf:
            continue
        fri_shifts = a["days"].get(0, [])
        sat_shifts = a["days"].get(1, [])
        fri_str = ", ".join(f"{s.get('role')} {s.get('service')} {s.get('label','')}" for s in fri_shifts) or "REST"
        sat_str = ", ".join(f"{s.get('role')} {s.get('service')} {s.get('venue_id','')} {s.get('label','')}" for s in sat_shifts) or "REST"
        print(f"  {a['name']:<26} Fri: {fri_str}")
        print(f"  {'':<26} Sat: {sat_str}")
    print()


def _diag_sat_bkf(results):
    """Print all Sat breakfast assignments at Deck, sorted by role."""
    from collections import defaultdict
    by_role = defaultdict(list)
    for a in results["assignments"]:
        for sh in a["days"].get(1, []):  # day=1 = Sat
            if sh.get("venue_id") == "the_deck" and sh.get("service") == "breakfast":
                by_role[sh["role"]].append(a["name"])
    print("\n  SAT BREAKFAST — The Deck assignments by role")
    print("  " + "-"*60)
    for role in ["station_chef","bays","setup","fridges","floor","beverage","host","bar"]:
        names = by_role.get(role, [])
        print(f"    {role:<14} ({len(names):>2}): {', '.join(names) if names else 'NONE'}")
    print()


def _diag_worker_sat(results):
    """Print full week schedule for bays/setup/fridges workers."""
    watch = {"Viktor Vasquez", "Diana Andrade", "Albina Savchenko",
             "Olha Petrenko", "Ruben Shevchenko", "Gabriela Novak",
             "Ihor Petrov", "Iryna Boyko", "Halyna Lysenko Jr",
             "Oksana Moroz"}
    print("\n  FULL WEEK — bays/setup/fridges workers")
    print("  " + "-"*90)
    for a in results["assignments"]:
        if a["name"] not in watch:
            continue
        print(f"\n  {a['name']} ({a['allocated_hours']}h):")
        for day in range(7):
            shifts = a["days"].get(day, [])
            if not shifts:
                print(f"    {DAYS[day]}: REST")
            else:
                for sh in shifts:
                    print(f"    {DAYS[day]}: {sh.get('role','?'):<14} "
                          f"{sh.get('service',''):<10} at {sh.get('venue_id','?'):<14} "
                          f"{sh.get('label','')}")
    print()


def _diag_bar_coverage(results):
    """Print bar role coverage per day per venue."""
    from collections import defaultdict
    DAYS = ["Fri", "Sat", "Sun", "Mon", "Tue", "Wed", "Thu"]
    bar_assignments = defaultdict(lambda: defaultdict(lambda: defaultdict(list)))
    for a in results["assignments"]:
        for day, shifts in a["days"].items():
            for sh in shifts:
                vid = sh.get("venue_id", "")
                if vid in ["centre_stage","reds","studio_36","bar_rosso","iotg","hot_shots"]:
                    bar_assignments[vid][day][sh.get("role","?")].append(a["name"])
    from data.config import BAR_MIN_STAGING, BAR_ROLES
    from data.shift_calculator import bar_shifts_for_day, bar_staging_for_day
    BAR_VIDS = ["centre_stage","reds","studio_36","bar_rosso","iotg","hot_shots"]
    print("\n  BAR COVERAGE — role counts per day")
    print("  " + "-"*110)
    for vid in BAR_VIDS:
        print(f"\n  {vid.replace('_',' ').title()}")
        for day in range(7):
            if not bar_assignments[vid][day]:
                continue
            day_shifts = bar_shifts_for_day(vid, BAR_SCHEDULE.get(vid, []), day)
            staging = bar_staging_for_day(vid, day, DAILY_HOURS, day_shifts) or {}
            num_sessions = len({(s["start_min"],s["end_min"]) for s in day_shifts})
            parts = []
            for role in BAR_ROLES:
                workers = bar_assignments[vid][day].get(role, [])
                per_session = staging.get(role, BAR_MIN_STAGING.get(role, 1))
                total_target = per_session * num_sessions
                gap = total_target - len(workers)
                flag = "✓" if gap <= 0 else f"GAP{gap}"
                parts.append(f"{role}={len(workers)}/{total_target}(x{num_sessions}sess)({flag})")
            print(f"    {DAYS[day]:<6}  " + "  ".join(parts))
    print()


def _diag_bar_workers_changeover(results):
    """Show what bar TM+1 workers do on Mon (changeover day)."""
    DAYS = ["Fri","Sat","Sun","Mon","Tue","Wed","Thu"]
    bar_vids = {"centre_stage","reds","studio_36","bar_rosso","iotg"}
    print("\n  BAR WORKERS — Mon (changeover) and Tue schedules")
    print("  " + "-"*90)
    shown = 0
    for a in results["assignments"]:
        if a.get("contract_type") != "tm_plus":
            continue
        has_bar = any(sh.get("venue_id") in bar_vids
                      for day_shifts in a["days"].values()
                      for sh in day_shifts)
        if not has_bar:
            continue
        if shown >= 12:
            break
        shown += 1
        print(f"\n  {a['name']}:")
        for day in [3, 4]:  # Mon, Tue
            shifts = a["days"].get(day, [])
            if not shifts:
                print(f"    {DAYS[day]}: REST")
            else:
                for sh in shifts:
                    print(f"    {DAYS[day]}: {sh.get('role','?'):<14} "
                          f"{sh.get('service',''):<14} at {sh.get('venue_id','?'):<16} "
                          f"{sh.get('label','')}")
    print()


def main():
    print("\n  Loading data...")
    print(f"  Staff: {len(STAFF)}")

    results = solve(
        staff          = STAFF,
        week_config    = WEEK_CONFIG,
        buffet_schedule= BUFFET_SCHEDULE,
        bar_schedule   = BAR_SCHEDULE,
        daily_hours    = DAILY_HOURS,
        time_limit     = 600,
    )

    print_summary(results, WEEK_CONFIG)
    _diag_week_grid(results)
    _diag_tue_breakdown(results)
    _diag_floor(results)
    _diag_specialized_roles(results)
    _diag_sat_bkf(results)
    _diag_absent_sat_bkf(results)
    _diag_worker_sat(results)
    _diag_bar_coverage(results)
    _diag_bar_workers_changeover(results)
    export_to_excel(results, WEEK_CONFIG, BUFFET_SCHEDULE, BAR_SCHEDULE)
    print("  Done. Check outputs/roster_report.xlsx\n")


if __name__ == "__main__":
    main()
