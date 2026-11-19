"""한국어 카피라이팅 금지어 규칙 — 단일 진실 공급원(SSOT).

- 생성 프롬프트(`generators/*`)는 `prompt_rules()` 로 이 규칙을 주입한다.
- 테스트·스킬(prompt-tuner, harness-verify)은 `find_violations()` 로 결과물을 검사한다.
- 규칙을 바꾸면 CLAUDE.md §9 표도 같이 고친다.

CLI:  python -m apps.agent.core.copy_rules <파일.md|txt ...>   (위반 있으면 exit 1)
"""
from __future__ import annotations

import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

Category = Literal["번역투", "과장광고", "효능단정"]


@dataclass(frozen=True)
class Rule:
    category: Category
    pattern: str  # 정규식
    hint: str  # 대신 이렇게 쓰세요


RULES: tuple[Rule, ...] = (
    # --- AI 번역투 ---
    Rule("번역투", r"에\s?대해(서)?", "'~을/를' 로 바로 쓰기 (원두 보관에 대해 → 원두 보관법)"),
    Rule("번역투", r"[을를]\s?통해(서)?", "'~로/~해서' (앱을 통해 → 앱으로)"),
    Rule("번역투", r"것이\s?가능", "'~할 수 있어요'"),
    Rule("번역투", r"하는\s?것이\s?중요", "'꼭 ~하세요'"),
    Rule("번역투", r"로\s?인해", "'~때문에/~해서'"),
    Rule("번역투", r"되어\s?(지|졌|져|집)", "이중피동 → '돼요/됩니다'"),
    Rule("번역투", r"하도록\s?하겠습니다", "'~할게요/~합니다'"),
    Rule("번역투", r"에\s?있어서", "'~에서/~할 때'"),
    Rule("번역투", r"를?\s?가지고\s?있", "'~이 있어요'"),
    # --- 과장·허위 광고 (표시광고법) ---
    Rule("과장광고", r"업계\s?(1위|최초|유일)|국내\s?(1위|최초|유일)", "근거 자료 없으면 삭제"),
    Rule("과장광고", r"최고의|최상의|역대급|세계\s?최고", "구체적 사실로 대체 (예: '매일 아침 직접 로스팅')"),
    Rule("과장광고", r"100\s?%\s?(만족|효과|보장)|무조건|완벽(한|하게)?", "보장 표현 삭제"),
    Rule("과장광고", r"(평생|영구)\s?(보장|유지)", "기간·조건을 사실대로"),
    # --- 의학적·효능 단정 ---
    Rule("효능단정", r"(완치|치료|치유)(됩니다|돼요|효과)", "의료 효능 표현 금지"),
    Rule("효능단정", r"(살이|체지방이)\s?빠집니다|다이어트\s?효과", "개인차 있는 효과 단정 금지"),
    Rule("효능단정", r"부작용\s?(없|0)", "부작용 없음 단정 금지"),
    Rule("효능단정", r"(피부|탈모|모발).{0,6}(개선|재생)\s?(효과|보장)", "화장품·미용 효능 단정 금지"),
)

_COMPILED = tuple((r, re.compile(r.pattern)) for r in RULES)


@dataclass(frozen=True)
class Violation:
    category: Category
    matched: str
    hint: str
    line: int


def find_violations(text: str) -> list[Violation]:
    """텍스트에서 금지 표현을 찾아 (줄 번호 포함) 돌려준다."""
    out: list[Violation] = []
    for lineno, line in enumerate(text.splitlines() or [text], 1):
        for rule, rx in _COMPILED:
            for m in rx.finditer(line):
                out.append(Violation(rule.category, m.group(0), rule.hint, lineno))
    return out


def prompt_rules() -> str:
    """생성 프롬프트에 넣을 한국어 규칙 문단. (RULES 를 바꾸면 여기 예시도 맞춰 고칠 것)"""
    return (
        "한국어 품질 규칙: 한 문장 40자 안팎, 첫 문장은 훅, 피동 남발 금지, 이모지는 채널 규칙에 맞게만. "
        "번역투 금지(예: '~에 대해', '~를 통해', '~것이 가능', '~로 인해', '~되어지다'). "
        "과장 광고 금지(근거 없는 1위·최초·최고, 100% 보장, 무조건). "
        "효능 단정 금지(치료·완치, 살 빠짐, 부작용 없음, 피부·탈모 개선 보장). "
        "가짜 후기·없는 수치를 지어내지 말 것."
    )


def main(argv: list[str]) -> int:
    if not argv:
        print("사용법: python -m apps.agent.core.copy_rules <파일 ...>")
        return 2
    total = 0
    for p in argv:
        for v in find_violations(Path(p).read_text(encoding="utf-8")):
            total += 1
            print(f"{p}:{v.line}  [{v.category}] '{v.matched}' → {v.hint}")
    print(f"\n위반 {total}건" if total else "✅ 금지 표현 없음")
    return 1 if total else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
