"""Pricing & purchasing economics — measure in $/1M-token, not $/GPU-hr.

Figures are June-2026 as-of snapshots from the deck's RESEARCH dossier; treat
live prices as fast-moving (re-baseline before each cohort).
"""
from __future__ import annotations


def request_cost(
    input_tok: int,
    output_tok: int,
    price_in_per_m: float,
    price_out_per_m: float,
    cached_in: int = 0,
    cache_discount: float = 0.10,   # Anthropic cached-read ~0.1x (=-90%)
    batch: bool = False,
    batch_discount: float = 0.50,   # Batch API ~ -50%
) -> float:
    """USD cost of a single request. Cached input billed at cache_discount x price."""
    cached_in = min(max(0, cached_in), input_tok)
    uncached_in = input_tok - cached_in
    cost = (
        (uncached_in / 1e6) * price_in_per_m
        + (cached_in / 1e6) * price_in_per_m * cache_discount
        + (output_tok / 1e6) * price_out_per_m
    )
    if batch:
        cost *= batch_discount
    return cost


def dollars_per_million(total_cost_usd: float, total_tokens: int) -> float:
    """Aggregate unit economics: $ per 1,000,000 tokens served."""
    if total_tokens <= 0:
        return 0.0
    return total_cost_usd / (total_tokens / 1e6)


def discount_stack(
    batch: bool = False,
    cache_hit_frac: float = 0.0,
    batch_discount: float = 0.50,
    cache_discount: float = 0.10,
) -> float:
    """Effective fraction of the naive bill after stacking discounts (input-heavy view).

    Discounts MULTIPLY: cache applies to the cached share of input, batch to the
    whole bill. batch + 100% cache-hit -> 0.5 * 0.1 = 0.05 (~95% off).
    """
    cache_mult = cache_hit_frac * cache_discount + (1.0 - cache_hit_frac)
    batch_mult = batch_discount if batch else 1.0
    return cache_mult * batch_mult


def break_even_utilization(discount_frac: float) -> float:
    """Utilization at which a commitment pays off ~= 1 - discount.

    A 45% reserved discount needs ~55% utilization (~13.2h/day) to beat on-demand.
    """
    return max(0.0, min(1.0, 1.0 - discount_frac))


def recommend_tier(
    hours_per_day: float,
    interruptible: bool,
    reserved_discount: float = 0.45,
    gpu_type: str | None = None,
    job_days: int | None = None,
) -> str:
    """Pick a purchasing tier from a workload's duty cycle + interruptibility.

    Policy:
      - interruptible & not 24/7  -> 'spot'      (checkpoint and ride the discount)
      - duty cycle >= break-even  -> 'reserved'  (steady, high utilization: 1yr or 3yr)
      - otherwise                 -> 'on_demand' (spiky / low duty)
    """
    duty = max(0.0, hours_per_day) / 24.0
    be = break_even_utilization(reserved_discount)
    if interruptible and hours_per_day < 24:
        return "spot"
    if duty >= be:
        return "reserved"
    return "on_demand"


# ---- Extension 1: Multi-Factor Tier Recommendation Matrix ----
GPU_INTERRUPTION_RATES = {
    "H100": 0.03,    # ~3% per hr
    "H200": 0.04,    # ~4% per hr
    "A100": 0.06,    # ~6% per hr
    "A10G": 0.12,    # ~12% per hr (higher spot reclaim contention)
    "L4": 0.05,      # ~5% per hr
    "B200": 0.03,    # ~3% per hr
    "MI300X": 0.08,  # ~8% per hr
}


def recommend_tier_advanced(
    hours_per_day: float,
    interruptible: bool,
    gpu_type: str = "H100",
    job_days: int = 30,
    on_demand_hr: float = 2.50,
    spot_hr: float = 1.50,
    r1yr_hr: float = 2.00,
    r3yr_hr: float = 1.40,
) -> dict:
    """Advanced tier recommendation incorporating GPU-specific interruption risk and commitment horizon."""
    total_hours = hours_per_day * job_days
    od_cost = total_hours * on_demand_hr
    
    # 1. Spot cost with realistic interruption simulation
    irate = GPU_INTERRUPTION_RATES.get(gpu_type, 0.05)
    spot_sim = spot_checkpoint_cost(
        job_hours=total_hours,
        spot_hr=spot_hr,
        on_demand_hr=on_demand_hr,
        interrupt_rate=irate,
        ckpt_overhead_frac=0.03,
        rework_hours_per_interrupt=0.5,
    )
    spot_cost = spot_sim["spot_cost"]

    # 2. Reserved costs (if project duration is short, multi-year commitment carries unamortized risk)
    # Effective hourly cost if commitment matches workload duration vs amortized
    r1_cost = total_hours * r1yr_hr
    r3_cost = total_hours * r3yr_hr

    duty_cycle = hours_per_day / 24.0
    r3_be = break_even_utilization((on_demand_hr - r3yr_hr) / on_demand_hr if on_demand_hr > 0 else 0.45)
    r1_be = break_even_utilization((on_demand_hr - r1yr_hr) / on_demand_hr if on_demand_hr > 0 else 0.20)

    # Decision Matrix Logic:
    # - If interruptible and not strict 24/7 baseline: Spot is best if spot_cost < reserved and od
    # - If steady 24/7 long-term (e.g. inference services): 3-yr Reserved
    # - If moderate duty cycle and medium term: 1-yr Reserved
    # - Otherwise: On-Demand
    options = {
        "on_demand": od_cost,
        "spot": spot_cost if interruptible else float("inf"),
        "reserved_1yr": r1_cost if duty_cycle >= r1_be else float("inf"),
        "reserved_3yr": r3_cost if duty_cycle >= r3_be else float("inf"),
    }
    
    best_tier = min(options, key=options.get)
    best_cost = options[best_tier]
    savings_pct = (1.0 - best_cost / od_cost) * 100.0 if od_cost > 0 else 0.0

    return {
        "recommended_tier": best_tier,
        "best_cost": round(best_cost, 2),
        "on_demand_cost": round(od_cost, 2),
        "spot_cost": round(spot_cost, 2),
        "reserved_1yr_cost": round(r1_cost, 2),
        "reserved_3yr_cost": round(r3_cost, 2),
        "savings_pct": round(savings_pct, 1),
        "interruption_rate": irate,
        "duty_cycle": round(duty_cycle, 3),
        "options": {k: round(v, 2) for k, v in options.items() if v != float("inf")},
    }


# ---- Extension 3: Economics of Prompt Caching ----
def cache_break_even_reads(
    write_cost_per_m: float,
    base_input_price_per_m: float | None = None,
    read_discount: float = 0.10,
) -> float:
    """Return the minimum number of cache reads required to break even.

    Formula:
      Naive cost: N * P_in
      Cached cost: P_write + N * (P_in * read_discount)
      Break-even: N_be = P_write / (P_in * (1 - read_discount))
      When P_write == P_in, N_be = 1 / (1 - read_discount) = 1 / 0.90 = 1.111 reads.
    """
    if base_input_price_per_m is None:
        base_input_price_per_m = write_cost_per_m
    if base_input_price_per_m <= 0 or (1.0 - read_discount) <= 0:
        return float("inf")
    return write_cost_per_m / (base_input_price_per_m * (1.0 - read_discount))


def cache_is_worth_it(
    avg_cache_reads: float,
    write_cost_per_m: float,
    read_discount: float = 0.10,
    base_input_price_per_m: float | None = None,
) -> bool:
    """Determine whether caching is financially advantageous given average reuse reads."""
    be = cache_break_even_reads(write_cost_per_m, base_input_price_per_m, read_discount)
    return avg_cache_reads > be


def spot_checkpoint_cost(
    job_hours: float,
    spot_hr: float,
    on_demand_hr: float,
    interrupt_rate: float = 0.05,      # per-hour chance (H100 spot ~<5%)
    ckpt_overhead_frac: float = 0.03,  # steady cost of writing checkpoints
    rework_hours_per_interrupt: float = 0.5,
) -> dict:
    """Effective cost of running a checkpointable job on spot vs on-demand.

    Interruptions waste the compute since the last checkpoint (rework); checkpointing
    adds a small steady overhead. Spot still wins for interruptible jobs.
    """
    expected_interrupts = job_hours * interrupt_rate
    rework_hours = expected_interrupts * rework_hours_per_interrupt
    effective_hours = job_hours * (1.0 + ckpt_overhead_frac) + rework_hours
    spot_cost = effective_hours * spot_hr
    on_demand_cost = job_hours * on_demand_hr
    savings_pct = (1.0 - spot_cost / on_demand_cost) * 100.0 if on_demand_cost > 0 else 0.0
    return {
        "spot_effective_hours": round(effective_hours, 2),
        "spot_cost": round(spot_cost, 2),
        "on_demand_cost": round(on_demand_cost, 2),
        "savings_pct": round(savings_pct, 1),
    }

