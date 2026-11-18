"""BƯỚC 2/4 — Sửa tự động những lỗi bắt buộc mà máy sửa được AN TOÀN.   ★★

Test:  pytest tests/test_autofix.py -q

`fix(ds, issues, cfg) -> list[dict]`: duyệt `issues` (chỉ lỗi severity ERROR), sửa thẳng vào thư mục `ds`,
và trả về danh sách thay đổi; mỗi phần tử có khoá: image, line, action, before, after
(đây chính là file `03_fixes.csv` — bằng chứng pipeline đã làm gì, người có thể kiểm lại).

| code lỗi                                       | cách sửa                                    | action           |
|------------------------------------------------|---------------------------------------------|------------------|
| BAD_FORMAT, BAD_CLASS_ID, BOX_ZERO, DUP_BOX    | xoá dòng đó khỏi file nhãn                  | "drop_line"      |
| BOX_OUT_OF_IMAGE                               | cắt box về trong [0,1] (giữ nguyên lớp)     | "clip_box"       |
| MISSING_LABEL_FILE                             | KHÔNG sửa file (máy không thể bịa nhãn): ghi 1 dòng fix, before="(không có file)", after="chuyển người gán" | "needs_label" |
| BAD_CLASS_NAME                                 | ghi lại `names` trong data.yaml đúng `cfg["classes"]` | "rename_classes" |
| DUP_IMAGE_*, LEAK_TEST, CORRUPT_IMAGE, BAD_SIZE| xoá ảnh + nhãn khỏi `ds`                    | "remove_image"   |

Bẫy cần nghĩ tới (có test cho từng cái)
- Một file có NHIỀU dòng lỗi: số dòng trong `issues` là số dòng GỐC. Nếu xoá từng dòng một thì số dòng lệch.
  Gom theo file, rồi ghi lại MỘT lần.
- Sau khi cắt, box có thể không còn diện tích (nằm hẳn ngoài ảnh): lúc đó xoá dòng thay vì ghi box rỗng.
- Một dòng có 2 lỗi (vd. BOX_OUT_OF_IMAGE + DUP_BOX): xoá dòng thắng, chỉ ghi 1 fix `drop_line`, không ghi thêm `clip_box`. Dòng trống ở giữa file vẫn đếm vào số dòng gốc.
- Ảnh vừa bị xoá (DUP_IMAGE_*...) mà còn issue dòng của chính nó: bỏ qua êm, không được báo lỗi/chết.
- Không động tới lỗi WARN (cảnh báo là việc của người). Không sửa file ở `data/raw/` — chỉ sửa `ds`.
- Chạy lần 2 trên dữ liệu đã sửa phải không làm gì thêm (idempotent) — NGOẠI LỆ duy nhất: `needs_label` được ghi lại mỗi lần còn lỗi `MISSING_LABEL_FILE` (vì ảnh vẫn chưa có nhãn).

- `needs_label` KHÔNG tạo file nhãn rỗng (rỗng = "ảnh nền", khác với "chưa gán"). `review_queue` sẽ đẩy ảnh này lên đầu hàng đợi cho người.

Gợi ý: `yaml.safe_load / safe_dump`.
"""
from collections import defaultdict
from pathlib import Path
from tempfile import NamedTemporaryFile

import yaml

from ..common import ERROR, iou_xywh, parse_yolo_line


DROP_CODES = {"BAD_FORMAT", "BAD_CLASS_ID", "BOX_ZERO", "DUP_BOX"}
REMOVE_CODES = {"LEAK_TEST", "CORRUPT_IMAGE", "BAD_SIZE"}


def _change(image, action, before, after, line=None):
    return dict(image=image, line=line, action=action, before=before, after=after)


def _replace_text(path, text):
    # Ghi xong bản tạm trước khi thay file, tránh để lại nhãn bị cắt nửa chừng.
    temporary = None
    try:
        with NamedTemporaryFile(mode="w", encoding="utf-8", newline="", delete=False, dir=path.parent) as stream:
            temporary = Path(stream.name)
            stream.write(text)
        temporary.replace(path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def _clip_box(text):
    class_id, cx, cy, width, height = parse_yolo_line(text)
    left, right = max(0, cx - width / 2), min(1, cx + width / 2)
    top, bottom = max(0, cy - height / 2), min(1, cy + height / 2)
    if left >= right or top >= bottom:
        return None
    return f"{class_id} {(left + right) / 2} {(top + bottom) / 2} {right - left} {bottom - top}"


def _duplicates_after_clip(text, previous_boxes, clipped, threshold):
    try:
        class_id, *box = parse_yolo_line(text)
    except (ValueError, OverflowError):
        return False
    earlier = previous_boxes[class_id]
    if any((clipped or other_clipped) and iou_xywh(box, other) > threshold
           for other, other_clipped in earlier):
        return True
    earlier.append((box, clipped))
    return False


def _fix_lines(path, actions, cfg):
    if not path.exists():
        return []
    with path.open(encoding="utf-8", errors="replace", newline="") as stream:
        original = stream.read().splitlines(keepends=True)

    kept = []
    fixes = []
    has_clips = "clip_box" in actions.values()
    previous_boxes = defaultdict(list)
    for line_no, line in enumerate(original, 1):
        action = actions.get(line_no)
        before = line.splitlines()[0]
        if action == "drop_line":
            fixes.append(_change(path.stem, action, before, "", line_no))
            continue

        clipped = action == "clip_box"
        after = _clip_box(before) if clipped else before
        # Việc cắt mép có thể làm hai box vốn khác nhau trở thành box trùng.
        if has_clips and after and _duplicates_after_clip(
            after, previous_boxes, clipped, cfg["label_format"]["dup_box_iou"]
        ):
            after = None
        if after is None:
            fixes.append(_change(path.stem, "drop_line", before, "", line_no))
        else:
            kept.append(after + line[len(before):])
            if clipped:
                fixes.append(_change(path.stem, action, before, after, line_no))

    if fixes:
        _replace_text(path, "".join(kept))
    return fixes


def _rename_classes(path, classes):
    data = yaml.safe_load(path.read_text(encoding="utf-8")) if path.exists() else None
    data = data or {}
    before = data.get("names")
    names = list(classes) if isinstance(before, list) else dict(enumerate(classes))
    if before == names:
        return []
    data["names"] = names
    _replace_text(path, yaml.safe_dump(data, allow_unicode=True, sort_keys=False))
    return [_change(path.name, "rename_classes", str(before), str(names))]


def fix(ds, issues, cfg):
    remove = set()
    missing_labels = set()
    line_actions = defaultdict(dict)
    rename_classes = False
    for issue in issues:
        if issue.severity != ERROR:
            continue
        code, stem = issue.code, issue.image
        if code in REMOVE_CODES or code.startswith("DUP_IMAGE_"):
            remove.add(stem)
        elif code == "BAD_CLASS_NAME":
            rename_classes = True
        elif code == "MISSING_LABEL_FILE":
            missing_labels.add(stem)
        elif issue.line is not None:
            if code in DROP_CODES:
                line_actions[stem][issue.line] = "drop_line"
            elif code == "BOX_OUT_OF_IMAGE":
                # Một quyết định xoá dòng luôn được ưu tiên hơn cắt box.
                line_actions[stem].setdefault(issue.line, "clip_box")

    fixes = []
    if remove:
        image_paths = defaultdict(list)
        for path in ds.image_files():
            if path.stem in remove:
                image_paths[path.stem].append(path)
        for stem in sorted(remove):
            label = ds.label_path(stem)
            paths = ([label] if label.exists() else []) + image_paths[stem]
            for path in paths:
                path.unlink(missing_ok=True)
            if paths:
                fixes.append(_change(stem, "remove_image", ", ".join(path.name for path in paths), ""))

    if rename_classes:
        fixes.extend(_rename_classes(ds.yaml_path, cfg["classes"]))
    for stem in sorted(line_actions.keys() - remove):
        fixes.extend(_fix_lines(ds.label_path(stem), line_actions[stem], cfg))
    for stem in sorted(missing_labels - remove):
        if not ds.label_path(stem).exists():
            fixes.append(_change(stem, "needs_label", "(không có file)", "chuyển người gán"))
    return fixes
