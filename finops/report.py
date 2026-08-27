"""Report assembly — the lab's deliverable: baseline vs optimized + savings chart."""
from __future__ import annotations


def build_report(
    baseline_usd: float,
    optimized_usd: float,
    levers: dict,
    sustainability: dict | None = None,
    period: str = "hàng tháng (monthly)",
    extra_sections: list[str] | None = None,
) -> str:
    """Return a comprehensive Vietnamese markdown cost-optimization report."""
    savings = baseline_usd - optimized_usd
    pct = (savings / baseline_usd * 100.0) if baseline_usd > 0 else 0.0
    lines = [
        "# NimbusAI — Báo cáo Tối ưu hóa Chi phí GPU (GPU Cost Optimization Report)",
        "",
        f"**Kỳ báo cáo (Period):** {period}  ",
        f"**Chi phí cơ sở (Baseline spend):** ${baseline_usd:,.0f}  ",
        f"**Chi phí sau tối ưu (Optimized spend):** ${optimized_usd:,.0f}  ",
        f"**Dự kiến tiết kiệm (Projected savings):** ${savings:,.0f}  (**{pct:.0f}%**)",
        "",
        "## 1. Tóm tắt Điều hành (Executive Summary)",
        "",
        f"Thông qua quá trình kiểm toán FinOps toàn diện 5 giai đoạn bao gồm tối ưu hóa suy luận (inference), cam kết mua sắm (purchasing), hiệu quả tính toán thực tế (MFU/MBU) và triệt tiêu lãng phí chạy không (idle waste), NimbusAI có thể cắt giảm chi phí GPU hàng tháng từ **${baseline_usd:,.0f}** xuống còn **${optimized_usd:,.0f}**, mang lại khoản tiết kiệm ròng **${savings:,.0f}/tháng (giảm {pct:.1f}%)**.",
        "",
        "## 2. Tiết kiệm theo Đòn bẩy FinOps (Savings by lever)",
        "",
        "| Đòn bẩy (Lever) | Tiết kiệm (USD) | Tỷ trọng tiết kiệm (%) |",
        "|---|---|---|",
    ]
    total_savings = sum(levers.values()) if levers else 1.0
    for name, amount in levers.items():
        share = (amount / total_savings * 100.0) if total_savings > 0 else 0.0
        lines.append(f"| {name} | ${amount:,.0f} | {share:.1f}% |")

    lines += [
        "",
        "## 3. Phân tích Nguyên nhân Gốc rễ: Cú lừa GPU-Util (\"GPU-Util Lie\")",
        "",
        "- **Bản chất của \"Lie\":** Các chỉ số đo lường từ `nvidia-smi` như `GPU-Util %` chỉ đo tỷ lệ thời gian mà xung nhịp xử lý (SM clock) ở trạng thái bận (active), **hoàn toàn không phản ánh** thông lượng tính toán hữu ích, cường độ số học hay hiệu suất Tensor Core (MFU).",
        "- **Nguyên nhân kỹ thuật:** Các tác vụ suy luận bị nghẽn băng thông bộ nhớ (Memory-bound autoregressive decoding với batch size nhỏ) hoặc chờ đợi nạp trọng số từ HBM sang SRAM khiến SM luôn trong trạng thái chờ (stall). Khi đó `GPU-Util` báo **98%** nhưng `MFU` thực tế chỉ đạt **19-20%**.",
        "- **Tác động tài chính:** NimbusAI phải trả 100% đơn giá thuê GPU đắt đỏ ($2.50/giờ cho H100) nhưng chỉ nhận lại ~1/5 năng lực tính toán phần cứng. Việc right-sizing sang A100/A10G hoặc tách biệt prefill/decode sẽ loại bỏ ngay khoản lãng phí này.",
        "",
        "## 4. Kế hoạch Hành động Ưu tiên theo ROI (Prioritized Action Plan)",
        "",
        "1. **Giai đoạn 1 (Ngay lập tức — Day 1, Không rủi ro): Hủy bỏ GPU chạy không qua đêm & sandbox**",
        "   - *Hành động:* Cấu hình auto-reaper và cơ chế scale-to-zero tự động cho các instance thử nghiệm, eval và phát triển sau giờ làm việc.",
        f"   - *Tác động:* Tiết kiệm ngay ~${levers.get('Kill idle GPUs', 600):,.0f}/tháng mà không ảnh hưởng tới người dùng.",
        "2. **Giai đoạn 2 (Thu hồi vốn nhanh — Tuần 1): Tối ưu hóa Suy luận (Cascading, Prompt Caching, Batch API)**",
        "   - *Hành động:* Định tuyến 80% truy vấn đơn giản sang model nhỏ ($0.20/$0.40 trên 1M token), kích hoạt Prompt Caching cho system prompt tĩnh (chiết khấu 90% khi đọc) và gom lô batch cho các tác vụ eval (-50% giá).",
        f"   - *Tác động:* Tiết kiệm ~${levers.get('Inference (cascade/cache/batch)', 1212):,.0f}/tháng.",
        "3. **Giai đoạn 3 (Mua sắm Chiến lược — Tuần 2): Kết hợp Spot + Checkpointing và Cam kết Reserved 3-Năm**",
        "   - *Hành động:* Chuyển các job training chịu lỗi sang Spot instances kèm checkpoint định kỳ; ký cam kết Reserved 3-Year cho cụm phục vụ inference 24/7.",
        f"   - *Tác động:* Đòn bẩy tiết kiệm lớn nhất (~${levers.get('Purchasing (spot/reserved)', 10040):,.0f}/tháng).",
        "4. **Giai đoạn 4 (Chuẩn hóa Phần cứng — Tháng 1): Right-Size GPU theo VRAM & Băng thông MBU**",
        "   - *Hành động:* Di chuyển các workload suy luận memory-bound từ H100 xuống A100 / A10G / L4 phù hợp với dung lượng VRAM thực tế.",
        f"   - *Tác động:* Tiết kiệm ~${levers.get('Right-size util-lies', 655):,.0f}/tháng.",
    ]

    if sustainability:
        lines += [
            "",
            "## 5. Tính Bền vững & Năng lượng (Sustainability)",
            "",
            f"- **Năng lượng tiêu thụ mỗi truy vấn (Energy per query):** {sustainability.get('wh_per_query', 0):.2f} Wh",
            f"- **Phát thải carbon mỗi truy vấn (Carbon per query):** {sustainability.get('carbon_g', 0):.3f} gCO2e",
            f"- **Vùng rẻ nhất & sạch nhất (Cheapest+cleanest region):** {sustainability.get('best_region', 'n/a')}",
            "",
            "### Đánh giá Phát thải Carbon & Điều phối Đa vùng",
            "- **Tối ưu hóa Vùng triển khai:** Di chuyển các tác vụ huấn luyện theo lô sang `europe-north1` (Thủy điện Na Uy, 30 gCO2/kWh) giúp giảm **92.1% lượng phát thải carbon** so với `us-east-1` (380 gCO2/kWh) đồng thời giảm chi phí điện.",
            "- **Chi phí Năng lượng của Reasoning:** Quá trình sinh token suy luận chuỗi dài tự hồi quy làm tăng mức tiêu thụ điện năng lên tới **80×**. Cần áp dụng Dynamic Routing để hạn chế lãng phí năng lượng không cần thiết.",
        ]

    if extra_sections:
        for sec in extra_sections:
            lines += ["", sec]

    lines += ["", "_Số liệu được trích xuất theo snapshot tháng 6/2026; vui lòng re-baseline trước khi áp dụng thực tế._"]
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

