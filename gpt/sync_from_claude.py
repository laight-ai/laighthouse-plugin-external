#!/usr/bin/env python3
"""Claude Code판(레포 루트의 skills/·hooks/)을 GPT판(gpt/)으로 복사한다.

스킬 본문과 스크립트는 Claude판이 단일 소스다 — gpt/skills/와 gpt/hooks/save_mcp_response.py는 이
스크립트가 만드는 사본이므로 직접 고치지 않는다. Claude판을 고친 뒤 다시 실행한다:

    python gpt/sync_from_claude.py

하는 일:
- skills/<스킬>/ → gpt/skills/<스킬>/ (통째로 교체, __pycache__ 제외)
- gpt/agents-meta/<스킬>.yaml → gpt/skills/<스킬>/agents/openai.yaml (ChatGPT 스킬 메타)
- laighthouse-report SKILL.md의 첫 제목 아래에 ChatGPT/Codex 환경 안내(GPT_NOTE)를 넣는다
- hooks/save_mcp_response.py → gpt/hooks/ (hooks.json은 gpt/ 쪽 것을 유지 — ${PLUGIN_ROOT} 기준)
"""
import os
import shutil

GPT = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(GPT)

GPT_NOTE = """> 🧩 **ChatGPT/Codex 환경**
> - 응답 저장 훅(`hooks/save_mcp_response.py`)은 ChatGPT 데스크톱 Work 모드·Codex에서 `/hooks`로 신뢰했을 때만 돈다.
>   그때는 아래 절차 그대로 동작한다(큰 응답은 저장 안내 한 줄로만 보인다).
> - 웹 Chat(스킬 업로드)에는 훅이 없다. `data`의 `missing_responses`에 key가 남으면 4단계의 "직접 저장" 방법으로
>   받은 응답을 `$WORK/responses/<key>.json`에 저장한다. `(대용량)` 표시가 있는 호출의 응답이 너무 커서 그대로
>   저장할 수 없으면 그 key는 저장하지 않고(해당 섹션 없이) 진행한다 — 일부만 저장하거나 값을 옮겨 적지 않는다.
> - `ASSETS`는 이 스킬 폴더의 `assets/` 절대 경로, `WORK`는 쓰기 가능한 임시 폴더다. 결과 HTML은 사용자가 내려받을
>   수 있는 위치(작업 환경의 출력 폴더)에 저장한다.

"""


def copy_skill(name):
    src = os.path.join(ROOT, "skills", name)
    dst = os.path.join(GPT, "skills", name)
    shutil.rmtree(dst, ignore_errors=True)
    shutil.copytree(src, dst, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    meta = os.path.join(GPT, "agents-meta", f"{name}.yaml")
    if os.path.exists(meta):
        os.makedirs(os.path.join(dst, "agents"), exist_ok=True)
        shutil.copyfile(meta, os.path.join(dst, "agents", "openai.yaml"))
    if name == "laighthouse-report":
        path = os.path.join(dst, "SKILL.md")
        text = open(path, encoding="utf-8").read()
        head, sep, rest = text.partition("\n# ")
        title, nl, body = rest.partition("\n")
        text = head + sep + title + nl + "\n" + GPT_NOTE + body.lstrip("\n")
        with open(path, "w", encoding="utf-8", newline="\n") as f:
            f.write(text)


def main():
    for name in sorted(os.listdir(os.path.join(ROOT, "skills"))):
        if os.path.isdir(os.path.join(ROOT, "skills", name)):
            copy_skill(name)
            print("skill", name)
    os.makedirs(os.path.join(GPT, "hooks"), exist_ok=True)
    shutil.copyfile(os.path.join(ROOT, "hooks", "save_mcp_response.py"), os.path.join(GPT, "hooks", "save_mcp_response.py"))
    print("hook save_mcp_response.py")


if __name__ == "__main__":
    main()
