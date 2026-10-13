#!/usr/bin/env python3
"""PostToolUse hook: save laighthouse MCP responses (get_ad_performance /
get_target_progress_v2 / list_promotions) to a file, untouched — only while the
`laighthouse-report` skill has armed capture for this session.

Why: the `laighthouse-report` skill feeds MCP responses to its builder script. Without
this hook the model would have to re-type each response into a file, which is slow and
risks altering numbers. With it, `build_report.py collect` simply matches the saved
responses to the planned calls (same tool + same arguments) and copies them.

Capture is opt-in: `build_report.py arm` creates <root>/<session_id>/.armed (or
<root>/_any/.armed when the session id is unknown to the script). Without a marker
younger than ARM_TTL nothing is written, so ordinary laighthouse use outside the skill
leaves no files behind. `build_report.py render` deletes the responses it used; anything
left is pruned after STALE_SECS.

The matcher in hooks.json does not depend on the MCP server name (plugin server,
claude.ai connector, ...); the `brand_name` argument check below keeps other servers'
same-named tools out.

The hook never changes what the model sees (no stdout) and never fails the tool call:
any error is swallowed.
"""

import io
import json
import os
import shutil
import sys
import tempfile
import time

ROOT = os.path.join(tempfile.gettempdir(), "laighthouse_mcp_responses")
ARM_TTL = 3 * 3600
STALE_SECS = 24 * 3600


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


def armed(session):
    for path in (os.path.join(ROOT, session, ".armed"), os.path.join(ROOT, "_any", ".armed")):
        try:
            if time.time() - os.path.getmtime(path) < ARM_TTL:
                return True
        except OSError:
            pass
    return False


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
    tool_input = data.get("tool_input") or {}
    if not isinstance(tool_input, dict) or "brand_name" not in tool_input:
        return
    session = "".join(c for c in str(data.get("session_id") or "nosession") if c.isalnum() or c in "-_") or "nosession"
    if not armed(session):
        return
    resp = next((data[k] for k in ("tool_response", "tool_output", "tool_result") if data.get(k) is not None), None)
    text = extract_text(resp)
    if not text:
        return
    tool = str(data.get("tool_name") or "")
    folder = os.path.join(ROOT, session)
    os.makedirs(folder, exist_ok=True)
    name = "%d_%s.json" % (int(time.time() * 1000), tool.rsplit("__", 1)[-1])
    with open(os.path.join(folder, name), "w", encoding="utf-8") as f:
        json.dump({"tool_name": tool, "tool_input": tool_input, "saved_at": time.time(), "response": text}, f, ensure_ascii=False)
    prune()


if __name__ == "__main__":
    try:
        main()
    except Exception:
        pass
