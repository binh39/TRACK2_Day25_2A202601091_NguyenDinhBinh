"""M2 — Inference Cost Levers: $/1M-token, batch x cache x cascade (deck §7).

Run: python missions/m2_inference_levers.py
"""
from __future__ import annotations
import os as _os, sys as _sys
_sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))
from missions._common import load_csv, num
from finops import pricing, sustainability

# $/1M tokens (input, output) — illustrative 2026.
MODEL_PRICES = {"small": (0.20, 0.40), "large": (3.00, 15.00)}


def run(verbose: bool = True) -> dict:
    rows = load_csv("token_usage.csv")
    base_cost = opt_cost = 0.0
    total_tokens = 0

    # Extension 3 tracking: Cache reuse stats
    # Simulated average cache prefix reuse in dataset (chat/rag templates reused ~4-8 times)
    avg_cache_reads = 5.0
    small_be = pricing.cache_break_even_reads(write_cost_per_m=0.20, base_input_price_per_m=0.20)
    large_be = pricing.cache_break_even_reads(write_cost_per_m=3.00, base_input_price_per_m=3.00)
    cache_active = pricing.cache_is_worth_it(avg_cache_reads, write_cost_per_m=0.20)

    # Extension 4 tracking: Reasoning vs Non-reasoning buckets
    reasoning_stats = {
        "count": 0, "tokens": 0, "base_cost": 0.0, "opt_cost": 0.0, "wh": 0.0,
    }
    standard_stats = {
        "count": 0, "tokens": 0, "base_cost": 0.0, "opt_cost": 0.0, "wh": 0.0,
    }

    for r in rows:
        inp, out = int(num(r["input_tokens"])), int(num(r["output_tokens"]))
        cached = int(num(r["cached_input_tokens"])) if cache_active else 0
        is_batch = bool(int(num(r["is_batch"])))
        is_reasoning = bool(int(num(r["is_reasoning"])))
        req_tokens = inp + out
        total_tokens += req_tokens

        # BASELINE: naive deployment — everything on the large model, no cache, no batch
        lin, lout = MODEL_PRICES["large"]
        r_base = pricing.request_cost(inp, out, lin, lout)
        base_cost += r_base

        # OPTIMIZED: cascade (route_tier), prompt caching, batch API
        pin, pout = MODEL_PRICES[r["route_tier"]]
        r_opt = pricing.request_cost(inp, out, pin, pout, cached_in=cached, batch=is_batch)
        opt_cost += r_opt

        # Energy tracking
        req_wh = sustainability.wh_per_query(req_tokens, is_reasoning=is_reasoning)

        if is_reasoning:
            reasoning_stats["count"] += 1
            reasoning_stats["tokens"] += req_tokens
            reasoning_stats["base_cost"] += r_base
            reasoning_stats["opt_cost"] += r_opt
            reasoning_stats["wh"] += req_wh
        else:
            standard_stats["count"] += 1
            standard_stats["tokens"] += req_tokens
            standard_stats["base_cost"] += r_base
            standard_stats["opt_cost"] += r_opt
            standard_stats["wh"] += req_wh

    base_pm = pricing.dollars_per_million(base_cost, total_tokens)
    opt_pm = pricing.dollars_per_million(opt_cost, total_tokens)
    savings_pct = (1 - opt_cost / base_cost) * 100 if base_cost else 0.0

    # Extension 4: Reasoning routing optimization simulation
    # If reasoning is strictly routed with complexity gating (capping to top 5% hardest queries)
    reasoning_pct_traffic = (reasoning_stats["count"] / len(rows) * 100) if rows else 0.0
    reasoning_pct_cost = (reasoning_stats["opt_cost"] / opt_cost * 100) if opt_cost else 0.0
    total_energy_kwh = (reasoning_stats["wh"] + standard_stats["wh"]) / 1000.0
    reasoning_pct_energy = (reasoning_stats["wh"] / (reasoning_stats["wh"] + standard_stats["wh"]) * 100) if total_energy_kwh else 0.0

    # Cap reasoning to 5% traffic simulation
    capped_reasoning_savings_usd = reasoning_stats["opt_cost"] * 0.5 * 30  # 50% reduction in reasoning
    capped_reasoning_savings_kwh = (reasoning_stats["wh"] * 0.5 * 30) / 1000.0

    if verbose:
        print("== M2 Inference Cost Levers ==")
        print(f"requests={len(rows)}  tokens={total_tokens:,}")
        print(f"baseline  : ${base_cost:,.2f}/day   ${base_pm:.3f}/1M-token")
        print(f"optimized : ${opt_cost:,.2f}/day   ${opt_pm:.3f}/1M-token")
        print(f"savings   : {savings_pct:.1f}%  (cascade + caching + batch)")
        print(f"discount stack (batch + 100% cache): {pricing.discount_stack(batch=True, cache_hit_frac=1.0):.3f} of naive")

        print("\n-- [Extension 3] Prompt Caching Economics & Break-Even --")
        print(f"  * Small tier break-even: {small_be:.2f} reads | Large tier break-even: {large_be:.2f} reads")
        print(f"  * Actual average prefix reads: {avg_cache_reads:.1f} reads -> Cache economically viable? {cache_active}")

        print("\n-- [Extension 4] Reasoning Traffic Budget & Energy Footprint --")
        print(f"  * Standard traffic : {standard_stats['count']:>4} reqs ({100-reasoning_pct_traffic:.1f}%) | Opt Cost: ${standard_stats['opt_cost']:.2f}/day | Energy: {standard_stats['wh']/1000:.2f} kWh/day")
        print(f"  * Reasoning traffic: {reasoning_stats['count']:>4} reqs ({reasoning_pct_traffic:.1f}%) | Opt Cost: ${reasoning_stats['opt_cost']:.2f}/day | Energy: {reasoning_stats['wh']/1000:.2f} kWh/day")
        print(f"  * Impact: Reasoning represents {reasoning_pct_traffic:.1f}% of requests but drives {reasoning_pct_cost:.1f}% of cost and {reasoning_pct_energy:.1f}% of energy!")
        print(f"  * Policy Proposal: Dynamic Routing (Complexity Threshold Gating) -> Potential Monthly Savings: ${capped_reasoning_savings_usd:,.2f} & {capped_reasoning_savings_kwh:,.1f} kWh")

    return {
        "baseline_daily": round(base_cost, 2),
        "optimized_daily": round(opt_cost, 2),
        "baseline_per_m": round(base_pm, 3),
        "optimized_per_m": round(opt_pm, 3),
        "savings_pct": round(savings_pct, 1),
        "total_tokens": total_tokens,
        "cache_economics": {
            "break_even_reads": round(small_be, 2),
            "avg_reads": avg_cache_reads,
            "is_worth_it": cache_active,
        },
        "reasoning_analysis": {
            "traffic_pct": round(reasoning_pct_traffic, 1),
            "cost_pct": round(reasoning_pct_cost, 1),
            "energy_pct": round(reasoning_pct_energy, 1),
            "capped_monthly_savings_usd": round(capped_reasoning_savings_usd, 2),
            "capped_monthly_savings_kwh": round(capped_reasoning_savings_kwh, 2),
        }
    }


if __name__ == "__main__":
    run()

