#!/usr/bin/env python3
"""보고서 엔진(shared/report_engine)의 응답 수집·목표 재요청·텍스트 입력 규칙 검사(표준 라이브러리 + pytest)."""

import json
import os
import sys
import time

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "shared", "report_engine"))

import build_report as br  # noqa: E402
import captures  # noqa: E402

TARGET = "get_target_progress_v2"


def test_repair_escapes_keeps_valid_pairs_and_fixes_lone_backslash():
    # 셸이 `\\_`를 `\_`로 줄인 부분과 이미 올바른 `\\_`, `\n`이 한 텍스트에 섞인 경우
    raw = r'{"t": "01\_x 02\\_y\nz \"q\""}'
    with pytest.raises(ValueError):
        json.loads(raw)
    assert json.loads(br.repair_escapes(raw)) == {"t": "01\\_x 02\\_y\nz \"q\""}


def test_repair_escapes_keeps_unicode_escape_but_fixes_backslash_u_text():
    raw = r'{"t": "\uac00 C:\user"}'
    assert json.loads(br.repair_escapes(raw)) == {"t": "가 C:\\user"}


def test_body_missing_from_index_is_still_found(tmp_path, monkeypatch):
    """병렬 호출의 훅이 index.jsonl에 동시에 덧붙이다 줄이 깨지거나 빠져도 본문 파일은 찾는다."""
    folder = tmp_path / "sess"
    folder.mkdir()
    monkeypatch.setattr(captures, "CAPTURE_ROOT", str(tmp_path))
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", "sess")
    ti = {"brand_name": "b", "start_date": "2026-08-01", "end_date": "2026-08-20", "time_grain": "day"}
    rec = {"tool_name": "mcp__x__get_ad_performance", "tool_input": ti, "saved_at": 5.0, "response": "{}"}
    (folder / "1_get_ad_performance.json").write_text(json.dumps(rec), encoding="utf-8")
    (folder / "index.jsonl").write_text('{"tool_name": "mcp__x__get_ad_perf', encoding="utf-8")   # 깨진 줄

    recs = captures.captured()

    assert [r["tool_input"] for r in recs] == [ti]


def test_target_planned_without_metric_names_accepts_call_that_named_them():
    planned = {"brand_name": "b", "month": "2026-11", "as_of_date": "2026-11-09"}
    rec = {"tool_name": "mcp__x__" + TARGET, "tool_input": dict(planned, cost_metric="spend", revenue_metric="rev")}
    assert captures.find_captured(TARGET, planned, records=[rec]) is rec


def test_target_planned_with_metric_names_rejects_call_without_them():
    planned = {"brand_name": "b", "month": "2026-11", "as_of_date": "2026-11-09", "cost_metric": "spend",
               "revenue_metric": "rev"}
    plain = {"tool_name": "mcp__x__" + TARGET, "tool_input": {"brand_name": "b", "month": "2026-11", "as_of_date": "2026-11-09"}}
    other = {"tool_name": "mcp__x__" + TARGET, "tool_input": dict(planned, cost_metric="광고비")}
    assert captures.find_captured(TARGET, planned, records=[plain, other]) is None


def test_other_tools_match_only_identical_arguments():
    planned = {"brand_name": "b", "start_date": "2026-11-01", "end_date": "2026-11-09", "time_grain": "day"}
    rec = {"tool_name": "mcp__x__get_ad_performance", "tool_input": dict(planned, metrics=["광고비"])}
    assert captures.find_captured("get_ad_performance", planned, records=[rec]) is None


@pytest.mark.parametrize("served, keys, expected", [
    # 서버 기본 선택(광고비 / 매출_AB→revenue→매출)과 보고서가 고른 지표가 같다 → 다시 부르지 않는다
    (["광고비", "매출", "클릭"], {"cost": "광고비", "revenue": "매출"}, {}),
    # 서버는 매출_AB를 읽는데 보고서는 매출을 쓴다 → 지표 이름을 붙여 다시 부른다
    (["광고비", "매출", "매출_AB"], {"cost": "광고비", "revenue": "매출"}, {"cost_metric": "광고비", "revenue_metric": "매출"}),
    # 서버 후보에 없는 광고비 이름(spend)
    (["spend", "revenue"], {"cost": "spend", "revenue": "revenue"}, {"cost_metric": "spend", "revenue_metric": "revenue"}),
])
def test_target_metric_args(served, keys, expected):
    assert captures.target_metric_args(keys, served) == expected


def test_collect_reads_body_of_the_newest_matching_index_record(tmp_path, monkeypatch):
    root, session = tmp_path / "captures", "sess-1"
    folder = root / session
    folder.mkdir(parents=True)
    params = {"brand_name": "b", "start_date": "2026-11-03", "end_date": "2026-11-09", "time_grain": "day"}
    stale = dict(params, start_date="2026-11-01")
    bodies = {"old.json": {"rows": [{"date": "2026-11-09", "광고비": 1}]},
              "new.json": {"rows": [{"date": "2026-11-09", "광고비": 2}]},
              "other.json": {"rows": [{"date": "2026-11-09", "광고비": 3}]},
              "prev_run.json": {"rows": [{"date": "2026-11-09", "광고비": 4}]}}
    started = time.time() - 100   # 이번 실행의 plan 시각 — 이보다 1분 넘게 먼저 저장된 응답(이전 실행)은 쓰지 않는다
    index = [("old.json", params, started + 30), ("other.json", dict(params, start_date="2026-11-02"), started + 50),
             ("new.json", params, started + 40), ("prev_run.json", stale, started - 120)]
    with open(folder / "index.jsonl", "w", encoding="utf-8") as f:
        for name, ti, at in index:
            f.write(json.dumps({"tool_name": "mcp__x__get_ad_performance", "tool_input": ti, "saved_at": at, "file": name}) + "\n")
            (folder / name).write_text(json.dumps({"response": json.dumps(bodies[name])}), encoding="utf-8")
    monkeypatch.setattr(captures, "CAPTURE_ROOT", str(root))
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", session)
    work = tmp_path / "work"
    (work / "responses").mkdir(parents=True)
    calls = [{"key": "trend7", "tool": "get_ad_performance", "params": params},
             {"key": "missing", "tool": "get_ad_performance", "params": dict(params, end_date="2026-11-10")},
             {"key": "stale", "tool": "get_ad_performance", "params": stale}]
    (work / "plan.json").write_text(json.dumps({"calls": calls, "started_at": started}), encoding="utf-8")

    got, missing = br.collect(str(work))

    assert (got, missing) == (["trend7"], ["missing", "stale"])
    assert br.envelope(str(work), "trend7")["rows"][0]["광고비"] == 2
