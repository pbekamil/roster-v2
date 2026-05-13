# reporter/console.py
from data.config import DAYS, CHANGEOVER_DAYS, ACCOM_FORMULA
from data.shift_calculator import active_buffets_by_day, accom_target_for_day
from datetime import datetime


def print_summary(results, week_config):
    s  = results["summary"]
    wc = week_config

    print("\n" + "="*65)
    print(f"  RESORT ROSTER — WEEK {wc['week_number']}")
    print("="*65)
    status = results.get('status', '?')
    status_note = ("  ← coverage may be suboptimal"
                   if status == "FEASIBLE" else "")
    print(f"  {wc['week_start']}   |   {status}{status_note}   |   "
          f"{results['solve_time']:.2f}s")
    print()

    fb = wc["fri_batch"]; mb = wc["mon_batch"]
    print(f"  Fri batch  Premium:{fb['premium_guests']:>5}  "
          f"FoodCourt:{fb['food_court_guests']:>5}  "
          f"Total:{fb['total_guests']:>5}")
    print(f"  Mon batch  Premium:{mb['premium_guests']:>5}  "
          f"FoodCourt:{mb['food_court_guests']:>5}  "
          f"Total:{mb['total_guests']:>5}")
    print()

    # Buffet schedule — per service
    active = active_buffets_by_day(wc)
    print("  BUFFET SCHEDULE  (B=breakfast  D=dinner)")
    print("  " + "-"*60)
    for day in range(7):
        b_venues = active[day].get("breakfast",[])
        d_venues = active[day].get("dinner",[])
        b_str = ", ".join(v.replace("_"," ").title() for v in b_venues) or "—"
        d_str = ", ".join(v.replace("_"," ").title() for v in d_venues) or "—"
        tag = " ★" if day in CHANGEOVER_DAYS else ""
        print(f"  {DAYS[day]:<6}{tag}  B: {b_str}")
        print(f"         D: {d_str}")
    print()

    # Accommodation
    print("  ACCOMMODATION TARGETS")
    print("  " + "-"*60)
    for day in range(7):
        t = accom_target_for_day(wc, day)
        if day in CHANGEOVER_DAYS:
            batch  = fb if day==0 else mb
            ov     = wc.get("accom_override",{})
            key    = "fri_arrivals" if day==0 else "mon_arrivals"
            ov_val = ov.get(key) if ov else None
            if ov_val:
                tag = (f" ← CHANGEOVER  override {ov_val} rooms "
                       f"÷ {ACCOM_FORMULA['rooms_per_staff']} = {t}")
            else:
                g = batch["total_guests"]
                r = g // ACCOM_FORMULA["avg_family_size"]
                tag = (f" ← CHANGEOVER  {g} guests "
                       f"÷ {ACCOM_FORMULA['avg_family_size']} = {r} rooms "
                       f"÷ {ACCOM_FORMULA['rooms_per_staff']} = {t}")
        else:
            tag = ""
        print(f"  {DAYS[day]:<6}  {t:>4} staff{tag}")
    print()

    # Coverage
    print("  VENUE COVERAGE")
    print("  " + "-"*60)
    cov = results.get("coverage",{})
    staffing_alerts = []   # (venue, day, service, role, target, eligible)
    for vid, days in cov.items():
        total_slots = 0; gap_slots = 0
        for day, ddata in days.items():
            for svc, svc_data in ddata.get("services",{}).items():
                for role, rdata in svc_data.items():
                    if not isinstance(rdata, dict) or "target" not in rdata:
                        continue
                    total_slots += rdata["target"]
                    gap_slots   += abs(rdata.get("gap", 0))
                    shortage = rdata.get("shortage", 0)
                    if shortage > 0:
                        staffing_alerts.append(
                            (vid, day, svc, role,
                             rdata["target"], rdata.get("eligible", 0)))
        pct = round(100*(total_slots-gap_slots)/total_slots) \
              if total_slots > 0 else 0
        if total_slots == 0:
            tag = "  no data"
        elif gap_slots == 0:
            tag = "  100% covered"
        else:
            tag = f"  ⚠ {gap_slots} role-slots gap ({pct}% covered)"
        print(f"  {vid.replace('_',' ').title():<24}{tag}")
    print()

    # Manager alert — slots where eligible staff < target (genuine shortage)
    if staffing_alerts:
        print("  !! MANAGER ACTION REQUIRED — GENUINE STAFFING SHORTAGES !!")
        print("  These slots cannot be filled regardless of scheduling.")
        print("  Hire additional staff or cross-train existing team.")
        print("  " + "-"*60)
        for vid, day, svc, role, tgt, el in staffing_alerts:
            day_name = DAYS[day]
            venue    = vid.replace("_"," ").title()
            print(f"  {venue:<20} {day_name:<4} {svc:<12} {role:<14} "
                  f"need {tgt}, only {el} trained")
        print()
    else:
        print("  All gaps are scheduling gaps — no genuine staffing shortages.")
        print()


    # Hours summary — now showing shift + holiday breakdown
    print("  HOURS SUMMARY")
    print("  " + "-"*60)
    print(f"  Staff:                {s.get('total_staff',0)}")
    print(f"  Contracted total:     {s.get('total_contracted_hrs',0)}h")
    print(f"  Shift hours:          {s.get('total_shift_hrs',0)}h")
    print(f"  Holiday hours:        {s.get('total_holiday_hrs',0)}h")
    print(f"  Allocated total:      {s.get('total_allocated_hrs',0)}h  "
          f"(shift + holiday)")
    print(f"  Gap vs contract:      {s.get('total_gap_hrs',0)}h")
    print(f"  Below contract:       {s.get('below_contracted_count',0)} staff")
    print(f"  Over contract:        {s.get('over_hours_count',0)} staff")
    print(f"  Holiday days used:    {s.get('holiday_days_total',0)}")
    print()

    # Signed form risk
    below = s.get("below_contracted_staff",[])
    if below:
        print("  SIGNED-FORM RISK")
        print("  " + "-"*60)
        for p in below[:15]:
            print(f"  {p['name']:<26} "
                  f"Contract:{p['contracted']}h  "
                  f"Shifts:{p['shift_h']}h  "
                  f"Hol:{p['holiday_h']}h  "
                  f"Total:{p['allocated']}h  "
                  f"Short:{p['shortfall']}h")
        if len(below)>15:
            print(f"  ... and {len(below)-15} more")
    print()

    over = s.get("over_hours_staff",[])
    if over:
        print("  OVER CONTRACT")
        print("  " + "-"*60)
        for p in over[:10]:
            print(f"  {p['name']:<26} "
                  f"Contract:{p['contracted']}h  "
                  f"Allocated:{p['allocated']}h  "
                  f"Over:{p['over']}h")
    print()
    print("="*65+"\n")
