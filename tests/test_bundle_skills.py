#!/usr/bin/env python3
"""스킬 폴더 사본(scripts/bundle_skills.py)과 GPT판(gpt/sync_from_claude.py)이 원본과 맞는지 검사한다."""
import filecmp
import os
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, ".."))
IGNORE = shutil.ignore_patterns("__pycache__", "*.pyc")


def test_bundled_copies_match_their_sources():
    proc = subprocess.run([sys.executable, os.path.join(ROOT, "scripts", "bundle_skills.py"), "--check"],
                          capture_output=True, text=True)
    assert proc.returncode == 0, proc.stdout + proc.stderr


def _diff(a, b, rel=""):
    """두 폴더의 다른 파일 목록(__pycache__ 제외)."""
    c = filecmp.dircmp(a, b, ignore=["__pycache__"])
    out = [os.path.join(rel, n) for n in c.left_only + c.right_only + c.diff_files + c.funny_files]
    for n in c.common_dirs:
        out += _diff(os.path.join(a, n), os.path.join(b, n), os.path.join(rel, n))
    return out


def test_gpt_sync_changes_nothing(tmp_path):
    # 레포 사본에서 sync를 돌리고 커밋된 gpt/·skills/와 비교한다 — 같으면 커밋된 GPT판이 최신이고 다시 돌려도 그대로다
    for d in ("skills", "shared", "hooks", "scripts", "gpt"):
        shutil.copytree(os.path.join(ROOT, d), tmp_path / d, ignore=IGNORE)
    for _ in range(2):
        proc = subprocess.run([sys.executable, str(tmp_path / "gpt" / "sync_from_claude.py")], capture_output=True, text=True)
        assert proc.returncode == 0, proc.stdout + proc.stderr
        filecmp.clear_cache()
        assert _diff(os.path.join(ROOT, "gpt"), tmp_path / "gpt") == []
        assert _diff(os.path.join(ROOT, "skills"), tmp_path / "skills") == []
