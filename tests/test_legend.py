import json
import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import icechart_caching as ic  # noqa: E402

FETCHED = datetime(2026, 10, 10, 8, 0, 0)
PUBLISHED = datetime(2026, 10, 10, 7, 0, 0)


def test_legend_json_schema(tmp_path):
    path = tmp_path / "legend.json"
    ic.create_legend_json(str(path), FETCHED, PUBLISHED)
    data = json.loads(path.read_text(encoding="utf-8"))

    assert data["version"] == 1
    assert data["updated"] == "2026-10-10T08:00:00Z"
    assert data["published"] == "2026-10-10T07:00:00Z"
    assert [i["id"] for i in data["items"]] == [c["id"] for c in ic.ICE_CLASSES]
    assert len(data["items"]) == 5
    assert all(
        {"label", "fill", "border", "opacity"} <= i.keys() for i in data["items"]
    )
    assert data["links"] == [ic.ICE_CHART_LINK]
    assert list(tmp_path.iterdir()) == [path]  # no temp file left behind


def test_legend_html_lists_every_class(tmp_path):
    path = tmp_path / "legend.html"
    ic.create_legend_html(str(path), FETCHED, PUBLISHED)
    html = path.read_text(encoding="utf-8")

    for ice_class in ic.ICE_CLASSES:
        assert ice_class["label"] in html
        assert f"background-color: {ice_class['fill']};" in html
        assert f"border: 1px solid {ice_class['border']};" in html
    assert "2026-10-10T08:00:00Z" in html
