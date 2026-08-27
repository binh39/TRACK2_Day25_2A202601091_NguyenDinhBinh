"""M1 — Efficiency Audit: MFU/MBU, the GPU-Util lie, and idle waste (deck §5).

Run: python missions/m1_efficiency_audit.py
"""
from __future__ import annotations
import os as _os, sys as _sys
_sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))
from collections import defaultdict
from missions._common import load_csv, num, catalog_by_type
from finops import metrics


def run(verbose: bool = True) -> dict:
    tel = load_csv("gpu_telemetry.csv")
    cat = catalog_by_type()

    # per-row MFU/MBU, then aggregate per GPU
    agg = defaultdict(lambda: {"util": [], "mfu": [], "mbu": [], "type": None, "idle_hours": 0})
    for r in tel:
        gtype = r["gpu_type"]
        peak_fp16 = num(cat[gtype]["peak_tflops_fp16"])
        peak_bw = num(cat[gtype]["peak_bw_tbs"])
        mfu = metrics.compute_mfu(num(r["achieved_tflops"]), peak_fp16)
        mbu = metrics.compute_mbu(num(r["achieved_bw_tbs"]), peak_bw)
        a = agg[r["gpu_id"]]
        a["type"] = gtype
        a["util"].append(num(r["gpu_util_pct"]))
        a["mfu"].append(mfu)
        a["mbu"].append(mbu)
        if num(r["gpu_util_pct"]) < 10:  # effectively idle this interval (1h)
            a["idle_hours"] += 1

    summary = []
    for gid, a in agg.items():
        summary.append({
            "gpu_id": gid, "gpu_type": a["type"],
            "gpu_util_pct": round(sum(a["util"]) / len(a["util"]), 1),
            "mfu": round(sum(a["mfu"]) / len(a["mfu"]), 3),
            "mbu": round(sum(a["mbu"]) / len(a["mbu"]), 3),
            "idle_hours": a["idle_hours"],
        })

    lies = metrics.flag_util_lies(summary)
    idle_waste = 0.0
    for s in summary:
        on_demand = num(catalog_by_type()[s["gpu_type"]]["on_demand_hr"])
        idle_waste += metrics.idle_waste_usd(s["idle_hours"], on_demand)

    # ---- Extension 2: Right-sizing analysis based on MBU & VRAM Economics ----
    catalog_metrics = []
    for gtype, row in cat.items():
        od = num(row["on_demand_hr"])
        hbm = num(row["hbm_gb"])
        bw = num(row["peak_bw_tbs"])
        catalog_metrics.append({
            "gpu_type": gtype,
            "on_demand_hr": od,
            "hbm_gb": hbm,
            "peak_bw_tbs": bw,
            "cost_per_gb_hr": round(metrics.vram_cost_per_gb_hr(od, hbm), 4),
            "cost_per_tbs_hr": round(metrics.bw_cost_per_tbs_hr(od, bw), 3),
        })

    # For each GPU in telemetry, calculate achieved requirements and right-sizing opportunity
    gpu_stats = defaultdict(lambda: {"tflops": [], "bw": [], "vram": []})
    for r in tel:
        gpu_stats[r["gpu_id"]]["tflops"].append(num(r["achieved_tflops"]))
        gpu_stats[r["gpu_id"]]["bw"].append(num(r["achieved_bw_tbs"]))
        gpu_stats[r["gpu_id"]]["vram"].append(num(r["mem_used_gb"]))

    rightsizing_recs = []
    monthly_rightsize_savings = 0.0
    for s in summary:
        gid = s["gpu_id"]
        gtype = s["gpu_type"]
        avg_tflops = sum(gpu_stats[gid]["tflops"]) / len(gpu_stats[gid]["tflops"])
        avg_bw = sum(gpu_stats[gid]["bw"]) / len(gpu_stats[gid]["bw"])
        max_vram = max(gpu_stats[gid]["vram"])
        
        rs = metrics.recommend_rightsizing(
            current_gpu=gtype,
            achieved_bw_tbs=avg_bw,
            achieved_tflops=avg_tflops,
            vram_used_gb=max_vram,
            catalog=cat,
        )
        if rs["recommended_gpu"] != gtype:
            hr_saved = rs["current_price_hr"] - rs["recommended_price_hr"]
            m_saved = hr_saved * (24 - s["idle_hours"]) * 30
            monthly_rightsize_savings += m_saved
            rightsizing_recs.append({
                "gpu_id": gid,
                "current_type": gtype,
                "recommended_type": rs["recommended_gpu"],
                "max_vram_gb": round(max_vram, 1),
                "avg_bw_tbs": round(avg_bw, 3),
                "cur_price_hr": rs["current_price_hr"],
                "rec_price_hr": rs["recommended_price_hr"],
                "monthly_savings_usd": round(m_saved, 2),
                "savings_pct": rs["savings_pct"],
                "rationale": rs["rationale"],
            })

    if verbose:
        print("== M1 Efficiency Audit ==")
        print(f"{'GPU':14}{'type':7}{'util%':>7}{'MFU':>7}{'MBU':>7}{'idle_h':>8}")
        for s in sorted(summary, key=lambda x: x["mfu"]):
            print(f"{s['gpu_id']:14}{s['gpu_type']:7}{s['gpu_util_pct']:>7}{s['mfu']:>7}{s['mbu']:>7}{s['idle_hours']:>8}")
        print(f"\nGPU-Util LIES (util>=90% but MFU<30%): {[l['gpu_id'] for l in lies]}")
        print(f"Idle waste (1 day): ${idle_waste:,.2f}  ->  ${idle_waste*30:,.0f}/month")

        print("\n-- [Extension 2] GPU Catalog Memory & Bandwidth Unit Economics --")
        print(f"{'GPU':10}{'$/hr':>8}{'VRAM(GB)':>10}{'BW(TB/s)':>10}{'$/GB-hr':>12}{'$/(TB/s)-hr':>14}")
        for cm in sorted(catalog_metrics, key=lambda x: x["cost_per_gb_hr"]):
            print(f"{cm['gpu_type']:10}${cm['on_demand_hr']:>7.2f}{cm['hbm_gb']:>10.0f}{cm['peak_bw_tbs']:>10.2f}${cm['cost_per_gb_hr']:>11.4f}${cm['cost_per_tbs_hr']:>13.2f}")

        if rightsizing_recs:
            print("\n-- [Extension 2] Workload Right-Sizing Recommendations (MBU & VRAM) --")
            for rr in rightsizing_recs:
                print(f"  * {rr['gpu_id']} ({rr['current_type']}) -> {rr['recommended_type']}: "
                      f"VRAM={rr['max_vram_gb']}GB, BW={rr['avg_bw_tbs']} TB/s, "
                      f"${rr['cur_price_hr']:.2f}/hr -> ${rr['rec_price_hr']:.2f}/hr "
                      f"({rr['savings_pct']}% off, save ${rr['monthly_savings_usd']:,.0f}/mo)")
            print(f"  Total potential monthly right-sizing savings: ${monthly_rightsize_savings:,.2f}")

    return {
        "summary": summary,
        "lies": lies,
        "idle_waste_daily": round(idle_waste, 2),
        "catalog_metrics": catalog_metrics,
        "rightsizing_recs": rightsizing_recs,
        "monthly_rightsize_savings": round(monthly_rightsize_savings, 2),
    }


if __name__ == "__main__":
    run()

