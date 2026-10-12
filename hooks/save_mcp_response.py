#!/usr/bin/env python3
"""PostToolUse hook: save every laighthouse MCP response (get_ad_performance /
get_target_progress_v2 / list_promotions) to a file, untouched.

Why: the `laighthouse-report` skill feeds MCP responses to its builder script. Without
this hook the model would have to re-type each response into a file, which is slow and
risks altering numbers. With it, `build_report.py collect` simply matches the saved
responses to the planned calls (same tool + same arguments) and copies them.

The hook never changes what the model sees (no stdout) and never fails the tool call:
any error is swallowed. Files live in <tmp>/laighthouse_mcp_responses/<session_id>/ and
are pruned after 3 days.
"""

import io
import json
import os
import shutil
import sys
import tempfile
import time

ROOT = os.path.join(tempfile.gettempdir(), "laighthouse_mcp_responses")
STALE_SECS = 3 * 24 * 3600


def extract_text(resp):
    if isinstance(resp, str):
        return resp
    if isinstance(resp, dict):
        if isinstance(resp.get("text"), str):
            return resp["text"]
        if "content" in resp:
            return extract_text(resp["content"])
        return json.dumps(resp, ensure_ascii=False)
    if isinstance(resp, list):
        parts = [b if isinstance(b, str) else b.get("text") for b in resp if isinstance(b, (str, dict))]
        parts = [p for p in parts if isinstance(p, str)]
        return "\n".join(parts) if parts else json.dumps(resp, ensure_ascii=False)
    return None


def prune():
    now = time.time()
    try:
        for name in os.listdir(ROOT):
            p = os.path.join(ROOT, name)
            if os.path.isdir(p) and now - os.path.getmtime(p) > STALE_SECS:
                shutil.rmtree(p, ignore_errors=True)
    except OSError:
        pass


def main():
    try:
        data = json.load(io.TextIOWrapper(sys.stdin.buffer, encoding="utf-8"))
    except Exception:
        return
    resp = next((data[k] for k in ("tool_response", "tool_output", "tool_result") if data.get(k) is not None), None)
    text = extract_text(resp)
    if not text:
        return
    tool = str(data.get("tool_name") or "")
    session = "".join(c for c in str(data.get("session_id") or "nosession") if c.isalnum() or c in "-_") or "nosession"
    folder = os.path.join(ROOT, session)
    os.makedirs(folder, exist_ok=True)
    name = "%d_%s.json" % (int(time.time() * 1000), tool.rsplit("__", 1)[-1])
    with open(os.path.join(folder, name), "w", encoding="utf-8") as f:
        json.dump({"tool_name": tool, "tool_input": data.get("tool_input") or {}, "saved_at": time.time(), "response": text}, f, ensure_ascii=False)
    prune()


if __name__ == "__main__":
    try:
        main()
    except Exception:
        pass
