#!/usr/bin/env python3
"""Cowork처럼 스킬 폴더 하나만 따로 올렸을 때 스킬이 도는지 검사한다(표준 라이브러리 + pytest).

Claude 데스크톱 Cowork는 스킬 폴더 하나만 `/mnt/skills/plugins/<플러그인>:<스킬>`에 올린다 — 플러그인 루트의
`shared/`도, 옆 스킬 폴더도 없다. 여기서는 스킬 폴더를 같은 이름으로 임시 폴더에 홀로 복사하고, 그 안에서만
문서가 가리키는 파일이 있는지, 스크립트가 공용 코드를 찾는지, 보고서를 실제로 그릴 수 있는지 본다.
"""
import json
import os
import re
import shutil
import subprocess
import sys

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, ".."))
PLUGIN = "laighthouse-plugin-external"
SKILLS = sorted(n for n in os.listdir(os.path.join(ROOT, "skills")) if os.path.isdir(os.path.join(ROOT, "skills", n)))
REPORT = ("daily-report", "mtd-report", "monthly-report")
EXTERNAL = ("naver-search", "naver-news", "naver-blog", "weather-impact")
OVERALL = [n for n in SKILLS if n.startswith("overall-summary")]
TEXT = (".md", ".py", ".html", ".css", ".js", ".json", ".yaml", ".txt")
# 문서 안 `shared/…`·`assets/…`·`references/…` 경로와 python3 명령의 스크립트 경로
DOC_PATH = re.compile(r"`((?:shared|assets|references)/[^`\s]*)`|python3 ((?:assets|shared)/\S+\.py)")

sys.path.insert(0, HERE)
from test_fees import KEYS, OVERALL_TP, env  # noqa: E402


def mount(tmp_path, name):
    """스킬 폴더 하나만 <tmp>/mnt/skills/plugins/<플러그인>:<스킬> 에 복사한다."""
    plugins = tmp_path / "mnt" / "skills" / "plugins"
    dst = plugins / f"{PLUGIN}:{name}"
    shutil.copytree(os.path.join(ROOT, "skills", name), dst, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    # 스크립트의 플러그인 루트 후보(assets/../../../shared)가 없어야 스킬 폴더 안만 보는 셈이다
    assert not (tmp_path / "mnt" / "skills" / "shared").exists()
    return dst


def run(args, cwd, tmp_path, stdin=None):
    env_ = {"PATH": os.environ.get("PATH", ""), "HOME": str(tmp_path), "TMPDIR": str(tmp_path)}
    return subprocess.run([sys.executable, "-E", "-s", *args], cwd=cwd, env=env_, input=stdin,
                          capture_output=True, text=True, timeout=180)


def ok(proc):
    assert proc.returncode == 0, f"rc={proc.returncode}\n{proc.stdout[-2000:]}\n{proc.stderr[-2000:]}"
    return proc


@pytest.mark.parametrize("name", SKILLS)
def test_text_never_points_outside_the_skill_folder(name):
    base = os.path.join(ROOT, "skills", name)
    bad = []
    for dirpath, dirs, files in os.walk(base):
        dirs[:] = [d for d in dirs if d != "__pycache__"]
        for f in files:
            if f.endswith(TEXT) and not f.endswith(".min.js"):
                with open(os.path.join(dirpath, f), encoding="utf-8") as fh:
                    if "../" in fh.read():
                        bad.append(os.path.relpath(os.path.join(dirpath, f), base))
    assert not bad, f"스킬 폴더 밖을 가리키는 ../ : {bad}"


@pytest.mark.parametrize("name", SKILLS)
def test_paths_in_skill_docs_exist_inside_the_folder(tmp_path, name):
    # 스킬 자신의 문서만 본다 — shared/references/ 사본은 플러그인 공용 문서라 다른 계열 파일 이름도 나온다
    skill = mount(tmp_path, name)
    missing = []
    for dirpath, dirs, files in os.walk(skill):
        dirs[:] = [d for d in dirs if d not in ("__pycache__", "shared")]
        for f in files:
            if f.endswith(".md"):
                with open(os.path.join(dirpath, f), encoding="utf-8") as fh:
                    for m in DOC_PATH.finditer(fh.read()):
                        ref = m.group(1) or m.group(2)
                        if not any(c in ref for c in "<…*{") and not (skill / ref).exists():
                            missing.append((f, ref))
    assert not missing, missing


@pytest.mark.parametrize("name", SKILLS)
def test_every_script_finds_its_shared_code(tmp_path, name):
    skill = mount(tmp_path, name)
    assets = skill / "assets"
    if not assets.is_dir():
        return
    scripts = sorted(p for p in assets.iterdir() if p.suffix == ".py")
    text = {p: p.read_text(encoding="utf-8") for p in scripts}
    finds = [p for p in scripts if "for cand in" in text[p]]   # 공용 코드를 찾는 스크립트
    runs_on_import = [p for p in finds if 'if __name__ == "__main__"' not in text[p]]
    for p in runs_on_import:   # 불러오기만 해도 실행되는 진입 스크립트 — 실행해서 공용 코드를 찾았는지만 본다
        proc = run([str(p), "--help"], skill, tmp_path, stdin="")
        assert not re.search(r"찾을 수 없다|ModuleNotFoundError|ImportError", proc.stderr), proc.stderr[-2000:]
    # 나머지는 python3 assets/<x>.py 로 실행될 때처럼 assets/를 sys.path 앞에 두고 불러온다.
    # 공용 코드를 찾는 스크립트가 먼저 와야 그 뒤의 라이브러리 모듈이 report_kit 등을 찾는다.
    rest = [p for p in finds if p not in runs_on_import] + [p for p in scripts if p not in finds]
    code = ("import importlib.util, sys\nsys.path.insert(0, sys.argv[1])\n"
            "for i, p in enumerate(sys.argv[2:]):\n"
            "    spec = importlib.util.spec_from_file_location(f'cowork_check_{i}', p)\n"
            "    spec.loader.exec_module(importlib.util.module_from_spec(spec))\n")
    if rest:
        ok(run(["-c", code, str(assets), *map(str, rest)], skill, tmp_path))


@pytest.mark.parametrize("name", REPORT)
def test_report_skill_plans_and_renders(tmp_path, name):
    skill = mount(tmp_path, name)
    work = tmp_path / "work"
    # 보고서 종류는 폴더 이름에서 정한다 — Cowork 폴더 이름은 <플러그인>:<스킬>이다
    ok(run(["assets/report.py", "plan", "--brand", "테스트", "--date", "2026-10-11", "--work", str(work)], skill, tmp_path))
    assert json.loads((work / "plan.json").read_text(encoding="utf-8"))["type"] == name.split("-")[0]
    payload = tmp_path / "payload.json"
    payload.write_text(json.dumps({"meta": {"name": "t"}, "items": [
        {"order": 1, "analysis_artifact": {"type": "tree_map", "data": {}}}]}), encoding="utf-8")
    out = tmp_path / "out.html"
    ok(run(["shared/report_engine/render_report.py", str(payload), str(out)], skill, tmp_path))
    assert out.stat().st_size > 100_000   # 엔진 CSS·JS·차트 라이브러리를 인라인으로 담는다


@pytest.mark.parametrize("name", EXTERNAL)
def test_external_skill_prepare_asks_for_the_missing_response(tmp_path, name):
    skill = mount(tmp_path, name)
    (tmp_path / "resp").mkdir()
    res = json.loads(ok(run(["assets/prepare.py", "--brand", "테스트", "--range", "2026-10-01~2026-10-05",
                             "--responses", str(tmp_path / "resp")], skill, tmp_path)).stdout)
    assert res["missing"] and res["missing"][0]["brand_name"] == "테스트", res


@pytest.mark.parametrize("name", EXTERNAL)
def test_external_skill_renders_a_page(tmp_path, name):
    skill = mount(tmp_path, name)
    code = ("import string, sys\nsys.path[:0] = ['shared/assets/external_context', 'shared/assets']\nimport page\n"
            "kw = {f: '' for _, f, _, _ in string.Formatter().parse(page.PAGE) if f}\n"
            "for k in ('note', 'banner', 'extra', 'charts', 'specs', 'chartjs'):\n    kw.pop(k, None)\n"
            "print(len(page.render([], **kw)))\n")
    assert int(ok(run(["-c", code], skill, tmp_path)).stdout) > 100_000   # Chart.js 인라인


@pytest.mark.parametrize("name", OVERALL)
def test_overall_skill_prepare_falls_back_without_saved_responses(tmp_path, name):
    skill = mount(tmp_path, name)
    part = ["--part", name.rsplit("-", 1)[-1]] if name != "overall-summary" else []
    res = json.loads(ok(run(["assets/prepare.py", "--brand", "테스트", "--target-date", "2026-10-05", *part],
                            skill, tmp_path, stdin="")).stdout)
    assert "저장된 응답이 없다" in res["note"], res   # 저장 훅이 없을 때의 안내까지 간다


@pytest.mark.parametrize("name", OVERALL)
def test_overall_skill_builds_html_and_xlsx(tmp_path, name):
    skill = mount(tmp_path, name)
    rows = [{"date": "2026-10-01", "media": "Meta", "campaign_name": "A", "cost": 1000, "impressions": 100}]
    out = tmp_path / "out" / "r.html"
    p = {"out": str(out), "brand": "b", "target_date": "2026-10-05", "start_date": "2026-10-01", "metric_keys": KEYS,
         "currency": "₩", "dims": "valid dimensions: ['date', 'media', 'campaign_name']",
         "data": {"json": json.dumps(env(rows, ["media", "campaign_name"], "gross"))},
         "budgets": [{"month": "2026-10", "target_progress": OVERALL_TP}]}
    res = json.loads(ok(run(["assets/build_report.py"], skill, tmp_path, stdin=json.dumps(p))).stdout)
    assert res["out"] == str(out) and out.exists()
    assert res.get("xlsx") and os.path.exists(res["xlsx"]), res


def test_media_mix_result_without_saved_responses_asks_for_json(tmp_path):
    skill = mount(tmp_path, "media-mix-result")
    res = json.loads(ok(run(["assets/build_report.py", "--brand", "테스트", "--job-id", "abc"], skill, tmp_path)).stdout)
    assert "저장된 응답이 없다" in res["note"], res


def test_media_mix_result_builds_from_a_saved_response(tmp_path):
    skill = mount(tmp_path, "media-mix-result")
    out = tmp_path / "mm.html"
    job = os.path.join(HERE, "fixtures", "media_mix", "job-even.json")
    res = json.loads(ok(run(["assets/build_report.py", "--brand", "테스트", "--json", job, "--out", str(out)],
                            skill, tmp_path)).stdout)
    assert res["out"] == str(out).replace("\\", "/")
    html = out.read_text(encoding="utf-8")
    # 그리기 코드와 모양이 인라인되고 자리표시가 남지 않는다
    assert "function summaryTable" in html and ".mm-summary" in html and "__MM_VIEW_JS__" not in html
