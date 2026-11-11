#!/usr/bin/env python3
"""Render a Laighthouse report payload into one self-contained HTML file.

The payload has the same shape the web app reads from `/api/analysis-artifact/{id}`
(plus a `meta` block), so the output matches the report page on app.laight.ai:

    {
      "meta":  {"type": "daily"|"mtd"|"monthly", "name": "...", "reference_date": "2026-10-11",
                "created": "2026-10-12 18:42", "author": "kjkim", "published": true,
                "brand": {"name": "라형식품", "advertiser": "Laight AI", "color": "rgb(63, 143, 115)", "initials": "라형"}},
      "items": [{"order": 1, "analysis_artifact": {"type": "target_progression", "data": {...}}}, ...]
    }

`build_report.py` writes this payload; you normally do not call this script directly.

Usage:
    python3 render_report.py <payload.json> <out.html>
"""

import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))

FONT_LINKS = (
    '<link rel="preconnect" href="https://cdn.jsdelivr.net">'
    '<link rel="stylesheet" href="https://cdn.jsdelivr.net/gh/orioncactus/pretendard@v1.3.9/dist/web/variable/'
    'pretendardvariable-dynamic-subset.min.css">'
    '<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;500;600;700&display=swap">'
)

# The web app shows the report under a top bar; standalone there is none.
STANDALONE_CSS = """
.app { min-width: 1120px; }  /* app min width (1440) minus its nav rail + sidebar (320) */
.ai-panel { top: 0; height: 100vh; }
.lh-ai-reopen { position: fixed; top: 16px; right: 20px; z-index: 10; }
@media print { .ai-panel, .lh-ai-reopen { display: none !important; } }
"""


def _read(name):
    with open(os.path.join(HERE, name), encoding="utf-8") as f:
        return f.read()


def _script(src):
    # Neutralise "</script" inside inlined code/data.
    return "<script>" + src.replace("</script", "<\\/script") + "</script>"


def render(payload):
    items = payload.get("items") or []
    needs_echarts = any(
        (it.get("analysis_artifact") or {}).get("type") == "tree_map"
        or any(c.get("type") == "tree_map" for c in ((it.get("analysis_artifact") or {}).get("data") or {}).get("components") or [])
        for it in items
    )
    data = json.dumps(payload, ensure_ascii=False)
    title = (payload.get("meta") or {}).get("name") or "Laighthouse report"
    parts = [
        "<!doctype html>",
        '<html lang="ko"><head><meta charset="utf-8">',
        '<meta name="viewport" content="width=device-width, initial-scale=1">',
        "<title>" + title.replace("<", "&lt;") + "</title>",
        FONT_LINKS,
        "<style>" + _read("app.css") + STANDALONE_CSS + "</style>",
        "</head><body>",
        '<div id="app"></div>',
        _script("window.__LH_REPORT__ = " + data + ";"),
        _script(_read("vendor/chart.umd.min.js")),
        _script(_read("vendor/chartjs-plugin-datalabels.min.js")),
        _script(_read("vendor/marked.umd.min.js")),
    ]
    if needs_echarts:
        parts.append(_script(_read("vendor/echarts.treemap.min.js")))
    parts.append(_script(_read("report.js")))
    parts.append("</body></html>")
    return "\n".join(parts)


def main():
    if len(sys.argv) != 3:
        sys.exit("usage: render_report.py <payload.json> <out.html>")
    with open(sys.argv[1], encoding="utf-8") as f:
        payload = json.load(f)
    out = os.path.expanduser(sys.argv[2])
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        f.write(render(payload))
    print(out)


if __name__ == "__main__":
    main()
