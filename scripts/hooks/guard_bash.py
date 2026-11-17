"""PreToolUse(Bash) 훅: 시크릿 유출·실수 발행을 막는 안전장치. 차단 시 exit 2."""
import json
import re
import sys

sys.stderr.reconfigure(encoding="utf-8")

try:
    cmd = (json.load(sys.stdin).get("tool_input") or {}).get("command", "")
except Exception:
    sys.exit(0)

RULES = [
    (r"git\s+add\s+(-A|--all|\.)\b.*", None),  # 통과(아래 .env 검사로 별도 처리)
    (r"git\s+(add|commit).*\.env(?!\.example)", "`.env` 는 커밋 금지입니다."),
    (r"git\s+(add|commit).*\.key\b", "라이선스 비밀키(*.key) 는 커밋 금지입니다."),
    (r"git\s+(add|commit).*\.browser_profile", "브라우저 세션 폴더는 커밋 금지입니다."),
    (r"curl[^|]*\|\s*(sh|bash)", "원격 스크립트 파이프 실행은 금지입니다."),
    (r"\"dry_run\"\s*:\s*false", "실제 발행 호출(dry_run=false) 은 사람이 UI에서 직접 하세요."),
]
for pat, msg in RULES:
    if msg and re.search(pat, cmd):
        print(f"차단됨: {msg}", file=sys.stderr)
        sys.exit(2)
