# NimbusAI — GPU Cost Optimization Report

**Period:** monthly  
**Baseline spend:** $27,133  
**Optimized spend:** $14,626  
**Projected savings:** $12,507  (**46%**)

## Executive Summary

Through a comprehensive 5-phase FinOps audit across model inference, instance purchasing commitments, utilization efficiency, and idle capacity management, NimbusAI can reduce its monthly GPU spend from **$27,133** to **$14,626**, achieving **$12,507/month in net savings (46.1% reduction)**.

## Savings by lever

| Lever | Savings (USD) | Share of Savings (%) |
|---|---|---|
| Inference (cascade/cache/batch) | $1,212 | 9.7% |
| Purchasing (spot/reserved) | $10,040 | 80.3% |
| Right-size util-lies | $655 | 5.2% |
| Kill idle GPUs | $600 | 4.8% |

## Root-Cause Analysis: The 'GPU-Util Lie'

- **What is the Lie?** Telemetry metrics such as `nvidia-smi` GPU-Util measure the percentage of time that the GPU compute engines / SM clocks are non-idle. They do **not** measure computational throughput, arithmetic intensity, or tensor core utilization (MFU).
- **Why does it happen?** A GPU running memory-bound operations (e.g. LLM decode with small batch size) or waiting on memory bandwidth / kernel launch synchronization can show **98% GPU-Util** while its Model FLOPs Utilization (MFU) is merely **19-20%**.
- **Financial Impact:** The organization pays 100% of the premium hourly rate (e.g. $2.50/hr for H100) while obtaining only ~1/5th of the hardware's computational capacity. Right-sizing or disaggregating prefill/decode resolves this waste immediately.

## Prioritized Action Plan (Ranked by ROI)

1. **Phase 1 (Immediate — Day 1, Zero Risk): Kill Idle overnight GPUs & sandbox instances**
   - *Action:* Configure auto-reaper and event-driven scale-to-zero for development/eval instances.
   - *Impact:* Saves ~$600/month with zero impact on production latency.
2. **Phase 2 (Fast ROI — Week 1): Inference Optimizations (Cascading, Prompt Caching, Batch API)**
   - *Action:* Route simple queries (80% volume) to small model tier ($0.20/$0.40 per 1M tokens), enable prompt caching for static system prompts (90% read discount), and offload asynchronous evaluation jobs to Batch API (-50% discount).
   - *Impact:* Saves ~$1,212/month.
3. **Phase 3 (Strategic Purchasing — Week 2): Spot with Checkpointing & 3-Year Reserved Commitments**
   - *Action:* Move fault-tolerant batch training jobs to Spot instances with automated checkpointing; secure 3-Year Reserved instances for predictable 24/7 inference baselines.
   - *Impact:* Largest dollar savings lever (~$10,040/month).
4. **Phase 4 (Hardware Governance — Month 1): Right-Size Memory-Bound GPUs**
   - *Action:* Migrate memory-bound inference workloads from H100 down to A100 / A10G / L4 based on VRAM footprint and memory bandwidth.
   - *Impact:* Saves ~$655/month.

## Sustainability

- Energy per query: 0.24 Wh
- Carbon per query: 0.091 gCO2e
- Cheapest+cleanest region: europe-north1

### Carbon & Regional Scheduling Insights
- **Region Optimization:** Deploying non-urgent batch training jobs in `europe-north1` (Norway hydro, 30 gCO2/kWh) reduces emissions by **92.1%** compared to `us-east-1` (380 gCO2/kWh) while saving on electricity costs.
- **Reasoning Energy Penalty:** Autoregressive reasoning expansion increases per-query energy consumption by up to **80×**. Implementing complexity-gated dynamic routing prevents unnecessary carbon and dollar expenditure.

## 'Your Turn' Extensions Implemented (5/5)



### 1. Extension 1: Multi-Factor Purchasing Tier Matrix

- Implemented `recommend_tier_advanced()` incorporating GPU-specific interruption probabilities (H100 ~3%, A10G ~12%) and project duration horizons.

- Monthly purchasing spend under advanced policy: **$14,758** (42.5% saved vs on-demand).



### 2. Extension 2: Right-Sizing by MBU & VRAM Economics

- Analyzed memory bandwidth utilization (MBU) and VRAM costs (`$/GB-VRAM-hr`).

- Memory-bound decode workloads are right-sized from H100 down to A100 / A10G, avoiding paying for unused compute FLOPs.

- Fleet-wide monthly right-sizing savings potential: **$2,724.00**.



### 3. Extension 3: Economics of Prompt Caching (`cache_is_worth_it`)

- Implemented break-even reuse formula: $N_{be} = \frac{P_{write}}{P_{in} \times (1 - \text{read\_discount})}$.

- Break-even threshold for small model: **1.11 reads**.

- With dataset average prefix reads of ~5.0, prompt caching is active and highly profitable.



### 4. Extension 4: Reasoning Budget Analysis & Routing

- Reasoning traffic represents **8.4%** of requests, but drives **16.5%** of inference cost and **94.0%** of energy consumption due to autoregressive chain-of-thought token expansion (~80× energy multiplier).

- Capping reasoning traffic with complexity threshold routing yields **$20.95/month** in financial savings and **446.8 kWh/month** in energy reduction.



### 5. Extension 5: Carbon-Aware Multi-Region Scheduling

- Evaluated 5 cloud regions for 4,227 kWh/month of interruptible training workloads.

- **Cleanest region:** `europe-north1` (cuts carbon emissions by 92.1%).

- **Cheapest power region:** `us-east-wa` (cuts electricity power bill by 54.2%).

- **Trade-off Analysis:** Non-real-time batch training has zero latency impact on interactive users, allowing flexible global scheduling.

_Figures are June-2026 as-of snapshots; re-baseline before acting._