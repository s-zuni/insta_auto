"""PostToolUse 훅: 방금 수정한 파일을 즉시 검증한다. (Claude Code 가 stdin 으로 JSON 전달)

- apps/agent/**/*.py  → py_compile + ruff (설치돼 있을 때)
- schemas.py / types.ts 수정 → 반대쪽 계약 파일도 같이 고쳤는지 리마인드
- 실패 시 exit 2 + stderr → Claude 에게 피드백으로 전달됨
"""
import json
import os
import py_compile
import shutil
import subprocess
import sys

try:
    data = json.load(sys.stdin)
except Exception:
    sys.exit(0)

path = (data.get("tool_input") or {}).get("file_path", "").replace("\\", "/")
if not path:
    sys.exit(0)

sys.stderr.reconfigure(encoding="utf-8")
if not os.path.exists(path):
    sys.exit(0)

problems: list[str] = []

if path.endswith(".py") and "/apps/agent/" in path:
    try:
        py_compile.compile(path, doraise=True)
    except py_compile.PyCompileError as e:
        problems.append(f"문법 오류: {e}")
    if not problems and shutil.which("ruff"):
        r = subprocess.run(["ruff", "check", "--select", "E9,F63,F7,F82", path], capture_output=True, text=True)
        if r.returncode != 0:
            problems.append(r.stdout.strip())

if problems:
    print("\n".join(problems), file=sys.stderr)
    sys.exit(2)

if path.endswith("core/schemas.py"):
    print("계약 변경 감지: apps/web/src/lib/types.ts 도 동기화했는지 확인하세요.", file=sys.stderr)
elif path.endswith("lib/types.ts"):
    print("계약 변경 감지: apps/agent/core/schemas.py 도 동기화했는지 확인하세요.", file=sys.stderr)
