"""
MariaDB 검토 로그 저장 모듈
검토 이력 저장, 조회, CSV보내기, 접근 로그
"""

import csv
import logging
from datetime import datetime
from pathlib import Path
from typing import Any

import config

logger = logging.getLogger(__name__)

# 자료유형 라벨
DATA_TYPE_LABELS: dict[str, str] = {
    "0": "일제점검(통합)",
    "1": "사업계획서",
    "2": "집행내역서",
    "3": "지출증빙자료",
    "4": "정산보고서",
}

# 최종결과 라벨
RESULT_LABELS: dict[str, str] = {
    "P": "적합",
    "W": "주의",
    "F": "부적합",
    "A": "해당없음",
}


def save_access_log(
    user_id: str,
    action: str,
    target_id: int | None = None,
    target_type: str | None = None,
    ip_addr: str | None = None,
    user_agent: str | None = None,
) -> int:
    """
    접근 로그 저장 (tb_access_log).

    Returns:
        생성된 log_id
    """
    connection = None
    try:
        connection = config.get_db_connection()
        with connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO tb_access_log
                    (user_id, action_type, target_id, target_type,
                     ip_addr, user_agent, logged_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    user_id,
                    action,
                    target_id,
                    target_type,
                    ip_addr,
                    user_agent,
                    datetime.now(),
                ),
            )
            log_id = cursor.lastrowid
            connection.commit()
            logger.info("접근 로그 저장 — action: %s, target: %s", action, target_id)
            return log_id
    except Exception as exc:
        if connection:
            connection.rollback()
        logger.error("접근 로그 저장 실패: %s", exc)
        raise RuntimeError(f"접근 로그 저장에 실패했습니다: {exc}") from exc
    finally:
        if connection:
            connection.close()


def save_review(
    review_data: dict[str, Any],
    file_info: dict[str, Any],
    reviewer: str,
) -> int:
    """
    검토 이력 마스터 저장 (tb_review).

    Args:
        review_data: checker.py compare 결과 (case_profile 스냅샷 포함 가능)
        file_info: 파일 정보 (file_nm, file_path, file_size, file_ext, ocr_yn)
        reviewer: 검토 담당자

    Returns:
        review_id
    """
    from na_engine import encode_profile_remark

    business_nm = (
        file_info.get("business_nm")
        or review_data.get("business_nm")
        or "미상"
    )

    remark = None
    case_profile = review_data.get("case_profile")
    if isinstance(case_profile, dict) and case_profile.get("docs") is not None:
        remark = encode_profile_remark(case_profile)

    connection = None
    try:
        connection = config.get_db_connection()
        with connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO tb_review
                    (business_nm, data_type, checklist_id, file_nm, file_path,
                     file_size, file_ext, ocr_yn, total_item_cnt,
                     pass_cnt, warn_cnt, fail_cnt, final_result,
                     reviewer, review_at, remark)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    business_nm,
                    str(review_data.get("data_type", "")),
                    review_data.get("checklist_id", 0),
                    file_info.get("file_nm", ""),
                    file_info.get("file_path", ""),
                    file_info.get("file_size", 0),
                    file_info.get("file_ext", ""),
                    file_info.get("ocr_yn", "N"),
                    review_data.get("total_items", 0),
                    review_data.get("pass_count", 0),
                    review_data.get("warn_count", 0),
                    review_data.get("fail_count", 0),
                    review_data.get("final_result", "W"),
                    reviewer,
                    datetime.now(),
                    remark,
                ),
            )
            review_id = cursor.lastrowid
            connection.commit()

            save_access_log(
                user_id=reviewer,
                action="REVIEW_CREATE",
                target_id=review_id,
                target_type="REVIEW",
            )

            logger.info("검토 이력 저장 — review_id: %d", review_id)
            return review_id

    except Exception as exc:
        if connection:
            connection.rollback()
        logger.error("검토 이력 저장 실패: %s", exc)
        raise RuntimeError(f"검토 이력 저장에 실패했습니다: {exc}") from exc
    finally:
        if connection:
            connection.close()


def save_review_details(
    review_id: int,
    details: list[dict[str, Any]],
    checklist_id: int | None = None,
) -> int:
    """
    항목별 판정 결과 저장 (tb_review_detail).

    Args:
        review_id: 검토 ID
        details: 판정 상세 목록
        checklist_id: 체크리스트 ID (규칙 항목 item_id=0 시 FK 대체용)

    Returns:
        저장된 항목 수
    """
    if not details:
        return 0

    # 규칙 기반 항목(item_id=0) FK 대체용 기본 item_id
    fallback_item_id = 1
    if checklist_id:
        import checklist_db

        checklist = checklist_db.get_checklist_detail(checklist_id)
        if checklist and checklist.get("items"):
            fallback_item_id = checklist["items"][0]["item_id"]

    connection = None
    try:
        connection = config.get_db_connection()
        with connection.cursor() as cursor:
            sql = """
                INSERT INTO tb_review_detail
                    (review_id, item_id, item_no, category, item_content,
                     extracted_val, judge_result, judge_reason, law_ref, similarity)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """
            for detail in details:
                item_id = detail.get("item_id", 0)
                if not item_id:
                    item_id = fallback_item_id

                similarity = detail.get("similarity")
                cursor.execute(
                    sql,
                    (
                        review_id,
                        item_id,
                        detail.get("item_no", 0),
                        detail.get("category", ""),
                        detail.get("item_content", ""),
                        detail.get("extracted_val", ""),
                        detail.get("judge_result", "W"),
                        detail.get("judge_reason", ""),
                        detail.get("law_ref", ""),
                        similarity,
                    ),
                )

            connection.commit()
            logger.info("검토 상세 저장 — review_id: %d, %d건", review_id, len(details))
            return len(details)

    except Exception as exc:
        if connection:
            connection.rollback()
        logger.error("검토 상세 저장 실패: %s", exc)
        raise RuntimeError(f"검토 상세 저장에 실패했습니다: {exc}") from exc
    finally:
        if connection:
            connection.close()


def save_duplicate_detect(
    review_id: int,
    duplicates: list[dict[str, Any]],
) -> int:
    """
    중복 증빙 탐지 결과 저장 (tb_duplicate_detect).

    Returns:
        저장된 건수
    """
    if not duplicates:
        return 0

    connection = None
    saved = 0
    try:
        connection = config.get_db_connection()
        with connection.cursor() as cursor:
            sql = """
                INSERT INTO tb_duplicate_detect
                    (review_id, file_nm_a, file_nm_b, file_hash_a, file_hash_b,
                     amount_a, amount_b, detect_type, detected_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """
            now = datetime.now()
            for dup in duplicates:
                files = dup.get("files", [])
                if len(files) < 2:
                    continue
                cursor.execute(
                    sql,
                    (
                        review_id,
                        Path(files[0]).name,
                        Path(files[1]).name,
                        dup.get("file_hash", ""),
                        dup.get("file_hash", ""),
                        dup.get("amount_a", 0),
                        dup.get("amount_b", 0),
                        dup.get("detect_type", "SHA256"),
                        now,
                    ),
                )
                saved += 1

            connection.commit()
            logger.info("중복 증빙 저장 — review_id: %d, %d건", review_id, saved)
            return saved

    except Exception as exc:
        if connection:
            connection.rollback()
        logger.error("중복 증빙 저장 실패: %s", exc)
        raise RuntimeError(f"중복 증빙 저장에 실패했습니다: {exc}") from exc
    finally:
        if connection:
            connection.close()


def _build_review_filters(filters: dict[str, Any]) -> tuple[str, list[Any]]:
    """조회 필터 SQL 조건 생성"""
    conditions = ["(remark IS NULL OR remark != '[DELETED]')"]
    params: list[Any] = []

    if filters.get("data_type"):
        conditions.append("data_type = %s")
        params.append(filters["data_type"])

    if filters.get("final_result"):
        conditions.append("final_result = %s")
        params.append(filters["final_result"])

    if filters.get("reviewer"):
        conditions.append("reviewer = %s")
        params.append(filters["reviewer"])

    if filters.get("date_from"):
        conditions.append("review_at >= %s")
        params.append(filters["date_from"])

    if filters.get("date_to"):
        conditions.append("review_at <= %s")
        params.append(f"{filters['date_to']} 23:59:59")

    if filters.get("keyword"):
        conditions.append("business_nm LIKE %s")
        params.append(f"%{filters['keyword']}%")

    where_clause = " AND ".join(conditions)
    return where_clause, params


def get_review_list(filters: dict[str, Any] | None = None) -> dict[str, Any]:
    """
    검토 이력 목록 조회 (필터·페이징).

    Returns:
        {"total": int, "page": int, "page_size": int, "items": list}
    """
    filters = filters or {}
    page = max(int(filters.get("page", 1)), 1)
    page_size = max(int(filters.get("page_size", 10)), 1)
    offset = (page - 1) * page_size

    where_clause, params = _build_review_filters(filters)
    connection = None

    try:
        connection = config.get_db_connection()
        with connection.cursor() as cursor:
            cursor.execute(
                f"SELECT COUNT(*) AS cnt FROM tb_review WHERE {where_clause}",
                params,
            )
            total = cursor.fetchone()["cnt"]

            cursor.execute(
                f"""
                SELECT review_id, business_nm, data_type, checklist_id,
                       file_nm, file_path, file_size, file_ext, ocr_yn,
                       total_item_cnt, pass_cnt, warn_cnt, fail_cnt,
                       final_result, reviewer, review_at, remark
                FROM tb_review
                WHERE {where_clause}
                ORDER BY review_at ASC, review_id ASC
                LIMIT %s OFFSET %s
                """,
                params + [page_size, offset],
            )
            items = cursor.fetchall()

            logger.info("검토 목록 조회 — %d건 (전체 %d)", len(items), total)
            return {
                "total": total,
                "page": page,
                "page_size": page_size,
                "items": items,
            }

    except Exception as exc:
        logger.error("검토 목록 조회 실패: %s", exc)
        raise RuntimeError(f"검토 목록 조회에 실패했습니다: {exc}") from exc
    finally:
        if connection:
            connection.close()


def get_review_detail(review_id: int, user_id: str = "system") -> dict[str, Any] | None:
    """
    검토 결과 상세 조회 (마스터 + 상세 항목).

    Returns:
        검토 상세 dict, 없으면 None
    """
    connection = None
    try:
        connection = config.get_db_connection()
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT review_id, business_nm, data_type, checklist_id,
                       file_nm, file_path, file_size, file_ext, ocr_yn,
                       total_item_cnt, pass_cnt, warn_cnt, fail_cnt,
                       final_result, reviewer, review_at, remark
                FROM tb_review
                WHERE review_id = %s
                  AND (remark IS NULL OR remark != '[DELETED]')
                """,
                (review_id,),
            )
            master = cursor.fetchone()
            if not master:
                logger.warning("검토 이력을 찾을 수 없습니다: review_id=%d", review_id)
                return None

            cursor.execute(
                """
                SELECT detail_id, review_id, item_id, item_no, category,
                       item_content, extracted_val, judge_result,
                       judge_reason, law_ref, similarity
                FROM tb_review_detail
                WHERE review_id = %s
                ORDER BY item_no, detail_id
                """,
                (review_id,),
            )
            details = cursor.fetchall()

            cursor.execute(
                """
                SELECT detect_id, review_id, file_nm_a, file_nm_b,
                       file_hash_a, file_hash_b, amount_a, amount_b,
                       detect_type, detected_at
                FROM tb_duplicate_detect
                WHERE review_id = %s
                """,
                (review_id,),
            )
            duplicates = cursor.fetchall()

            from na_engine import decode_profile_remark

            result = dict(master)
            result["details"] = details
            result["duplicates"] = duplicates
            result["na_cnt"] = sum(1 for d in details if d.get("judge_result") == "A")
            result["applicable_item_cnt"] = (
                int(result.get("pass_cnt") or 0)
                + int(result.get("warn_cnt") or 0)
                + int(result.get("fail_cnt") or 0)
            )
            result["case_profile"] = decode_profile_remark(result.get("remark"))

            save_access_log(
                user_id=user_id,
                action="REVIEW_VIEW",
                target_id=review_id,
                target_type="REVIEW",
            )

            logger.info("검토 상세 조회 — review_id: %d, 항목 %d건", review_id, len(details))
            return result

    except Exception as exc:
        logger.error("검토 상세 조회 실패: %s", exc)
        raise RuntimeError(f"검토 상세 조회에 실패했습니다: {exc}") from exc
    finally:
        if connection:
            connection.close()


def export_csv(filters: dict[str, Any], output_path: str, user_id: str = "system") -> str:
    """
    필터 조건으로 검토 이력 CSV보내기.

    Returns:
        생성된 CSV 파일 경로
    """
    filters = filters or {}
    filters["page"] = 1
    filters["page_size"] = 10000

    data = get_review_list(filters)
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    headers = [
        "검토ID", "자료유형", "사업명", "검토일시", "담당자",
        "최종결과", "적합", "주의", "부적합", "파일명",
    ]

    try:
        with open(path, "w", encoding="utf-8-sig", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(headers)
            for item in data["items"]:
                review_at = item["review_at"]
                if isinstance(review_at, datetime):
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

        save_access_log(
            user_id=user_id,
            action="EXPORT_CSV",
            target_type="REVIEW",
        )

        logger.info("CSV보내기 완료: %s (%d건)", path, len(data["items"]))
        return str(path)

    except OSError as exc:
        logger.error("CSV보내기 실패: %s", exc)
        raise RuntimeError(f"CSV보내기에 실패했습니다: {exc}") from exc


def delete_review(review_id: int, user_id: str = "system") -> bool:
    """
    검토 이력 소프트 삭제 (remark='[DELETED]').
    """
    return delete_reviews([review_id], user_id=user_id) == 1


def delete_reviews(review_ids: list[int], user_id: str = "system") -> int:
    """
    검토 이력 일괄 소프트 삭제 (remark='[DELETED]').

    Returns:
        삭제된 건수
    """
    ids = sorted({int(rid) for rid in review_ids if rid})
    if not ids:
        return 0

    connection = None
    try:
        connection = config.get_db_connection()
        with connection.cursor() as cursor:
            placeholders = ", ".join(["%s"] * len(ids))
            affected = cursor.execute(
                f"""
                UPDATE tb_review
                SET remark = '[DELETED]'
                WHERE review_id IN ({placeholders})
                  AND (remark IS NULL OR remark != '[DELETED]')
                """,
                ids,
            )
            if affected == 0:
                logger.warning("삭제 대상 검토를 찾을 수 없습니다: review_ids=%s", ids)
                return 0

            connection.commit()
            save_access_log(
                user_id=user_id,
                action="REVIEW_DELETE",
                target_id=ids[0],
                target_type="REVIEW",
            )
            logger.info("검토 이력 삭제 — %d건 (review_ids=%s)", affected, ids)
            return affected

    except Exception as exc:
        if connection:
            connection.rollback()
        logger.error("검토 이력 삭제 실패: %s", exc)
        raise RuntimeError(f"검토 이력 삭제에 실패했습니다: {exc}") from exc
    finally:
        if connection:
            connection.close()


def delete_reviews_by_filter(filters: dict[str, Any] | None = None, user_id: str = "system") -> int:
    """
    필터 조건에 맞는 검토 이력 전체 소프트 삭제.

    Returns:
        삭제된 건수
    """
    where_clause, params = _build_review_filters(filters or {})
    connection = None
    try:
        connection = config.get_db_connection()
        with connection.cursor() as cursor:
            affected = cursor.execute(
                f"""
                UPDATE tb_review
                SET remark = '[DELETED]'
                WHERE {where_clause}
                """,
                params,
            )
            if affected == 0:
                return 0

            connection.commit()
            save_access_log(
                user_id=user_id,
                action="REVIEW_DELETE",
                target_type="REVIEW",
            )
            logger.info("검토 이력 필터 삭제 — %d건", affected)
            return affected

    except Exception as exc:
        if connection:
            connection.rollback()
        logger.error("검토 이력 필터 삭제 실패: %s", exc)
        raise RuntimeError(f"검토 이력 삭제에 실패했습니다: {exc}") from exc
    finally:
        if connection:
            connection.close()
