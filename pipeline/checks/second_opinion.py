"""CHECK 6 — Ý kiến thứ hai: so nhãn với một model LỚN HƠN (yolo26l).   ★★★ (khó nhất, đáng điểm nhất)

Test:  pytest tests/test_second_opinion.py -q

Máy kiểm quy tắc, người kiểm ý nghĩa (slide). Các lỗi như thiếu nhãn / gán nhầm lớp hợp lệ / box lỏng
KHÔNG bắt được bằng quy tắc cú pháp. Ta nhờ một model mạnh hơn "nhìn lại" và CHỈ CẢNH BÁO (model cũng có thể sai):
những ảnh bị cờ sẽ vào hàng đợi cho NGƯỜI duyệt.

`preds[stem]` = list `[id_lớp, conf, cx, cy, w, h]` của model (lấy qua `get_preds(ds, cfg, "checker")` nếu preds=None).
`L = ds.valid_boxes(stem)` = list `(id_lớp, cx, cy, w, h)` của nhãn (đã bỏ dòng hỏng).
Ngưỡng ở `cfg["second_opinion"]`: conf, min_area_px, fp_conf, iou_missing, iou_match, iou_loose.

Thuật toán gợi ý, với từng ảnh (bỏ qua ảnh không có trong preds hoặc không có file nhãn):
  P = dự đoán có conf >= conf  VÀ diện tích px (w*W * h*H) >= min_area_px
  Với mỗi dự đoán r trong P: lấy các nhãn có IoU(r, nhãn) >= iou_missing  (cands)
   - không có cands                            -> POSSIBLE_MISSING     (model thấy vật mà nhãn không có box)
   - có cands cùng lớp, tốt nhất IoU < iou_loose -> POSSIBLE_LOOSE_BOX  (đúng vật, box lỏng/lệch)
   - không có cands cùng lớp, nhưng cands tốt nhất IoU >= iou_match (khác lớp) -> POSSIBLE_WRONG_CLASS
  Với mỗi dòng nhãn hợp lệ: nếu IoU với MỌI dự đoán (conf >= fp_conf, không lọc diện tích) đều < iou_missing
                                             -> POSSIBLE_FALSE_POS  (box nhãn không khớp vật nào model thấy; Issue.line = số dòng)

Chi tiết các ca biên (test kiểm đúng các ca này)
- `cands` gồm nhãn MỌI lớp có IoU >= iou_missing; "tốt nhất cùng lớp" = cands cùng lớp có IoU lớn nhất; "tốt nhất khác lớp" tương tự với cands khác lớp.
- Thứ tự quyết định cho mỗi dự đoán: (1) cands rỗng -> MISSING. (2) có cands cùng lớp: IoU tốt nhất < iou_loose -> LOOSE_BOX, ngược lại KHÔNG cờ
  (nhãn đúng lớp đã phủ vật này, kể cả khi còn nhãn khác lớp chồng lên). (3) không có cands cùng lớp: nếu IoU tốt nhất khác lớp >= iou_match -> WRONG_CLASS;
  nếu chỉ có khác lớp với IoU trong [iou_missing, iou_match) -> không cờ gì (mơ hồ: để cho FALSE_POS / lần duyệt khác).
- Một dự đoán sinh tối đa MỘT issue (MISSING / LOOSE_BOX / WRONG_CLASS); một ảnh có thể có nhiều issue.
- Thứ tự issue: theo `ds.image_files()` rồi theo thứ tự dự đoán trong `preds[stem]`, cuối cùng là các FALSE_POS theo số dòng; `Issue.image` = stem, `Issue.line` chỉ đặt cho FALSE_POS.

Lưu ý số dòng: dùng `ds.read_label_lines(stem)` (giữ số dòng gốc, kể cả dòng hỏng/trống) để lấy `Issue.line`; `valid_boxes` KHÔNG giữ số dòng.

Tất cả severity WARN; `Issue.extra` nên có {"conf": ...} hoặc {"iou": ...} (hàng đợi duyệt dùng conf để xếp ưu tiên).

Gợi ý
- `iou_xywh` có sẵn. Dòng nhãn hỏng không được làm script chết (dùng `ds.valid_boxes` và `parse_yolo_line` trong try).
- Kết quả phụ thuộc mạnh vào ngưỡng: calibrate chúng ở Bước 3 thay vì đoán.
"""
from ..common import WARN, Issue, iou_xywh, parse_yolo_line
from ..model_cache import get_preds


def _prediction_warning(stem, class_id, confidence, box, labels, rules):
    overlaps = [(iou_xywh(box, label_box), label_class) for _, label_class, label_box in labels]
    candidates = [(iou, label_class) for iou, label_class in overlaps if iou >= rules["iou_missing"]]
    extra = {"conf": confidence}
    if not candidates:
        return Issue("second_opinion", WARN, "POSSIBLE_MISSING", stem,
                     f"model thấy vật lớp {class_id} nhưng chưa có box nhãn khớp", extra=extra)

    best_same = max((iou for iou, label_class in candidates if label_class == class_id), default=None)
    if best_same is not None:
        if best_same < rules["iou_loose"]:
            return Issue("second_opinion", WARN, "POSSIBLE_LOOSE_BOX", stem,
                         "box nhãn và dự đoán cùng lớp nhưng lệch nhau", extra={**extra, "iou": best_same})
        return None

    best_iou, label_class = max(candidates)
    if best_iou >= rules["iou_match"]:
        return Issue("second_opinion", WARN, "POSSIBLE_WRONG_CLASS", stem,
                     f"nhãn lớp {label_class}, model dự đoán lớp {class_id}", extra={**extra, "iou": best_iou})
    return None


def run(ds, cfg, preds=None):
    if preds is None:
        preds = get_preds(ds, cfg, "checker")

    rules = cfg["second_opinion"]
    issues = []
    for path in ds.image_files():
        stem = path.stem
        if stem not in preds:
            continue
        lines = ds.read_label_lines(stem)
        if lines is None:
            continue

        labels = []
        for line, text in lines:
            try:
                class_id, *box = parse_yolo_line(text)
            except (ValueError, OverflowError):
                continue
            if 0 <= class_id < len(ds.classes):
                labels.append((line, class_id, box))

        predictions = preds[stem]
        size = ds.image_size(stem)
        if size is not None:
            image_width, image_height = size
            for class_id, confidence, *box in predictions:
                if confidence < rules["conf"]:
                    continue
                area = (box[2] * image_width) * (box[3] * image_height)
                if area < rules["min_area_px"]:
                    continue
                warning = _prediction_warning(stem, class_id, confidence, box, labels, rules)
                if warning is not None:
                    issues.append(warning)

        fp_boxes = [box for _, confidence, *box in predictions if confidence >= rules["fp_conf"]]
        for line, _, label_box in labels:
            best_iou = max((iou_xywh(label_box, box) for box in fp_boxes), default=None)
            if best_iou is None or best_iou < rules["iou_missing"]:
                issues.append(Issue("second_opinion", WARN, "POSSIBLE_FALSE_POS", stem,
                                    "box nhãn không khớp vật nào model thấy", line,
                                    extra={"iou": best_iou if best_iou is not None else 0.0}))
    return issues
