"""M3 — Purchasing Strategy: break-even, tier choice, spot-checkpoint sim (deck §4).

Run: python missions/m3_purchasing.py
"""
from __future__ import annotations
import os as _os, sys as _sys
_sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))
from missions._common import load_csv, num, catalog_by_type
from finops import pricing, sustainability

DAYS = 30


def run(verbose: bool = True) -> dict:
    jobs = load_csv("workloads.csv")
    cat = catalog_by_type()
    on_demand_monthly = optimized_monthly = 0.0
    recs = []

    # Extension 1 tracking: Advanced recommendations
    advanced_recs = []
    advanced_opt_monthly = 0.0

    # Extension 5 tracking: Energy of interruptible workloads
    interruptible_kwh = 0.0

    for j in jobs:
        gtype = j["gpu_type"]
        ngpu = int(num(j["num_gpus"]))
        hpd = num(j["hours_per_day"])
        days = int(num(j["days"])) if "days" in j and num(j["days"]) > 0 else DAYS
        interruptible = bool(int(num(j["interruptible"])))
        c = cat[gtype]
        gpu_hours = hpd * DAYS * ngpu
        od = num(c["on_demand_hr"])
        on_demand_cost = gpu_hours * od

        # 1. Base policy
        tier = pricing.recommend_tier(hpd, interruptible)
        if tier == "spot":
            sim = pricing.spot_checkpoint_cost(gpu_hours, num(c["spot_hr"]), od)
            opt_cost = sim["spot_cost"]
        elif tier == "reserved":
            opt_cost = gpu_hours * num(c["reserved_3yr_hr"])
        else:
            opt_cost = on_demand_cost

        on_demand_monthly += on_demand_cost
        optimized_monthly += opt_cost
        recs.append({"job_id": j["job_id"], "gpu_type": gtype, "tier": tier,
                     "on_demand": round(on_demand_cost), "optimized": round(opt_cost)})

        # 2. Extension 1: Advanced multi-factor tier policy
        adv = pricing.recommend_tier_advanced(
            hours_per_day=hpd,
            interruptible=interruptible,
            gpu_type=gtype,
            job_days=DAYS,
            on_demand_hr=od,
            spot_hr=num(c["spot_hr"]),
            r1yr_hr=num(c["reserved_1yr_hr"]),
            r3yr_hr=num(c["reserved_3yr_hr"]),
        )
        adv_cost = adv["best_cost"] * ngpu
        advanced_opt_monthly += adv_cost
        advanced_recs.append({
            "job_id": j["job_id"],
            "gpu_type": gtype,
            "best_tier": adv["recommended_tier"],
            "adv_cost": round(adv_cost),
            "savings_pct": adv["savings_pct"],
            "irate": adv["interruption_rate"],
        })

        # 3. Extension 5: Track interruptible job energy
        if interruptible:
            watts = num(c["watts"])
            job_kwh = (gpu_hours * watts) / 1000.0
            interruptible_kwh += job_kwh

    savings = on_demand_monthly - optimized_monthly
    savings_pct = savings / on_demand_monthly * 100 if on_demand_monthly else 0.0

    adv_savings = on_demand_monthly - advanced_opt_monthly
    adv_savings_pct = adv_savings / on_demand_monthly * 100 if on_demand_monthly else 0.0

    # Extension 5: Region sustainability comparison
    region_comparison = sustainability.compare_regions_for_workload(interruptible_kwh, baseline_region="us-east-1")
    best_clean = sustainability.recommend_optimal_region(interruptible_kwh, criterion="cleanest")
    best_cheap = sustainability.recommend_optimal_region(interruptible_kwh, criterion="cheapest")
    best_balanced = sustainability.recommend_optimal_region(interruptible_kwh, criterion="balanced")

    if verbose:
        print("== M3 Purchasing Strategy ==")
        print(f"break-even utilization @ 45% reserved discount = {pricing.break_even_utilization(0.45):.0%}")
        print(f"{'job':18}{'gpu':7}{'tier':11}{'on-demand':>12}{'optimized':>12}")
        for r in recs:
            print(f"{r['job_id']:18}{r['gpu_type']:7}{r['tier']:11}${r['on_demand']:>11,}${r['optimized']:>11,}")
        print(f"\nmonthly: on-demand ${on_demand_monthly:,.0f} -> optimized ${optimized_monthly:,.0f}  ({savings_pct:.1f}% saved)")

        print("\n-- [Extension 1] Multi-Factor Tier Decision Matrix --")
        print(f"{'job':18}{'gpu':7}{'adv tier':15}{'interr_rate':>12}{'monthly_cost':>14}{'savings':>10}")
        for ar in advanced_recs:
            print(f"{ar['job_id']:18}{ar['gpu_type']:7}{ar['best_tier']:15}{ar['irate']:>11.0%}${ar['adv_cost']:>13,}{ar['savings_pct']:>9.1f}%")
        print(f"Advanced policy monthly spend: ${advanced_opt_monthly:,.0f} ({adv_savings_pct:.1f}% saved vs on-demand)")

        print("\n-- [Extension 5] Carbon-Aware Multi-Region Scheduling (Interruptible Training) --")
        print(f"Total interruptible workloads energy: {interruptible_kwh:,.0f} kWh / month")
        print(f"{'Region':18}{'$/kWh':>8}{'gCO2/kWh':>10}{'Power Cost($)':>14}{'Emissions(kg)':>16}{'CO2 Saved%':>12}")
        for reg in region_comparison:
            print(f"{reg['region']:18}${reg['price_per_kwh']:>7.3f}{reg['carbon_g_per_kwh']:>10}${reg['cost_usd']:>13,.2f}{reg['emissions_kg']:>15,.1f}kg{reg['carbon_savings_pct']:>11.1f}%")
        print(f"  * Cleanest Region: {best_clean['region']} (cuts carbon by {best_clean['carbon_savings_pct']}%)")
        print(f"  * Cheapest Power : {best_cheap['region']} (cuts electricity bill by {best_cheap['cost_savings_pct']}%)")
        print(f"  * Balanced Region: {best_balanced['region']}")

    return {
        "recommendations": recs,
        "on_demand_monthly": round(on_demand_monthly),
        "optimized_monthly": round(optimized_monthly),
        "savings_pct": round(savings_pct, 1),
        "advanced_recommendations": advanced_recs,
        "advanced_optimized_monthly": round(advanced_opt_monthly),
        "advanced_savings_pct": round(adv_savings_pct, 1),
        "carbon_scheduling": {
            "interruptible_kwh": round(interruptible_kwh, 1),
            "region_comparison": region_comparison,
            "best_clean": best_clean,
            "best_cheap": best_cheap,
            "best_balanced": best_balanced,
        }
    }


if __name__ == "__main__":
    run()

