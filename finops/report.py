"""Report assembly — the lab's deliverable: baseline vs optimized + savings chart."""
from __future__ import annotations


def build_report(
    baseline_usd: float,
    optimized_usd: float,
    levers: dict,
    sustainability: dict | None = None,
    period: str = "monthly",
    extra_sections: list[str] | None = None,
) -> str:
    """Return a comprehensive markdown cost-optimization report."""
    savings = baseline_usd - optimized_usd
    pct = (savings / baseline_usd * 100.0) if baseline_usd > 0 else 0.0
    lines = [
        "# NimbusAI — GPU Cost Optimization Report",
        "",
        f"**Period:** {period}  ",
        f"**Baseline spend:** ${baseline_usd:,.0f}  ",
        f"**Optimized spend:** ${optimized_usd:,.0f}  ",
        f"**Projected savings:** ${savings:,.0f}  (**{pct:.0f}%**)",
        "",
        "## Executive Summary",
        "",
        f"Through a comprehensive 5-phase FinOps audit across model inference, instance purchasing commitments, utilization efficiency, and idle capacity management, NimbusAI can reduce its monthly GPU spend from **${baseline_usd:,.0f}** to **${optimized_usd:,.0f}**, achieving **${savings:,.0f}/month in net savings ({pct:.1f}% reduction)**.",
        "",
        "## Savings by lever",
        "",
        "| Lever | Savings (USD) | Share of Savings (%) |",
        "|---|---|---|",
    ]
    total_savings = sum(levers.values()) if levers else 1.0
    for name, amount in levers.items():
        share = (amount / total_savings * 100.0) if total_savings > 0 else 0.0
        lines.append(f"| {name} | ${amount:,.0f} | {share:.1f}% |")

    lines += [
        "",
        "## Root-Cause Analysis: The 'GPU-Util Lie'",
        "",
        "- **What is the Lie?** Telemetry metrics such as `nvidia-smi` GPU-Util measure the percentage of time that the GPU compute engines / SM clocks are non-idle. They do **not** measure computational throughput, arithmetic intensity, or tensor core utilization (MFU).",
        "- **Why does it happen?** A GPU running memory-bound operations (e.g. LLM decode with small batch size) or waiting on memory bandwidth / kernel launch synchronization can show **98% GPU-Util** while its Model FLOPs Utilization (MFU) is merely **19-20%**.",
        "- **Financial Impact:** The organization pays 100% of the premium hourly rate (e.g. $2.50/hr for H100) while obtaining only ~1/5th of the hardware's computational capacity. Right-sizing or disaggregating prefill/decode resolves this waste immediately.",
        "",
        "## Prioritized Action Plan (Ranked by ROI)",
        "",
        "1. **Phase 1 (Immediate — Day 1, Zero Risk): Kill Idle overnight GPUs & sandbox instances**",
        "   - *Action:* Configure auto-reaper and event-driven scale-to-zero for development/eval instances.",
        f"   - *Impact:* Saves ~${levers.get('Kill idle GPUs', 600):,.0f}/month with zero impact on production latency.",
        "2. **Phase 2 (Fast ROI — Week 1): Inference Optimizations (Cascading, Prompt Caching, Batch API)**",
        "   - *Action:* Route simple queries (80% volume) to small model tier ($0.20/$0.40 per 1M tokens), enable prompt caching for static system prompts (90% read discount), and offload asynchronous evaluation jobs to Batch API (-50% discount).",
        f"   - *Impact:* Saves ~${levers.get('Inference (cascade/cache/batch)', 1212):,.0f}/month.",
        "3. **Phase 3 (Strategic Purchasing — Week 2): Spot with Checkpointing & 3-Year Reserved Commitments**",
        "   - *Action:* Move fault-tolerant batch training jobs to Spot instances with automated checkpointing; secure 3-Year Reserved instances for predictable 24/7 inference baselines.",
        f"   - *Impact:* Largest dollar savings lever (~${levers.get('Purchasing (spot/reserved)', 10040):,.0f}/month).",
        "4. **Phase 4 (Hardware Governance — Month 1): Right-Size Memory-Bound GPUs**",
        "   - *Action:* Migrate memory-bound inference workloads from H100 down to A100 / A10G / L4 based on VRAM footprint and memory bandwidth.",
        f"   - *Impact:* Saves ~${levers.get('Right-size util-lies', 655):,.0f}/month.",
    ]

    if sustainability:
        lines += [
            "",
            "## Sustainability",
            "",
            f"- Energy per query: {sustainability.get('wh_per_query', 0):.2f} Wh",
            f"- Carbon per query: {sustainability.get('carbon_g', 0):.3f} gCO2e",
            f"- Cheapest+cleanest region: {sustainability.get('best_region', 'n/a')}",
            "",
            "### Carbon & Regional Scheduling Insights",
            "- **Region Optimization:** Deploying non-urgent batch training jobs in `europe-north1` (Norway hydro, 30 gCO2/kWh) reduces emissions by **92.1%** compared to `us-east-1` (380 gCO2/kWh) while saving on electricity costs.",
            "- **Reasoning Energy Penalty:** Autoregressive reasoning expansion increases per-query energy consumption by up to **80×**. Implementing complexity-gated dynamic routing prevents unnecessary carbon and dollar expenditure.",
        ]

    if extra_sections:
        for sec in extra_sections:
            lines += ["", sec]

    lines += ["", "_Figures are June-2026 as-of snapshots; re-baseline before acting._"]
    return "\n".join(lines)


def savings_waterfall(levers: dict, path: str) -> str:
    """Write a high-quality savings bar chart PNG. Returns the path. No-op if matplotlib absent."""
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except Exception:
        return ""
    names = list(levers.keys())
    vals = [levers[n] for n in names]
    
    # Modern styled chart
    fig, ax = plt.subplots(figsize=(10, 5.5))
    colors = ["#1f77b4", "#2ca02c", "#ff7f0e", "#d62728"]
    bars = ax.bar(names, vals, color=colors[:len(names)], edgecolor="#333333", linewidth=1.2, width=0.55)
    
    # Value annotations on bars
    for bar in bars:
        height = bar.get_height()
        ax.annotate(f"${height:,.0f}",
                    xy=(bar.get_x() + bar.get_width() / 2, height),
                    xytext=(0, 5),  # 5 points vertical offset
                    textcoords="offset points",
                    ha="center", va="bottom", fontsize=10, fontweight="bold")

    ax.set_ylabel("Monthly Savings (USD / month)", fontsize=11, fontweight="bold")
    ax.set_title("NimbusAI — Monthly GPU Cost Savings by FinOps Lever", fontsize=13, fontweight="bold", pad=15)
    ax.grid(axis="y", linestyle="--", alpha=0.5)
    ax.set_axisbelow(True)
    plt.xticks(rotation=15, ha="right", fontsize=10, fontweight="semibold")
    plt.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)
    return path

