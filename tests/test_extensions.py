"""Unit tests for Lab 25 'Your Turn' Extensions (1 to 5)."""
from __future__ import annotations
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from finops import pricing, metrics, sustainability


def test_cache_is_worth_it_logic():
    """Test Extension 3: Prompt Caching Economics."""
    # Break-even when write_cost == base_input_price at 10% discount: 1 / 0.90 = 1.111
    be = pricing.cache_break_even_reads(write_cost_per_m=0.20, base_input_price_per_m=0.20, read_discount=0.10)
    assert abs(be - 1.1111) < 1e-3

    # 1 read is not worth it; 2 reads is worth it
    assert pricing.cache_is_worth_it(avg_cache_reads=1.0, write_cost_per_m=0.20, read_discount=0.10) is False
    assert pricing.cache_is_worth_it(avg_cache_reads=2.0, write_cost_per_m=0.20, read_discount=0.10) is True

    # Higher write cost requires more reads to break even
    be_high_write = pricing.cache_break_even_reads(write_cost_per_m=1.00, base_input_price_per_m=0.20, read_discount=0.10)
    assert abs(be_high_write - 5.5555) < 1e-3
    assert pricing.cache_is_worth_it(avg_cache_reads=5.0, write_cost_per_m=1.00, base_input_price_per_m=0.20, read_discount=0.10) is False
    assert pricing.cache_is_worth_it(avg_cache_reads=6.0, write_cost_per_m=1.00, base_input_price_per_m=0.20, read_discount=0.10) is True


def test_recommend_tier_advanced():
    """Test Extension 1: Multi-factor tier recommendation."""
    # Interruptible short/medium job -> spot
    res_spot = pricing.recommend_tier_advanced(
        hours_per_day=8,
        interruptible=True,
        gpu_type="H100",
        job_days=30,
        on_demand_hr=2.50,
        spot_hr=1.50,
        r1yr_hr=2.00,
        r3yr_hr=1.40,
    )
    assert res_spot["recommended_tier"] == "spot"
    assert res_spot["savings_pct"] > 0

    # 24/7 steady non-interruptible job -> reserved_3yr
    res_r3 = pricing.recommend_tier_advanced(
        hours_per_day=24,
        interruptible=False,
        gpu_type="H100",
        job_days=30,
        on_demand_hr=2.50,
        spot_hr=1.50,
        r1yr_hr=2.00,
        r3yr_hr=1.40,
    )
    assert res_r3["recommended_tier"] == "reserved_3yr"
    assert res_r3["savings_pct"] == 44.0  # (2.5 - 1.4) / 2.5 = 44%

    # Low duty non-interruptible -> on_demand
    res_od = pricing.recommend_tier_advanced(
        hours_per_day=4,
        interruptible=False,
        gpu_type="H100",
        job_days=30,
        on_demand_hr=2.50,
        spot_hr=1.50,
        r1yr_hr=2.00,
        r3yr_hr=1.40,
    )
    assert res_od["recommended_tier"] == "on_demand"
    assert res_od["savings_pct"] == 0.0


def test_rightsizing_logic():
    """Test Extension 2: VRAM & Bandwidth Right-Sizing."""
    catalog = {
        "H100": {"on_demand_hr": 2.50, "hbm_gb": 80, "peak_bw_tbs": 3.35, "peak_tflops_fp16": 990},
        "A100": {"on_demand_hr": 1.79, "hbm_gb": 80, "peak_bw_tbs": 2.00, "peak_tflops_fp16": 312},
        "A10G": {"on_demand_hr": 1.00, "hbm_gb": 24, "peak_bw_tbs": 0.60, "peak_tflops_fp16": 125},
        "L4":   {"on_demand_hr": 0.80, "hbm_gb": 24, "peak_bw_tbs": 0.30, "peak_tflops_fp16": 121},
    }

    # H100 running light workload that only needs 18GB VRAM and 0.4 TB/s BW
    rs = metrics.recommend_rightsizing(
        current_gpu="H100",
        achieved_bw_tbs=0.4,
        achieved_tflops=80,
        vram_used_gb=18,
        catalog=catalog,
    )
    assert rs["recommended_gpu"] in ("A10G", "L4", "A100")
    assert rs["savings_pct"] > 0

    # VRAM unit cost calculation
    cost_gb = metrics.vram_cost_per_gb_hr(on_demand_hr=2.50, hbm_gb=80)
    assert abs(cost_gb - 0.03125) < 1e-4


def test_carbon_multi_region_scheduling():
    """Test Extension 5: Multi-region Carbon & Cost Scheduling."""
    kwh = 1000.0
    regions = sustainability.compare_regions_for_workload(kwh, baseline_region="us-east-1")
    assert len(regions) == 5

    cleanest = sustainability.recommend_optimal_region(kwh, criterion="cleanest")
    assert cleanest["region"] == "europe-north1"
    assert cleanest["carbon_savings_pct"] > 90.0  # 30 g vs 380 g -> 92.1%

    cheapest = sustainability.recommend_optimal_region(kwh, criterion="cheapest")
    assert cheapest["region"] == "us-east-wa"
    assert cheapest["cost_savings_pct"] > 50.0  # $0.055 vs $0.12 -> 54.2%


def test_reasoning_energy_multiplier():
    """Test Extension 4: Reasoning Energy Multiplier."""
    tokens = 1000
    std_wh = sustainability.wh_per_query(tokens, is_reasoning=False)
    rsn_wh = sustainability.wh_per_query(tokens, is_reasoning=True)
    assert abs(rsn_wh / std_wh - 80.0) < 1e-3
