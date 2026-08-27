"""Sustainability economics — energy and carbon as governed cost levers (deck §11).

Region selection cuts $ and carbon together; reasoning queries are an energy bomb.
"""
from __future__ import annotations

# Grid carbon intensity (gCO2 / kWh) — illustrative 2026 snapshot.
REGION_CARBON = {
    "us-east-1": 380,
    "us-west-2": 120,   # Oregon hydro
    "europe-north1": 30,  # Norway
    "europe-central2": 660,  # Poland (dirtiest)
    "us-east-wa": 90,
}
# Electricity price (USD / kWh) — illustrative.
REGION_PRICE_KWH = {
    "us-east-1": 0.12,
    "us-west-2": 0.07,
    "europe-north1": 0.09,
    "europe-central2": 0.18,
    "us-east-wa": 0.055,
}

REASONING_ENERGY_MULTIPLIER = 80.0  # deck: reasoning ~74-86x a small-model query


def wh_per_query(total_tokens: int, wh_per_1k_tokens: float = 0.30, is_reasoning: bool = False) -> float:
    """Energy for one query. Median Gemini prompt ~0.24 Wh; reasoning ~74-86x."""
    base = (total_tokens / 1000.0) * wh_per_1k_tokens
    return base * (REASONING_ENERGY_MULTIPLIER if is_reasoning else 1.0)


def carbon_g(wh: float, region: str = "us-east-1") -> float:
    """Grams CO2 for an energy amount in a region."""
    gco2_kwh = REGION_CARBON.get(region, 400)
    return (wh / 1000.0) * gco2_kwh


def energy_cost_usd(wh: float, region: str = "us-east-1") -> float:
    """Electricity cost of an energy amount in a region."""
    return (wh / 1000.0) * REGION_PRICE_KWH.get(region, 0.12)


def tokens_per_watt(total_tokens: int, wh: float, seconds: float = 1.0) -> float:
    """Energy efficiency of serving: tokens per watt (higher is better)."""
    watts = (wh * 3600.0) / seconds if seconds > 0 else 0.0
    return total_tokens / watts if watts > 0 else 0.0


# ---- Extension 5: Carbon-Aware Multi-Region Scheduling ----
def compare_regions_for_workload(kwh: float, baseline_region: str = "us-east-1") -> list[dict]:
    """Compare all available cloud regions for electricity cost and carbon emissions.

    kwh: Total energy consumed by workload in kilowatt-hours (kWh).
    """
    base_price = REGION_PRICE_KWH.get(baseline_region, 0.12)
    base_carbon = REGION_CARBON.get(baseline_region, 380)
    base_cost = kwh * base_price
    base_emissions_kg = (kwh * base_carbon) / 1000.0

    results = []
    for region, gco2_kwh in REGION_CARBON.items():
        price_kwh = REGION_PRICE_KWH[region]
        cost_usd = kwh * price_kwh
        emissions_kg = (kwh * gco2_kwh) / 1000.0
        
        cost_savings_pct = (1.0 - cost_usd / base_cost) * 100.0 if base_cost > 0 else 0.0
        carbon_savings_pct = (1.0 - emissions_kg / base_emissions_kg) * 100.0 if base_emissions_kg > 0 else 0.0

        results.append({
            "region": region,
            "price_per_kwh": price_kwh,
            "carbon_g_per_kwh": gco2_kwh,
            "cost_usd": round(cost_usd, 2),
            "emissions_kg": round(emissions_kg, 2),
            "cost_savings_pct": round(cost_savings_pct, 1),
            "carbon_savings_pct": round(carbon_savings_pct, 1),
        })
    return results


def recommend_optimal_region(kwh: float, criterion: str = "balanced") -> dict:
    """Recommend best region according to 'cleanest', 'cheapest', or 'balanced' priority."""
    regions = compare_regions_for_workload(kwh)
    if criterion == "cleanest":
        best = min(regions, key=lambda x: x["emissions_kg"])
    elif criterion == "cheapest":
        best = min(regions, key=lambda x: x["cost_usd"])
    else:  # balanced Pareto rank
        # Normalized score: lower is better (50% cost + 50% carbon)
        max_cost = max(r["cost_usd"] for r in regions) or 1.0
        max_em = max(r["emissions_kg"] for r in regions) or 1.0
        best = min(regions, key=lambda x: (0.5 * x["cost_usd"] / max_cost + 0.5 * x["emissions_kg"] / max_em))
    return best

