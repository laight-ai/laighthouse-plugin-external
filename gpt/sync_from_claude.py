#!/usr/bin/env python3
"""Claude Code판(레포 루트의 skills/·shared/·hooks/)을 GPT판(gpt/)으로 복사한다.

스킬 본문과 스크립트는 Claude판이 단일 소스다 — gpt/skills/와 gpt/hooks/*.py는 이 스크립트가 만드는
사본이므로 직접 고치지 않는다. Claude판을 고친 뒤 다시 실행한다:

    python gpt/sync_from_claude.py

하는 일:
- scripts/bundle_skills.py로 Claude판 스킬 폴더의 사본(shared/ 부분, overall-summary-* 하위 스킬의 assets/·references/)을
  먼저 원본에 맞춘다 — Claude판 스킬 폴더도 자기완결이므로(Cowork는 스킬 폴더만 올린다) GPT판은 그 폴더를 그대로 쓴다.
  웹 Chat에도 스킬 zip 하나만 올라가므로 같은 이유로 자기완결이어야 한다.
- skills/<스킬>/ → gpt/skills/<스킬>/ (통째로 교체, __pycache__ 제외)
- gpt/agents-meta/<스킬>.yaml → gpt/skills/<스킬>/agents/openai.yaml (ChatGPT 스킬 메타)
- 첫 제목 아래에 ChatGPT/Codex 환경 안내(GPT_NOTE)를 넣는다(스킬 계열별)
- hooks/*.py → gpt/hooks/ (hooks.json은 gpt/ 쪽 것을 유지 — ${PLUGIN_ROOT} 기준)
"""
import os
import re
import shutil
import sys

GPT = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(GPT)
IGNORE = shutil.ignore_patterns("__pycache__", "*.pyc")
sys.path.insert(0, os.path.join(ROOT, "scripts"))
import bundle_skills  # noqa: E402

HOOKS = ("capture_ad_performance.py", "capture_change_raw.py", "save_responses.py")

NOTE_HEAD = """> 🧩 **ChatGPT/Codex 환경**
> - 응답 저장 훅(`hooks/save_responses.py`·`capture_*.py`)은 ChatGPT 데스크톱 Work 모드·Codex에서 `/hooks`로 신뢰했을 때만 돈다.
>   그때는 아래 절차 그대로 동작한다(큰 응답은 저장 안내 한 줄로만 보인다).
> - 스크립트 경로(`assets/…`)는 이 스킬 폴더 기준이다. 결과 파일은 사용자가 내려받을 수 있는 위치(작업 환경의 출력 폴더)에 저장한다.
"""
NOTE = {
    "report": NOTE_HEAD + """> - 웹 Chat(스킬 업로드)에는 훅이 없다. `data`의 `missing_responses`에 key가 남으면 받은 응답 원문을 그대로
>   `$WORK/responses/<key>.json`에 저장하고 `data`를 다시 실행한다. 응답이 너무 커서 그대로 저장할 수 없으면 그 key는
>   저장하지 않고(해당 섹션 없이) 진행한다 — 일부만 저장하거나 값을 옮겨 적지 않는다.

""",
    "overall": NOTE_HEAD + """> - 웹 Chat(스킬 업로드)에는 훅이 없다. `prepare.py`가 `note`(저장된 응답 없음)를 내면 이 문서(또는 `references/overall-summary.md`)의
>   「빌더 입력 (build.json) — 저장 훅이 없는 호스트에서만 직접 만든다」대로 build.json을 직접 만든다.

""",
    "external": NOTE_HEAD + """> - 웹 Chat(스킬 업로드)에는 훅이 없다. `prepare.py`가 `missing`을 내면 받은 응답마다 쓰기 가능한 폴더 `<RESP>`에
>   `<번호>_<도구>.json` 파일로 `{"tool_name": "<도구>", "saved_at": <번호>, "tool_input": {<보낸 인자 그대로>}, "response": "<응답 원문 그대로>"}`를
>   저장하고 `prepare.py … --responses <RESP>`로 다시 실행한다. 응답 원문을 고치거나 줄이지 않는다.

""",
}


def add_note(path, note):
    with open(path, encoding="utf-8") as f:
        text = f.read()
    m = re.search(r"^---\n.*?\n---\n", text, re.S)          # 앞머리(frontmatter) 뒤
    head, body = (text[:m.end()], text[m.end():]) if m else ("", text)
    h = re.search(r"^# .*\n", body, re.M)                    # 첫 제목이 있으면 그 아래, 없으면 앞머리 바로 아래
    if h:
        body = body[:h.end()] + "\n" + note + body[h.end():].lstrip("\n")
    else:
        body = "\n" + note + body.lstrip("\n")
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(head + body)


def copy_skill(name):
    src = os.path.join(ROOT, "skills", name)
    dst = os.path.join(GPT, "skills", name)
    shutil.rmtree(dst, ignore_errors=True)
    shutil.copytree(src, dst, ignore=IGNORE)   # Claude판 스킬 폴더가 이미 자기완결이다(bundle_skills)
    fam = bundle_skills.family(name)
    meta = os.path.join(GPT, "agents-meta", f"{name}.yaml")
    if os.path.exists(meta):
        os.makedirs(os.path.join(dst, "agents"), exist_ok=True)
        shutil.copyfile(meta, os.path.join(dst, "agents", "openai.yaml"))
    if fam in NOTE:
        note = NOTE[fam]
        if name == "overall-summary":   # 본 스킬은 자기 문서가 기준이다
            note = note.replace("이 문서(또는 `references/overall-summary.md`)의", "이 문서의")
        add_note(os.path.join(dst, "SKILL.md"), note)


def main():
    bundle_skills.bundle()
    names = sorted(n for n in os.listdir(os.path.join(ROOT, "skills")) if os.path.isdir(os.path.join(ROOT, "skills", n)))
    for stale in os.listdir(os.path.join(GPT, "skills")):   # Claude판에서 없어진 스킬(예: laighthouse-report)
        if stale not in names:
            shutil.rmtree(os.path.join(GPT, "skills", stale), ignore_errors=True)
            print("removed", stale)
    for name in names:
        copy_skill(name)
        print("skill", name)
    os.makedirs(os.path.join(GPT, "hooks"), exist_ok=True)
    for old in os.listdir(os.path.join(GPT, "hooks")):
        if old.endswith(".py") and old not in HOOKS:
            os.remove(os.path.join(GPT, "hooks", old))
            print("removed hook", old)
    for h in HOOKS:
        shutil.copyfile(os.path.join(ROOT, "hooks", h), os.path.join(GPT, "hooks", h))
        print("hook", h)


if __name__ == "__main__":
    main()
