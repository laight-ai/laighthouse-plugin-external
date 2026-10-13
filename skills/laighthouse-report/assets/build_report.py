#!/usr/bin/env python3
"""Laighthouse report builder — reproduces the daily / MTD / monthly reports of app.laight.ai.

Sub-commands, run in order (see SKILL.md):

  arm     Turn on response capture for this session (before the first MCP call). The plugin
          hook (hooks/save_mcp_response.py) only saves responses while capture is armed.
            python3 build_report.py arm

  plan    Decide the dates and print the exact MCP calls to make.
            python3 build_report.py plan --type daily --brand 라형식품 --date 2026-10-11 \
                --discovery <discovery.json> --work <work_dir> [--author kjkim] [--advertiser "Laight AI"]
          Writes <work_dir>/plan.json and prints the call list as JSON.

  collect Copy the responses saved by the plugin hook (hooks/save_mcp_response.py) into
          <work_dir>/responses/ by matching tool name + arguments to the plan.
            python3 build_report.py collect --work <work_dir>

  data    Build every number/table/chart section from the saved MCP responses.
            python3 build_report.py data --work <work_dir>
          Reads <work_dir>/responses/<key>.json (one file per planned call), writes
          <work_dir>/data.json and prints a compact "facts" digest to write the texts from.

  render  Merge the texts + action cards and write the final HTML, then delete the captured
          responses this report used.
            python3 build_report.py render --work <work_dir> --texts <texts.json> --out <file.html>

Response files may contain the raw JSON envelope returned by the tool, the tool's text
wrapper ({"result": "..."} or [{"type": "text", "text": "..."}]), or plain text (for
get_target_progress_v2 / list_promotions). Values are never estimated: a missing
response makes the dependent section disappear, exactly like the web app's
"데이터 준비 중" behaviour.
"""

import argparse
import calendar
import collections
import datetime as dt
import json
import math
import os
import re
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

KST = dt.timezone(dt.timedelta(hours=9))

# ───────────────────────────── media / metric vocab ─────────────────────────────
MEDIA_LABEL = {
    "BRS": "네이버 브랜드검색",
    "PLINK": "네이버 파워링크",
    "NVSHOP": "네이버 쇼핑검색",
    "NVGFA_ADVOOST": "네이버 GFA 애드부스트",
    "NVGFA_DISPLAY": "네이버 GFA 디스플레이",
}
MEDIA_ORDER = ["BRS", "PLINK", "NVSHOP", "NVGFA_ADVOOST", "NVGFA_DISPLAY"]
SEARCH_MEDIA = ["BRS", "PLINK", "NVSHOP"]  # keyword-search channels (keyword tables)
MEDIA_GROUP = "SA / DA"

ROLE_CANDIDATES = {
    "cost": ["광고비", "cost", "spend", "spending"],
    "impression": ["노출", "impression", "impressions", "imps"],
    "click": ["클릭", "click", "clicks"],
    "conversion": ["전환", "conversion", "conversions", "구매", "구매수", "purchase", "purchases"],
    "revenue": ["매출", "revenue"],
    "roas": ["roas"],
}

# Korean public holidays (incl. 대체공휴일) — the web app's calendar artifact lists the ones
# inside the 7-day window with type "holyday" / description "브랜드 정보".
KR_HOLIDAYS = {
    "2025-01-01": "신정", "2025-01-28": "설날 연휴", "2025-01-29": "설날", "2025-01-30": "설날 연휴",
    "2025-03-01": "삼일절", "2025-03-03": "삼일절 대체 휴일", "2025-05-05": "어린이날·부처님오신날",
    "2025-05-06": "어린이날 대체 휴일", "2025-06-03": "대통령 선거일", "2025-06-06": "현충일",
    "2025-08-15": "광복절", "2025-10-03": "개천절", "2025-10-05": "추석 연휴", "2025-10-06": "추석",
    "2025-10-07": "추석 연휴", "2025-10-08": "추석 대체 휴일", "2025-10-09": "한글날", "2025-12-25": "성탄절",
    "2026-01-01": "신정", "2026-02-16": "설날 연휴", "2026-02-17": "설날", "2026-02-18": "설날 연휴",
    "2026-03-01": "삼일절", "2026-03-02": "삼일절 대체 휴일", "2026-05-05": "어린이날",
    "2026-05-24": "부처님오신날", "2026-05-25": "부처님오신날 대체 휴일", "2026-06-03": "전국동시지방선거일",
    "2026-06-06": "현충일", "2026-08-15": "광복절", "2026-08-17": "광복절 대체 휴일",
    "2026-09-24": "추석 연휴", "2026-09-25": "추석", "2026-09-26": "추석 연휴",
    "2026-10-03": "개천절", "2026-10-05": "개천절 대체 휴일", "2026-10-09": "한글날", "2026-12-25": "성탄절",
    "2027-01-01": "신정", "2027-02-06": "설날 연휴", "2027-02-07": "설날", "2027-02-08": "설날 연휴",
    "2027-02-09": "설날 대체 휴일", "2027-03-01": "삼일절", "2027-05-05": "어린이날",
    "2027-05-13": "부처님오신날", "2027-06-06": "현충일", "2027-08-15": "광복절",
    "2027-08-16": "광복절 대체 휴일", "2027-09-14": "추석 연휴", "2027-09-15": "추석",
    "2027-09-16": "추석 연휴", "2027-10-03": "개천절", "2027-10-04": "개천절 대체 휴일",
    "2027-10-09": "한글날", "2027-10-11": "한글날 대체 휴일", "2027-12-25": "성탄절", "2027-12-27": "성탄절 대체 휴일",
}

WORKFLOW = {"daily": "2026_daily v1.3", "mtd": "2026_MTD_V1.11", "monthly": "2026_Monthly v1.1"}
KIND = {"daily": "일간", "mtd": "MTD", "monthly": "월 마감"}


# ───────────────────────────── small helpers ─────────────────────────────
def d(s):
    return dt.date.fromisoformat(s)


def iso(x):
    return x.isoformat()


def add_days(x, n):
    return x + dt.timedelta(days=n)


def month_start(x):
    return x.replace(day=1)


def month_end(x):
    return x.replace(day=calendar.monthrange(x.year, x.month)[1])


def add_months(x, n):
    y, m = divmod(x.month - 1 + n, 12)
    return dt.date(x.year + y, m + 1, 1)


def days_between(a, b):
    return [iso(add_days(a, i)) for i in range((b - a).days + 1)]


def yymm_label(ym):  # "2026-09" -> "26년 9월"
    y, m = ym.split("-")
    return f"{y[2:]}년 {int(m)}월"


def yyyymm_label(ym):  # "2026-09" -> "2026년 9월"
    y, m = ym.split("-")
    return f"{y}년 {int(m)}월"


def f0(x):
    return f"{x:,.0f}"


def f2(x):
    return f"{x:,.2f}"


def nz(x):
    return 0 if x is None else x


def media_sort_key(code, cost_lookup=None):
    if code in MEDIA_ORDER:
        return (0, MEDIA_ORDER.index(code), "")
    return (1, -(cost_lookup or {}).get(code, 0), str(code))


def media_label(code):
    return MEDIA_LABEL.get(code, code)


# ───────────────────────────── response loading ─────────────────────────────
def _unwrap(obj):
    """Peel MCP text wrappers until we reach the payload."""
    for _ in range(5):
        if isinstance(obj, list) and obj and all(isinstance(b, dict) and "text" in b for b in obj):
            obj = "\n".join(b["text"] for b in obj)
        elif isinstance(obj, dict) and set(obj.keys()) <= {"result", "type", "text"} and ("result" in obj or "text" in obj):
            obj = obj.get("result", obj.get("text"))
        elif isinstance(obj, dict) and isinstance(obj.get("content"), list):
            obj = obj["content"]
        else:
            break
        if isinstance(obj, str):
            s = obj.strip()
            if s[:1] in "[{":
                try:
                    obj = json.loads(s)
                    continue
                except ValueError:
                    pass
            return obj
    return obj


# When a result exceeds the host's token limit the tool output (and what the hook receives)
# is only a notice pointing at the saved full output. Same pattern as hooks/save_mcp_response.py.
SPILL_RE = re.compile(r"^Error: result \([\d,]+ characters\) exceeds maximum allowed tokens\. Output has been saved to (.+?)\.?$")


def spilled_path(text):
    m = SPILL_RE.match(str(text).lstrip().split("\n", 1)[0].strip())
    if not m:
        return None
    path = m.group(1).strip()
    return path if os.path.basename(os.path.dirname(path)) == "tool-results" else None


def resolve_spill(text):
    """The full output for a spill notice (None if unreadable); other text unchanged."""
    path = spilled_path(text)
    if not path:
        return text
    try:
        with open(path, encoding="utf-8") as f:
            return f.read()
    except OSError:
        return None


def is_envelope(text):
    """True when `text` is a get_ad_performance data envelope (JSON with `rows`)."""
    try:
        obj = _unwrap(json.loads(text))
    except ValueError:
        return False
    return isinstance(obj, dict) and isinstance(obj.get("rows"), list)


def load_response(work, key):
    path = os.path.join(work, "responses", key + ".json")
    if not os.path.exists(path):
        alt = os.path.join(work, "responses", key + ".txt")
        if not os.path.exists(alt):
            return None
        path = alt
    with open(path, encoding="utf-8") as f:
        raw = resolve_spill(f.read())
    if raw is None:
        return None
    s = raw.strip()
    if not s:
        return None
    try:
        obj = json.loads(s)
    except ValueError:
        return s
    return _unwrap(obj)


CAPTURE_ROOT = os.path.join(__import__("tempfile").gettempdir(), "laighthouse_mcp_responses")
CAPTURES_USED = ".captures_used.json"  # in <work_dir>: capture files to delete after render


def _canon(params):
    return json.dumps({k: v for k, v in (params or {}).items() if v is not None}, ensure_ascii=False, sort_keys=True)


def session_id():
    """Claude Code session id (same value the hook receives), or "" when unknown."""
    return "".join(c for c in os.environ.get("CLAUDE_CODE_SESSION_ID", "") if c.isalnum() or c in "-_")


def arm_path():
    return os.path.join(CAPTURE_ROOT, session_id() or "_any", ".armed")


def armed_since(default):
    """When capture was armed (minus a minute of slack), else `default`."""
    try:
        return os.path.getmtime(arm_path()) - 60
    except OSError:
        return default


def capture_folders():
    """This session's capture folder only; every session's when the session id is unknown."""
    sess = session_id()
    if sess:
        return [os.path.join(CAPTURE_ROOT, sess)]
    if not os.path.isdir(CAPTURE_ROOT):
        return []
    return [os.path.join(CAPTURE_ROOT, n) for n in os.listdir(CAPTURE_ROOT) if n != "_any"]


def captured(since=0.0):
    """Responses saved by hooks/save_mcp_response.py, newest first."""
    out = []
    for folder in capture_folders():
        if not os.path.isdir(folder):
            continue
        for name in os.listdir(folder):
            if not name.endswith(".json"):
                continue
            path = os.path.join(folder, name)
            try:
                if os.path.getmtime(path) < since:
                    continue
                with open(path, encoding="utf-8") as f:
                    rec = json.load(f)
            except (OSError, ValueError):
                continue
            rec["_path"] = path
            out.append(rec)
    out.sort(key=lambda r: r.get("saved_at", 0), reverse=True)
    return out


def find_captured(tool, params, since=0.0, records=None):
    want = _canon(params)
    for rec in records if records is not None else captured(since):
        if str(rec.get("tool_name", "")).endswith("__" + tool) or rec.get("tool_name") == tool:
            if _canon(rec.get("tool_input")) == want:
                return rec
    return None


def envelope(work, key):
    r = load_response(work, key)
    if isinstance(r, dict) and "rows" in r:
        return r
    return None


def resolve_metrics(metrics):
    """role -> metric key, from an envelope's `metrics` list."""
    out = {}
    low = {m.lower(): m for m in metrics}
    for role, cands in ROLE_CANDIDATES.items():
        hit = next((low[c.lower()] for c in cands if c.lower() in low), None)
        if not hit:
            pref = [m for m in metrics if any(m.lower().startswith(c.lower() + "_") for c in cands)]
            if len(pref) == 1:
                hit = pref[0]
        if hit:
            out[role] = hit
    return out


def parse_target(text):
    """get_target_progress_v2 markdown -> {'cost': (target, actual), ...} or None (no target)."""
    if text is None:
        return None
    if isinstance(text, dict):
        text = text.get("result") or json.dumps(text)
    rows = {}
    for line in str(text).splitlines():
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) >= 3 and cells[0] in ("cost", "revenue", "roas"):
            def num(v):
                try:
                    return float(v.replace(",", ""))
                except ValueError:
                    return None
            rows[cells[0]] = (num(cells[1]), num(cells[2]))
    return rows or None


def parse_promotions(obj):
    if isinstance(obj, list):
        return [p for p in obj if isinstance(p, dict)]
    if isinstance(obj, dict) and isinstance(obj.get("promotions"), list):
        return obj["promotions"]
    return []


def artifact(atype, data, order=None):
    return {"order": order, "analysis_artifact": {"type": atype, "data": data}}


def as_int_if_whole(x):
    return int(x) if isinstance(x, float) and x.is_integer() else x


# ───────────────────────────── plan ─────────────────────────────
def gap(brand, key, start, end, grain, group_by=None, metrics=None, filters=None, day_offset=None, purpose=""):
    p = {"brand_name": brand, "start_date": iso(start), "end_date": iso(end), "time_grain": grain}
    if group_by:
        p["group_by"] = group_by
    if metrics is not None:
        p["metrics"] = metrics
    if filters:
        p["filters"] = filters
    if day_offset:
        p["day_offset"] = day_offset
    return {"key": key, "tool": "get_ad_performance", "params": p, "purpose": purpose}


def cmd_plan(a):
    work = os.path.abspath(os.path.expanduser(a.work))
    os.makedirs(os.path.join(work, "responses"), exist_ok=True)
    disc = None
    used = []
    if a.discovery == "auto":
        for rec in captured(armed_since(time.time() - 6 * 3600)):
            ti = rec.get("tool_input") or {}
            if str(rec.get("tool_name", "")).endswith("get_ad_performance") and ti.get("brand_name") == a.brand \
                    and ti.get("group_by") == ["media"] and not ti.get("metrics") and ti.get("time_grain") == "total":
                resp = resolve_spill(rec["response"]) or ""
                disc = _unwrap(json.loads(resp) if resp.strip()[:1] in "[{" else resp)
                used.append(rec["_path"])
                break
        if not isinstance(disc, dict):
            sys.exit("no captured discovery response found — save it to a file and pass --discovery <file>")
    elif a.discovery:
        with open(os.path.expanduser(a.discovery), encoding="utf-8") as f:
            disc = _unwrap(json.loads(f.read()))
    metrics = (disc or {}).get("metrics") or ["광고비", "노출", "클릭", "전환", "매출", "ROAS"]
    roles = resolve_metrics(metrics)
    missing = [r for r in ("cost", "impression", "click", "revenue") if r not in roles]
    if missing:
        sys.exit(f"metric roles not found in discovery metrics {metrics}: {missing} — this skill needs 광고비/노출/클릭/매출")
    K = roles
    base = [K["cost"], K["impression"], K["click"]] + ([K["conversion"]] if "conversion" in K else []) + [K["revenue"]]
    media = []
    if disc and disc.get("rows"):
        media = sorted({r.get("media") for r in disc["rows"] if r.get("media")}, key=media_sort_key)
    b = a.brand
    t = a.type
    calls = []
    if t == "daily":
        D0 = d(a.date)
        ms = month_start(D0)
        calls += [
            {"key": "target", "tool": "get_target_progress_v2", "params": {"brand_name": b, "month": D0.strftime("%Y-%m"), "as_of_date": iso(D0), "cost_metric": K["cost"], "revenue_metric": K["revenue"]}, "purpose": "목표 달성 현황"},
            gap(b, "media_day", ms, D0, "day", ["media"], [K["cost"], K["revenue"]], purpose="광고 채널 성과(당일·월 누적·적정 광고비)"),
            gap(b, "trend7", add_days(D0, -6), D0, "day", None, [K["cost"], K["revenue"]], purpose="최근 7일 일별 광고 성과 차트"),
            gap(b, "treemap", add_days(D0, -7), D0, "day", ["media", "campaign_name", "ad_group_name"], base, purpose="성과 진단 트리맵 (대용량)"),
            gap(b, "detail", add_days(D0, -30), D0, "total", ["media", "campaign_name", "ad_group_name", "ad_name"], base, purpose="캠페인/광고그룹/키워드 표 (대용량)"),
            {"key": "promotions", "tool": "list_promotions", "params": {"brand_name": b, "start_date": iso(D0), "end_date": iso(D0)}, "purpose": "프로모션"},
        ]
        calls += [{"key": f"target_media.{m}", "tool": "get_target_progress_v2", "params": {"brand_name": b, "month": D0.strftime("%Y-%m"), "media": m, "as_of_date": iso(D0), "cost_metric": K["cost"], "revenue_metric": K["revenue"]}, "purpose": "매체별 월 예산 (적정 광고비)"} for m in media]
        calls += [  # optional context for the written summary
            gap(b, "ctx_daily", add_months(ms, -1), D0, "day", None, base, purpose="(텍스트용) 전월 1일~D0 일별 합계: 직전 7일·전월 일평균 비교"),
        ]
    elif t == "mtd":
        E = d(a.date)
        S = month_start(E)
        calls += [
            {"key": "target", "tool": "get_target_progress_v2", "params": {"brand_name": b, "month": E.strftime("%Y-%m"), "as_of_date": iso(E), "cost_metric": K["cost"], "revenue_metric": K["revenue"]}, "purpose": "목표 달성 현황"},
            gap(b, "months", add_months(S, -5), E, "month", None, [K["cost"], K["revenue"]] + ([K["roas"]] if "roas" in K else []), purpose="월별 광고 성과 (최근 6개월, 당월은 MTD)"),
            gap(b, "cat_month", add_months(S, -12), E, "month", ["product_category"], [K["revenue"]], day_offset=E.day, purpose="카테고리별 누적 판매액·MoM (같은 기간 비교)"),
            gap(b, "cat_day", S, E, "day", ["product_category"], [K["revenue"]], purpose="일일 카테고리별 매출"),
            gap(b, "daily_media", S, E, "day", ["media"], [K["cost"], K["click"]] + ([K["conversion"]] if "conversion" in K else []) + [K["revenue"]], purpose="매체 예산 소진 실적 + 일별 광고기여 매출"),
            gap(b, "detail", S, E, "total", ["media", "campaign_name", "ad_group_name", "ad_name"], base, purpose="캠페인/그룹/키워드 표 (대용량)"),
            {"key": "promotions", "tool": "list_promotions", "params": {"brand_name": b, "start_date": iso(S), "end_date": iso(E)}, "purpose": "프로모션"},
        ]
        calls += [{"key": f"target_media.{m}", "tool": "get_target_progress_v2", "params": {"brand_name": b, "month": E.strftime("%Y-%m"), "media": m, "as_of_date": iso(E), "cost_metric": K["cost"], "revenue_metric": K["revenue"]}, "purpose": "매체별 월 예산 소진 현황"} for m in media]
        calls += [  # optional context for the written analyses
            gap(b, "ctx_months_same_period", add_months(S, -12), E, "month", None, [K["cost"], K["revenue"]] + ([K["roas"]] if "roas" in K else []), day_offset=E.day, purpose="(텍스트용) 전월·3개월·전년 동기간 비교"),
            gap(b, "ctx_groups_prev", add_months(S, -1), min(add_days(add_months(S, -1), E.day - 1), add_days(S, -1)), "total", ["media", "campaign_name", "ad_group_name"], base, purpose="(텍스트용) 전월 동기간 광고그룹 성과"),
            gap(b, "ctx_cat_groups", S, E, "total", ["product_category", "media", "campaign_name", "ad_group_name"], [K["cost"], K["revenue"]], purpose="(텍스트용) 광고그룹↔카테고리 연결"),
            gap(b, "ctx_groups_3m", add_months(S, -3), E, "month", ["media", "campaign_name", "ad_group_name"], [K["cost"], K["revenue"]], day_offset=E.day, purpose="(텍스트용) 광고그룹 ROAS 최근 3개월 동기간 추이"),
        ]
    elif t == "monthly":
        M = month_start(d(a.date if len(a.date) > 7 else a.date + "-01"))
        ME = month_end(M)
        P = add_months(M, -1)
        calls += [
            {"key": "target", "tool": "get_target_progress_v2", "params": {"brand_name": b, "month": M.strftime("%Y-%m"), "as_of_date": iso(ME), "cost_metric": K["cost"], "revenue_metric": K["revenue"]}, "purpose": "목표 달성 현황"},
            gap(b, "months", add_months(M, -12), ME, "month", None, [K["cost"], K["revenue"]] + ([K["roas"]] if "roas" in K else []), purpose="월별 광고 성과 (차트는 최근 6개월, 13개월은 텍스트용)"),
            gap(b, "cat_month", add_months(M, -12), ME, "month", ["product_category"], [K["revenue"]], purpose="카테고리별 매출액 비교 (전월 vs 당월, 전년 동월은 텍스트용)"),
            gap(b, "cat_day", M, ME, "day", ["product_category"], [K["revenue"]], purpose="일일 카테고리별 매출"),
            gap(b, "media_month", P, ME, "month", ["media"], [K["cost"], K["revenue"]] + ([K["roas"]] if "roas" in K else []), purpose="매체 별 성과 비교"),
        ]
        calls += [
            gap(b, "ctx_groups", P, ME, "month", ["product_category", "media", "campaign_name", "ad_group_name"], base, purpose="(텍스트용) 캠페인·광고그룹·카테고리 전월 대비"),
            {"key": "ctx_promotions", "tool": "list_promotions", "params": {"brand_name": b, "start_date": iso(M), "end_date": iso(ME)}, "purpose": "(텍스트용) 월 중 프로모션"},
        ]
    else:
        sys.exit("--type must be daily, mtd or monthly")
    plan = {
        "type": t, "brand": b, "date": a.date, "metric_keys": K, "media": media, "work": work,
        "author": a.author or "", "advertiser": a.advertiser or "", "brand_color": a.brand_color or "rgb(63, 143, 115)",
        "brand_initials": a.brand_initials or b[:2], "published": not a.unpublished,
        "created": a.created or dt.datetime.now(KST).strftime("%Y-%m-%d %H:%M"),
        "calls": calls,
    }
    with open(os.path.join(work, "plan.json"), "w", encoding="utf-8") as f:
        json.dump(plan, f, ensure_ascii=False, indent=1)
    note_used(work, used)
    print(json.dumps({"plan": os.path.join(work, "plan.json"), "responses_dir": os.path.join(work, "responses"),
                      "calls": [{"key": c["key"], "tool": c["tool"], "params": c["params"]} for c in calls]}, ensure_ascii=False, indent=1))


# ───────────────────────────── shared sections ─────────────────────────────
def target_progression(plan, work, period_total, period_current, fallback):
    """fallback = (cost_actual, revenue_actual) used when no target exists."""
    t = parse_target(load_response(work, "target"))
    if t:
        cost, rev, roas = t.get("cost", (0, 0)), t.get("revenue", (0, 0)), t.get("roas", (0, 0))
    else:
        c, r = fallback
        cost, rev, roas = (0, c), (0, r), (0, (r / c) if c else 0)

    def item(name, display, tv, av):
        tv, av = nz(tv), nz(av)
        return {"name": name, "display": display, "target": tv, "expected": tv, "actual": as_int_if_whole(av), "unit": None, "change_rate": None}

    return artifact("target_progression", {
        "slot_key": "target_progression", "type": "target_progression", "name": "목표 달성 현황",
        "period": {"total": period_total, "current": period_current},
        "items": [
            item("월 예산 목표", "월 예산대비 소진율", cost[0], cost[1]),
            item("월 매출 목표", "월 목표 매출 대비 달성률", rev[0], rev[1]),
            item("월 ROAS 목표", "월 누적 ROAS", roas[0], roas[1]),
        ]}, 1)


def media_cost_target(work, code):
    t = parse_target(load_response(work, "target_media." + code))
    if not t or "cost" not in t or not t["cost"][0]:
        return None
    return t["cost"][0]


def months_chart(env, K, months, slot="ad_performance_recent_months"):
    rows = {r["month"]: r for r in env["rows"]}
    cost, rev, roas = [], [], []
    for ym in months:
        r = rows.get(ym, {})
        c, v = nz(r.get(K["cost"])), nz(r.get(K["revenue"]))
        rr = r.get(K["roas"]) if "roas" in K else None
        if rr is None:
            rr = v / c * 100 if c else 0
        cost.append({"x": yymm_label(ym), "y": round(c)})
        rev.append({"x": yymm_label(ym), "y": as_int_if_whole(v) if isinstance(v, float) else v})
        roas.append({"x": yymm_label(ym), "y": round(rr, 4)})
    return {"slot_key": slot, "type": "chart", "name": "월별 광고 성과", "chart_series": [
        {"type": "chart_component", "name": "광고비", "label": "광고비", "unit": "KRW", "items": cost},
        {"type": "chart_component", "name": "매출", "label": "매출", "unit": "KRW", "items": rev},
        {"type": "chart_component", "name": "ROAS", "label": "ROAS", "unit": "%", "items": roas}]}


def cat_totals(env, K, month_key):
    out = collections.defaultdict(float)
    for r in env["rows"]:
        if r.get("month") == month_key and r.get("product_category") is not None:
            out[r["product_category"]] += nz(r.get(K["revenue"]))
    return out


def cat_daily_series(env, K, cats, dates):
    by = collections.defaultdict(dict)
    for r in env["rows"]:
        if r.get("product_category") is not None:
            by[r["product_category"]][r["date"]] = by[r["product_category"]].get(r["date"], 0) + nz(r.get(K["revenue"]))
    series = []
    for c in cats:
        series.append({"type": "chart_component", "name": c, "label": c, "unit": "KRW",
                       "items": [{"x": x, "y": as_int_if_whole(float(by[c].get(x, 0)))} for x in dates]})
    return series


def promo_items(work):
    return parse_promotions(load_response(work, "promotions"))


# ───────────────────────────── daily ─────────────────────────────
def build_daily(plan, work):
    K = plan["metric_keys"]
    D0 = d(plan["date"])
    D0s = iso(D0)
    ms = month_start(D0)
    nd = calendar.monthrange(D0.year, D0.month)[1]
    items, facts = [], {"type": "daily", "date": D0s}
    C, R, I, CL = K["cost"], K["revenue"], K["impression"], K["click"]
    CV = K.get("conversion")

    md = envelope(work, "media_day")
    mtd_cost = mtd_rev = 0.0
    by_media = collections.defaultdict(dict)
    if md:
        for r in md["rows"]:
            by_media[r.get("media")][r["date"]] = r
            mtd_cost += nz(r.get(C))
            mtd_rev += nz(r.get(R))
    items.append(target_progression(plan, work, nd, D0.day, (mtd_cost, mtd_rev)))

    items.append(artifact("text", {"slot_key": "daily_executive_summary", "type": "text", "name": f"{D0.month}월 {D0.day}일의 성과요약", "items": []}, 2))

    # 최근 7일 일별 광고 성과
    tr = envelope(work, "trend7")
    if tr:
        days7 = days_between(add_days(D0, -6), D0)
        rows = {r["date"]: r for r in tr["rows"]}
        cs, rs, ro = [], [], []
        for x in days7:
            r = rows.get(x, {})
            c, v = nz(r.get(C)), nz(r.get(R))
            cs.append({"x": x, "y": as_int_if_whole(float(c))})
            rs.append({"x": x, "y": as_int_if_whole(float(v))})
            ro.append({"x": x, "y": round(v / c * 100) if c else 0})
        events = [{"name": KR_HOLIDAYS[x], "type": "holyday", "description": "브랜드 정보", "start_date": x, "end_date": x} for x in days7 if x in KR_HOLIDAYS]
        for p in parse_promotions(load_response(work, "promotions")):
            events.append({"name": p.get("title", ""), "type": "promotion", "description": p.get("info") or "", "start_date": p.get("start_date") or p.get("date_begin"), "end_date": p.get("end_date") or p.get("date_end")})
        items.append(artifact("component_group", {"slot_key": "daily_ad_performance_group", "type": "component_group", "name": "최근 7일 일별 광고 성과", "components": [
            {"slot_key": "daily_ad_performance_chart", "type": "chart", "name": None, "chart_series": [
                {"type": "chart_component", "name": "광고비", "label": "광고비", "unit": "KRW", "items": cs},
                {"type": "chart_component", "name": "매출", "label": "매출", "unit": "KRW", "items": rs},
                {"type": "chart_component", "name": "ROAS", "label": "ROAS", "unit": "%", "items": ro}]},
            {"slot_key": "promotion_calendar", "name": "프로모션 캘린더", "type": "calendar", "start_date": days7[0], "end_date": days7[-1], "events": events}]}, 3))

    # 성과 진단 트리맵
    tm = envelope(work, "treemap")
    if tm:
        win = days_between(add_days(D0, -7), add_days(D0, -1))
        W = set(win + [D0s])
        M5 = [C, I, CL, CV, R] if CV else [C, I, CL, R]
        agg = collections.OrderedDict()
        camp = collections.OrderedDict()
        for r in tm["rows"]:
            k = (r.get("campaign_name"), r.get("ad_group_name"))
            if k[0] is None:
                continue
            for tgt, key in ((agg, k), (camp, k[0])):
                byd = tgt.setdefault(key, collections.defaultdict(collections.Counter))
                byd[r["date"]].update({m: nz(r.get(m)) for m in M5})

        def rate(n, dn):
            return n / dn * 100 if dn else 0

        def vals(src, kind):
            t = src.get(D0s, collections.Counter())
            if kind == 0:
                avg = sum(src.get(x, collections.Counter())[R] for x in win) / 7
                return [str(round(t[C])), str(round(t[R])), str(round(avg)), f"{(t[R] / avg if avg else 0):.2f}"]
            num, den = ((CL, I) if kind == 1 else (CV, CL))
            tv = rate(t[num], t[den]) if num else 0
            avg = sum(rate(src.get(x, collections.Counter())[num], src.get(x, collections.Counter())[den]) for x in win) / 7 if num else 0
            return [str(round(t[den])), f"{tv:.2f}", f"{avg:.2f}", f"{(tv / avg if avg else 0):.2f}"]

        def merge(srcs):
            o = collections.defaultdict(collections.Counter)
            for s in srcs:
                for k, v in s.items():
                    o[k].update(v)
            return o

        size = {0: C, 1: I, 2: CL}

        def gen(kind):
            m = size[kind]
            z = collections.Counter()
            camps = [c for c in camp if any(camp[c].get(x) for x in W)]
            camps.sort(key=lambda c: (-camp[c].get(D0s, z)[m], -camp[c].get(D0s, z)[C]))
            rows = []
            for c in camps[:10]:
                rows.append([c, ""] + vals(camp[c], kind))
                gs = [g for (cc, g) in agg if cc == c and any(agg[(cc, g)].get(x) for x in W)]
                gs.sort(key=lambda g: (-agg[(c, g)].get(D0s, z)[m], -agg[(c, g)].get(D0s, z)[C]))
                for g in gs[:10]:
                    rows.append([c, g or "미지정"] + vals(agg[(c, g)], kind))
                if len(gs) > 10:
                    rows.append([c, "기타"] + vals(merge([agg[(c, g)] for g in gs[10:]]), kind))
            if len(camps) > 10:
                rows.append(["기타", ""] + vals(merge([camp[c] for c in camps[10:]]), kind))
            return rows

        md_ = f"{D0.month}월 {D0.day}일"
        comps = [
            {"slot_key": "daily_campaign_diagnosis_table.cost", "type": "tree_map", "name": "매출 진단",
             "description": "각 박스의 크기는 일일 광고비를 기준으로 표현됩니다.\n성과 색상은 최근 7일 평균 대비 오늘의 매출 비율로 결정됩니다.",
             "cols": ["campaign_name", "ad_group_name", "cost", "revenue", "revenue_average", "revenue_ratio"], "units": [None, None, "KRW", "KRW", "KRW", None], "items": gen(0)},
            {"slot_key": "daily_campaign_diagnosis_table.imp", "type": "tree_map", "name": "CTR 진단",
             "description": "각 박스의 크기는 노출 수를 기준으로 표현됩니다.\n성과 색상은 최근 7일 평균 대비 오늘의 CTR 비율로 결정됩니다.",
             "cols": ["campaign_name", "ad_group_name", "impression", "ctr", "ctr_average", "ctr_ratio"], "units": [None, None, None, "%", "%", None], "items": gen(1)},
        ]
        if CV:
            comps.append({"slot_key": "daily_campaign_diagnosis_table.click", "type": "tree_map", "name": "CVR 진단",
                          "description": "각 박스의 크기는 클릭 수를 기준으로 표현됩니다.\n성과 색상은 최근 7일 평균 대비 오늘의 CVR 비율로 결정됩니다.",
                          "cols": ["campaign_name", "ad_group_name", "click", "cvr", "cvr_average", "cvr_ratio"], "units": [None, None, None, "%", "%", None], "items": gen(2)})
        items.append(artifact("component_group", {"slot_key": "daily_campaign_diagnosis_group", "type": "component_group",
                                                  "name": f"주요 캠페인의 {md_} 성과 진단(최근 7일 대비)", "components": comps}, 4))

    # 전체 광고 성과 세부 데이터
    det = envelope(work, "detail")
    comps = []
    if md:
        rem = nd - D0.day + 1
        codes = sorted(by_media.keys(), key=lambda m: media_sort_key(m, {k: sum(nz(r.get(C)) for r in v.values()) for k, v in by_media.items()}))
        ch_rows = []
        for m in codes:
            if m is None:
                continue
            dd = by_media[m]
            t = dd.get(D0s, {})
            c0, r0 = nz(t.get(C)), nz(t.get(R))
            mc = sum(nz(r.get(C)) for r in dd.values())
            mr = sum(nz(r.get(R)) for r in dd.values())
            prev = sum(nz(r.get(C)) for x, r in dd.items() if x < D0s)
            tgt = media_cost_target(work, m)
            proper = f"{round((tgt - prev) / rem):,}" if tgt else "-"
            ch_rows.append([media_label(m), f"{round(c0):,}", proper, f"{round(r0):,}", f"{round(r0 / c0 * 100)}%" if c0 else "0%", f"{round(mr / mc * 100)}%" if mc else "0%"])
        comps.append({"slot_key": "channel_performance_table", "type": "paged_table", "name": f"{D0.month}월 {D0.day}일 광고 채널 성과", "description": None,
                      "cols": ["광고 채널", "일 광고비", "적정 광고비", "일 광고 매출", "일 ROAS", "월 누적 ROAS"], "units": None, "items": ch_rows})
    if det:
        M5 = [I, CL, C, CV, R] if CV else [I, CL, C, R]

        def agg(keys, keep=lambda r: True):
            o = collections.OrderedDict()
            for r in det["rows"]:
                if not keep(r):
                    continue
                k = tuple(r.get(x) for x in keys)
                a = o.setdefault(k, collections.Counter())
                a.update({m: nz(r.get(m)) for m in M5})
            return o

        def row(k, v):
            imp, clk, cost, rev = v[I], v[CL], v[C], v[R]
            cv = v[CV] if CV else 0
            return [media_label(k[0])] + [x if x is not None else "-" for x in k[1:]] + [
                f"{round(imp):,}", f"{round(clk):,}", f"{clk / imp * 100:.2f}%" if imp else "0.00%", f"{round(cost):,}",
                f"{cost / clk:,.2f}" if clk else "0.00", f"{round(cv):,}", f"{round(rev):,}", f"{round(rev / cost * 100)}%" if cost else "0%"]

        def table(keys, keep=lambda r: True, drop_null=True):
            a = agg(keys, keep)
            its = [(k, v) for k, v in a.items() if not (drop_null and None in k)]
            its.sort(key=lambda kv: (-kv[1][C], -kv[1][R], tuple("" if x is None else str(x) for x in kv[0])))
            return [row(k, v) for k, v in its]

        perf = ["노출", "클릭", "CTR", "광고비", "CPC", "전환", "매출", "ROAS"]
        search = [m for m in SEARCH_MEDIA if any(r.get("media") == m for r in det["rows"])]
        comps += [
            {"slot_key": "ad_detail_campaign_table", "type": "paged_table", "name": "캠페인 성과", "description": None,
             "cols": ["광고 채널", "캠페인"] + perf, "units": None, "items": table(["media", "campaign_name"])},
            {"slot_key": "ad_detail_group_table", "type": "paged_table", "name": "광고그룹 성과", "description": None,
             "cols": ["광고 채널", "캠페인", "광고그룹"] + perf, "units": None, "items": table(["media", "campaign_name", "ad_group_name"])},
            {"slot_key": "ad_detail_keyword_table", "type": "paged_table", "name": "키워드 성과", "description": None,
             "cols": ["광고 채널", "캠페인", "광고그룹", "키워드"] + perf, "units": None,
             "items": table(["media", "campaign_name", "ad_group_name", "ad_name"], keep=lambda r: (not search or r.get("media") in search) and r.get("ad_name") not in (None, "", "-"))},
        ]
    if comps:
        items.append(artifact("component_group", {"slot_key": "daily_ad_detail_group", "type": "component_group", "name": "전체 광고 성과 세부 데이터", "components": comps}, 5))

    items.append(artifact("metadata", {"workflow_name": WORKFLOW["daily"]}))
    items.append(artifact("promotion", {"type": "promotion", "target_date": D0s, "items": promo_items(work)}))
    name = f"{D0.year}년 {D0.month}월 {D0.day}일 {plan['brand']} 일간 보고서"
    return name, D0s, items, facts


# ───────────────────────────── MTD ─────────────────────────────
def build_mtd(plan, work):
    K = plan["metric_keys"]
    E = d(plan["date"])
    S = month_start(E)
    nd = calendar.monthrange(E.year, E.month)[1]
    C, R, I, CL = K["cost"], K["revenue"], K["impression"], K["click"]
    CV = K.get("conversion")
    items, facts = [], {"type": "mtd", "period": f"{iso(S)}~{iso(E)}"}

    dm = envelope(work, "daily_media")
    mtd_cost = sum(nz(r.get(C)) for r in dm["rows"]) if dm else 0
    mtd_rev = sum(nz(r.get(R)) for r in dm["rows"]) if dm else 0
    items.append(target_progression(plan, work, nd, E.day, (mtd_cost, mtd_rev)))

    items.append(artifact("text", {"slot_key": "mtd_executive_summary", "type": "text", "name": "Executive Summary", "items": []}, 2))
    items.append(artifact("text", {"slot_key": "mtd_performance_overview", "type": "text", "name": "성과에 대한 개괄", "items": []}, 3))

    mo = envelope(work, "months")
    if mo:
        months = [add_months(S, -i).strftime("%Y-%m") for i in range(5, -1, -1)]
        items.append(artifact("chart", months_chart(mo, K, months), 4))

    cm = envelope(work, "cat_month")
    top5 = []
    if cm:
        cur = cat_totals(cm, K, E.strftime("%Y-%m"))
        prv = cat_totals(cm, K, add_months(S, -1).strftime("%Y-%m"))
        order = sorted(cur.keys(), key=lambda c: -cur[c])
        rows = [[c, f0(cur[c]), (f"{(cur[c] / prv[c] - 1) * 100:.2f}%" if prv.get(c) else "-")] for c in order]
        items.append(artifact("paged_table", {"slot_key": "items_table", "type": "paged_table", "name": "카테고리별 누적 판매액", "description": None,
                                              "cols": ["카테고리", "판매액", "MoM(%)"], "units": None, "items": rows}, 5))
        top5 = order[:5]
        yoy = cat_totals(cm, K, add_months(S, -12).strftime("%Y-%m"))
        m3 = [cat_totals(cm, K, add_months(S, -i).strftime("%Y-%m")) for i in (1, 2, 3)]
    cd = envelope(work, "cat_day")
    if cd:
        if not top5:
            tot = collections.Counter()
            for r in cd["rows"]:
                if r.get("product_category") is not None:
                    tot[r["product_category"]] += nz(r.get(R))
            top5 = [c for c, _ in tot.most_common(5)]
        items.append(artifact("chart", {"slot_key": "daily_sales_by_category_chart", "type": "chart", "name": "일일 카테고리별 매출 현황",
                                        "chart_series": cat_daily_series(cd, K, top5, days_between(S, E))}, 6))
    items.append(artifact("text", {"slot_key": "mtd_ad_performance_analysis", "type": "text", "name": "제품 판매 성과의 심층 분석", "items": []}, 7))

    if dm:
        cost_by = collections.defaultdict(float)
        for r in dm["rows"]:
            if r.get("media") is not None:
                cost_by[r["media"]] += nz(r.get(C))
        sp = []
        for m in sorted(cost_by, key=lambda x: media_sort_key(x, cost_by)):
            tgt = media_cost_target(work, m)
            if tgt is None:
                continue
            nm = f"{MEDIA_GROUP}:{media_label(m)}"
            sp.append({"name": nm, "display": nm, "target": as_int_if_whole(tgt), "expected": round(tgt * E.day / nd),
                       "actual": math.floor(cost_by[m] + 1e-6), "unit": None, "change_rate": None})
        if sp:
            items.append(artifact("source_progression", {"slot_key": "source_progression", "type": "source_progression", "name": "매체 별 예산 소진 현황", "items": sp}, 8))

    det = envelope(work, "detail")
    if det:
        search = [m for m in SEARCH_MEDIA if any(r.get("media") == m for r in det["rows"])]
        rows = [r for r in det["rows"] if not search or r.get("media") in search]
        M5 = [C, I, CL, CV, R] if CV else [C, I, CL, R]

        def agg(keyf, flt=lambda r: True):
            acc = collections.OrderedDict()
            for r in rows:
                if not flt(r):
                    continue
                a = acc.setdefault(keyf(r), collections.Counter())
                a.update({m: nz(r.get(m)) for m in M5})
            return acc

        def met(a):
            c, i, k, rv = a[C], a[I], a[CL], a[R]
            cv = a[CV] if CV else 0
            return dict(c=c, i=i, k=k, cv=cv, rv=rv, roas=rv / c * 100 if c else 0, ctr=k / i * 100 if i else 0, cpc=c / k if k else 0,
                        cpm=c / i * 1000 if i else 0, aov=rv / cv if cv else 0)

        def sk(name, x):
            return (-x["roas"], -x["c"], -x["rv"], name)

        acc = agg(lambda r: (r.get("campaign_name"), r.get("media")))
        L = sorted(((k, met(a)) for k, a in acc.items() if k[0] is not None), key=lambda t: sk(str(t[0][0]), t[1]))
        camp_rows = [[k[0], k[1], f0(x["rv"]), f0(x["c"]), f0(x["roas"]) + "%", f0(x["i"]), f0(x["k"]), f2(x["ctr"]) + "%", f2(x["cpc"]), f0(x["cv"]), f0(x["aov"])] for k, x in L]
        acc = agg(lambda r: r.get("ad_group_name"), lambda r: r.get("ad_group_name") is not None)
        L = sorted(((k, met(a)) for k, a in acc.items()), key=lambda t: sk(str(t[0]), t[1]))
        grp_rows = [[k, f0(x["i"]), f0(x["k"]), f2(x["cpc"]), f0(x["c"]), f0(x["rv"])] for k, x in L]
        acc = agg(lambda r: r.get("ad_name"), lambda r: r.get("ad_name") not in (None, "", "-"))
        L = sorted(((k, met(a)) for k, a in acc.items()), key=lambda t: sk(str(t[0]), t[1]))
        kw_rows = [[k, f0(x["i"]), f0(x["k"]), f0(x["c"]), f2(x["cpc"]), f2(x["ctr"]) + "%", f2(x["cpm"]), f0(x["cv"]), f0(x["rv"]), f0(x["roas"]) + "%"] for k, x in L]
        items.append(artifact("paged_table", {"slot_key": "campaign_table", "type": "paged_table", "name": "캠페인 별 성과", "description": None,
                                              "cols": ["캠페인", "네이버 광고 채널명", "매출", "광고비", "ROAS", "노출", "클릭", "CTR", "CPC", "구매", "평균단가"], "units": None, "items": camp_rows}, 9))
        items.append(artifact("text", {"slot_key": "mtd_ad_group_analysis", "type": "text", "name": "광고 그룹별 심층 분석", "items": []}, 10))
        items.append(artifact("paged_table", {"slot_key": "groups_table", "type": "paged_table", "name": "그룹 별 성과", "description": None,
                                              "cols": ["광고그룹", "노출", "클릭", "CPC", "광고비", "매출"], "units": None, "items": grp_rows}, 11))
        items.append(artifact("paged_table", {"slot_key": "keywords_table", "type": "paged_table", "name": "키워드 별 성과", "description": None,
                                              "cols": ["키워드", "노출", "클릭", "광고비", "CPC", "클릭율", "CPM", "구매건수", "매출", "ROAS"], "units": None, "items": kw_rows}, 12))
    else:
        items.append(artifact("text", {"slot_key": "mtd_ad_group_analysis", "type": "text", "name": "광고 그룹별 심층 분석", "items": []}, 10))

    if dm:
        per = collections.defaultdict(lambda: collections.Counter())
        cost_r = collections.Counter()
        for r in dm["rows"]:
            per[r["date"]].update({m: nz(r.get(m)) for m in [CL, R] + ([CV] if CV else [])})
            cost_r[r["date"]] += round(nz(r.get(C)))
        dates = days_between(S, E)
        dc_rows = [[f0(cost_r[x]), f0(per[x][CL]), f0(per[x][CV]) if CV else "0", f0(per[x][R])] for x in dates]
        items.append(artifact("daily_contribution", {"slot_key": "daily_contribution", "type": "daily_contribution", "name": "일별 광고기여 매출 분석",
                                                     "cols": ["광고비", "클릭", "구매", "매출"], "dates": dates, "items": dc_rows}, 13))

    items.append(artifact("promotion", {"type": "promotion", "target_date": iso(E), "items": promo_items(work)}))
    items.append(artifact("metadata", {"workflow_name": WORKFLOW["mtd"]}))
    name = f"{S.strftime('%y.%m.%d')} ~ {E.strftime('%y.%m.%d')} {plan['brand']} MTD 보고서"
    return name, f"{iso(S)}~{iso(E)}", items, facts


# ───────────────────────────── monthly ─────────────────────────────
def build_monthly(plan, work):
    K = plan["metric_keys"]
    M = month_start(d(plan["date"] if len(plan["date"]) > 7 else plan["date"] + "-01"))
    ME = month_end(M)
    P = add_months(M, -1)
    nd = ME.day
    C, R = K["cost"], K["revenue"]
    items, facts = [], {"type": "monthly", "month": M.strftime("%Y-%m")}
    mo = envelope(work, "months")
    cur_cost = cur_rev = 0
    if mo:
        r = next((x for x in mo["rows"] if x.get("month") == M.strftime("%Y-%m")), {})
        cur_cost, cur_rev = nz(r.get(C)), nz(r.get(R))
    items.append(target_progression(plan, work, nd, nd, (cur_cost, cur_rev)))
    if mo:
        months = [add_months(M, -i).strftime("%Y-%m") for i in range(5, -1, -1)]
        items.append(artifact("chart", months_chart(mo, K, months), 2))
    items.append(artifact("text", {"slot_key": "monthly_executive_summary", "type": "text", "name": "Executive Summary", "items": []}, 3))
    cm = envelope(work, "cat_month")
    top5 = []
    if cm:
        cur = cat_totals(cm, K, M.strftime("%Y-%m"))
        prv = cat_totals(cm, K, P.strftime("%Y-%m"))
        order = sorted(cur.keys(), key=lambda c: -cur[c])
        series = [{"type": "chart_component", "name": c, "label": c, "unit": "KRW",
                   "items": [{"x": yymm_label(P.strftime("%Y-%m")), "y": as_int_if_whole(float(prv.get(c, 0)))},
                             {"x": yymm_label(M.strftime("%Y-%m")), "y": as_int_if_whole(float(cur[c]))}]} for c in order]
        items.append(artifact("chart", {"slot_key": "monthly_sales_by_category_chart", "type": "chart", "name": "카테고리별 매출액 비교", "chart_series": series}, 4))
        top5 = order[:5]
        yoy = cat_totals(cm, K, add_months(M, -12).strftime("%Y-%m"))
    cd = envelope(work, "cat_day")
    if cd:
        if not top5:
            tot = collections.Counter()
            for r in cd["rows"]:
                if r.get("product_category") is not None:
                    tot[r["product_category"]] += nz(r.get(R))
            top5 = [c for c, _ in tot.most_common(5)]
        items.append(artifact("chart", {"slot_key": "monthly_daily_sales_by_category_chart", "type": "chart", "name": "일일 카테고리별 매출 현황",
                                        "chart_series": cat_daily_series(cd, K, top5, days_between(M, ME))}, 5))
    items.append(artifact("text", {"slot_key": "monthly_sales_trend_analysis", "type": "text", "name": "제품 판매 트렌드 분석", "items": []}, 6))
    mm = envelope(work, "media_month")
    if mm:
        by = collections.defaultdict(dict)
        for r in mm["rows"]:
            if r.get("media") is not None:
                by[r["media"]][r["month"]] = r
        cost_tot = {m: sum(nz(r.get(C)) for r in v.values()) for m, v in by.items()}
        comps = []
        for m in sorted(by, key=lambda x: media_sort_key(x, cost_tot)):
            rows = []
            for ym in (P.strftime("%Y-%m"), M.strftime("%Y-%m")):
                r = by[m].get(ym, {})
                c, v = nz(r.get(C)), nz(r.get(R))
                ro = r.get(K["roas"]) if "roas" in K else None
                if ro is None:
                    ro = v / c * 100 if c else 0
                rows.append([yyyymm_label(ym), f"{int(c):,}", f"{int(v):,}", f"{ro:.2f}%"])
            comps.append({"slot_key": f"monthly_source_progression_table.{media_label(m)}", "type": "table", "name": media_label(m), "description": None,
                          "cols": ["월", "광고비 (원)", "매출 (원)", "ROAS"], "units": None, "items": rows})
        items.append(artifact("component_group", {"slot_key": "monthly_source_progression_group", "type": "component_group", "name": "매체 별 성과 비교", "components": comps}, 7))
    items.append(artifact("metadata", {"workflow_name": WORKFLOW["monthly"]}))
    name = f"{M.year}년 {M.month}월 {plan['brand']} 월 마감 보고서"
    return name, iso(M), items, facts


# ───────────────────────────── data / render ─────────────────────────────
def load_plan(work):
    with open(os.path.join(work, "plan.json"), encoding="utf-8") as f:
        return json.load(f)


def note_used(work, paths):
    """Remember capture files this report consumed, so render can delete them."""
    f = os.path.join(work, CAPTURES_USED)
    try:
        with open(f, encoding="utf-8") as fh:
            old = json.load(fh)
    except (OSError, ValueError):
        old = []
    with open(f, "w", encoding="utf-8") as fh:
        json.dump(sorted(set(old) | set(paths)), fh, ensure_ascii=False)


def delete_used(work):
    f = os.path.join(work, CAPTURES_USED)
    try:
        with open(f, encoding="utf-8") as fh:
            paths = json.load(fh)
    except (OSError, ValueError):
        return 0
    root = os.path.realpath(CAPTURE_ROOT) + os.sep
    n = 0
    for p in paths:
        if os.path.realpath(p).startswith(root):  # never delete outside the capture folder
            try:
                os.remove(p)
                n += 1
            except OSError:
                pass
    os.remove(f)
    return n


def cmd_arm(a):
    path = arm_path()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(str(time.time()))
    print(json.dumps({"armed": path, "session": session_id() or None,
                      "note": "the hook saves laighthouse responses for 3 hours from now"}, ensure_ascii=False, indent=1))


def cmd_collect(a):
    work = os.path.abspath(os.path.expanduser(a.work))
    plan = load_plan(work)
    since = armed_since(os.path.getmtime(os.path.join(work, "plan.json")) - 6 * 3600)
    records = captured(since)
    got, missing, used = [], [], []
    for c in plan["calls"]:
        dst = os.path.join(work, "responses", c["key"] + ".json")
        if os.path.exists(dst) and not a.overwrite:
            got.append(c["key"])
            continue
        rec = find_captured(c["tool"], c["params"], records=records)
        resp = resolve_spill(rec["response"]) if rec else None
        if not resp or spilled_path(resp) or (c["tool"] == "get_ad_performance" and not is_envelope(resp)):
            missing.append(c["key"])
            continue
        with open(dst, "w", encoding="utf-8") as f:
            f.write(resp)
        got.append(c["key"])
        used.append(rec["_path"])
    note_used(work, used)
    print(json.dumps({"collected": got, "missing": missing, "capture_dir": CAPTURE_ROOT}, ensure_ascii=False, indent=1))


def cmd_data(a):
    work = os.path.abspath(os.path.expanduser(a.work))
    plan = load_plan(work)
    # get_ad_performance must yield a data envelope; anything else (error text, an unresolved
    # "exceeds maximum allowed tokens" notice) is as good as missing
    missing = [c["key"] for c in plan["calls"] if not c["key"].startswith("ctx_") and (
        envelope(work, c["key"]) is None if c["tool"] == "get_ad_performance" else load_response(work, c["key"]) is None)]
    builder = {"daily": build_daily, "mtd": build_mtd, "monthly": build_monthly}[plan["type"]]
    name, ref, items, _ = builder(plan, work)
    from facts import make_facts
    facts = make_facts(plan, work, items)
    data = {"meta": {"type": plan["type"], "name": name, "reference_date": ref, "created": plan["created"], "author": plan["author"],
                     "published": plan.get("published", True),
                     "brand": {"name": plan["brand"], "advertiser": plan["advertiser"], "color": plan["brand_color"], "initials": plan["brand_initials"]}},
            "items": items}
    with open(os.path.join(work, "data.json"), "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)
    with open(os.path.join(work, "facts.json"), "w", encoding="utf-8") as f:
        json.dump(facts, f, ensure_ascii=False, indent=1)
    text_slots = [it["analysis_artifact"]["data"]["slot_key"] for it in items if it["analysis_artifact"]["type"] == "text"]
    print(json.dumps({"data": os.path.join(work, "data.json"), "facts": os.path.join(work, "facts.json"), "report_name": name,
                      "missing_responses": missing, "text_slots_to_write": text_slots,
                      "action_cards": plan["type"] in ("daily", "mtd")}, ensure_ascii=False, indent=1))


def cmd_render(a):
    work = os.path.abspath(os.path.expanduser(a.work))
    with open(os.path.join(work, "data.json"), encoding="utf-8") as f:
        data = json.load(f)
    texts = {}
    if a.texts:
        with open(os.path.expanduser(a.texts), encoding="utf-8") as f:
            texts = json.load(f)
    slots = texts.get("texts", texts)
    for it in data["items"]:
        art = it["analysis_artifact"]
        if art["type"] == "text":
            v = slots.get(art["data"]["slot_key"])
            if v:
                art["data"]["items"] = v if isinstance(v, list) else [v]
    cards = texts.get("action_cards") or []
    for i, c in enumerate(cards):
        data["items"].append(artifact("action_card", {
            "slot_key": f"action_card.{i}", "type": "action_card", "title": c.get("title", ""), "tags": c.get("tags") or [],
            "description": c.get("description", ""), "actions": c.get("actions") or [], "background": c.get("background", "")}))
    # drop text sections nobody wrote (the web app never shows empty text cards)
    data["items"] = [it for it in data["items"] if not (it["analysis_artifact"]["type"] == "text" and not it["analysis_artifact"]["data"].get("items"))]
    with open(os.path.join(work, "payload.json"), "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)
    from render_report import render
    out = os.path.abspath(os.path.expanduser(a.out))
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        f.write(render(data))
    deleted = delete_used(work)
    print(out)
    if deleted:
        print(f"deleted {deleted} captured MCP response file(s)", file=sys.stderr)


def main():
    # the JSON we print (brand / metric names, paths) is copied into MCP calls verbatim;
    # a legacy console code page (cp949 on Korean Windows) would mangle it
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")
        except (AttributeError, ValueError):
            pass
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("arm")
    pl = sub.add_parser("plan")
    pl.add_argument("--type", required=True, choices=["daily", "mtd", "monthly"])
    pl.add_argument("--brand", required=True)
    pl.add_argument("--date", required=True, help="daily: D0, mtd: end date, monthly: YYYY-MM")
    pl.add_argument("--discovery", help="saved discovery response file, or 'auto' to take it from the hook captures")
    pl.add_argument("--work", required=True)
    pl.add_argument("--author")
    pl.add_argument("--advertiser")
    pl.add_argument("--brand-color")
    pl.add_argument("--brand-initials")
    pl.add_argument("--created", help="'YYYY-MM-DD HH:MM' (default: now, KST)")
    pl.add_argument("--unpublished", action="store_true")
    co = sub.add_parser("collect")
    co.add_argument("--work", required=True)
    co.add_argument("--overwrite", action="store_true")
    da = sub.add_parser("data")
    da.add_argument("--work", required=True)
    re_ = sub.add_parser("render")
    re_.add_argument("--work", required=True)
    re_.add_argument("--texts")
    re_.add_argument("--out", required=True)
    a = p.parse_args()
    {"arm": cmd_arm, "plan": cmd_plan, "collect": cmd_collect, "data": cmd_data, "render": cmd_render}[a.cmd](a)


if __name__ == "__main__":
    main()
