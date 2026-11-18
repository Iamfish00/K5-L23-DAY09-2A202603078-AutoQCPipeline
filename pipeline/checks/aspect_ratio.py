from argparse import ArgumentParser

from ..common import Dataset, Issue, WARN, load_config, parse_yolo_line


def run(ds, max_ratio=8):
    issues = []
    for image in ds.image_files():
        size = ds.image_size(image.stem)
        if size is None:
            continue

        image_width, image_height = size
        for line, text in ds.read_label_lines(image.stem) or []:
            try:
                class_id, _, _, width, height = parse_yolo_line(text)
            except (ValueError, OverflowError):
                continue

            short, long = sorted((width * image_width, height * image_height))
            if not 0 <= class_id < len(ds.classes) or short <= 0:
                continue

            ratio = long / short
            if ratio > max_ratio:
                issues.append(Issue(
                    "aspect_ratio", WARN, "BOX_EXTREME_ASPECT",
                    image.stem, f"tỉ lệ {ratio:.2f}:1", line,
                    extra={"ratio": ratio},
                ))
    return issues


if __name__ == "__main__":
    parser = ArgumentParser()
    parser.add_argument("dataset")
    args = parser.parse_args()
    for issue in run(Dataset(args.dataset, load_config()["classes"])):
        print(f"{issue.image}:{issue.line} {issue.code} {issue.message}")