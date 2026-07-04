"""
체크리스트 DB CRUD 모듈
tb_checklist, tb_checklist_item 테이블 연동
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any

import config

logger = logging.getLogger(__name__)


def save_checklist(
    json_path: str,
    created_by: str = "system",
    source_file: str | None = None,
) -> int:
    """
    JSON 파일의 체크리스트를 DB에 저장.

    Args:
        json_path: 체크리스트 JSON 파일 경로
        created_by: 등록자
        source_file: 생성에 사용된 지식DB 파일명 (없으면 None)
    """
    path = Path(json_path)
    if not path.is_file():
        raise FileNotFoundError(f"체크리스트 JSON 파일을 찾을 수 없습니다: {json_path}")

    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError) as exc:
        logger.error("JSON 파일 읽기 실패: %s", exc)
        raise RuntimeError(f"체크리스트 JSON 파일 읽기에 실패했습니다: {exc}") from exc

    items = data.get("items", [])
    if not items:
        raise ValueError("체크리스트 항목(items)이 비어 있습니다.")

    connection = None
    try:
        connection = config.get_db_connection()
        with connection.cursor() as cursor:
            # 마스터 저장
            sql_master = """
                INSERT INTO tb_checklist
                    (checklist_nm, data_type, base_law, source_file, item_cnt,
                     created_by, created_at, updated_at, use_yn)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """
            now = datetime.now()
            cursor.execute(
                sql_master,
                (
                    data.get("checklist_nm", ""),
                    str(data.get("data_type", "")),
                    data.get("base_law", ""),
                    source_file,
                    len(items),
                    created_by,
                    now,
                    now,
                    "Y",
                ),
            )
            checklist_id = cursor.lastrowid

            # 항목 저장
            sql_item = """
                INSERT INTO tb_checklist_item
                    (checklist_id, item_no, category, item_content,
                     judge_criteria, law_ref, risk_level, created_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """
            for item in items:
                cursor.execute(
                    sql_item,
                    (
                        checklist_id,
                        item.get("item_no", 0),
                        item.get("category", ""),
                        item.get("item_content", ""),
                        item.get("judge_criteria", ""),
                        item.get("law_ref", ""),
                        item.get("risk_level", "M"),
                        now,
                    ),
                )

            connection.commit()
            logger.info(
                "체크리스트 DB 저장 완료 — id: %d, 항목: %d개",
                checklist_id,
                len(items),
            )
            return checklist_id

    except Exception as exc:
        if connection:
            connection.rollback()
        logger.error("체크리스트 DB 저장 실패: %s", exc)
        raise RuntimeError(f"체크리스트 DB 저장에 실패했습니다: {exc}") from exc
    finally:
        if connection:
            connection.close()


def save_checklist_empty(
    *,
    source_file: str,
    checklist_nm: str,
    data_type: str,
    base_law: str = "",
    created_by: str = "web",
) -> int:
    """추출 항목이 없을 때 지식DB 파일과의 연결만 기록 (item_cnt=0, use_yn=N)"""
    connection = None
    try:
        connection = config.get_db_connection()
        with connection.cursor() as cursor:
            now = datetime.now()
            cursor.execute(
                """
                INSERT INTO tb_checklist
                    (checklist_nm, data_type, base_law, source_file, item_cnt,
                     created_by, created_at, updated_at, use_yn)
                VALUES (%s, %s, %s, %s, 0, %s, %s, %s, 'N')
                """,
                (checklist_nm, str(data_type), base_law, source_file, created_by, now, now),
            )
            checklist_id = cursor.lastrowid
            connection.commit()
            logger.info(
                "빈 체크리스트 기록 — id: %d, source_file: %s",
                checklist_id,
                source_file,
            )
            return checklist_id
    except Exception as exc:
        if connection:
            connection.rollback()
        logger.error("빈 체크리스트 기록 실패: %s", exc)
        raise RuntimeError(f"빈 체크리스트 기록에 실패했습니다: {exc}") from exc
    finally:
        if connection:
            connection.close()


def get_checklist_list(data_type: str | None = None) -> list[dict[str, Any]]:
    """
    체크리스트 목록 조회 (유형별 필터 가능).

    Args:
        data_type: "1"~"4" 또는 None(전체)

    Returns:
        체크리스트 마스터 목록
    """
    connection = None
    try:
        connection = config.get_db_connection()
        with connection.cursor() as cursor:
            if data_type:
                sql = """
                    SELECT checklist_id, checklist_nm, data_type, base_law,
                           item_cnt, created_by, created_at, updated_at, use_yn
                    FROM tb_checklist
                    WHERE data_type = %s AND use_yn = 'Y'
                    ORDER BY created_at DESC
                """
                cursor.execute(sql, (data_type,))
            else:
                sql = """
                    SELECT checklist_id, checklist_nm, data_type, base_law,
                           item_cnt, created_by, created_at, updated_at, use_yn
                    FROM tb_checklist
                    WHERE use_yn = 'Y'
                    ORDER BY created_at DESC
                """
                cursor.execute(sql)

            results = cursor.fetchall()
            logger.info("체크리스트 목록 조회 — %d건", len(results))
            return results

    except Exception as exc:
        logger.error("체크리스트 목록 조회 실패: %s", exc)
        raise RuntimeError(f"체크리스트 목록 조회에 실패했습니다: {exc}") from exc
    finally:
        if connection:
            connection.close()


def get_checklist_detail(checklist_id: int) -> dict[str, Any] | None:
    """
    체크리스트 상세 조회 (항목 포함).

    Args:
        checklist_id: 체크리스트 ID

    Returns:
        마스터 + items 목록 dict, 없으면 None
    """
    connection = None
    try:
        connection = config.get_db_connection()
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT checklist_id, checklist_nm, data_type, base_law,
                       item_cnt, created_by, created_at, updated_at, use_yn
                FROM tb_checklist
                WHERE checklist_id = %s
                """,
                (checklist_id,),
            )
            master = cursor.fetchone()
            if not master:
                logger.warning("체크리스트를 찾을 수 없습니다: id=%d", checklist_id)
                return None

            cursor.execute(
                """
                SELECT item_id, checklist_id, item_no, category, item_content,
                       judge_criteria, law_ref, risk_level, created_at
                FROM tb_checklist_item
                WHERE checklist_id = %s
                ORDER BY item_no
                """,
                (checklist_id,),
            )
            items = cursor.fetchall()

            result = dict(master)
            result["items"] = items
            logger.info(
                "체크리스트 상세 조회 — id: %d, 항목: %d개",
                checklist_id,
                len(items),
            )
            return result

    except Exception as exc:
        logger.error("체크리스트 상세 조회 실패: %s", exc)
        raise RuntimeError(f"체크리스트 상세 조회에 실패했습니다: {exc}") from exc
    finally:
        if connection:
            connection.close()


def update_checklist_item(item_id: int, data: dict[str, Any]) -> bool:
    """
    체크리스트 항목 수정.

    Args:
        item_id: 항목 ID
        data: 수정할 필드 dict
            (category, item_content, judge_criteria, law_ref, risk_level)

    Returns:
        수정 성공 여부
    """
    allowed_fields = {
        "category",
        "item_content",
        "judge_criteria",
        "law_ref",
        "risk_level",
    }
    update_fields = {k: v for k, v in data.items() if k in allowed_fields}

    if not update_fields:
        raise ValueError("수정할 항목이 없습니다.")

    if "risk_level" in update_fields and update_fields["risk_level"] not in ("H", "M", "L"):
        raise ValueError("risk_level은 H, M, L 중 하나여야 합니다.")

    set_clause = ", ".join(f"{field} = %s" for field in update_fields)
    values = list(update_fields.values()) + [item_id]

    connection = None
    try:
        connection = config.get_db_connection()
        with connection.cursor() as cursor:
            sql = f"UPDATE tb_checklist_item SET {set_clause} WHERE item_id = %s"
            affected = cursor.execute(sql, values)

            if affected == 0:
                logger.warning("수정 대상 항목을 찾을 수 없습니다: item_id=%d", item_id)
                return False

            # 마스터 updated_at 갱신
            cursor.execute(
                """
                UPDATE tb_checklist c
                INNER JOIN tb_checklist_item i ON c.checklist_id = i.checklist_id
                SET c.updated_at = %s
                WHERE i.item_id = %s
                """,
                (datetime.now(), item_id),
            )

            connection.commit()
            logger.info("체크리스트 항목 수정 완료 — item_id: %d", item_id)
            return True

    except Exception as exc:
        if connection:
            connection.rollback()
        logger.error("체크리스트 항목 수정 실패: %s", exc)
        raise RuntimeError(f"체크리스트 항목 수정에 실패했습니다: {exc}") from exc
    finally:
        if connection:
            connection.close()


def delete_checklist(checklist_id: int, hard_delete: bool = False) -> bool:
    """
    체크리스트 삭제.

    Args:
        checklist_id: 체크리스트 ID
        hard_delete: True면 물리 삭제, False면 use_yn='N' 소프트 삭제

    Returns:
        삭제 성공 여부
    """
    connection = None
    try:
        connection = config.get_db_connection()
        with connection.cursor() as cursor:
            if hard_delete:
                cursor.execute(
                    "DELETE FROM tb_checklist_item WHERE checklist_id = %s",
                    (checklist_id,),
                )
                affected = cursor.execute(
                    "DELETE FROM tb_checklist WHERE checklist_id = %s",
                    (checklist_id,),
                )
            else:
                affected = cursor.execute(
                    """
                    UPDATE tb_checklist
                    SET use_yn = 'N', updated_at = %s
                    WHERE checklist_id = %s AND use_yn = 'Y'
                    """,
                    (datetime.now(), checklist_id),
                )

            if affected == 0:
                logger.warning("삭제 대상 체크리스트를 찾을 수 없습니다: id=%d", checklist_id)
                return False

            connection.commit()
            logger.info(
                "체크리스트 삭제 완료 — id: %d (%s)",
                checklist_id,
                "물리삭제" if hard_delete else "소프트삭제",
            )
            return True

    except Exception as exc:
        if connection:
            connection.rollback()
        logger.error("체크리스트 삭제 실패: %s", exc)
        raise RuntimeError(f"체크리스트 삭제에 실패했습니다: {exc}") from exc
    finally:
        if connection:
            connection.close()


def load_checklist_for_review(checklist_id: int) -> dict[str, Any]:
    """
    문서 검토용 체크리스트 로드.
    활성(use_yn='Y') 체크리스트만 반환하며 검토에 필요한 필드만 포함.

    Args:
        checklist_id: 체크리스트 ID

    Returns:
        검토용 체크리스트 dict

    Raises:
        ValueError: 체크리스트가 없거나 비활성인 경우
    """
    detail = get_checklist_detail(checklist_id)

    if not detail:
        raise ValueError(f"체크리스트를 찾을 수 없습니다: id={checklist_id}")

    if detail.get("use_yn") != "Y":
        raise ValueError(f"비활성 체크리스트입니다: id={checklist_id}")

    review_items = [
        {
            "item_id": item["item_id"],
            "item_no": item["item_no"],
            "category": item["category"],
            "item_content": item["item_content"],
            "judge_criteria": item["judge_criteria"],
            "law_ref": item["law_ref"],
            "risk_level": item["risk_level"],
        }
        for item in detail.get("items", [])
    ]

    return {
        "checklist_id": detail["checklist_id"],
        "checklist_nm": detail["checklist_nm"],
        "data_type": detail["data_type"],
        "base_law": detail["base_law"],
        "item_cnt": detail["item_cnt"],
        "items": review_items,
    }


def add_checklist_item(checklist_id: int, data: dict[str, Any]) -> int:
    """
    체크리스트에 항목 추가.

    Args:
        checklist_id: 체크리스트 ID
        data: 추가할 항목 dict
            (category, item_content, judge_criteria, law_ref, risk_level)

    Returns:
        생성된 item_id
    """
    required = {"item_content"}
    if not required.issubset(data.keys()):
        raise ValueError("item_content는 필수 항목입니다.")

    risk_level = data.get("risk_level", "M")
    if risk_level not in ("H", "M", "L"):
        raise ValueError("risk_level은 H, M, L 중 하나여야 합니다.")

    connection = None
    try:
        connection = config.get_db_connection()
        with connection.cursor() as cursor:
            # 현재 최대 item_no 조회
            cursor.execute(
                "SELECT COALESCE(MAX(item_no), 0) AS max_no FROM tb_checklist_item WHERE checklist_id = %s",
                (checklist_id,),
            )
            row = cursor.fetchone()
            next_no = (row["max_no"] if row else 0) + 1

            now = datetime.now()
            cursor.execute(
                """
                INSERT INTO tb_checklist_item
                    (checklist_id, item_no, category, item_content,
                     judge_criteria, law_ref, risk_level, created_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    checklist_id,
                    next_no,
                    data.get("category", ""),
                    data["item_content"],
                    data.get("judge_criteria", ""),
                    data.get("law_ref", ""),
                    risk_level,
                    now,
                ),
            )
            item_id = cursor.lastrowid

            # 마스터 item_cnt / updated_at 갱신
            cursor.execute(
                """
                UPDATE tb_checklist
                SET item_cnt = item_cnt + 1, updated_at = %s
                WHERE checklist_id = %s
                """,
                (now, checklist_id),
            )

            connection.commit()
            logger.info(
                "체크리스트 항목 추가 완료 — checklist_id: %d, item_id: %d, item_no: %d",
                checklist_id,
                item_id,
                next_no,
            )
            return item_id

    except Exception as exc:
        if connection:
            connection.rollback()
        logger.error("체크리스트 항목 추가 실패: %s", exc)
        raise RuntimeError(f"체크리스트 항목 추가에 실패했습니다: {exc}") from exc
    finally:
        if connection:
            connection.close()


def delete_checklist_item(item_id: int) -> bool:
    """
    체크리스트 항목 삭제.

    Args:
        item_id: 삭제할 항목 ID

    Returns:
        삭제 성공 여부
    """
    connection = None
    try:
        connection = config.get_db_connection()
        with connection.cursor() as cursor:
            # 체크리스트 ID 확인
            cursor.execute(
                "SELECT checklist_id FROM tb_checklist_item WHERE item_id = %s",
                (item_id,),
            )
            row = cursor.fetchone()
            if not row:
                logger.warning("삭제 대상 항목을 찾을 수 없습니다: item_id=%d", item_id)
                return False

            checklist_id = row["checklist_id"]
            cursor.execute(
                "DELETE FROM tb_checklist_item WHERE item_id = %s",
                (item_id,),
            )

            # 마스터 item_cnt / updated_at 갱신
            cursor.execute(
                """
                UPDATE tb_checklist
                SET item_cnt = GREATEST(item_cnt - 1, 0), updated_at = %s
                WHERE checklist_id = %s
                """,
                (datetime.now(), checklist_id),
            )

            connection.commit()
            logger.info("체크리스트 항목 삭제 완료 — item_id: %d", item_id)
            return True

    except Exception as exc:
        if connection:
            connection.rollback()
        logger.error("체크리스트 항목 삭제 실패: %s", exc)
        raise RuntimeError(f"체크리스트 항목 삭제에 실패했습니다: {exc}") from exc
    finally:
        if connection:
            connection.close()


def create_empty_checklist(
    checklist_nm: str,
    data_type: str,
    base_law: str = "",
    created_by: str = "web",
) -> int:
    """
    빈 체크리스트(항목 0개) 생성. '+ 새 생성' 기능에서 사용.

    Args:
        checklist_nm: 체크리스트 이름
        data_type: 자료유형 코드 ("1"~"4")
        base_law: 근거 법령
        created_by: 등록자

    Returns:
        생성된 checklist_id
    """
    if not checklist_nm.strip():
        raise ValueError("체크리스트 이름은 필수입니다.")

    connection = None
    try:
        connection = config.get_db_connection()
        with connection.cursor() as cursor:
            now = datetime.now()
            cursor.execute(
                """
                INSERT INTO tb_checklist
                    (checklist_nm, data_type, base_law, item_cnt,
                     created_by, created_at, updated_at, use_yn)
                VALUES (%s, %s, %s, %s, %s, %s, %s, 'Y')
                """,
                (
                    checklist_nm.strip(),
                    str(data_type),
                    base_law.strip(),
                    0,
                    created_by,
                    now,
                    now,
                ),
            )
            checklist_id = cursor.lastrowid
            connection.commit()
            logger.info(
                "빈 체크리스트 생성 완료 — id: %d, 이름: %s",
                checklist_id,
                checklist_nm,
            )
            return checklist_id

    except Exception as exc:
        if connection:
            connection.rollback()
        logger.error("빈 체크리스트 생성 실패: %s", exc)
        raise RuntimeError(f"빈 체크리스트 생성에 실패했습니다: {exc}") from exc
    finally:
        if connection:
            connection.close()


def toggle_checklist_active(checklist_id: int, use_yn: str) -> bool:
    """
    체크리스트 활성/비활성 전환.

    Args:
        checklist_id: 체크리스트 ID
        use_yn: 'Y' (활성) 또는 'N' (비활성)

    Returns:
        변경 성공 여부
    """
    if use_yn not in ("Y", "N"):
        raise ValueError("use_yn은 'Y' 또는 'N'이어야 합니다.")

    connection = None
    try:
        connection = config.get_db_connection()
        with connection.cursor() as cursor:
            affected = cursor.execute(
                """
                UPDATE tb_checklist
                SET use_yn = %s, updated_at = %s
                WHERE checklist_id = %s
                """,
                (use_yn, datetime.now(), checklist_id),
            )
            if affected == 0:
                logger.warning(
                    "활성/비활성 변경 대상을 찾을 수 없습니다: id=%d", checklist_id
                )
                return False
            connection.commit()
            label = "활성화" if use_yn == "Y" else "비활성화"
            logger.info("체크리스트 %s 완료 — id: %d", label, checklist_id)
            return True

    except Exception as exc:
        if connection:
            connection.rollback()
        logger.error("체크리스트 활성/비활성 변경 실패: %s", exc)
        raise RuntimeError(f"체크리스트 상태 변경에 실패했습니다: {exc}") from exc
    finally:
        if connection:
            connection.close()


def get_checklist_list_all(data_type: str | None = None) -> list[dict[str, Any]]:
    """
    체크리스트 전체 목록 조회 (비활성 포함).
    관리 화면 전용 — 활성/비활성 여부를 함께 반환.

    Args:
        data_type: "1"~"4" 또는 None(전체)

    Returns:
        use_yn 포함 체크리스트 마스터 목록
    """
    connection = None
    try:
        connection = config.get_db_connection()
        with connection.cursor() as cursor:
            if data_type:
                sql = """
                    SELECT checklist_id, checklist_nm, data_type, base_law,
                           item_cnt, created_by, created_at, updated_at, use_yn
                    FROM tb_checklist
                    WHERE data_type = %s
                    ORDER BY use_yn DESC, created_at DESC
                """
                cursor.execute(sql, (data_type,))
            else:
                sql = """
                    SELECT checklist_id, checklist_nm, data_type, base_law,
                           item_cnt, created_by, created_at, updated_at, use_yn
                    FROM tb_checklist
                    ORDER BY use_yn DESC, created_at DESC
                """
                cursor.execute(sql)

            results = cursor.fetchall()
            logger.info("체크리스트 전체 목록 조회(비활성 포함) — %d건", len(results))
            return results

    except Exception as exc:
        logger.error("체크리스트 전체 목록 조회 실패: %s", exc)
        raise RuntimeError(f"체크리스트 전체 목록 조회에 실패했습니다: {exc}") from exc
    finally:
        if connection:
            connection.close()


def ensure_source_file_column() -> None:
    """tb_checklist.source_file 컬럼이 없으면 추가"""
    connection = None
    try:
        connection = config.get_db_connection()
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT COUNT(*) AS cnt
                FROM information_schema.COLUMNS
                WHERE TABLE_SCHEMA = %s
                  AND TABLE_NAME = 'tb_checklist'
                  AND COLUMN_NAME = 'source_file'
                """,
                (config.DB_NAME,),
            )
            row = cursor.fetchone()
            if row and row["cnt"] == 0:
                cursor.execute(
                    """
                    ALTER TABLE tb_checklist
                    ADD COLUMN source_file VARCHAR(500) NULL
                    COMMENT '생성에 사용된 지식DB 파일명'
                    AFTER base_law
                    """
                )
                connection.commit()
                logger.info("tb_checklist.source_file 컬럼 추가 완료")
    except Exception as exc:
        if connection:
            connection.rollback()
        logger.warning("source_file 컬럼 확인/추가 실패: %s", exc)
    finally:
        if connection:
            connection.close()


def get_source_file_status(filenames: list[str]) -> dict[str, dict]:
    """
    지식DB 파일명 목록에 대해 체크리스트 생성 현황 반환.

    파일명당 가장 최신 체크리스트 1건을 매핑한다.
    """
    if not filenames:
        return {}

    ensure_source_file_column()

    connection = None
    try:
        connection = config.get_db_connection()
        with connection.cursor() as cursor:
            placeholders = ", ".join(["%s"] * len(filenames))
            sql = f"""
                SELECT source_file, checklist_id, checklist_nm,
                       use_yn, item_cnt, updated_at, created_at
                FROM tb_checklist
                WHERE source_file IN ({placeholders})
                ORDER BY source_file, created_at DESC
            """
            cursor.execute(sql, filenames)
            rows = cursor.fetchall()

        result: dict[str, dict] = {}
        seen: set[str] = set()
        for row in rows:
            fn = row["source_file"]
            if fn not in seen:
                seen.add(fn)
                updated = row["updated_at"]
                result[fn] = {
                    "has_checklist": True,
                    "checklist_id": row["checklist_id"],
                    "checklist_nm": row["checklist_nm"],
                    "use_yn": row["use_yn"],
                    "item_cnt": row.get("item_cnt") or 0,
                    "updated_at": updated.isoformat()
                    if hasattr(updated, "isoformat")
                    else str(updated),
                }

        for fn in filenames:
            if fn not in result:
                result[fn] = {"has_checklist": False}

        logger.info("파일별 체크리스트 현황 조회 — %d개 파일", len(filenames))
        return result

    except Exception as exc:
        logger.error("파일별 체크리스트 현황 조회 실패: %s", exc)
        raise RuntimeError(f"파일별 체크리스트 현황 조회에 실패했습니다: {exc}") from exc
    finally:
        if connection:
            connection.close()
