"""
일제점검 교차 항목 규칙 판정 (Phase 3-4)

JC-01: ① 계획 예산 vs ② 집행액
X07: ① 사업기간 vs ② 집행일
"""

from __future__ import annotations

import re
from typing import Any

from na_engine import CaseProfile


def _normalize_date(date_str: str) -> str | None:
    if not date_str:
        return None
    match = re.search(
        r"(\d{4})[.\-/년\s]*(\d{1,2})[.\-/월\s]*(\d{1,2})",
        str(date_str).strip(),
    )
    if match:
        y, m, d = int(match.group(1)), int(match.group(2)), int(match.group(3))
        return f"{y:04d}-{m:02d}-{d:02d}"
    return None


def _as_int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _plan_budget(parsed: dict[str, Any]) -> int:
    """① 계획 예산 — 예산집행계획 세목 합계 우선."""
    plan_items = parsed.get("budget_plan_items") or []
    if plan_items:
        total = sum(_as_int(i.get("amount")) for i in plan_items)
        if total > 0:
            return total
    plan = _as_int(parsed.get("plan_total_budget"))
    if plan > 0:
        return plan
    if parsed.get("budget_breakdown") is not None or parsed.get("business_period"):
        return _as_int(parsed.get("total_budget"))
    return 0


def _executed_amount(parsed: dict[str, Any]) -> int:
    executed = _as_int(parsed.get("total_executed"))
    if executed > 0:
        return executed
    items = parsed.get("execution_items") or []
    return sum(_as_int(i.get("amount")) for i in items)


def _execution_items(parsed: dict[str, Any]) -> list[dict[str, Any]]:
    """② 집행 건 — 비어 있으면 엑셀 원본·combined_text 에서 재추출."""
    items = list(parsed.get("execution_items") or [])
    if items:
        return items

    # 엑셀 원본 경로로 재시도 (L/P/T/U)
    path = parsed.get("execution_file_path") or parsed.get("_source_file") or ""
    if path:
        from parser import parse_execution_detail_excel

        retry = parse_execution_detail_excel(str(path))
        items = list(retry.get("execution_items") or [])
        if items:
            return items

    from parser import _extract_execution_items

    text = parsed.get("combined_text") or ""
    if "=== 집행내역서 ===" in text:
        text = text.split("=== 집행내역서 ===", 1)[1]
        if "\n=== " in text:
            text = text.split("\n=== ", 1)[0]
    if text.strip():
        return _extract_execution_items(text)
    return []


def _budget_plan_items(parsed: dict[str, Any]) -> list[dict[str, Any]]:
    items = list(parsed.get("budget_plan_items") or [])
    if items:
        return items

    from parser import _extract_budget_plan_items

    text = parsed.get("combined_text") or ""
    if "=== 사업계획서 ===" in text:
        text = text.split("=== 사업계획서 ===", 1)[1]
        if "\n=== " in text:
            text = text.split("\n=== ", 1)[0]
    if text.strip():
        return _extract_budget_plan_items(text)
    return []


def _business_period(parsed: dict[str, Any]) -> tuple[str, str, str, str]:
    period = parsed.get("business_period") or parsed.get("settlement_period") or {}
    start_raw = period.get("start", "") or ""
    end_raw = period.get("end", "") or ""
    start = _normalize_date(start_raw) or ""
    end = _normalize_date(end_raw) or ""
    if start and end:
        return start_raw, end_raw, start, end

    # 파서가 못 잡은 경우 combined_text / 원문에서 재추출
    from parser import _find_date_range

    for key in ("combined_text", "raw_text", "execution_plan"):
        blob = parsed.get(key)
        if not isinstance(blob, str) or len(blob) < 8:
            continue
        found = _find_date_range(
            blob,
            ["사업기간", "사업 기간", "추진기간", "공사기간", "수행기간", "계약기간"],
        )
        if found.get("start") and found.get("end"):
            start_raw, end_raw = found["start"], found["end"]
            start = _normalize_date(start_raw) or ""
            end = _normalize_date(end_raw) or ""
            if start and end:
                return start_raw, end_raw, start, end

    return start_raw, end_raw, start, end


def _result(
    grade: str,
    reason: str,
    extracted: str,
) -> dict[str, Any]:
    return {
        "judge_result": grade,
        "judge_reason": reason,
        "extracted_val": extracted,
        "check_method": "cross_rule",
        "similarity": None,
        "law_ref": "지방보조금 부정수급 일제점검",
    }


def rule_x07(parsed: dict[str, Any], profile: CaseProfile | None = None) -> dict[str, Any] | None:
    """X07: 사업기간 내 집행 여부 (① 기간 vs ② 집행거래일자)."""
    start_raw, end_raw, start, end = _business_period(parsed)
    items = _execution_items(parsed)

    if not start or not end:
        return _result(
            "W",
            "① 사업기간을 확인할 수 없어 집행일 대조 불가",
            "사업기간 미확인",
        )

    if not items:
        return _result(
            "W",
            f"② 집행거래일자를 확인할 수 없음 (사업기간 {start_raw}~{end_raw})",
            f"사업기간 {start}~{end}",
        )

    violations: list[str] = []
    checked = 0
    for item in items:
        raw = item.get("date") or item.get("raw_date") or ""
        exec_date = _normalize_date(str(raw))
        if not exec_date:
            continue
        checked += 1
        if exec_date < start or exec_date > end:
            name = item.get("item_name", "")
            amount = _as_int(item.get("amount"))
            violations.append(f"{exec_date} {name} {amount:,}원".strip())

    if checked == 0:
        return _result(
            "W",
            f"② 집행일자를 파싱하지 못함 (사업기간 {start_raw}~{end_raw})",
            f"사업기간 {start}~{end}, 집행 {len(items)}건",
        )

    if violations:
        sample = "; ".join(violations[:3])
        more = f" 외 {len(violations) - 3}건" if len(violations) > 3 else ""
        return _result(
            "F",
            f"사업기간({start_raw}~{end_raw}) 외 집행 {len(violations)}건 - {sample}{more}",
            f"기간외 {len(violations)}건 / 확인 {checked}건",
        )

    return _result(
        "P",
        f"사업기간({start_raw}~{end_raw}) 내 집행 확인 ({checked}건)",
        f"사업기간 {start}~{end}, 집행 {checked}건",
    )


def rule_jc01(parsed: dict[str, Any], profile: CaseProfile | None = None) -> dict[str, Any] | None:
    """JC-01: ① 예산집행(사용)계획 세목별 금액 vs ② 실제 집행액 대조."""
    plan_items = _budget_plan_items(parsed)
    plan = sum(_as_int(i.get("amount")) for i in plan_items) if plan_items else _plan_budget(parsed)

    exec_items = _execution_items(parsed)
    executed = _executed_amount(parsed)
    if executed <= 0 and exec_items:
        executed = sum(_as_int(i.get("amount")) for i in exec_items)

    if plan <= 0 and executed <= 0:
        return None  # 수치 부족 → 유사도 판정으로 위임

    if plan <= 0:
        return _result(
            "W",
            "① 예산집행계획(세목별 계획 금액)을 확인할 수 없어 집행액과 대조 불가",
            f"집행 {executed:,}원",
        )

    if executed <= 0:
        return _result(
            "W",
            "② 집행액을 확인할 수 없어 계획 예산과 대조 불가",
            f"계획 {plan:,}원",
        )

    rate = round(executed / plan * 100, 1)
    if plan_items:
        sample = ", ".join(
            f"{i.get('seomok', '')} {i.get('item_name', '')} {_as_int(i.get('amount')):,}원".strip()
            for i in plan_items[:3]
        )
        more = f" 외 {len(plan_items) - 3}개" if len(plan_items) > 3 else ""
        extracted = (
            f"계획 {len(plan_items)}개 항목 {plan:,}원"
            f" / 집행 {executed:,}원 (집행률 {rate}%)"
        )
        plan_detail = f"계획({sample}{more})"
    else:
        extracted = f"계획 {plan:,}원 / 집행 {executed:,}원 (집행률 {rate}%)"
        plan_detail = "계획 총액"

    if executed > plan:
        over = executed - plan
        return _result(
            "F",
            f"집행액이 {plan_detail}을 {over:,}원 초과 - {extracted}",
            extracted,
        )

    out_items = parsed.get("out_of_budget_items") or []
    if out_items:
        return _result(
            "W",
            f"예산 외 집행 징후 - {extracted}",
            extracted,
        )

    return _result(
        "P",
        f"예산집행계획 대비 실제 집행 대조 완료 - {extracted}",
        extracted,
    )


_HANDLERS = {
    "X07": rule_x07,
    "JC-01": rule_jc01,
}


def apply_cross_item_rule(
    external_id: str,
    parsed_data: dict[str, Any],
    profile: CaseProfile | None = None,
) -> dict[str, Any] | None:
    """
    교차 항목 규칙 판정.

    Returns:
        판정 dict 또는 None (유사도 등 일반 점검으로 진행)
    """
    handler = _HANDLERS.get(external_id or "")
    if not handler:
        return None
    return handler(parsed_data, profile)
