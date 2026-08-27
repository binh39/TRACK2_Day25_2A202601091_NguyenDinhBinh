"""Efficiency metrics — the numbers that actually drive GPU cost.

Key teaching point (deck §5): nvidia-smi "GPU-Util %" is a *time-active* clock,
not an efficiency metric. A GPU can read 100% util while its MFU is ~20% — you
are paying the full GPU-hour for a fraction of the FLOPs you rented.
"""
from __future__ import annotations


def compute_mfu(achieved_tflops: float, peak_tflops: float) -> float:
    """Model FLOPs Utilization = achieved / peak (clamped to 0..1).

    Good training MFU is ~0.35-0.45; >0.50 is excellent. Returns 0 if peak<=0.
    """
    if peak_tflops <= 0:
        return 0.0
    return max(0.0, min(1.0, achieved_tflops / peak_tflops))


def compute_mbu(achieved_bw_tbs: float, peak_bw_tbs: float) -> float:
    """Model Bandwidth Utilization = achieved HBM BW / peak BW (clamped 0..1).

    The right metric for memory-bound decode; target ~0.60 on H100-80GB batch-1.
    """
    if peak_bw_tbs <= 0:
        return 0.0
    return max(0.0, min(1.0, achieved_bw_tbs / peak_bw_tbs))


def arithmetic_intensity(flops: float, bytes_moved: float) -> float:
    """FLOP / byte for a workload (the x-axis of the roofline model)."""
    if bytes_moved <= 0:
        return 0.0
    return flops / bytes_moved


def roofline_regime(intensity: float, ridge_point: float) -> str:
    """Below the ridge point a workload is memory-bound; at/above it is compute-bound.

    H100 ridge ~295 FLOP/byte (BF16). LLM decode (~1-2) is memory-bound; prefill
    (~455) is compute-bound — which is *why* prefill/decode disaggregation pays off.
    """
    return "compute-bound" if intensity >= ridge_point else "memory-bound"


def flag_util_lies(rows, util_threshold: float = 0.90, mfu_threshold: float = 0.30):
    """Return the rows where GPU-Util is high but MFU is low — money leaking.

    `rows` is an iterable of dicts each having 'gpu_util_pct' (0-100) and 'mfu' (0-1).
    These are GPUs you are billed full-rate for while they do little real compute.
    """
    out = []
    for r in rows:
        util = float(r.get("gpu_util_pct", 0)) / 100.0
        mfu = float(r.get("mfu", 0))
        if util >= util_threshold and mfu < mfu_threshold:
            out.append(r)
    return out


def idle_waste_usd(idle_hours: float, on_demand_hr: float) -> float:
    """Dollars burned by a GPU left running idle (training done, instance up)."""
    return max(0.0, idle_hours) * max(0.0, on_demand_hr)


# ---- Extension 2: Right-Sizing by MBU & VRAM Economics ----
def vram_cost_per_gb_hr(on_demand_hr: float, hbm_gb: float) -> float:
    """Cost per GB of VRAM per hour ($/GB-hr)."""
    return on_demand_hr / hbm_gb if hbm_gb > 0 else 0.0


def bw_cost_per_tbs_hr(on_demand_hr: float, peak_bw_tbs: float) -> float:
    """Cost per TB/s of memory bandwidth per hour ($/(TB/s)-hr)."""
    return on_demand_hr / peak_bw_tbs if peak_bw_tbs > 0 else 0.0


def recommend_rightsizing(
    current_gpu: str,
    achieved_bw_tbs: float,
    achieved_tflops: float,
    vram_used_gb: float,
    catalog: dict,
) -> dict:
    """Find the most cost-effective GPU that satisfies the memory, BW, and compute requirements.

    Key insight: Memory-bound decode workloads don't need expensive compute FLOPS;
    they only need sufficient HBM bandwidth and VRAM capacity.
    """
    cur_info = catalog.get(current_gpu)
    if not cur_info:
        return {"current_gpu": current_gpu, "recommended_gpu": current_gpu, "savings_pct": 0.0}

    cur_price = float(cur_info["on_demand_hr"])
    best_candidate = current_gpu
    best_price = cur_price
    rationale = "Current GPU is already right-sized."

    # Look for cheaper GPUs in catalog that meet capacity and bandwidth with safety margin (20%)
    for gtype, info in catalog.items():
        price = float(info["on_demand_hr"])
        hbm = float(info["hbm_gb"])
        bw = float(info["peak_bw_tbs"])
        fp16 = float(info["peak_tflops_fp16"])

        # Check if candidate GPU satisfies workload constraints
        if price < best_price:
            if hbm >= vram_used_gb * 1.1 and bw >= achieved_bw_tbs * 1.1 and fp16 >= achieved_tflops:
                best_candidate = gtype
                best_price = price
                rationale = (
                    f"Workload needs {vram_used_gb:.1f}GB VRAM & {achieved_bw_tbs:.2f} TB/s BW. "
                    f"{gtype} provides {hbm:.0f}GB & {bw:.2f} TB/s for ${price:.2f}/hr (vs ${cur_price:.2f}/hr)."
                )

    savings_pct = (1.0 - best_price / cur_price) * 100.0 if cur_price > 0 else 0.0
    return {
        "current_gpu": current_gpu,
        "recommended_gpu": best_candidate,
        "current_price_hr": cur_price,
        "recommended_price_hr": best_price,
        "savings_pct": round(savings_pct, 1),
        "rationale": rationale,
    }

