"""Responses the plugin hook (hooks/save_responses.py) saved: listing them and matching one to a call.

The hook writes <tmp>/laighthouse_mcp_responses/<session>/<ms>_<tool>.json ({tool_name, tool_input, saved_at,
response}) and an index.jsonl line per record (no body), so records can be listed without opening the bodies.
"""
import json
import os
import tempfile

CAPTURE_ROOT = os.path.join(tempfile.gettempdir(), "laighthouse_mcp_responses")
# A target call may omit these: the server then reads the first published of 광고비/cost (cost) and
# 매출_AB/revenue/매출 (revenue) — SERVER_DEFAULT. target_metric_args tells when that pick is not the wanted one.
TARGET_METRIC_ARGS = ("cost_metric", "revenue_metric")
SERVER_DEFAULT = {"cost": ["광고비", "cost"], "revenue": ["매출_AB", "revenue", "매출"]}


def _canon(params, ignore=()):
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
    """Records of one capture folder. Indexed records (index.jsonl — hooks/save_responses.py) come without
    their bodies, so matching does not open the big files."""
    out, indexed = [], set()
    index = os.path.join(folder, "index.jsonl")
    if os.path.exists(index):
        with open(index, encoding="utf-8") as f:
            for line in f:
                try:
                    rec = json.loads(line)
                except ValueError:
                    continue   # a line torn by concurrent appends — its body file is picked up below
                rec["_path"] = os.path.join(folder, rec.get("file", ""))
                indexed.add(rec.get("file"))
                out.append(rec)
    # bodies the index does not list (no index, or a lost / torn line) are opened directly
    for name in os.listdir(folder):
        if not name.endswith(".json") or name in indexed:
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
            rec["response"] = full.get("response") if isinstance(full, dict) else None
        except (OSError, ValueError, KeyError):
            return None
    resp = rec.get("response")
    if resp is not None and not isinstance(resp, str):
        resp = json.dumps(resp, ensure_ascii=False)
    return resp


def find_captured(tool, params, since=0.0, records=None):
    # a target call given without metric names also accepts a saved call that named them;
    # given with metric names, only a saved call with exactly those names matches
    ignore = [k for k in TARGET_METRIC_ARGS if k not in (params or {})] if tool == "get_target_progress_v2" else ()
    want = _canon(params, ignore)
    for rec in records if records is not None else captured(since):
        if str(rec.get("tool_name", "")).endswith("__" + tool) or rec.get("tool_name") == tool:
            if _canon(rec.get("tool_input"), ignore) == want:
                return rec
    return None


def target_metric_args(K, served):
    """{cost_metric, revenue_metric} when the server's default pick would read other metrics than K, else {}.
    The server matches its candidates case-sensitively (`Cost` is not `cost`), so this does too."""
    pick = {role: next((c for c in cands if c in served), None) for role, cands in SERVER_DEFAULT.items()}
    if pick["cost"] == K.get("cost") and pick["revenue"] == K.get("revenue"):
        return {}
    return {"cost_metric": K.get("cost"), "revenue_metric": K.get("revenue")}
