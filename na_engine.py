"""
일제점검 체크리스트 N/A(해당없음) 판정 엔진 — Phase 2

규칙 출처: docs/phase1/02_골든케이스_작성안.md, 07_판정유형_정의.md
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

# DB·UI 공통: 해당없음 (CHAR(1) 제약 — 'A' = Applicable skip / N/A)
JUDGE_NA = "A"

DOC_SYMBOL_TO_CODE = {
    "①": "1",
    "②": "2",
    "③": "3",
    "④": "4",
}


@dataclass
class CaseProfile:
    """사업 1건 검토용 프로필 (블록 B·C 최소 세트)."""

    has_plan: bool = True
    has_execution: bool = True
    has_proof: bool = True
    has_settlement: bool = True
    executed_seomoks: frozenset[str] = field(default_factory=frozenset)
    operating_grant_only: bool = False  # JC-04 운영비 교부 사업

    def doc_available(self) -> dict[str, bool]:
        return {
            "1": self.has_plan,
            "2": self.has_execution,
            "3": self.has_proof,
            "4": self.has_settlement,
        }


def parse_required_docs(required_docs: str) -> frozenset[str]:
    """「①,②」 형식 → {'1','2'}"""
    codes: set[str] = set()
    for part in required_docs.split(","):
        sym = part.strip()
        code = DOC_SYMBOL_TO_CODE.get(sym)
        if code:
            codes.add(code)
    return frozenset(codes)


def seomok_has_execution(executed: frozenset[str], item_seomok: str) -> bool:
    """② 집행내역에 해당 세목(또는 편성목) 집행건이 있는지."""
    if not item_seomok or item_seomok == "-":
        return True
    if item_seomok in executed:
        return True
    if item_seomok == "203-01~04":
        return any(e == "203" or e.startswith("203-") for e in executed)
    if item_seomok == "101":
        return any(e == "101" or e.startswith("101-") for e in executed)
    prefix = item_seomok.split("-")[0]
    return any(e == prefix or e.startswith(f"{prefix}-") for e in executed)


def evaluate_na(
    item_meta: dict[str, Any],
    profile: CaseProfile,
) -> tuple[str | None, str | None]:
    """
    N/A 여부 판정.

    Returns:
        (JUDGE_NA, reason) 또는 (None, None) — 후자는 일반 점검(유사도·규칙) 진행
    """
    external_id = item_meta.get("external_id", "")
    seomok = item_meta.get("seomok", "-")
    na_when = item_meta.get("na_when", "")
    required = parse_required_docs(item_meta.get("required_docs", ""))
    available = profile.doc_available()
    missing = {c for c in required if not available.get(c, False)}

    # JC-04: 운영비 교부 사업만 — 해당 없으면 N/A
    if external_id == "JC-04" and not profile.operating_grant_only:
        return JUDGE_NA, na_when or "운영비 교부 사업 아님"

    # ② 세목 집행 없음 → 비목별 항목 N/A
    if seomok != "-" and profile.has_execution:
        if not seomok_has_execution(profile.executed_seomoks, seomok):
            return JUDGE_NA, na_when or f"② {seomok} 집행 없음"

    if not missing:
        return None, None

    # ③만 없음
    if missing == {"3"}:
        if required == frozenset({"3"}):
            return JUDGE_NA, "③ 지출증빙 미제출"
        # ②+③ 교차: N/A 아님 → W는 compare 단계에서 처리
        return None, None

    # ③ 포함 복합이나 ③ 외 자료도 없음 → ③ 전용이면 N/A
    if missing == {"3"} and required <= frozenset({"3"}):
        return JUDGE_NA, "③ 지출증빙 미제출"

    # ①만 없음 + 교차 항목 → compare에서 W
    if missing == {"1"} and "1" in required and len(required) > 1:
        return None, None

    # 그 외 필수 자료 전부 없음 → N/A (점검 불가)
    if missing == required and required:
        labels = {"1": "①", "2": "②", "3": "③", "4": "④"}
        missing_labels = ",".join(labels[c] for c in sorted(missing))
        return JUDGE_NA, f"{missing_labels} 미제출"

    return None, None


def apply_cross_doc_w(
    item_meta: dict[str, Any],
    profile: CaseProfile,
) -> tuple[str, str] | None:
    """
    교차 항목에서 자료 부족 시 W(확인필요) 선판정.

    Returns:
        ('W', reason) 또는 None
    """
    external_id = item_meta.get("external_id", "")
    required = parse_required_docs(item_meta.get("required_docs", ""))
    available = profile.doc_available()
    missing = {c for c in required if not available.get(c, False)}

    # JC-01 은 required_docs=①,② 만 — ③ 없어도 계획↔집행 규칙 적용
    if not missing:
        return None

    if missing == {"3"} and "2" in required and "3" in required:
        return "W", "③ 미제출로 교차 대조 불가"

    if missing == {"1"} and "1" in required and len(required) > 1:
        return "W", "① 미제출로 교차 검증 불가"

    return None


def profile_to_snapshot(profile: CaseProfile) -> dict[str, Any]:
    """결과 화면·DB 저장용 프로필 스냅샷."""
    docs: list[str] = []
    if profile.has_plan:
        docs.append("1")
    if profile.has_execution:
        docs.append("2")
    if profile.has_proof:
        docs.append("3")
    if profile.has_settlement:
        docs.append("4")
    return {
        "docs": docs,
        "seomoks": sorted(profile.executed_seomoks),
        "operating_grant_only": profile.operating_grant_only,
    }


def encode_profile_remark(snapshot: dict[str, Any]) -> str:
    """tb_review.remark 에 넣을 압축 문자열 (VARCHAR 500)."""
    docs = ",".join(snapshot.get("docs") or [])
    seomoks = ",".join(snapshot.get("seomoks") or [])
    og = "1" if snapshot.get("operating_grant_only") else "0"
    return f"PROFILE|d={docs}|s={seomoks}|og={og}"


def decode_profile_remark(remark: str | None) -> dict[str, Any] | None:
    """remark 에서 프로필 스냅샷 복원. 없거나 삭제 표시면 None."""
    if not remark or not remark.startswith("PROFILE|"):
        return None
    parts: dict[str, str] = {}
    for token in remark.split("|")[1:]:
        if "=" in token:
            key, val = token.split("=", 1)
            parts[key] = val
    docs = [d for d in parts.get("d", "").split(",") if d]
    seomoks = [s for s in parts.get("s", "").split(",") if s]
    return {
        "docs": docs,
        "seomoks": seomoks,
        "operating_grant_only": parts.get("og") == "1",
    }
