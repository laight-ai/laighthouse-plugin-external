"""Responses the plugin hook (hooks/save_responses.py) saved — finding the one that answers a planned call.

The hook writes <tmp>/laighthouse_mcp_responses/<session>/<ms>_<tool>.json ({tool_name, tool_input, saved_at,
response}) and an index.jsonl line per record (no body). build_report.collect matches the plan's calls
against the index and reads only the bodies it picked.
"""
import json
import os
import tempfile

CAPTURE_ROOT = os.path.join(tempfile.gettempdir(), "laighthouse_mcp_responses")
# The target call is planned without these: the server then reads the first published of
# 광고비/cost (cost) and 매출_AB/revenue/매출 (revenue). Only when the brand's metric names differ does
# `data` ask for the call again with them (see target_metric_args).
TARGET_METRIC_ARGS = ("cost_metric", "revenue_metric")
SERVER_DEFAULT = {"cost": ["광고비", "cost"], "revenue": ["매출_AB", "revenue", "매출"]}


def _canon(params, tool=None, ignore=()):
    p = {k: v for k, v in (params or {}).items() if v is not None and k not in ignore}
    return json.dumps(p, ensure_ascii=False, sort_keys=True)


def session_id():
    """Claude Code session id (same value the hook receives), or "" when unknown."""
    return "".join(c for c in os.environ.get("CLAUDE_CODE_SESSION_ID", "") if c.isalnum() or c in "-_")


def capture_folders():
    """This session's capture folder only; every session's when the session id is unknown."""
    sess = session_id()
    if sess:
        return [os.path.join(CAPTURE_ROOT, sess)]
    if not os.path.isdir(CAPTURE_ROOT):
        return []
    return [os.path.join(CAPTURE_ROOT, n) for n in os.listdir(CAPTURE_ROOT)]


def _folder_records(folder):
    """Records of one capture folder without their response bodies when the hook left an index
    (index.jsonl — hooks/save_responses.py), so matching never opens the big files."""
    index = os.path.join(folder, "index.jsonl")
    if os.path.exists(index):
        out = []
        with open(index, encoding="utf-8") as f:
            for line in f:
                try:
                    rec = json.loads(line)
                except ValueError:
                    continue
                rec["_path"] = os.path.join(folder, rec.get("file", ""))
                out.append(rec)
        return out
    out = []
    for name in os.listdir(folder):
        if not name.endswith(".json"):
            continue
        path = os.path.join(folder, name)
        try:
            with open(path, encoding="utf-8") as f:
                rec = json.load(f)
        except (OSError, ValueError):
            continue
        if isinstance(rec, dict):
            rec["_path"] = path
            out.append(rec)
    return out


def captured(since=0.0):
    """Responses saved by the plugin hook, newest first (bodies are read by `record_response`)."""
    out = []
    for folder in capture_folders():
        if os.path.isdir(folder):
            out += [r for r in _folder_records(folder) if (r.get("saved_at") or 0) >= since]
    out.sort(key=lambda r: r.get("saved_at", 0), reverse=True)
    return out


def record_response(rec):
    """The saved response text of a record (reads the body file for index records)."""
    if "response" not in rec:
        try:
            with open(rec["_path"], encoding="utf-8") as f:
                full = json.load(f)
            rec["response"] = full.get("response")
        except (OSError, ValueError, KeyError):
            return None
    resp = rec.get("response")
    if resp is not None and not isinstance(resp, str):
        resp = json.dumps(resp, ensure_ascii=False)
    return resp


def find_captured(tool, params, since=0.0, records=None):
    # a target planned without metric names accepts a call that named them (they are then the right ones);
    # once `data` has put them in the plan, only a call with exactly those names matches
    ignore = [k for k in TARGET_METRIC_ARGS if k not in (params or {})] if tool == "get_target_progress_v2" else ()
    want = _canon(params, tool, ignore)
    for rec in records if records is not None else captured(since):
        if str(rec.get("tool_name", "")).endswith("__" + tool) or rec.get("tool_name") == tool:
            if _canon(rec.get("tool_input"), tool, ignore) == want:
                return rec
    return None


def target_metric_args(K, served):
    """{cost_metric, revenue_metric} when the server's default pick would read other metrics than K, else {}."""
    low = {m.lower(): m for m in served}
    pick = {role: next((low[c.lower()] for c in cands if c.lower() in low), None) for role, cands in SERVER_DEFAULT.items()}
    if pick["cost"] == K.get("cost") and pick["revenue"] == K.get("revenue"):
        return {}
    return {"cost_metric": K.get("cost"), "revenue_metric": K.get("revenue")}
