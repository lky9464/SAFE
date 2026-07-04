"""감사사례 체크리스트 항목 병합 공통 유틸"""

from typing import Any


def merge_audit_items(
    base_items: list[dict[str, str]],
    extra_items: list[dict[str, str]],
    source_label: str,
) -> list[dict[str, str]]:
    """기존 항목에 감사사례 항목 병합 (item_no는 최종에 일괄 재부여)"""
    merged = [dict(item) for item in base_items]
    for raw in extra_items:
        criteria = raw["judge_criteria"]
        case_ref = raw.get("case_ref", "")
        if case_ref:
            criteria = f"{criteria} (출처: {source_label} {case_ref})"
        merged.append({
            "item_no": len(merged) + 1,
            "category": raw["category"],
            "item_content": raw["item_content"],
            "judge_criteria": criteria,
            "law_ref": raw["law_ref"],
            "risk_level": raw["risk_level"],
        })
    return merged


def renumber_items(items: list[dict[str, str]]) -> list[dict[str, str]]:
    for i, item in enumerate(items, 1):
        item["item_no"] = i
    return items
