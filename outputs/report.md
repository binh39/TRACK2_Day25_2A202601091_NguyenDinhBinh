# NimbusAI — Báo cáo Tối ưu hóa Chi phí GPU (GPU Cost Optimization Report)

**Kỳ báo cáo (Period):** hàng tháng (monthly)  
**Chi phí cơ sở (Baseline spend):** $27,133  
**Chi phí sau tối ưu (Optimized spend):** $14,626  
**Dự kiến tiết kiệm (Projected savings):** $12,507  (**46%**)

## 1. Tóm tắt Điều hành (Executive Summary)

Thông qua quá trình kiểm toán FinOps toàn diện 5 giai đoạn bao gồm tối ưu hóa suy luận (inference), cam kết mua sắm (purchasing), hiệu quả tính toán thực tế (MFU/MBU) và triệt tiêu lãng phí chạy không (idle waste), NimbusAI có thể cắt giảm chi phí GPU hàng tháng từ **$27,133** xuống còn **$14,626**, mang lại khoản tiết kiệm ròng **$12,507/tháng (giảm 46.1%)**.

## 2. Tiết kiệm theo Đòn bẩy FinOps (Savings by lever)

| Đòn bẩy (Lever) | Tiết kiệm (USD) | Tỷ trọng tiết kiệm (%) |
|---|---|---|
| Inference (cascade/cache/batch) | $1,212 | 9.7% |
| Purchasing (spot/reserved) | $10,040 | 80.3% |
| Right-size util-lies | $655 | 5.2% |
| Kill idle GPUs | $600 | 4.8% |

## 3. Phân tích Nguyên nhân Gốc rễ: Cú lừa GPU-Util ("GPU-Util Lie")

- **Bản chất của "Lie":** Các chỉ số đo lường từ `nvidia-smi` như `GPU-Util %` chỉ đo tỷ lệ thời gian mà xung nhịp xử lý (SM clock) ở trạng thái bận (active), **hoàn toàn không phản ánh** thông lượng tính toán hữu ích, cường độ số học hay hiệu suất Tensor Core (MFU).
- **Nguyên nhân kỹ thuật:** Các tác vụ suy luận bị nghẽn băng thông bộ nhớ (Memory-bound autoregressive decoding với batch size nhỏ) hoặc chờ đợi nạp trọng số từ HBM sang SRAM khiến SM luôn trong trạng thái chờ (stall). Khi đó `GPU-Util` báo **98%** nhưng `MFU` thực tế chỉ đạt **19-20%**.
- **Tác động tài chính:** NimbusAI phải trả 100% đơn giá thuê GPU đắt đỏ ($2.50/giờ cho H100) nhưng chỉ nhận lại ~1/5 năng lực tính toán phần cứng. Việc right-sizing sang A100/A10G hoặc tách biệt prefill/decode sẽ loại bỏ ngay khoản lãng phí này.

## 4. Kế hoạch Hành động Ưu tiên theo ROI (Prioritized Action Plan)

1. **Giai đoạn 1 (Ngay lập tức — Day 1, Không rủi ro): Hủy bỏ GPU chạy không qua đêm & sandbox**
   - *Hành động:* Cấu hình auto-reaper và cơ chế scale-to-zero tự động cho các instance thử nghiệm, eval và phát triển sau giờ làm việc.
   - *Tác động:* Tiết kiệm ngay ~$600/tháng mà không ảnh hưởng tới người dùng.
2. **Giai đoạn 2 (Thu hồi vốn nhanh — Tuần 1): Tối ưu hóa Suy luận (Cascading, Prompt Caching, Batch API)**
   - *Hành động:* Định tuyến 80% truy vấn đơn giản sang model nhỏ ($0.20/$0.40 trên 1M token), kích hoạt Prompt Caching cho system prompt tĩnh (chiết khấu 90% khi đọc) và gom lô batch cho các tác vụ eval (-50% giá).
   - *Tác động:* Tiết kiệm ~$1,212/tháng.
3. **Giai đoạn 3 (Mua sắm Chiến lược — Tuần 2): Kết hợp Spot + Checkpointing và Cam kết Reserved 3-Năm**
   - *Hành động:* Chuyển các job training chịu lỗi sang Spot instances kèm checkpoint định kỳ; ký cam kết Reserved 3-Year cho cụm phục vụ inference 24/7.
   - *Tác động:* Đòn bẩy tiết kiệm lớn nhất (~$10,040/tháng).
4. **Giai đoạn 4 (Chuẩn hóa Phần cứng — Tháng 1): Right-Size GPU theo VRAM & Băng thông MBU**
   - *Hành động:* Di chuyển các workload suy luận memory-bound từ H100 xuống A100 / A10G / L4 phù hợp với dung lượng VRAM thực tế.
   - *Tác động:* Tiết kiệm ~$655/tháng.

## 5. Tính Bền vững & Năng lượng (Sustainability)

- **Năng lượng tiêu thụ mỗi truy vấn (Energy per query):** 0.24 Wh
- **Phát thải carbon mỗi truy vấn (Carbon per query):** 0.091 gCO2e
- **Vùng rẻ nhất & sạch nhất (Cheapest+cleanest region):** europe-north1

### Đánh giá Phát thải Carbon & Điều phối Đa vùng
- **Tối ưu hóa Vùng triển khai:** Di chuyển các tác vụ huấn luyện theo lô sang `europe-north1` (Thủy điện Na Uy, 30 gCO2/kWh) giúp giảm **92.1% lượng phát thải carbon** so với `us-east-1` (380 gCO2/kWh) đồng thời giảm chi phí điện.
- **Chi phí Năng lượng của Reasoning:** Quá trình sinh token suy luận chuỗi dài tự hồi quy làm tăng mức tiêu thụ điện năng lên tới **80×**. Cần áp dụng Dynamic Routing để hạn chế lãng phí năng lượng không cần thiết.

## 6. Chi tiết 5 Phần Mở Rộng "Your Turn" Đã Triển Khai (5/5)



### 1. Extension 1: Ma trận Quyết định Tier Mua sắm Đa Yếu tố (`recommend_tier_advanced`)

- Đã xây dựng hàm `recommend_tier_advanced()` tích hợp rủi ro gián đoạn theo từng dòng GPU (H100 ~3%, A10G ~12%) và thời lượng dự án.

- Chi phí mua sắm hàng tháng theo chính sách nâng cao: **$14,758** (tiết kiệm 42.5% so với On-Demand).



### 2. Extension 2: Right-Sizing theo Hiệu quả Băng thông MBU & Đơn vị VRAM

- Phân tích chỉ số Model Bandwidth Utilization (MBU) và đơn giá VRAM (`$/GB-VRAM-hr`).

- Các workload suy luận memory-bound được chuyển đổi chính xác từ H100 sang A100 / A10G, tránh lãng phí FLOPs tính toán không dùng đến.

- Tiềm năng tiết kiệm Right-sizing trên toàn cụm GPU: **$2,724.00/tháng**.



### 3. Extension 3: Kinh tế học của Prompt Caching (`cache_is_worth_it`)

- Thiết lập công thức điểm hòa vốn: $N_{be} = \frac{P_{write}}{P_{in} \times (1 - \text{read\_discount})}$.

- Ngưỡng hòa vốn cho model nhỏ: **1.11 lần đọc**.

- Với số lần tái sử dụng tiền tố trung bình đạt ~5.0 lần trong dữ liệu, Prompt Caching đem lại hiệu quả tài chính vượt trội.



### 4. Extension 4: Phân tích Ngân sách & Định tuyến Suy luận (Reasoning Budget)

- Lưu lượng Reasoning chiếm **8.4%** tổng truy vấn, nhưng ngốn **16.5%** chi phí suy luận và **94.0%** tổng điện năng do quá trình sinh chuỗi suy nghĩ tự hồi quy (~80× năng lượng).

- Áp dụng bộ lọc định tuyến phân loại độ phức tạp giúp tiết kiệm thêm **$20.95/tháng** và giảm **446.8 kWh/tháng**.



### 5. Extension 5: Lịch trình Nhận thức Carbon & Chi phí Đa vùng (Carbon-Aware Scheduling)

- Đánh giá 5 vùng cloud cho 4,227 kWh/tháng workload huấn luyện có thể gián đoạn.

- **Vùng sạch nhất (Cleanest):** `europe-north1` (giảm 92.1% lượng phát thải CO2).

- **Vùng giá điện rẻ nhất (Cheapest):** `us-east-wa` (giảm 54.2% hóa đơn tiền điện).

- **Phân tích Đánh đổi:** Các tác vụ Batch Training chạy phi thời gian thực không bị ảnh hưởng bởi độ trễ mạng đối với người dùng cuối, cho phép linh hoạt điều phối toàn cầu.

_Số liệu được trích xuất theo snapshot tháng 6/2026; vui lòng re-baseline trước khi áp dụng thực tế._