"""Facts digest for writing the report texts (`build_report.py data` → facts.json).

Every number here comes from the saved MCP responses; the model must only quote these
(or values in data.json). Units are explicit in key names:
  *_krw   원 (rounded to 1 won)          *_pct  percent value (1 decimal, 980.5 = 980.5%)
  *_pp    percentage-point difference    *_chg_pct  relative change in percent
  roas_pct is always a percent (ROAS 9.8051 배 → 980.5).
"""

import calendar
import collections
import datetime as dt

from build_report import (KR_HOLIDAYS, add_days, add_months, d, days_between, envelope, iso, load_response, media_label,
                          media_sort_key, month_end, month_start, nz, parse_promotions, parse_target)

WD = ["월", "화", "수", "목", "금", "토", "일"]


def pct(a, b, nd=1):
    return round(a / b * 100, nd) if b else None


def chg(a, b, nd=1):
    return round((a / b - 1) * 100, nd) if b else None


def kpis(c, v, imp=None, clk=None, cv=None):
    o = {"cost_krw": round(c), "revenue_krw": round(v), "roas_pct": pct(v, c)}
    if imp is not None:
        o["impressions"] = round(imp)
    if clk is not None:
        o["clicks"] = round(clk)
        o["ctr_pct"] = pct(clk, imp, 2) if imp else None
        o["cpc_krw"] = round(c / clk) if clk else None
    if cv is not None:
        o["conversions"] = round(cv)
        o["cvr_pct"] = pct(cv, clk, 2) if clk else None
        o["revenue_per_conversion_krw"] = round(v / cv) if cv else None
    return o


def day_info(x):
    dd = d(x)
    return {"date": x, "weekday": WD[dd.weekday()], "holiday": KR_HOLIDAYS.get(x)}


def target_block(work, elapsed, days):
    t = parse_target(load_response(work, "target"))
    if not t:
        return {"exists": False, "note": "월 목표 미설정"}
    (ct, ca), (rt, ra), (ot, oa) = t.get("cost", (0, 0)), t.get("revenue", (0, 0)), t.get("roas", (0, 0))
    ct, ca, rt, ra, ot, oa = (nz(x) for x in (ct, ca, rt, ra, ot, oa))
    frac = elapsed / days if days else 0
    return {
        "exists": True,
        "days_elapsed": elapsed, "days_in_month": days, "period_progress_pct": round(frac * 100, 1),
        "cost": {"target_krw": round(ct), "actual_krw": round(ca), "burn_pct": pct(ca, ct),
                 "even_pace_krw": round(ct * frac), "vs_even_pace_krw": round(ca - ct * frac),
                 "month_end_projection_krw": round(ca / elapsed * days) if elapsed else None},
        "revenue": {"target_krw": round(rt), "actual_krw": round(ra), "achievement_pct": pct(ra, rt),
                    "even_pace_krw": round(rt * frac), "vs_even_pace_krw": round(ra - rt * frac),
                    "month_end_projection_krw": round(ra / elapsed * days) if elapsed else None},
        "roas": {"target_pct": round(ot * 100, 1), "actual_pct": round(oa * 100, 1), "diff_pp": round((oa - ot) * 100, 1)},
    }


def media_targets(work, codes):
    out = {}
    for m in codes:
        t = parse_target(load_response(work, "target_media." + m))
        if t and t.get("cost") and t["cost"][0]:
            out[m] = t["cost"][0]
    return out


# ───────────────────────────── daily ─────────────────────────────
def daily(plan, work, items):
    K = plan["metric_keys"]
    C, R, I, CL, CV = K["cost"], K["revenue"], K["impression"], K["click"], K.get("conversion")
    D0 = d(plan["date"])
    D0s = iso(D0)
    nd = calendar.monthrange(D0.year, D0.month)[1]
    f = {"report": "daily", "d0": day_info(D0s), "target": target_block(work, D0.day, nd)}

    ctx = envelope(work, "ctx_daily") or envelope(work, "trend7")
    if ctx:
        by = {r["date"]: r for r in ctx["rows"]}

        def k(x):
            r = by.get(x, {})
            return kpis(nz(r.get(C)), nz(r.get(R)), r.get(I) if I in r else None, r.get(CL) if CL in r else None, r.get(CV) if CV and CV in r else None)

        def avg(dates):
            dates = [x for x in dates if x in by] or dates
            rows = [by.get(x, {}) for x in dates]
            n = len(dates)
            s = lambda m: sum(nz(r.get(m)) for r in rows) if m else None
            o = kpis(s(C) / n, s(R) / n, s(I) / n if any(I in r for r in rows) else None, s(CL) / n if any(CL in r for r in rows) else None,
                     s(CV) / n if CV and any(CV in r for r in rows) else None)
            o["days"] = n
            o["note"] = "일평균(합계÷일수), ROAS·CTR·CVR은 합계 기준"
            return o
        f["d0"].update(k(D0s))
        prev7 = [x for x in days_between(add_days(D0, -7), add_days(D0, -1)) if x in by]
        f["prev7_daily_avg"] = dict(avg(prev7), period=f"{prev7[0]}~{prev7[-1]}" if prev7 else None)
        f["d0_vs_prev7_avg"] = {"cost_chg_pct": chg(f["d0"]["cost_krw"], f["prev7_daily_avg"]["cost_krw"]),
                                "revenue_chg_pct": chg(f["d0"]["revenue_krw"], f["prev7_daily_avg"]["revenue_krw"]),
                                "roas_diff_pp": round((f["d0"]["roas_pct"] or 0) - (f["prev7_daily_avg"]["roas_pct"] or 0), 1)}
        ms = month_start(D0)
        if envelope(work, "ctx_daily"):
            pm = days_between(add_months(ms, -1), add_days(ms, -1))
            f["prev_month_daily_avg"] = dict(avg(pm), period=f"{pm[0]}~{pm[-1]}")
            if D0.day > 1:
                mt = days_between(ms, add_days(D0, -1))
                f["this_month_until_d-1_daily_avg"] = dict(avg(mt), period=f"{mt[0]}~{mt[-1]}")
        f["last7_days"] = [dict(day_info(x), **k(x)) for x in days_between(add_days(D0, -6), D0)]

    # channels
    md = envelope(work, "media_day")
    if md:
        bym = collections.defaultdict(dict)
        for r in md["rows"]:
            if r.get("media") is not None:
                bym[r["media"]][r["date"]] = r
        tg = media_targets(work, bym.keys())
        rem = nd - D0.day + 1
        ch = []
        for m in sorted(bym, key=media_sort_key):
            dd = bym[m]
            t = dd.get(D0s, {})
            mc, mr = sum(nz(r.get(C)) for r in dd.values()), sum(nz(r.get(R)) for r in dd.values())
            prev = sum(nz(r.get(C)) for x, r in dd.items() if x < D0s)
            ch.append({"media": media_label(m), "d0": kpis(nz(t.get(C)), nz(t.get(R))), "mtd": kpis(mc, mr),
                       "monthly_budget_krw": round(tg[m]) if m in tg else None,
                       "optimal_daily_cost_krw": round((tg[m] - prev) / rem) if m in tg else None,
                       "budget_burn_pct": pct(mc, tg[m]) if m in tg else None})
        f["channels"] = ch

    # diagnosis (D0 vs D-7~D-1) per campaign / ad group
    tm = envelope(work, "treemap")
    if tm:
        win = days_between(add_days(D0, -7), add_days(D0, -1))
        grp = collections.defaultdict(lambda: collections.defaultdict(collections.Counter))
        med = {}
        for r in tm["rows"]:
            if r.get("campaign_name") is None:
                continue
            for key in ((r["campaign_name"], None), (r["campaign_name"], r.get("ad_group_name") or "미지정")):
                grp[key][r["date"]].update({m: nz(r.get(m)) for m in (C, R, I, CL, CV) if m})
            med.setdefault(r["campaign_name"], media_label(r.get("media")))

        def summ(src, dates):
            s = collections.Counter()
            for x in dates:
                s.update(src.get(x, {}))
            n = len(dates)
            return kpis(s[C] / n, s[R] / n, s[I] / n, s[CL] / n, s[CV] / n if CV else None)
        rows = []
        for (cp, ag), src in grp.items():
            t = src.get(D0s, collections.Counter())
            if not t[C] and not t[R] and not t[I]:
                continue
            a = summ(src, win)
            dk = kpis(t[C], t[R], t[I], t[CL], t[CV] if CV else None)
            rows.append({"level": "campaign" if ag is None else "ad_group", "media": med.get(cp), "campaign": cp, "ad_group": ag,
                         "d0": dk, "prev7_daily_avg": a,
                         "revenue_ratio": round(dk["revenue_krw"] / a["revenue_krw"], 2) if a["revenue_krw"] else None,
                         "roas_diff_pp": round((dk["roas_pct"] or 0) - (a["roas_pct"] or 0), 1),
                         "cvr_diff_pp": round((dk.get("cvr_pct") or 0) - (a.get("cvr_pct") or 0), 2) if CV else None,
                         "ctr_diff_pp": round((dk.get("ctr_pct") or 0) - (a.get("ctr_pct") or 0), 2)})
        rows.sort(key=lambda x: -x["d0"]["cost_krw"])
        f["diagnosis_note"] = "d0 vs prev7_daily_avg(D-7~D-1 합계÷7, 비율은 합계 기준). 트리맵 색은 웹앱 규칙(일별 비율의 7일 단순평균)이라 수치가 조금 다를 수 있음"
        f["diagnosis_campaigns"] = [x for x in rows if x["level"] == "campaign"][:12]
        f["diagnosis_ad_groups"] = [x for x in rows if x["level"] == "ad_group"][:25]

    det = envelope(work, "detail")
    if det:
        acc = collections.defaultdict(collections.Counter)
        for r in det["rows"]:
            acc[(r.get("media"), r.get("campaign_name"))].update({m: nz(r.get(m)) for m in (C, R, I, CL, CV) if m})
        top = sorted(acc.items(), key=lambda kv: -kv[1][C])[:10]
        f["top_campaigns_d30_to_d0"] = [{"media": media_label(k[0]), "campaign": k[1], **kpis(v[C], v[R], v[I], v[CL], v[CV] if CV else None)} for k, v in top]
    return f


# ───────────────────────────── MTD ─────────────────────────────
def mtd(plan, work, items):
    K = plan["metric_keys"]
    C, R, I, CL, CV = K["cost"], K["revenue"], K["impression"], K["click"], K.get("conversion")
    E = d(plan["date"])
    S = month_start(E)
    nd = calendar.monthrange(E.year, E.month)[1]
    f = {"report": "mtd", "period": f"{iso(S)}~{iso(E)}", "target": target_block(work, E.day, nd)}

    ctx = envelope(work, "ctx_months_same_period") or envelope(work, "months")
    if ctx:
        rows = sorted(ctx["rows"], key=lambda r: r.get("month", ""))
        lst = [{"month": r["month"], **kpis(nz(r.get(C)), nz(r.get(R)))} for r in rows]
        cur = lst[-1] if lst else None
        f["same_period_by_month_note"] = f"각 월 1~{E.day}일 (day_offset), 마지막이 이번 달"
        f["same_period_by_month"] = lst
        if cur and len(lst) >= 2:
            prev = lst[-2]
            p3 = lst[-4:-1]
            yoy = next((x for x in lst if x["month"] == add_months(S, -12).strftime("%Y-%m")), None)
            avg3 = sum(x["roas_pct"] or 0 for x in p3) / len(p3) if p3 else None
            rank = sorted(lst, key=lambda x: -(x["roas_pct"] or 0)).index(cur) + 1
            f["roas_comparison"] = {"this_month_pct": cur["roas_pct"], "prev_month_pct": prev["roas_pct"], "avg_prev_3m_pct": round(avg3, 1) if avg3 is not None else None,
                                    "same_period_last_year_pct": yoy["roas_pct"] if yoy else None, "rank_in_listed_months": f"{rank}/{len(lst)}"}

    cm = envelope(work, "cat_month")
    if cm:
        tot = collections.defaultdict(lambda: collections.Counter())
        for r in cm["rows"]:
            if r.get("product_category") is not None:
                tot[r["product_category"]][r["month"]] += nz(r.get(R))
        ym = lambda n: add_months(S, n).strftime("%Y-%m")
        cur_all = sum(v[ym(0)] for v in tot.values())
        cats = []
        for c, v in sorted(tot.items(), key=lambda kv: -kv[1][ym(0)]):
            a3 = (v[ym(-1)] + v[ym(-2)] + v[ym(-3)]) / 3
            cats.append({"category": c, "this_period_krw": round(v[ym(0)]), "share_pct": pct(v[ym(0)], cur_all),
                         "prev_month_same_period_krw": round(v[ym(-1)]), "mom_chg_pct": chg(v[ym(0)], v[ym(-1)]),
                         "avg_prev_3m_same_period_krw": round(a3), "vs_3m_chg_pct": chg(v[ym(0)], a3),
                         "last_year_same_period_krw": round(v[ym(-12)]), "yoy_chg_pct": chg(v[ym(0)], v[ym(-12)])})
        f["categories_same_period"] = cats
    cd = envelope(work, "cat_day")
    if cd:
        by = collections.defaultdict(collections.Counter)
        for r in cd["rows"]:
            by[r["date"]][r.get("product_category")] += nz(r.get(R))
        f["daily_revenue_by_category"] = [dict(day_info(x), total_krw=round(sum(by[x].values())), **{str(k): round(v) for k, v in by[x].items()}) for x in days_between(S, E)]

    dm = envelope(work, "daily_media")
    if dm:
        cost = collections.Counter()
        for r in dm["rows"]:
            if r.get("media") is not None:
                cost[r["media"]] += nz(r.get(C))
        tg = media_targets(work, cost.keys())
        f["media_budget"] = [{"media": media_label(m), "monthly_budget_krw": round(tg[m]) if m in tg else None, "spent_krw": int(cost[m] + 1e-6),
                              "burn_pct": pct(cost[m], tg[m]) if m in tg else None, "even_pace_pct": round(E.day / nd * 100, 1)} for m in sorted(cost, key=media_sort_key)]

    cat_of = {}
    cg = envelope(work, "ctx_cat_groups")
    if cg:
        best = {}
        for r in cg["rows"]:
            key = (r.get("media"), r.get("campaign_name"), r.get("ad_group_name"))
            v = nz(r.get(R)) + nz(r.get(C))
            if r.get("product_category") is not None and v >= best.get(key, (-1, None))[0]:
                best[key] = (v, r["product_category"])
        cat_of = {k: v[1] for k, v in best.items()}
    det = envelope(work, "detail")
    if det:
        acc = collections.defaultdict(collections.Counter)
        for r in det["rows"]:
            if r.get("ad_group_name") is None:
                continue
            acc[(r.get("media"), r.get("campaign_name"), r.get("ad_group_name"))].update({m: nz(r.get(m)) for m in (C, R, I, CL, CV) if m})
        prev = {}
        gp = envelope(work, "ctx_groups_prev")
        if gp:
            for r in gp["rows"]:
                prev[(r.get("media"), r.get("campaign_name"), r.get("ad_group_name"))] = r
        out = []
        for k, v in sorted(acc.items(), key=lambda kv: -kv[1][R])[:20]:
            cur = kpis(v[C], v[R], v[I], v[CL], v[CV] if CV else None)
            g = {"media": media_label(k[0]), "campaign": k[1], "ad_group": k[2], "category": cat_of.get(k), "this_period": cur}
            p = prev.get(k)
            if p:
                pk = kpis(nz(p.get(C)), nz(p.get(R)), nz(p.get(I)), nz(p.get(CL)), nz(p.get(CV)) if CV else None)
                g["prev_month_same_period"] = pk
                g["changes"] = {"cost_chg_pct": chg(cur["cost_krw"], pk["cost_krw"]), "revenue_chg_pct": chg(cur["revenue_krw"], pk["revenue_krw"]),
                                "clicks_chg_pct": chg(cur["clicks"], pk["clicks"]), "roas_diff_pp": round((cur["roas_pct"] or 0) - (pk["roas_pct"] or 0), 1),
                                "cvr_diff_pp": round((cur.get("cvr_pct") or 0) - (pk.get("cvr_pct") or 0), 2) if CV else None,
                                "cpc_chg_pct": chg(cur["cpc_krw"] or 0, pk["cpc_krw"] or 0) if pk.get("cpc_krw") else None}
            out.append(g)
        f["top_ad_groups_by_revenue"] = out
    return f


# ───────────────────────────── monthly ─────────────────────────────
def monthly(plan, work, items):
    K = plan["metric_keys"]
    C, R, I, CL, CV = K["cost"], K["revenue"], K["impression"], K["click"], K.get("conversion")
    M = month_start(d(plan["date"] if len(plan["date"]) > 7 else plan["date"] + "-01"))
    P = add_months(M, -1)
    nd = month_end(M).day
    f = {"report": "monthly", "month": M.strftime("%Y-%m"), "target": target_block(work, nd, nd)}
    mo = envelope(work, "months")
    if mo:
        lst = [{"month": r["month"], **kpis(nz(r.get(C)), nz(r.get(R)))} for r in sorted(mo["rows"], key=lambda r: r.get("month", ""))]
        f["months"] = lst
        cur = next((x for x in lst if x["month"] == M.strftime("%Y-%m")), None)
        if cur:
            f["roas_rank_in_listed_months"] = f"{sorted(lst, key=lambda x: -(x['roas_pct'] or 0)).index(cur) + 1}/{len(lst)}"
            pm = next((x for x in lst if x["month"] == P.strftime("%Y-%m")), None)
            ly = next((x for x in lst if x["month"] == add_months(M, -12).strftime("%Y-%m")), None)
            f["revenue_mom_chg_pct"] = chg(cur["revenue_krw"], pm["revenue_krw"]) if pm else None
            f["revenue_yoy_chg_pct"] = chg(cur["revenue_krw"], ly["revenue_krw"]) if ly else None
    cm = envelope(work, "cat_month")
    if cm:
        tot = collections.defaultdict(collections.Counter)
        for r in cm["rows"]:
            if r.get("product_category") is not None:
                tot[r["product_category"]][r["month"]] += nz(r.get(R))
        ym = lambda n: add_months(M, n).strftime("%Y-%m")
        allc = sum(v[ym(0)] for v in tot.values())
        f["categories"] = [{"category": c, "this_month_krw": round(v[ym(0)]), "share_pct": pct(v[ym(0)], allc), "prev_month_krw": round(v[ym(-1)]),
                            "mom_chg_pct": chg(v[ym(0)], v[ym(-1)]), "same_month_last_year_krw": round(v[ym(-12)]), "yoy_chg_pct": chg(v[ym(0)], v[ym(-12)]),
                            "monthly_trend_krw": {ym(n): round(v[ym(n)]) for n in range(-5, 1)}}
                           for c, v in sorted(tot.items(), key=lambda kv: -kv[1][ym(0)])]
    cd = envelope(work, "cat_day")
    if cd:
        by = collections.defaultdict(lambda: collections.defaultdict(float))
        for r in cd["rows"]:
            by[r.get("product_category")][r["date"]] += nz(r.get(R))
        days = days_between(M, month_end(M))
        out = []
        for c, s in by.items():
            vals = [s.get(x, 0) for x in days]
            h1, h2 = vals[:15], vals[15:]
            mx = max(range(len(vals)), key=lambda i: vals[i])
            mn = min(range(len(vals)), key=lambda i: vals[i])
            out.append({"category": c, "first_half_daily_avg_krw": round(sum(h1) / len(h1)), "second_half_daily_avg_krw": round(sum(h2) / len(h2)) if h2 else None,
                        "max_day": dict(day_info(days[mx]), revenue_krw=round(vals[mx])), "min_day": dict(day_info(days[mn]), revenue_krw=round(vals[mn])),
                        "daily_krw": [round(x) for x in vals]})
        f["category_daily"] = out
    mm = envelope(work, "media_month")
    if mm:
        by = collections.defaultdict(dict)
        for r in mm["rows"]:
            if r.get("media") is not None:
                by[r["media"]][r["month"]] = r
        f["media"] = [{"media": media_label(m), **{ym: kpis(nz(v.get(ym, {}).get(C)), nz(v.get(ym, {}).get(R))) for ym in (P.strftime("%Y-%m"), M.strftime("%Y-%m"))}}
                      for m, v in sorted(by.items(), key=lambda kv: media_sort_key(kv[0]))]
    gp = envelope(work, "ctx_groups")
    if gp:
        acc = collections.defaultdict(lambda: collections.defaultdict(collections.Counter))
        cat = {}
        for r in gp["rows"]:
            k = (r.get("media"), r.get("campaign_name"), r.get("ad_group_name"))
            acc[k][r["month"]].update({m: nz(r.get(m)) for m in (C, R, I, CL, CV) if m})
            if r.get("product_category") is not None:
                cat.setdefault(k, collections.Counter())[r["product_category"]] += nz(r.get(R)) + nz(r.get(C))
        cur, prv = M.strftime("%Y-%m"), P.strftime("%Y-%m")
        out = []
        for k, v in sorted(acc.items(), key=lambda kv: -kv[1][cur][R])[:20]:
            a, b = v[cur], v[prv]
            ka = kpis(a[C], a[R], a[I], a[CL], a[CV] if CV else None)
            kb = kpis(b[C], b[R], b[I], b[CL], b[CV] if CV else None)
            out.append({"media": media_label(k[0]), "campaign": k[1], "ad_group": k[2] if k[2] is not None else "(광고그룹 없음)",
                        "category": cat[k].most_common(1)[0][0] if k in cat else None, "this_month": ka, "prev_month": kb,
                        "changes": {"cost_chg_pct": chg(ka["cost_krw"], kb["cost_krw"]), "revenue_chg_pct": chg(ka["revenue_krw"], kb["revenue_krw"]),
                                    "clicks_chg_pct": chg(ka["clicks"], kb["clicks"]), "roas_diff_pp": round((ka["roas_pct"] or 0) - (kb["roas_pct"] or 0), 1),
                                    "cvr_diff_pp": round((ka.get("cvr_pct") or 0) - (kb.get("cvr_pct") or 0), 2) if CV else None}})
        f["top_ad_groups_by_revenue"] = out

        def compare(a, b):
            ka = kpis(a[C], a[R], a[I], a[CL], a[CV] if CV else None)
            kb = kpis(b[C], b[R], b[I], b[CL], b[CV] if CV else None)
            return {"this_month": ka, "prev_month": kb,
                    "changes": {"cost_delta_krw": ka["cost_krw"] - kb["cost_krw"], "revenue_delta_krw": ka["revenue_krw"] - kb["revenue_krw"],
                                "cost_chg_pct": chg(ka["cost_krw"], kb["cost_krw"]), "revenue_chg_pct": chg(ka["revenue_krw"], kb["revenue_krw"]),
                                "clicks_chg_pct": chg(ka["clicks"], kb["clicks"]), "roas_diff_pp": round((ka["roas_pct"] or 0) - (kb["roas_pct"] or 0), 1),
                                "cvr_diff_pp": round((ka.get("cvr_pct") or 0) - (kb.get("cvr_pct") or 0), 2) if CV else None}}

        # campaigns ranked by how much they moved total revenue vs last month
        camp = collections.defaultdict(lambda: collections.defaultdict(collections.Counter))
        for k, v in acc.items():
            for ym, c in v.items():
                camp[(k[0], k[1])][ym].update(c)
        rows = [{"media": media_label(k[0]), "campaign": k[1], **compare(v[cur], v[prv])} for k, v in camp.items()]
        f["top_campaigns_by_impact_note"] = "전월 대비 매출 변화 절대값(revenue_delta_krw) 내림차순"
        f["top_campaigns_by_impact"] = sorted(rows, key=lambda x: -abs(x["changes"]["revenue_delta_krw"]))[:5]

        # ad-group performance rolled up to each group's main category
        cad = collections.defaultdict(lambda: collections.defaultdict(collections.Counter))
        for k, v in acc.items():
            if k in cat:
                for ym, c in v.items():
                    cad[cat[k].most_common(1)[0][0]][ym].update(c)
        f["category_ad_response_note"] = "광고그룹을 주 카테고리(매출+광고비 최대)에 귀속해 합산"
        f["category_ad_response"] = [{"category": c, **compare(v[cur], v[prv])} for c, v in sorted(cad.items(), key=lambda kv: -kv[1][cur][R])]
    if load_response(work, "ctx_promotions") is not None:
        f["promotions"] = [{"title": p.get("title", ""), "start_date": p.get("start_date") or p.get("date_begin"), "end_date": p.get("end_date") or p.get("date_end"),
                            "info": p.get("info") or ""} for p in parse_promotions(load_response(work, "ctx_promotions"))]
    return f


def make_facts(plan, work, items):
    return {"daily": daily, "mtd": mtd, "monthly": monthly}[plan["type"]](plan, work, items)
