"""체크리스트 관리 라우터"""

import logging
from pathlib import Path

from fastapi import APIRouter, Request
from pydantic import BaseModel

import checklist
import checklist_db
import config
from web_common import DATA_TYPE_LABELS, templates

logger = logging.getLogger(__name__)
router = APIRouter()


class ToggleActiveRequest(BaseModel):
    """활성/비활성 전환 요청"""
    use_yn: str  # 'Y' 또는 'N'


class ItemUpdateRequest(BaseModel):
    category: str | None = None
    item_content: str | None = None
    judge_criteria: str | None = None
    law_ref: str | None = None
    risk_level: str | None = None


class ItemAddRequest(BaseModel):
    category: str = ""
    item_content: str
    judge_criteria: str = ""
    law_ref: str = ""
    risk_level: str = "M"


class GenerateRequest(BaseModel):
    data_type: str
    checklist_nm: str | None = None


class CreateEmptyRequest(BaseModel):
    """+ 새 생성 요청"""
    checklist_nm: str
    data_type: str
    base_law: str = ""


class GenerateFromKnowledgeRequest(BaseModel):
    """지식DB 기반 체크리스트 생성/재생성 요청"""
    data_type: str
    checklist_nm: str | None = None
    pdf_filenames: list[str] | None = None
    regenerate: bool = False


@router.get("")
async def checklist_page(request: Request):
    """SCR-002 체크리스트 관리 화면"""
    items = checklist_db.get_checklist_list_all()
    for item in items:
        item["data_type_nm"] = DATA_TYPE_LABELS.get(item["data_type"], item["data_type"])
    return templates.TemplateResponse(
        request,
        "checklist.html",
        {
            "active_page": "checklist",
            "checklists": items,
            "data_types": DATA_TYPE_LABELS,
        },
    )


@router.get("/api/list")
async def api_checklist_list(data_type: str | None = None):
    """체크리스트 목록 JSON (활성만)"""
    items = checklist_db.get_checklist_list(data_type)
    for item in items:
        item["data_type_nm"] = DATA_TYPE_LABELS.get(item["data_type"], item["data_type"])
        for k, v in item.items():
            if hasattr(v, "isoformat"):
                item[k] = v.isoformat()
    return {"items": items}


@router.get("/api/list-all")
async def api_checklist_list_all(data_type: str | None = None):
    """체크리스트 전체 목록 JSON (비활성 포함 — 관리 화면 전용)"""
    items = checklist_db.get_checklist_list_all(data_type)
    for item in items:
        item["data_type_nm"] = DATA_TYPE_LABELS.get(item["data_type"], item["data_type"])
        for k, v in item.items():
            if hasattr(v, "isoformat"):
                item[k] = v.isoformat()
    return {"items": items}


@router.get("/api/{checklist_id}")
async def api_checklist_detail(checklist_id: int):
    """체크리스트 상세 JSON"""
    detail = checklist_db.get_checklist_detail(checklist_id)
    if not detail:
        return {"error": "체크리스트를 찾을 수 없습니다."}
    detail["data_type_nm"] = DATA_TYPE_LABELS.get(detail["data_type"], detail["data_type"])
    for k, v in detail.items():
        if hasattr(v, "isoformat"):
            detail[k] = v.isoformat()
    for item in detail.get("items", []):
        for ik, iv in item.items():
            if hasattr(iv, "isoformat"):
                item[ik] = iv.isoformat()
    return detail


@router.post("/api/generate")
async def api_generate_checklist(body: GenerateRequest):
    """Gemini API 체크리스트 생성 (공개자료만)"""
    if body.data_type not in DATA_TYPE_LABELS:
        return {"success": False, "message": "지원하지 않는 자료유형입니다."}

    try:
        result = checklist.generate_checklist(body.data_type)
        json_path = checklist.save_checklist_json(result, body.data_type)
        checklist_id = checklist_db.save_checklist(json_path, created_by="web")
        return {
            "success": True,
            "checklist_id": checklist_id,
            "item_cnt": len(result.get("items", [])),
            "message": "체크리스트 생성 완료",
        }
    except Exception as exc:
        logger.error("체크리스트 생성 실패: %s", exc)
        return {"success": False, "message": str(exc)}


@router.post("/api/create-empty")
async def api_create_empty_checklist(body: CreateEmptyRequest):
    """+ 새 생성 — 빈 체크리스트 생성 후 항목 직접 추가"""
    if body.data_type not in DATA_TYPE_LABELS:
        return {"success": False, "message": "지원하지 않는 자료유형입니다."}
    if not body.checklist_nm.strip():
        return {"success": False, "message": "체크리스트 이름을 입력하세요."}

    try:
        checklist_id = checklist_db.create_empty_checklist(
            checklist_nm=body.checklist_nm,
            data_type=body.data_type,
            base_law=body.base_law,
            created_by="web",
        )
        return {
            "success": True,
            "checklist_id": checklist_id,
            "message": f"'{body.checklist_nm}' 체크리스트가 생성되었습니다. 항목을 추가해 주세요.",
        }
    except Exception as exc:
        logger.error("빈 체크리스트 생성 실패: %s", exc)
        return {"success": False, "message": str(exc)}


@router.post("/api/generate-from-knowledge")
async def api_generate_from_knowledge(body: GenerateFromKnowledgeRequest):
    """지식DB(open_docs) 파일을 참조하여 체크리스트 생성 또는 재생성"""
    if body.data_type not in DATA_TYPE_LABELS:
        return {"success": False, "message": "지원하지 않는 자료유형입니다."}

    try:
        knowledge_dir = Path(config.PUBLIC_DATA_PATH)
        if not knowledge_dir.is_dir():
            return {"success": False, "message": f"지식DB 폴더를 찾을 수 없습니다: {config.PUBLIC_DATA_PATH}"}

        if body.pdf_filenames:
            pdf_paths = [
                str(knowledge_dir / fn)
                for fn in body.pdf_filenames
                if (knowledge_dir / fn).is_file() and fn.lower().endswith(".pdf")
            ]
            if not pdf_paths:
                return {"success": False, "message": "지정한 PDF 파일을 지식DB에서 찾을 수 없습니다."}
        else:
            pdf_paths = None

        deactivated_ids: list[int] = []
        if body.regenerate and body.pdf_filenames:
            status_map = checklist_db.get_source_file_status(body.pdf_filenames)
            for fn, info in status_map.items():
                if info.get("has_checklist") and info.get("checklist_id"):
                    cid = info["checklist_id"]
                    if info.get("use_yn") == "Y":
                        checklist_db.toggle_checklist_active(cid, "N")
                    deactivated_ids.append(cid)
            logger.info("재생성 — 기존 체크리스트 비활성화: %s", deactivated_ids)

        result = checklist.generate_checklist(body.data_type, pdf_paths=pdf_paths)

        if body.checklist_nm:
            result["checklist_nm"] = body.checklist_nm

        source_file = body.pdf_filenames[0] if body.pdf_filenames else None
        items = result.get("items", [])

        if not items:
            type_config = checklist.DATA_TYPE_CONFIG.get(body.data_type, {})
            checklist_id = checklist_db.save_checklist_empty(
                source_file=source_file or "",
                checklist_nm=result.get("checklist_nm", ""),
                data_type=body.data_type,
                base_law=result.get("base_law", type_config.get("base_law", "")),
                created_by="web",
            )
            action = "재생성" if body.regenerate else "생성"
            return {
                "success": True,
                "empty": True,
                "checklist_id": checklist_id,
                "item_cnt": 0,
                "checklist_nm": result.get("checklist_nm", ""),
                "regenerate": body.regenerate,
                "deactivated_ids": deactivated_ids,
                "message": f"체크리스트를 {action}했으나 추출할 항목이 없습니다.",
            }

        json_path = checklist.save_checklist_json(result, body.data_type)
        checklist_id = checklist_db.save_checklist(
            json_path,
            created_by="web",
            source_file=source_file,
        )

        action = "재생성" if body.regenerate else "생성"
        return {
            "success": True,
            "checklist_id": checklist_id,
            "item_cnt": len(result.get("items", [])),
            "checklist_nm": result.get("checklist_nm", ""),
            "regenerate": body.regenerate,
            "deactivated_ids": deactivated_ids,
            "message": f"지식DB 기반 체크리스트 {action} 완료",
        }
    except Exception as exc:
        logger.error("지식DB 기반 체크리스트 생성 실패: %s", exc)
        return {"success": False, "message": str(exc)}


@router.put("/api/{checklist_id}/item/{item_id}")
async def api_update_item(checklist_id: int, item_id: int, body: ItemUpdateRequest):
    """체크리스트 항목 수정"""
    try:
        data = body.model_dump(exclude_none=True)
        ok = checklist_db.update_checklist_item(item_id, data)
        return {"success": ok}
    except Exception as exc:
        return {"success": False, "message": str(exc)}


@router.post("/api/{checklist_id}/item")
async def api_add_item(checklist_id: int, body: ItemAddRequest):
    """체크리스트 항목 추가"""
    try:
        item_id = checklist_db.add_checklist_item(
            checklist_id,
            body.model_dump(),
        )
        return {
            "success": True,
            "item_id": item_id,
            "message": "항목이 추가되었습니다.",
        }
    except Exception as exc:
        logger.error("항목 추가 실패: %s", exc)
        return {"success": False, "message": str(exc)}


@router.delete("/api/{checklist_id}/item/{item_id}")
async def api_delete_item(checklist_id: int, item_id: int):
    """체크리스트 항목 삭제"""
    try:
        ok = checklist_db.delete_checklist_item(item_id)
        return {"success": ok, "message": "항목이 삭제되었습니다." if ok else "항목을 찾을 수 없습니다."}
    except Exception as exc:
        return {"success": False, "message": str(exc)}


@router.delete("/api/{checklist_id}")
async def api_delete_checklist(checklist_id: int):
    """체크리스트 삭제"""
    ok = checklist_db.delete_checklist(checklist_id)
    return {"success": ok}


@router.patch("/api/{checklist_id}/toggle-active")
async def api_toggle_active(checklist_id: int, body: ToggleActiveRequest):
    """
    체크리스트 활성/비활성 전환.
    - use_yn='Y' → 활성화 (자료검토 콤보에 노출)
    - use_yn='N' → 비활성화 (자료검토 콤보에서 숨김, 데이터 보존)
    """
    if body.use_yn not in ("Y", "N"):
        return {"success": False, "message": "use_yn은 'Y' 또는 'N'이어야 합니다."}
    try:
        ok = checklist_db.toggle_checklist_active(checklist_id, body.use_yn)
        label = "활성화" if body.use_yn == "Y" else "비활성화"
        return {
            "success": ok,
            "use_yn": body.use_yn,
            "message": f"체크리스트가 {label}되었습니다." if ok else "체크리스트를 찾을 수 없습니다.",
        }
    except Exception as exc:
        logger.error("활성/비활성 전환 실패: %s", exc)
        return {"success": False, "message": str(exc)}

