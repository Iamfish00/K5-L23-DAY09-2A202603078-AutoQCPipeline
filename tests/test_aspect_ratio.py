import pytest

from pipeline.checks.aspect_ratio import run


@pytest.mark.parametrize("width,height,expected", [
    (0.45, 0.10, True),   # 90 × 10 px
    (0.40, 0.10, False),  # 80 × 10 px, đúng ngưỡng
    (0.20, 0.20, False),  # 40 × 20 px
])
def test_aspect_ratio(make_ds, width, height, expected):
    labels = {"a": [f"0 0.5 0.5 {width} {height}"]}
    ds = make_ds(images={"a": 1}, labels=labels, size=(200, 100))
    issues = run(ds)
    assert [(i.image, i.line, i.code, i.severity) for i in issues] == (
        [("a", 1, "BOX_EXTREME_ASPECT", "warn")] if expected else []
    )