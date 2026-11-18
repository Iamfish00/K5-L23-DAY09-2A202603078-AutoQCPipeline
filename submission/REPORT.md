# Báo cáo Day 09 — Trương Tuấn Vũ, 2A202603078

## 1. Kết luận trước

Pipeline kết luận **Hold**. Pipeline nhận **224 ảnh**, loại **19 ảnh** và xuất bản nháp **205 ảnh**. Sau khi duyệt, còn **0 lỗi bắt buộc** và **38/205 ảnh (18,54%)** có cảnh báo chưa duyệt, vượt ngưỡng **10%**.

## 2. Lỗi và phân việc

Mã lỗi	Số ảnh/dòng	Ai sửa (máy/người)	Vì sao

`02_error_list_v1.csv` có **208 mục**, gồm **55 lỗi bắt buộc** và **153 cảnh báo**. Cột số lượng đếm theo mục báo cáo. Một ảnh có thể xuất hiện ở nhiều mục. Các check nhãn chạy trên **205 ảnh qua bước tiếp nhận**, với **675 dòng nhãn không trống** trước autofix.

| Mã lỗi | Số ảnh/dòng | Ai sửa (máy/người) | Vì sao |
| --- | ---: | --- | --- |
| `CORRUPT_IMAGE` | 2 ảnh | Máy | Loại ảnh không giải mã được. |
| `BAD_SIZE` | 3 ảnh | Máy | Loại ảnh có cạnh ngắn dưới 250 px. |
| `DUP_IMAGE_EXACT` | 8 ảnh | Máy | Loại bản lặp trùng từng byte. |
| `DUP_IMAGE_NEAR` | 2 ảnh | Máy | Loại bản gần trùng theo pHash đã hiệu chỉnh. |
| `LEAK_TEST` | 4 ảnh | Máy | Loại ảnh khớp với ảnh thuộc tập tham chiếu để hạn chế rò rỉ. |
| `MISSING_LABEL_FILE` | 6 ảnh | Người | Cần nhìn ảnh và gán nhãn cho các vật thể. |
| `EMPTY_LABEL` | 12 ảnh | Người | Xác nhận ảnh nền hay ảnh bị bỏ sót nhãn. |
| `BAD_FORMAT` | 3 dòng | Máy | Bỏ dòng không hợp lệ theo định dạng YOLO. |
| `BAD_CLASS_ID` | 6 dòng | Máy | Bỏ dòng có ID ngoài danh sách lớp. |
| `BAD_CLASS_NAME` | 2 tên lớp | Máy | Khôi phục tên lớp chuẩn trong `data.yaml`. |
| `BOX_ZERO` | 4 dòng | Máy | Bỏ box có cạnh không dương. |
| `BOX_OUT_OF_IMAGE` | 8 dòng | Máy | Cắt box theo biên ảnh hoặc bỏ nếu diện tích còn lại bằng 0. |
| `DUP_BOX` | 7 dòng | Máy | Bỏ box trùng ở dòng sau. |
| `BOX_TINY` | 6 dòng trên 4 ảnh | Người | Xem box nhỏ có thực sự bao vật thể và phù hợp quy tắc gán nhãn hay không. |
| `BOX_HUGE` | 3 dòng trên 3 ảnh | Người | Xem box lớn có bám sát đối tượng hay bao cả nền. |
| `CLASS_RARE` | 4 cảnh báo cấp bộ dữ liệu | Người | Xem phân bố nhãn và kiểm tra các token ID bất thường. |
| `POSSIBLE_MISSING` | 53 cảnh báo trên 52 ảnh | Người | Xác nhận vật thể thiếu box. |
| `POSSIBLE_WRONG_CLASS` | 18 cảnh báo trên 18 ảnh | Người | Đối chiếu lớp của vật thể trong ảnh. |
| `POSSIBLE_LOOSE_BOX` | 28 cảnh báo trên 24 ảnh | Người | Kiểm tra mức độ bám sát của box. |
| `POSSIBLE_FALSE_POS` | 29 cảnh báo trên 27 ảnh | Người | Xác nhận box thừa hay model đã bỏ sót vật thể. |

`img_0020` đứng đầu hàng đợi với **11,524 điểm**. Ảnh này có cả thay đổi `FIXED_DROP_LINE` và hai loại cảnh báo `POSSIBLE_MISSING`, `POSSIBLE_WRONG_CLASS`. Pipeline cộng trọng số của các cảnh báo, tăng điểm theo độ tin cậy của dự đoán khi có, rồi cộng điểm cho dòng đã sửa. Những ảnh thiếu nhãn được cộng **10 điểm** qua `NEEDS_LABEL`.

Đã duyệt **80/125 ảnh** trong hàng đợi. Đối chiếu `04_error_list_v2.csv` và `06_review_log.csv`, **74/80 ảnh** đã duyệt chứa **94/123 cảnh báo ngữ nghĩa** được ghi trước khi duyệt.

## 3. Calibration (2 ngưỡng)

Tham số	Khởi đầu	Đã chọn	Precision / Recall (trước → sau)	Lý do (đánh đổi)

| Tham số | Khởi đầu | Đã chọn | Precision / Recall (trước → sau) | Lý do (đánh đổi) |
| --- | --- | --- | --- | --- |
| `duplicates.phash_dist` | 2 | 4 | Với ảnh gần trùng, precision 100% → 100% (3/3 → 4/4) và recall 50% → 66,7% (3/6 → 4/6). | Ngưỡng 4 bắt thêm một ca mà vẫn có 0 cảnh báo sai trên `calib`. Các mức 6–14 bắt cùng 4/6 ca, nên chọn 4 để hạn chế nguy cơ loại nhầm ảnh. |
| `second_opinion.conf` | 0.25 | 0.60 | Với lỗi **thiếu box**, precision 50% → 57,1% (8/16 → 8/14) và recall 100% → 100% (8/8).<br>Với lỗi **sai lớp**, precision 55,6% → 62,5% (5/9 → 5/8) và recall 83,3% → 83,3% (5/6).<br>Với lỗi **box lỏng**, precision 28,6% → 20% (2/7 → 1/5) và recall 40% → 20% (2/5 → 1/5). | Giảm ba cảnh báo sai thuộc nhóm thiếu box và sai lớp, vẫn bắt được cùng số ca đúng ở hai nhóm này. Đổi lại, bỏ sót thêm một ca box lỏng. |

Trên `calib`, tăng pHash từ `2` lên `4` bắt thêm **1/6 ca gần trùng**. Khi so trong nội bộ lô `raw`, hai ngưỡng đều đánh dấu cùng **2/224 ảnh**. `01_intake.csv` ghi hai cặp `img_0076`/`img_0042` và `img_0143`/`img_0037`, đều có khoảng cách pHash `0`. Kết quả trên tập có lỗi chèn cho thấy mức cải thiện trên `calib`, còn recall của `raw` chưa đo được.

## 4. Cửa chặn và điều pipeline KHÔNG bắt được

Lệnh dưới đây chạy thử với ngân sách duyệt bằng 0 và lưu kết quả vào thư mục riêng.

```powershell
.\.venv\Scripts\python.exe -X utf8 -m pipeline.run --budget 0 --work work/cp5_gate/run --reports work/cp5_gate/reports --export-dir work/cp5_gate/export
$LASTEXITCODE
```

Kết quả là **Rework**, mã thoát **20**. Cả **6 lỗi `MISSING_LABEL_FILE`** vẫn còn ở vòng QC cuối và `exported` là `null`.

### Hai điểm mù có bằng chứng

1. **Ảnh gần trùng biến đổi mạnh.** Với ngưỡng pHash `4`, hai cặp `calib_037`/`calib_015` và `calib_038`/`calib_024` có khoảng cách lần lượt **16** và **18**. Đây là hai ca gần trùng trong manifest nhưng check bỏ sót cả hai.
2. **Gán sai lớp hợp lệ.** Ở `calib_009` dòng **6**, manifest ghi lỗi chèn `truck → bus`. ID `bus` hợp lệ về cú pháp, và `second_opinion` không phát cảnh báo cho ảnh này ở cấu hình đã chọn.

### Ba quan sát trên ảnh gốc (bước 1 trong GUIDE.md)

- `img_0001.png` vẽ thiếu đối tượng person
- `img_0002.png` vẽ nhầm đối tượng person vào máy
- `img_0004.png` chưa vẽ đối tượng nào

## 5. Train: raw vs clean (tùy chọn, chấm riêng)

Colab chạy **4 lượt** với `yolo26n.pt`, **20 epoch**, seed **0 và 1**, batch **16**, ảnh đầu vào **640 px**. Cả hai biến thể dùng cùng **40 ảnh validation** và **100 ảnh test**.

| biến thể | #ảnh train | số seed | map50 (TB ± độ lệch) | map50_95 (TB ± độ lệch) | precision (TB ± độ lệch) | recall (TB ± độ lệch) |
| --- | --- | --- | --- | --- | --- | --- |
| raw | 224 | 2 | 0.726 ± 0.000 | 0.512 ± 0.004 | 0.764 ± 0.061 | 0.649 ± 0.028 |
| clean | 205 | 2 | 0.700 ± 0.030 | 0.486 ± 0.013 | 0.715 ± 0.073 | 0.615 ± 0.017 |

`clean` có mAP50 trung bình thấp hơn **2,54 điểm phần trăm**. Chênh lệch này nhỏ hơn độ lệch chuẩn của `clean` giữa hai seed (**3,05 điểm phần trăm**), nên cần thêm seed và đối chứng để kết luận tác động của QC.

- `01_intake.csv` đánh dấu **4/224 ảnh raw** nghi trùng với ảnh test. Để kiểm giả thuyết này, xác nhận các cặp rồi train lại `raw` sau khi loại ảnh xác nhận trùng. Giữ cùng seed, siêu tham số và tập test để đo tác động của rò rỉ.
- Hai bộ train có số ảnh và nhãn khác nhau. Để đo tác động riêng của sửa nhãn, dùng **cùng 205 ảnh** và so nhãn gốc với nhãn sau QC. Kiểm tra log Ultralytics để biết số ảnh thực sự được loader dùng.

## 6. Quyết định và ghi chú AI

**Giữ Hold**. Với cùng **205 ảnh**, để xuống dưới 10% cần còn tối đa **20 ảnh** có cảnh báo chưa duyệt. Từ **38 ảnh** hiện tại, cần xử lý cảnh báo trên ít nhất **18 ảnh** và chạy lại QC. Điều kiện Release cũng yêu cầu tiếp tục có **0 lỗi bắt buộc**.

- Nhờ Codex viết bốn module `label_format`, `gate`, `autofix` và `second_opinion` theo docstring và test trong repo.
- Kiểm phạm vi đọc và ghi của code, đối chiếu lỗi chèn trên `calib`, thử gate với `--budget 0` và chạy toàn bộ unit test (**82 test đạt**, gồm 3 test bonus).

### Bonus CVAT (+2)

Trên `img_0020.jpg`, bộ lọc `Width < 20 px` hiển thị 3/9 box.
Pipeline ghi 0 cảnh báo `BOX_TINY` cho ảnh này vì check dùng
cạnh ngắn dưới 12 px. Người gán dùng `can_review` để đánh dấu
box khó cần xem lại. Trong pipeline, các ảnh cần duyệt được
xếp vào `05_review_queue.csv`.

[Ảnh chụp kết quả lọc CVAT](reports/Day09%20Bonus.png)

### Bonus check tỉ lệ box (+3)

`aspect_ratio.py` cảnh báo `BOX_EXTREME_ASPECT` khi cạnh dài
lớn hơn 8 lần cạnh ngắn, tính theo pixel. Cả 3 test đều đạt.
Trên bộ dữ liệu sau QC, check đánh dấu `img_0042` dòng 5
(9,58:1) và `img_0124` dòng 6 (9,11:1).
