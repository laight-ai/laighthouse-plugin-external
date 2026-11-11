#!/usr/bin/env python3
"""라이트하우스 보고서 엔진(shared/report_engine/build_report.py)을 이 스킬의 보고서 종류로 부르는 래퍼.

daily-report·mtd-report·monthly-report가 같은 파일을 쓴다 — 보고서 종류는 스킬 폴더 이름(`<종류>-report`)에서 정한다.
  python3 assets/report.py plan --brand <브랜드> --date <날짜> --work <WORK> [--author ...]
  python3 assets/report.py data --work <WORK>
  python3 assets/report.py render --work <WORK> --out <파일.html>  <<'EOF' ... EOF
"""
import os
import runpy
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
KIND = os.path.basename(os.path.dirname(HERE)).split("-")[0]   # daily | mtd | monthly

for cand in (os.path.join(HERE, "..", "shared", "report_engine"),            # zip 번들
             os.path.join(HERE, "..", "..", "..", "shared", "report_engine")):  # 플러그인 트리
    engine = os.path.normpath(os.path.join(cand, "build_report.py"))
    if os.path.exists(engine):
        break
else:
    raise SystemExit("build_report.py를 찾을 수 없다 (shared/report_engine)")

args = sys.argv[1:]
if args[:1] == ["plan"] and not any(a == "--type" or a.startswith("--type=") for a in args):
    if KIND not in ("daily", "mtd", "monthly"):
        raise SystemExit(f"스킬 폴더 이름({os.path.basename(os.path.dirname(HERE))})에서 보고서 종류를 알 수 없다 — "
                         "plan에 --type daily|mtd|monthly를 붙인다")
    args += ["--type", KIND]
sys.argv = [engine] + args
runpy.run_path(engine, run_name="__main__")
