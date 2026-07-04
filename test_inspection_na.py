"""
일제점검 N/A 엔진 골든케이스 회귀 테스트 (G1, G4, G5, G6)

DB·임베딩 모델 없이 na_engine + inspection_checklist 메타만 검증.
"""

from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(_ROOT))

from inspection_checklist import ITEM_META_BY_ID, get_item_meta  # noqa: E402
from na_engine import JUDGE_NA, CaseProfile, apply_cross_doc_w, evaluate_na  # noqa: E402

PASS = "[PASS]"
FAIL = "[FAIL]"


def _judge(external_id: str, profile: CaseProfile) -> tuple[str, str]:
    meta = get_item_meta(external_id)
    if not meta:
        return "?", f"unknown id {external_id}"
    na, reason = evaluate_na(meta, profile)
    if na:
        return na, reason or ""
    cross = apply_cross_doc_w(meta, profile)
    if cross:
        return cross[0], cross[1]
    return "RUN", "일반 점검 진행"


def _expect_na(external_id: str, profile: CaseProfile, label: str = "") -> bool:
    grade, reason = _judge(external_id, profile)
    ok = grade == JUDGE_NA
    tag = label or external_id
    print(f"  {PASS if ok else FAIL} {tag}: {grade} - {reason}")
    return ok


def _expect_w(external_id: str, profile: CaseProfile, label: str = "") -> bool:
    grade, reason = _judge(external_id, profile)
    ok = grade == "W"
    tag = label or external_id
    print(f"  {PASS if ok else FAIL} {tag}: {grade} - {reason}")
    return ok


def _expect_run(external_id: str, profile: CaseProfile, label: str = "") -> bool:
    grade, reason = _judge(external_id, profile)
    ok = grade == "RUN"
    tag = label or external_id
    print(f"  {PASS if ok else FAIL} {tag}: {grade} - {reason}")
    return ok


def test_g1_facility_only() -> bool:
    """G1: 401만 집행, 101 없음 → J101-* N/A"""
    print("\n=== G1: 시설만, 101 집행 없음 ===")
    profile = CaseProfile(
        executed_seomoks=frozenset({"401-01", "401"}),
    )
    results = [
        _expect_na("J101-01", profile),
        _expect_na("J101-02", profile),
        _expect_run("J40101-02", profile),
        _expect_na("J20132-02", profile),
    ]
    return all(results)


def test_g4_rent_only() -> bool:
    """G4: 201-33 임차만"""
    print("\n=== G4: 201-33 임차만 ===")
    profile = CaseProfile(executed_seomoks=frozenset({"201-33"}))
    results = [
        _expect_na("J101-02", profile),
        _expect_na("J40101-02", profile),
        _expect_run("J20133-03", profile),
    ]
    return all(results)


def test_g5_facility_only() -> bool:
    """G5: 401 시설만"""
    print("\n=== G5: 401 시설만 ===")
    profile = CaseProfile(executed_seomoks=frozenset({"401-01"}))
    results = [
        _expect_run("J40101-02", profile),
        _expect_na("J101-02", profile),
    ]
    return all(results)


def test_g6_no_proof() -> bool:
    """G6: ③ 없음"""
    print("\n=== G6: ③ 없음 ===")
    profile = CaseProfile(
        has_proof=False,
        executed_seomoks=frozenset({"201-01"}),
    )
    results = [
        _expect_na("J20101-02", profile, "③전용 사무관리 증빙"),
        # JC-01 은 ①②만 필요 — ③ 없어도 계획↔집행 규칙으로 진행
        _expect_run("JC-01", profile, "계획vs집행 교차"),
        _expect_run("JC-02", profile, "② 비목 적정"),
        _expect_run("X07", profile, "사업기간 내 집행"),
    ]
    return all(results)


def test_item_count() -> bool:
    print("\n=== 메타 항목 수 ===")
    n = len(ITEM_META_BY_ID)
    ok = n == 48  # 47 + X07
    print(f"  {PASS if ok else FAIL} ITEM_META_BY_ID: {n} (기대 48)")
    return ok


def main() -> int:
    print("# 일제점검 N/A 골든케이스 테스트")
    results = [
        test_item_count(),
        test_g1_facility_only(),
        test_g4_rent_only(),
        test_g5_facility_only(),
        test_g6_no_proof(),
    ]
    passed = sum(results)
    total = len(results)
    print(f"\n결과: {passed}/{total}")
    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())
