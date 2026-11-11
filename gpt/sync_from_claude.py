#!/usr/bin/env python3
"""Claude Code판(레포 루트의 skills/·shared/·hooks/)을 GPT판(gpt/)으로 복사한다.

스킬 본문과 스크립트는 Claude판이 단일 소스다 — gpt/skills/와 gpt/hooks/*.py는 이 스크립트가 만드는
사본이므로 직접 고치지 않는다. Claude판을 고친 뒤 다시 실행한다:

    python gpt/sync_from_claude.py

하는 일:
- skills/<스킬>/ → gpt/skills/<스킬>/ (통째로 교체, __pycache__ 제외)
- 스킬마다 필요한 shared/ 부분을 gpt/skills/<스킬>/shared/ 로 넣는다 — 웹 Chat에는 스킬 zip 하나만 올라가므로
  스킬 폴더가 자기완결이어야 한다. 스크립트는 `assets/../shared/…`(번들)를 먼저 찾는다.
- overall-summary-* 하위 스킬은 `../overall-summary/`를 가리키므로, overall-summary의 assets·SKILL.md·섹션 문서를
  자기 폴더(assets/·references/)로 넣고 경로를 바꾼다.
- gpt/agents-meta/<스킬>.yaml → gpt/skills/<스킬>/agents/openai.yaml (ChatGPT 스킬 메타)
- 첫 제목 아래에 ChatGPT/Codex 환경 안내(GPT_NOTE)를 넣는다(스킬 계열별)
- hooks/*.py → gpt/hooks/ (hooks.json은 gpt/ 쪽 것을 유지 — ${PLUGIN_ROOT} 기준)
"""
import os
import re
import shutil

GPT = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(GPT)
IGNORE = shutil.ignore_patterns("__pycache__", "*.pyc")

REPORT = ("daily-report", "mtd-report", "monthly-report")
EXTERNAL = ("naver-search", "naver-news", "naver-blog", "weather-impact")
KIT_FILES = ("report_kit.py", "report_kit.css", "fees.py", "fees_legacy.py", "saved_responses.py")
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


def family(name):
    if name in REPORT:
        return "report"
    if name.startswith("overall-summary"):
        return "overall"
    if name in EXTERNAL:
        return "external"
    return None


def copy_shared(dst, fam):
    src, out = os.path.join(ROOT, "shared"), os.path.join(dst, "shared")
    if fam == "report":
        shutil.copytree(os.path.join(src, "report_engine"), os.path.join(out, "report_engine"), ignore=IGNORE)
        os.makedirs(os.path.join(out, "references"), exist_ok=True)
        shutil.copyfile(os.path.join(src, "references", "report-artifact-schema.md"),
                        os.path.join(out, "references", "report-artifact-schema.md"))
    elif fam == "overall":
        os.makedirs(os.path.join(out, "assets"), exist_ok=True)
        for f in KIT_FILES:
            shutil.copyfile(os.path.join(src, "assets", f), os.path.join(out, "assets", f))
        shutil.copytree(os.path.join(src, "references"), os.path.join(out, "references"), ignore=IGNORE)
    elif fam == "external":
        shutil.copytree(os.path.join(src, "assets", "external_context"), os.path.join(out, "assets", "external_context"),
                        ignore=IGNORE)
        os.makedirs(os.path.join(out, "references"), exist_ok=True)
        shutil.copyfile(os.path.join(src, "references", "mcp-tools.md"), os.path.join(out, "references", "mcp-tools.md"))


def rewrite(path, pairs):
    with open(path, encoding="utf-8") as f:
        text = f.read()
    for a, b in pairs:
        text = text.replace(a, b)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)


def inline_overall(dst):
    """overall-summary-* 하위 스킬: ../overall-summary/ 의 assets·문서를 자기 폴더로 넣는다."""
    base = os.path.join(ROOT, "skills", "overall-summary")
    shutil.copytree(os.path.join(base, "assets"), os.path.join(dst, "assets"), ignore=IGNORE, dirs_exist_ok=True)
    refs = os.path.join(dst, "references")
    os.makedirs(refs, exist_ok=True)
    for name in os.listdir(base):
        if name.startswith("overall-summary-section-") and name.endswith(".md"):
            shutil.copyfile(os.path.join(base, name), os.path.join(refs, name))
    main = os.path.join(refs, "overall-summary.md")
    shutil.copyfile(os.path.join(base, "SKILL.md"), main)
    # 본 스킬 문서 안의 섹션 문서 이름은 references/ 아래로
    rewrite(main, [(f"`{n}`", f"`references/{n}`") for n in os.listdir(refs) if n.startswith("overall-summary-section-")])
    rewrite(os.path.join(dst, "SKILL.md"), [
        ("../overall-summary/SKILL.md", "references/overall-summary.md"),
        ("../overall-summary/assets/", "assets/"),
        ("../overall-summary/overall-summary-section-", "references/overall-summary-section-"),
    ])


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
    shutil.copytree(src, dst, ignore=IGNORE)
    fam = family(name)
    if fam:
        copy_shared(dst, fam)
    if fam == "overall" and name != "overall-summary":
        inline_overall(dst)
    # 플러그인 루트 기준 경로 → 번들 안 shared/
    for dirpath, _, files in os.walk(dst):
        for f in files:
            if f.endswith(".md"):
                rewrite(os.path.join(dirpath, f), [("`../../shared/references/`", "`shared/references/`"),
                                                   ("../../shared/references/", "shared/references/")])
    meta = os.path.join(GPT, "agents-meta", f"{name}.yaml")
    if os.path.exists(meta):
        os.makedirs(os.path.join(dst, "agents"), exist_ok=True)
        shutil.copyfile(meta, os.path.join(dst, "agents", "openai.yaml"))
    if fam:
        note = NOTE[fam]
        if name == "overall-summary":   # 본 스킬은 자기 문서가 기준이다
            note = note.replace("이 문서(또는 `references/overall-summary.md`)의", "이 문서의")
        add_note(os.path.join(dst, "SKILL.md"), note)


def main():
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
