#!/usr/bin/env python3
"""플러그인 공용 파일(shared/)과 overall-summary의 스크립트·문서를 스킬 폴더마다 복사해 넣는다.

왜 필요한가: Claude 데스크톱 Cowork는 스킬 폴더 하나만 `/mnt/skills/plugins/<플러그인>:<스킬>`에 올린다.
플러그인 루트의 `shared/`도, 옆 스킬 폴더(`../overall-summary/`)도 보이지 않는다. 그래서 스킬 폴더가
자기완결이어야 한다 — 스크립트는 `assets/../shared/…`(스킬 폴더 안)를 먼저 찾는다.

원본은 하나다: 플러그인 루트 `shared/`와 `skills/overall-summary/`. 스킬 폴더 안의 사본
(`skills/<스킬>/shared/`, overall-summary-* 하위 스킬의 `assets/`·`references/`)은 이 스크립트가 만든다.
사본을 직접 고치지 말고 원본을 고친 뒤 다시 실행한다:

    python3 scripts/bundle_skills.py           # 사본을 원본에 맞춘다
    python3 scripts/bundle_skills.py --check   # 어긋난 파일만 출력하고 0이 아닌 값으로 끝낸다

GPT판(gpt/sync_from_claude.py)도 이 스크립트로 Claude판 스킬 폴더를 맞춘 뒤 그 폴더를 그대로 복사한다.
"""
import argparse
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SKILLS = os.path.join(ROOT, "skills")
SHARED = os.path.join(ROOT, "shared")
OVERALL = "overall-summary"

REPORT = ("daily-report", "mtd-report", "monthly-report")
EXTERNAL = ("naver-search", "naver-news", "naver-blog", "weather-impact")
MEDIA_MIX = ("media-mix-result",)
KIT_FILES = ("report_kit.py", "report_kit.css", "fees.py", "fees_legacy.py", "saved_responses.py")

# 계열마다 스킬 폴더의 shared/ 아래로 넣을 것 — 플러그인 shared/ 기준 경로, 폴더면 통째로
SHARED_BY_FAMILY = {
    "report": ("report_engine", "references/report-artifact-schema.md"),
    "overall": tuple(f"assets/{f}" for f in KIT_FILES) + ("references",),
    "external": ("assets/external_context", "references/mcp-tools.md"),
    "media-mix": ("assets/saved_responses.py",),   # 저장 훅 응답 리더만
}


def family(name):
    if name in REPORT:
        return "report"
    if name.startswith(OVERALL):
        return "overall"
    if name in EXTERNAL:
        return "external"
    if name in MEDIA_MIX:
        return "media-mix"
    return None


def skill_names():
    return sorted(n for n in os.listdir(SKILLS) if os.path.isdir(os.path.join(SKILLS, n)))


def is_overall_sub(name):
    return name.startswith(OVERALL + "-")


def generated_roots(name):
    """이 스크립트가 통째로 관리하는 스킬 폴더 안 하위 폴더. 이 안의 파일은 전부 사본이다."""
    return ("shared", "assets", "references") if is_overall_sub(name) else ("shared",)


def _walk(path):
    """path(파일 또는 폴더) 아래 파일의 상대 경로. __pycache__·.pyc는 뺀다."""
    if os.path.isfile(path):
        return [""]
    out = []
    for dirpath, dirs, files in os.walk(path):
        dirs[:] = [d for d in dirs if d != "__pycache__"]
        for f in files:
            if not f.endswith(".pyc"):
                out.append(os.path.relpath(os.path.join(dirpath, f), path).replace(os.sep, "/"))
    return sorted(out)


def _read(path):
    with open(path, "rb") as f:
        return f.read()


def plan(name):
    """스킬 폴더 기준 상대 경로 → 들어가야 할 내용(bytes)."""
    out = {}
    for item in SHARED_BY_FAMILY.get(family(name), ()):
        src = os.path.join(SHARED, item)
        for rel in _walk(src):
            out["/".join(p for p in ("shared", item, rel) if p)] = _read(os.path.join(src, rel) if rel else src)
    if is_overall_sub(name):
        # 하위 스킬은 overall-summary의 스크립트·문서를 자기 폴더(assets/·references/)로 넣는다
        base = os.path.join(SKILLS, OVERALL)
        for rel in _walk(os.path.join(base, "assets")):
            out["assets/" + rel] = _read(os.path.join(base, "assets", rel))
        sections = sorted(n for n in os.listdir(base) if n.startswith(OVERALL + "-section-") and n.endswith(".md"))
        for n in sections:
            out["references/" + n] = _read(os.path.join(base, n))
        # 본 스킬 문서는 references/overall-summary.md로 — 안의 섹션 문서 이름은 references/ 아래로 바꾼다
        text = _read(os.path.join(base, "SKILL.md")).decode("utf-8")
        for n in sections:
            text = text.replace(f"`{n}`", f"`references/{n}`")
        out["references/overall-summary.md"] = text.encode("utf-8")
    return out


def drift(name):
    """(종류, 스킬 폴더 기준 경로) 목록. 종류: differs·missing·extra."""
    want = plan(name)
    skill = os.path.join(SKILLS, name)
    have = set()
    for root in generated_roots(name):
        if os.path.isdir(os.path.join(skill, root)):
            have.update(f"{root}/{rel}" for rel in _walk(os.path.join(skill, root)))
    out = []
    for rel in sorted(set(want) | have):
        if rel not in have:
            out.append(("missing", rel))
        elif rel not in want:
            out.append(("extra", rel))
        elif _read(os.path.join(skill, rel)) != want[rel]:
            out.append(("differs", rel))
    return out


def _prune_empty(path):
    """빈 폴더를 아래에서부터 지운다."""
    for dirpath, _, _ in os.walk(path, topdown=False):
        if not os.listdir(dirpath):
            os.rmdir(dirpath)


def bundle():
    """모든 스킬 폴더의 사본을 원본에 맞춘다. 바꾼 (종류, 스킬/경로) 목록을 돌려준다."""
    changed = []
    for name in skill_names():
        skill = os.path.join(SKILLS, name)
        want = plan(name)
        for kind, rel in drift(name):
            path = os.path.join(skill, rel)
            if kind == "extra":
                os.remove(path)
            else:
                os.makedirs(os.path.dirname(path), exist_ok=True)
                with open(path, "wb") as f:
                    f.write(want[rel])
            changed.append((kind, f"{name}/{rel}"))
        for root in generated_roots(name):
            if os.path.isdir(os.path.join(skill, root)):
                _prune_empty(os.path.join(skill, root))
    for kind, rel in changed:
        print(f"{kind}\tskills/{rel}")
    return changed


def check():
    return [(kind, f"{name}/{rel}") for name in skill_names() for kind, rel in drift(name)]


def main(argv=None):
    p = argparse.ArgumentParser(description="스킬 폴더에 shared/·overall-summary 사본을 넣는다(Cowork는 스킬 폴더만 올린다).")
    p.add_argument("--check", action="store_true", help="고치지 않고 어긋난 파일만 출력한다(있으면 종료 코드 1)")
    args = p.parse_args(argv)
    if args.check:
        bad = check()
        for kind, rel in bad:
            print(f"{kind}\tskills/{rel}")
        if bad:
            print(f"사본 {len(bad)}개가 원본과 다르다 — python3 scripts/bundle_skills.py 를 실행한다", file=sys.stderr)
            return 1
        return 0
    bundle()
    return 0


if __name__ == "__main__":
    sys.exit(main())
