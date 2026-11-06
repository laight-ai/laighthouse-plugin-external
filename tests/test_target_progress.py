"""get_target_progress_v2 reads the same whether the server answers its JSON object or the old markdown.
"""

import filecmp
import importlib.util
import json
import os

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

MARKDOWN = "\n".join([
    "month: 2026-10",
    "as_of_date: 2026-10-31",
    "media: all",
    "fee_basis: net",
    "",
    "| metric | target | actual | progress_ratio |",
    "| --- | --- | --- | --- |",
    "| cost | 161400000 | 190828604 | 1.1823 |",
    "| revenue | 500000000 | 412345678 | 0.8247 |",
    "| roas | 3.0979 | 2.1608 | 0.6975 |",
    "",
    "| media | campaign_name | included | metric | target | actual | achievement |",
    "| --- | --- | --- | --- | --- | --- | --- |",
    "| Google | - | - | cost | 31300000 | 65858985 | 2.1041 |",
    "| Google | 2609_현대카드 카텔란_VRC ~10/5 | Y | cpv | 28 | - | - |",
    "| Meta | - | - | cost | 130100000 | 124969619 | 0.9606 |",
    "| Meta | - | - | revenue | 500000000 | 412345678 | 0.8247 |",
    "| Meta | - | - | roas | 3.8432 | 3.2996 | 0.8586 |",
    "| Meta | 브랜드 캠페인 | N | cost | 20000000 | 18000000 | 0.9 |",
    "",
    "| media | fee_mode | rate |",
    "| --- | --- | --- |",
    "| Google | commission | 10 |",
    "| Meta | commission | 15 |",
])

# The same month as the new server's object, written by hand from MARKDOWN.
OBJECT = {
    "status": "ok",
    "message": None,
    "month": "2026-10",
    "as_of_date": "2026-10-31",
    "media": "all",
    "fee_basis": "net",
    "summary": [
        {"metric": "cost", "target": 161400000, "actual": 190828604, "progress_ratio": 1.1823},
        {"metric": "revenue", "target": 500000000, "actual": 412345678, "progress_ratio": 0.8247},
        {"metric": "roas", "target": 3.0979, "actual": 2.1608, "progress_ratio": 0.6975},
    ],
    "scopes": [
        {"media": "Google", "campaign_name": None, "included": None, "metric": "cost",
         "target": 31300000, "actual": 65858985, "achievement": 2.1041},
        {"media": "Google", "campaign_name": "2609_현대카드 카텔란_VRC ~10/5", "included": True, "metric": "cpv",
         "target": 28, "actual": None, "achievement": None},
        {"media": "Meta", "campaign_name": None, "included": None, "metric": "cost",
         "target": 130100000, "actual": 124969619, "achievement": 0.9606},
        {"media": "Meta", "campaign_name": None, "included": None, "metric": "revenue",
         "target": 500000000, "actual": 412345678, "achievement": 0.8247},
        {"media": "Meta", "campaign_name": None, "included": None, "metric": "roas",
         "target": 3.8432, "actual": 3.2996, "achievement": 0.8586},
        {"media": "Meta", "campaign_name": "브랜드 캠페인", "included": False, "metric": "cost",
         "target": 20000000, "actual": 18000000, "achievement": 0.9},
    ],
    "fees": [
        {"media": "Google", "fee_mode": "commission", "rate": 10},
        {"media": "Meta", "fee_mode": "commission", "rate": 15},
    ],
}

# Hand-derived from the tables: (target, actual) of the first table's rows, as floats.
TARGET = {"cost": (161400000.0, 190828604.0), "revenue": (500000000.0, 412345678.0), "roas": (3.0979, 2.1608)}
MEDIA_BUDGET = {"Google": 31300000.0, "Meta": 130100000.0}

NO_REVENUE_MARKDOWN = "\n".join([
    "month: 2026-06",
    "as_of_date: 2026-06-15",
    "media: all",
    "fee_basis: net",
    "",
    "| metric | target | actual | progress_ratio |",
    "| --- | --- | --- | --- |",
    "| cost | 10000 | 3600 | 0.36 |",
    "| revenue | 0 | - | - |",
    "| roas | 0.0 | - | - |",
    "",
    "| media | campaign_name | included | metric | target | actual | achievement |",
    "| --- | --- | --- | --- | --- | --- | --- |",
    "| Google | - | - | cost | 10000 | 3600 | 0.36 |",
    "| Google | A | Y | cost | 6000 | 3000 | 0.5 |",
])
NO_REVENUE_OBJECT = {
    "status": "ok",
    "message": None,
    "month": "2026-06",
    "as_of_date": "2026-06-15",
    "media": "all",
    "fee_basis": "net",
    "summary": [
        {"metric": "cost", "target": 10000, "actual": 3600, "progress_ratio": 0.36},
        {"metric": "revenue", "target": 0, "actual": None, "progress_ratio": None},
        {"metric": "roas", "target": 0.0, "actual": None, "progress_ratio": None},
    ],
    "scopes": [
        {"media": "Google", "campaign_name": None, "included": None, "metric": "cost",
         "target": 10000, "actual": 3600, "achievement": 0.36},
        {"media": "Google", "campaign_name": "A", "included": True, "metric": "cost",
         "target": 6000, "actual": 3000, "achievement": 0.5},
    ],
    "fees": [],
}
NO_REVENUE_TARGET = {"cost": (10000.0, 3600.0), "revenue": (0.0, None), "roas": (0.0, None)}
NO_REVENUE_MEDIA_BUDGET = {"Google": 10000.0}

PLAIN_LINES = {
    "no_target": "No all budget/target available for 2026-10.",
    "no_cost_metric": ("No cost metric in the brand's data mart (looked for 광고비, cost); "
                       "available metrics: 노출, 클릭."),
    "no_media_dimension": "No 'media' dimension in the brand's data mart, so naver-only actuals cannot be computed.",
}


def not_ok(status, message):
    return {"status": status, "message": message, "month": "2026-10", "as_of_date": "2026-10-31", "media": "all",
            "fee_basis": "net", "summary": [], "scopes": [], "fees": []}


_SPEC = importlib.util.spec_from_file_location(
    "build_report", os.path.join(ROOT, "skills", "laighthouse-report", "assets", "build_report.py"))
br_module = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(br_module)


@pytest.fixture
def br():
    return br_module


def same(got, expected):
    return got == expected and repr(got) == repr(expected)


def save(tmp_path, text, key="target"):
    work = tmp_path / "work"
    (work / "responses").mkdir(parents=True, exist_ok=True)
    (work / "responses" / (key + ".json")).write_text(text, encoding="utf-8")
    return str(work)


@pytest.mark.parametrize("markdown, obj, target, media_budget", [
    (MARKDOWN, OBJECT, TARGET, MEDIA_BUDGET),
    (NO_REVENUE_MARKDOWN, NO_REVENUE_OBJECT, NO_REVENUE_TARGET, NO_REVENUE_MEDIA_BUDGET),
], ids=["month", "no-revenue-metric"])
def test_both_formats_read_the_same(br, markdown, obj, target, media_budget):
    for resp in (markdown, obj, json.dumps(obj, ensure_ascii=False)):
        assert same(br.parse_target(resp), target)
        assert same(br.parse_target_media(resp), media_budget)


@pytest.mark.parametrize("text", [
    MARKDOWN,
    json.dumps({"result": MARKDOWN}, ensure_ascii=False),
    json.dumps([{"type": "text", "text": MARKDOWN}]),
    json.dumps(OBJECT, ensure_ascii=False, indent=2),
    json.dumps(OBJECT),
    json.dumps([{"type": "text", "text": json.dumps(OBJECT, ensure_ascii=False)}]),
    json.dumps({"content": [{"type": "text", "text": json.dumps(OBJECT, indent=2)}], "structuredContent": OBJECT}),
], ids=["markdown", "result-wrapper", "content-list-markdown", "json-indented", "json", "content-list-json",
        "content-dict-json"])
def test_saved_response_shapes(br, tmp_path, text):
    work = save(tmp_path, text)
    resp = br.load_response(work, "target")
    assert same(br.parse_target(resp), TARGET)
    assert same(br.parse_target_media(resp), MEDIA_BUDGET)


def test_media_cost_target_reads_the_saved_json(br, tmp_path):
    work = save(tmp_path, json.dumps(OBJECT))
    assert br.media_cost_target(work, "google") == 31300000.0
    assert br.media_cost_target(work, "Kakao") is None


@pytest.mark.parametrize("status", sorted(PLAIN_LINES))
def test_status_other_than_ok_is_no_target(br, status):
    for resp in (PLAIN_LINES[status], not_ok(status, PLAIN_LINES[status]),
                 json.dumps(not_ok(status, PLAIN_LINES[status]))):
        assert br.parse_target(resp) is None
        assert br.parse_target_media(resp) == {}


def test_status_decides_even_when_rows_are_present(br):
    for status in ("no_target", "some_future_status"):
        resp = dict(OBJECT, status=status, message="x")
        assert br.parse_target(resp) is None
        assert br.parse_target_media(resp) == {}


def test_target_section_is_the_same(br, tmp_path):
    def section(text):
        return br.target_progression({}, save(tmp_path, text), 31, 31, (1000.0, 3000.0))["analysis_artifact"]["data"]

    def item(name, display, target, actual):
        return {"name": name, "display": display, "target": target, "expected": target, "actual": actual,
                "unit": None, "change_rate": None}

    expected = [
        item("월 예산 목표", "월 예산대비 소진율", 161400000.0, 190828604),
        item("월 매출 목표", "월 목표 매출 대비 달성률", 500000000.0, 412345678),
        item("월 ROAS 목표", "월 누적 ROAS", 3.0979, 2.1608),
    ]
    fallback = [
        item("월 예산 목표", "월 예산대비 소진율", 0, 1000),
        item("월 매출 목표", "월 목표 매출 대비 달성률", 0, 3000),
        item("월 ROAS 목표", "월 누적 ROAS", 0, 3),
    ]
    for text, items in ((MARKDOWN, expected), (json.dumps(OBJECT), expected),
                        (PLAIN_LINES["no_target"], fallback), (json.dumps(not_ok("no_target", "x")), fallback)):
        got = section(text)["items"]
        assert json.dumps(got) == json.dumps(items)


@pytest.mark.parametrize("original, gpt_copy", [
    ("skills/laighthouse-report/assets/build_report.py", "gpt/skills/laighthouse-report/assets/build_report.py"),
    ("hooks/save_mcp_response.py", "gpt/hooks/save_mcp_response.py"),
])
def test_gpt_copies_are_byte_identical(original, gpt_copy):
    assert filecmp.cmp(os.path.join(ROOT, original), os.path.join(ROOT, gpt_copy), shallow=False), (
        "%s differs from %s: run `python gpt/sync_from_claude.py`" % (gpt_copy, original))
