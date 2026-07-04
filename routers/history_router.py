"""검토 이력 라우터"""

import csv
import io
import logging
from datetime import datetime

from fastapi import APIRouter, Query, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

import logger as safe_logger
from web_common import DATA_TYPE_LABELS, RESULT_LABELS, get_static_version, templates

logger = logging.getLogger(__name__)
router = APIRouter()


class DeleteSelectedRequest(BaseModel):
    review_ids: list[int] = Field(..., min_length=1)


class DeleteAllRequest(BaseModel):
    data_type: str | None = None
    final_result: str | None = None
    reviewer: str | None = None
    date_from: str | None = None
    date_to: str | None = None
    keyword: str | None = None


def _filter_kwargs(
    data_type: str | None = None,
    final_result: str | None = None,
    reviewer: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    keyword: str | None = None,
) -> dict:
    return {
        "data_type": data_type,
        "final_result": final_result,
        "reviewer": reviewer,
        "date_from": date_from,
        "date_to": date_to,
        "keyword": keyword,
    }


def _serialize_items(items: list[dict]) -> list[dict]:
    """datetime 직렬화"""
    result = []
    for item in items:
        row = dict(item)
        for k, v in row.items():
            if hasattr(v, "isoformat"):
                row[k] = v.isoformat()
        row["data_type_nm"] = DATA_TYPE_LABELS.get(row.get("data_type", ""), "")
        row["final_result_nm"] = RESULT_LABELS.get(row.get("final_result", ""), "")
        result.append(row)
    return result


@router.get("")
async def history_page(request: Request):
    """SCR-005 검토 이력 조회 화면"""
    return templates.TemplateResponse(
        request,
        "history.html",
        {
            "active_page": "history",
            "data_types": DATA_TYPE_LABELS,
            "result_labels": RESULT_LABELS,
            "static_ver": get_static_version("static/js/history.js"),
        },
    )


@router.get("/api/list")
async def api_history_list(
    data_type: str | None = None,
    final_result: str | None = None,
    reviewer: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    keyword: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
):
    """이력 목록 JSON (필터·페이징)"""
    filters = {
        **_filter_kwargs(data_type, final_result, reviewer, date_from, date_to, keyword),
        "page": page,
        "page_size": page_size,
    }
    data = safe_logger.get_review_list(filters)
    data["items"] = _serialize_items(data["items"])
    return data


@router.get("/api/export")
async def api_history_export(
    data_type: str | None = None,
    final_result: str | None = None,
    reviewer: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    keyword: str | None = None,
):
    """CSV보내기 (감사용)"""
    filters = {
        **_filter_kwargs(data_type, final_result, reviewer, date_from, date_to, keyword),
        "page": 1,
        "page_size": 10000,
    }
    data = safe_logger.get_review_list(filters)

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "검토ID", "자료유형", "사업명", "검토일시",
        "담당자", "최종결과", "적합", "주의", "부적합", "파일명",
    ])
    for item in data["items"]:
        review_at = item["review_at"]
        if hasattr(review_at, "strftime"):
            review_at = review_at.strftime("%Y-%m-%d %H:%M:%S")
        writer.writerow([
            item["review_id"],
            DATA_TYPE_LABELS.get(item["data_type"], item["data_type"]),
            item["business_nm"],
            review_at,
            item["reviewer"],
            RESULT_LABELS.get(item["final_result"], item["final_result"]),
            item["pass_cnt"],
            item["warn_cnt"],
            item["fail_cnt"],
            item["file_nm"],
        ])

    filename = f"SAFE_검토이력_{datetime.now().strftime('%Y%m%d')}.csv"
    content = output.getvalue().encode("utf-8-sig")

    return StreamingResponse(
        io.BytesIO(content),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/api/delete-selected")
async def api_delete_selected(body: DeleteSelectedRequest):
    """선택한 검토 이력 소프트 삭제"""
    try:
        deleted = safe_logger.delete_reviews(body.review_ids)
        if deleted == 0:
            return {"success": False, "message": "삭제할 검토 이력을 찾을 수 없습니다.", "deleted": 0}
        return {
            "success": True,
            "message": f"검토 이력 {deleted}건을 삭제했습니다.",
            "deleted": deleted,
        }
    except Exception as exc:
        logger.error("선택 삭제 실패: %s", exc)
        return {"success": False, "message": str(exc), "deleted": 0}


@router.post("/api/delete-all")
async def api_delete_all(body: DeleteAllRequest):
    """현재 필터 조건에 해당하는 검토 이력 전체 소프트 삭제"""
    try:
        filters = body.model_dump()
        preview = safe_logger.get_review_list({**filters, "page": 1, "page_size": 1})
        total = preview["total"]
        if total == 0:
            return {"success": False, "message": "삭제할 검토 이력이 없습니다.", "deleted": 0}

        deleted = safe_logger.delete_reviews_by_filter(filters)
        return {
            "success": True,
            "message": f"검토 이력 {deleted}건을 삭제했습니다.",
            "deleted": deleted,
        }
    except Exception as exc:
        logger.error("전체 삭제 실패: %s", exc)
        return {"success": False, "message": str(exc), "deleted": 0}
