"""
일제점검 통합 체크리스트 (47항목) — Phase 2 앱 연동

데이터 원본: scripts/phase1_inspection_items.py
문서: docs/phase1/08_일제점검_체크리스트_항목목록.md
"""

from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parent
if str(_ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(_ROOT / "scripts"))

from phase1_inspection_items import ALL_ITEMS, CROSS_RULES  # noqa: E402

# 통합 일제점검 자료유형 (CHAR(1) — 기존 1~4와 구분)
INSPECTION_DATA_TYPE = "0"

INSPECTION_CHECKLIST_NM = "지방보조금 부정수급 일제점검 체크리스트 (47항목)"

# 일제점검 PDF에 실제 포함된 세목 (프로필 최소 세트)
INSPECTION_SEOMOKS: tuple[str, ...] = (
    "101",
    "201-01",
    "201-02",
    "201-32",
    "201-33",
    "201-34",
    "202-01",
    "202-03",
    "203-01~04",
    "401-01",
)

INSPECTION_SEOMOK_LABELS: dict[str, str] = {
    "101": "인건비",
    "201-01": "사무관리비",
    "201-02": "공공운영비",
    "201-32": "운영수당",
    "201-33": "임차료",
    "201-34": "용역비",
    "202-01": "국내여비",
    "202-03": "국외업무여비",
    "203-01~04": "업무추진비",
    "401-01": "시설비",
}


def get_profile_schema() -> list[dict[str, str]]:
    """검토 화면 프로필 UI용 세목 목록."""
    return [
        {"code": code, "label": INSPECTION_SEOMOK_LABELS.get(code, code)}
        for code in INSPECTION_SEOMOKS
    ]

_RISK_BY_CLASS = {
    "C02": "H",
    "C03": "M",
    "C04": "M",
    "C05": "H",
    "C06": "M",
}


def _row_to_meta(row: tuple) -> dict[str, Any]:
    ext_id, pyeonseong, seomok, content, evidence, req_docs, integ_class, na_when = row
    return {
        "external_id": ext_id,
        "pyeonseong": pyeonseong,
        "seomok": seomok,
        "item_content": content,
        "required_evidence": evidence,
        "required_docs": req_docs,
        "integration_class": integ_class,
        "na_when": na_when,
    }


def get_all_item_meta() -> dict[str, dict[str, Any]]:
    """external_id → 메타데이터"""
    meta = {_row_to_meta(r)["external_id"]: _row_to_meta(r) for r in ALL_ITEMS}
    for row in CROSS_RULES:
        m = _row_to_meta(row)
        meta[m["external_id"]] = m
    return meta


ITEM_META_BY_ID: dict[str, dict[str, Any]] = get_all_item_meta()


def get_item_meta(external_id: str) -> dict[str, Any] | None:
    return ITEM_META_BY_ID.get(external_id)


def enrich_review_item(item: dict[str, Any]) -> dict[str, Any]:
    """DB 항목에 일제점검 메타 병합 (law_ref = external_id)."""
    ext_id = (item.get("law_ref") or "").strip()
    meta = get_item_meta(ext_id)
    if not meta:
        return item
    merged = dict(item)
    merged["external_id"] = ext_id
    merged.update({k: v for k, v in meta.items() if k != "item_content"})
    return merged


def build_json_item(item_no: int, row: tuple) -> dict[str, Any]:
    meta = _row_to_meta(row)
    ext_id = meta["external_id"]
    risk = _RISK_BY_CLASS.get(meta["integration_class"].split(",")[0], "M")
    criteria_parts = [
        f"구비: {meta['required_docs']}",
        f"점검서류: {meta['required_evidence']}" if meta["required_evidence"] != "-" else "",
        f"N/A: {meta['na_when']}" if meta["na_when"] != "-" else "",
    ]
    return {
        "item_no": item_no,
        "category": meta["pyeonseong"],
        "item_content": meta["item_content"],
        "judge_criteria": " | ".join(p for p in criteria_parts if p),
        "law_ref": ext_id,
        "risk_level": risk,
    }


def build_checklist_dict(include_cross: bool = True) -> dict[str, Any]:
    """DB·JSON 저장용 체크리스트 dict."""
    rows = list(ALL_ITEMS)
    if include_cross:
        rows.extend(CROSS_RULES)
    items = [build_json_item(i, row) for i, row in enumerate(rows, start=1)]
    return {
        "checklist_nm": INSPECTION_CHECKLIST_NM,
        "data_type": INSPECTION_DATA_TYPE,
        "base_law": "지방보조금 부정수급 일제점검 실시계획",
        "created_at": date.today().isoformat(),
        "items": items,
    }


def save_checklist_json(path: str | Path | None = None) -> Path:
    out = Path(path) if path else _ROOT / "checklists" / "checklist_inspection.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    data = build_checklist_dict()
    with open(out, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    return out


def build_review_items_for_test() -> list[dict[str, Any]]:
    """DB 없이 N/A·골든 테스트용 항목 목록."""
    items: list[dict[str, Any]] = []
    for i, row in enumerate(
        list(ALL_ITEMS) + list(CROSS_RULES),
        start=1,
    ):
        j = build_json_item(i, row)
        j["item_id"] = i
        items.append(enrich_review_item(j))
    return items
