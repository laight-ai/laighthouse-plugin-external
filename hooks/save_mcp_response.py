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

Large responses: when a result exceeds the host's token limit, the hook does not receive
the data but the host's notice ("Error: result (N characters) exceeds maximum allowed
tokens. Output has been saved to <path>.") — the full response is in <path>. The hook
then saves that file's content instead; if it cannot be read, the notice is saved with
`spilled_path` so `build_report.py collect` can retry (and never mistakes it for data).

Large responses are also kept out of the model's context: once a response longer than STUB_MIN
characters is saved, the hook replaces what the model sees with a one-line notice
(`hookSpecificOutput.updatedToolOutput`) — `build_report.py data` reads the saved copy, and the
model never needs the raw rows. Small responses (targets, promotions, short envelopes) pass through
unchanged, and so does anything when saving failed. The hook never fails the tool call: any error
is swallowed (the response then simply reaches the model as before).
"""

import io
import json
import os
import re
import shutil
import sys
import tempfile
import time

ROOT = os.path.join(tempfile.gettempdir(), "laighthouse_mcp_responses")
ARM_TTL = 3 * 3600
STALE_SECS = 24 * 3600
SPILL_RE = re.compile(r"^Error: result \([\d,]+ characters\) exceeds maximum allowed tokens\. Output has been saved to (.+?)\.?$")
SPILL_WAIT = 5.0
STUB_MIN = 3000   # responses longer than this are shown to the model as a short "saved" notice


def spilled_path(text):
    """Path of the host's saved full output when `text` is the "exceeds maximum allowed tokens" notice."""
    m = SPILL_RE.match(str(text).lstrip().split("\n", 1)[0].strip())
    if not m:
        return None
    path = m.group(1).strip()
    # only the host's own spill folder (…/tool-results/<file>)
    return path if os.path.basename(os.path.dirname(path)) == "tool-results" else None


def read_spilled(path, wait=SPILL_WAIT):
    deadline = time.time() + wait
    while True:
        try:
            with open(path, encoding="utf-8") as f:
                return f.read()
        except OSError:
            if time.time() >= deadline:
                return None
            time.sleep(0.25)


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


def rebuild_like(resp, new_text):
    """updatedToolOutput keeps the original tool output's shape, with only the text swapped."""
    if isinstance(resp, dict):
        if isinstance(resp.get("text"), str):
            return dict(resp, text=new_text)
        if "content" in resp:
            return dict(resp, content=rebuild_like(resp["content"], new_text))
        return new_text
    if isinstance(resp, list):
        return [{"type": "text", "text": new_text}]
    return new_text


def stub_text(rec, path):
    body = rec["response"]
    rows = None
    try:
        obj = json.loads(body)
        if isinstance(obj, dict) and isinstance(obj.get("rows"), list):
            rows = len(obj["rows"])
    except ValueError:
        pass
    size = f"{len(body):,}자" + (f", {rows}행" if rows is not None else "")
    return (f"[laighthouse-report] 응답 원본({size})을 저장했다: {path}\n"
            "이 응답은 읽거나 옮겨 적지 않는다 — `build_report.py data`가 저장본을 쓴다.")


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
    rec = {"tool_name": str(data.get("tool_name") or ""), "tool_input": tool_input, "saved_at": time.time(), "response": text}
    spill = spilled_path(text)
    if spill:
        full = read_spilled(spill)
        if full:
            rec["response"] = full
        else:
            rec["spilled_path"] = spill
    folder = os.path.join(ROOT, session)
    os.makedirs(folder, exist_ok=True)
    name = "%d_%s.json" % (int(time.time() * 1000), rec["tool_name"].rsplit("__", 1)[-1])
    path = os.path.join(folder, name)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(rec, f, ensure_ascii=False)
    prune()
    if "spilled_path" not in rec and len(rec["response"]) > STUB_MIN:
        out = {"hookSpecificOutput": {"hookEventName": "PostToolUse",
                                      "updatedToolOutput": rebuild_like(resp, stub_text(rec, path))}}
        sys.stdout.buffer.write(json.dumps(out, ensure_ascii=False).encode("utf-8"))


if __name__ == "__main__":
    try:
        main()
    except Exception:
        pass
