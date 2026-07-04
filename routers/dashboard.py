"""대시보드 라우터"""

import logging
from datetime import datetime

from fastapi import APIRouter, Request

import config
import logger as safe_logger
from web_common import DATA_TYPE_LABELS, RESULT_LABELS, templates

logger = logging.getLogger(__name__)
router = APIRouter()


def _get_stats() -> dict:
    """대시보드 현황 통계 조회"""
    connection = None
    try:
        connection = config.get_db_connection()
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT final_result, data_type, COUNT(*) AS cnt
                FROM tb_review
                WHERE remark IS NULL OR remark != '[DELETED]'
                GROUP BY final_result, data_type
                """
            )
            rows = cursor.fetchall()

            cursor.execute(
                """
                SELECT review_id, business_nm, data_type, review_at,
                       reviewer, final_result
                FROM tb_review
                WHERE remark IS NULL OR remark != '[DELETED]'
                ORDER BY review_at DESC
                LIMIT 10
                """
            )
            recent_rows = cursor.fetchall()
    except Exception as exc:
        logger.error("통계 조회 실패: %s", exc)
        rows, recent_rows = [], []
    finally:
        if connection:
            connection.close()

    total = pass_cnt = warn_cnt = fail_cnt = 0
    by_type = {
        dt: {"name": DATA_TYPE_LABELS[dt], "total": 0, "pass": 0, "warn": 0, "fail": 0}
        for dt in DATA_TYPE_LABELS
    }

    for row in rows:
        cnt = row["cnt"]
        dt = row["data_type"]
        fr = row["final_result"]
        total += cnt
        if fr == "P":
            pass_cnt += cnt
        elif fr == "W":
            warn_cnt += cnt
        elif fr == "F":
            fail_cnt += cnt
        if dt in by_type:
            by_type[dt]["total"] += cnt
            if fr == "P":
                by_type[dt]["pass"] += cnt
            elif fr == "W":
                by_type[dt]["warn"] += cnt
            elif fr == "F":
                by_type[dt]["fail"] += cnt

    recent = []
    for r in recent_rows:
        review_at = r["review_at"]
        if isinstance(review_at, datetime):
            review_at = review_at.strftime("%Y-%m-%d")
        recent.append({
            "review_id": r["review_id"],
            "business_nm": r["business_nm"],
            "data_type_nm": DATA_TYPE_LABELS.get(r["data_type"], r["data_type"]),
            "review_at": review_at,
            "reviewer": r["reviewer"],
            "final_result": r["final_result"],
            "final_result_nm": RESULT_LABELS.get(r["final_result"], r["final_result"]),
        })

    return {
        "total": total,
        "pass": pass_cnt,
        "warn": warn_cnt,
        "fail": fail_cnt,
        "by_type": by_type,
        "recent": recent,
    }


@router.get("/")
async def dashboard_page(request: Request):
    """SCR-001 대시보드 메인"""
    stats = _get_stats()
    return templates.TemplateResponse(
        request,
        "dashboard.html",
        {"active_page": "dashboard", "stats": stats},
    )


@router.get("/api/stats")
async def api_stats():
    """현황 통계 JSON (AJAX)"""
    return _get_stats()
