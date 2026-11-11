#!/usr/bin/env python3
"""종합 리포트 빌더의 광고비·예산 Gross / Net 연결 검사(표준 라이브러리만). 규칙 자체는 test_fees.py.
기대값은 손으로 계산한 값이다: 마크업 Gross = Net × (1 + r/100), 커미션 Gross = Net ÷ (1 − r/100), 옛 서버는 Gross = Net × cost ÷ cost_net.
성공하면 "ok"."""

import importlib.util
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PLUGIN = os.path.normpath(os.path.join(HERE, ".."))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(PLUGIN, "shared", "assets"))

from test_fees import KEYS, OVERALL_TP, close, env, fee  # noqa: E402


def _builder(skill):
    path = os.path.join(PLUGIN, "skills", skill, "assets", "build_report.py")
    spec = importlib.util.spec_from_file_location(f"build_{skill.replace('-', '_')}", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


overall = _builder("overall-summary")


def test_overall_compute_served_gross():
    rows = [{"date": "2026-10-01", "media": m, "campaign_name": c, "cost": v, "impressions": 100}
            for m, c, v in (("Meta", "A", 1100), ("Google", "G", 500), ("Naver", "N", 400))]
    fl = [fee("Meta", "2026-10", "markup", 10), fee("Google", "2026-10", "commission", 20)]
    p = {"out": "unused.html", "brand": "b", "target_date": "2026-10-05", "start_date": "2026-10-01", "metric_keys": KEYS,
         "currency": "₩", "dims": "valid dimensions: ['date', 'media', 'campaign_name']",
         "data": {"json": json.dumps(env(rows, ["media", "campaign_name"], "gross", fl))},
         "budgets": [{"month": "2026-10", "target_progress": OVERALL_TP}]}
    report, out = overall.compute(p)
    assert report["fee"]["default"] == "gross" and "브랜드 기준 Gross" in report["fee"]["note"]
    by = {r["m"]: (r["cost"], r["cost_g"]) for r in out}
    assert by == {"Meta": (1000, 1100), "Google": (400, 500), "Naver": (400, 400)}, by

    def total(bs):
        return next(b["v"]["cost"] for b in bs if not b["scope"])
    assert total(report["table"]["budgets"]) == 3600 and close(total(report["table"]["budgets_net"]), 3100)
    rep, rs = overall.basis_view(report, out, "net")   # _net.xlsx가 보는 값
    assert rep["header"]["basis"] == "Net" and sorted(r["cost"] for r in rs) == [400, 400, 1000]


OLD_MONTH_TP = """month: 2026-10
as_of_date: 2026-10-31
media: all

| metric | target | actual | progress_ratio |
| --- | --- | --- | --- |
| cost | 2900 | 2300 | 0.79 |

| media | campaign_name | included | metric | target | actual | achievement |
| --- | --- | --- | --- | --- | --- | --- |
| Meta | - | - | cost | 1100 | 1100 | 1 |
| Meta | - | - | cost_net | 1000 | - | - |
| Meta | A | Y | cost | 660 | 500 | 0.76 |
| Meta | A | Y | cost_net | 550 | - | - |
| Google | - | - | cost | 1000 | 800 | 0.8 |
| Google | C | Y | cost | 600 | 700 | 1 |
| Google | C | Y | cost_net | 500 | - | - |
| Naver | - | - | cost | 800 | 400 | 0.5 |"""


OLD_OVERALL_TP = OLD_MONTH_TP.replace("as_of_date: 2026-10-31", "as_of_date: 2026-10-05")


def test_overall_old_server_gross_rows_net_budgets_and_placement():
    """옛 서버. Meta 비율 1.1(캠페인 A만 1.2), Google은 매체 cost_net이 없고 캠페인 C 600/500 = 1.2, Naver 수수료 없음."""
    data = [("Meta", "A", 500), ("Meta", "B", 600), ("Google", "C", 700), ("Google", "D", 100), ("Naver", "N", 400)]
    rows = [{"date": "2026-10-01", "media": m, "campaign_name": c, "cost": v, "impressions": 100} for m, c, v in data]
    prow = [{"date": "2026-10-01", "media": m, "placement": "feed", "cost": v, "impressions": 100}
            for m, v in (("Meta", 1100), ("Google", 800), ("Naver", 400))]
    p = {"out": "unused.html", "brand": "b", "target_date": "2026-10-05", "start_date": "2026-10-01", "metric_keys": KEYS,
         "currency": "₩", "dims": "valid dimensions: ['date', 'media', 'campaign_name']",
         "data": {"json": json.dumps(env(rows, ["media", "campaign_name"], None))},
         "place": {"json": json.dumps(env(prow, ["media", "placement"], None))},
         "budgets": [{"month": "2026-10", "target_progress": OLD_OVERALL_TP}]}
    report, out = overall.compute(p)
    g = {r["c"]: r["cost_g"] for r in out}
    # A 500 × 1.2, B 600 × Meta 1.1, C 700 × 1.2, D 100 × Google(캠페인 합 600/500) 1.2, N 400 × 1
    assert [round(g[c], 6) for c in "ABCDN"] == [600, 660, 840, 120, 400], g
    gross = {tuple(sorted(b["scope"].items())): b["v"]["cost"] for b in report["table"]["budgets"]}
    net = {tuple(sorted(b["scope"].items())): b["v"]["cost"] for b in report["table"]["budgets_net"]}
    assert gross[()] == 2900 and gross[(("m", "Google"),)] == 1000
    assert close(net[(("m", "Meta"),)], 1000) and close(net[(("c", "A"), ("m", "Meta"))], 550) and close(net[(("m", "Naver"),)], 800)
    assert close(net[(("m", "Google"),)], 900)   # cost_net 없음: 1000 − 캠페인 C 수수료(600 − 500)
    assert close(net[()], 2700)   # cost_net 없음: 2900 − 매체 수수료(Meta 100 + Google 100 + Naver 0)
    # Placement는 본 표의 (달, 매체) 실효 비율을 쓴다 — Meta (600 + 660) ÷ (500 + 600), Google (840 + 120) ÷ 800, Naver 1
    pl = report["place"]
    cg = {pl["dict"]["m"][i]: v for i, v in zip(pl["cols"]["m"], pl["cols"]["cost_g"])}
    assert close(cg["Meta"], 1260) and close(cg["Google"], 960) and close(cg["Naver"], 400), cg


def test_overall_stops_on_legacy_placement():
    rows = [{"date": "2026-10-01", "media": "Meta", "campaign_name": "A", "cost": 1100, "impressions": 100}]
    prow = [{"date": "2026-10-01", "media": "Meta", "placement": "feed", "cost": 1000, "impressions": 100}]
    p = {"out": "unused.html", "brand": "b", "target_date": "2026-10-05", "start_date": "2026-10-01", "metric_keys": KEYS,
         "currency": "₩", "dims": "valid dimensions: ['date', 'media', 'campaign_name']",
         "data": {"json": json.dumps(env(rows, ["media", "campaign_name"], "gross"))},
         "place": {"json": json.dumps(env(prow, ["media", "placement"], None))}}
    try:
        overall.compute(p)
    except SystemExit as e:
        assert "수수료 기준" in str(e.code)
        return
    raise AssertionError("fee_basis가 없는 Placement 응답에서 멈추지 않았다")


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
    print("ok")
