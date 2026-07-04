"""설정 라우터"""

import logging
import os
import re
from pathlib import Path

from fastapi import APIRouter, Request
from pydantic import BaseModel

import checklist
import config
from web_common import templates

logger = logging.getLogger(__name__)
router = APIRouter()

_ENV_PATH = Path(__file__).resolve().parent.parent / ".env"


class SettingsUpdate(BaseModel):
    gemini_api_key: str | None = None
    gemini_model: str | None = None
    upload_path: str | None = None
    auto_clean_days: int | None = None


class ResetRequest(BaseModel):
    confirm_text: str = ""


class GeminiTestRequest(BaseModel):
    gemini_api_key: str | None = None


def _read_settings() -> dict:
    """현재 설정값 조회"""
    db_ok = False
    try:
        conn = config.get_db_connection()
        conn.close()
        db_ok = True
    except Exception:
        pass

    return {
        "gemini_api_key": "***" if config.GEMINI_API_KEY else "",
        "gemini_model": config.GEMINI_MODEL,
        "embedding_model": config.EMBEDDING_MODEL,
        "upload_path": config.UPLOAD_PATH,
        "public_data_path": config.PUBLIC_DATA_PATH,
        "db_host": config.DB_HOST,
        "db_port": config.DB_PORT,
        "db_name": config.DB_NAME,
        "db_connected": db_ok,
        "tesseract_path": config.TESSERACT_PATH,
        "ocr_lang": "kor+eng",
    }


def _update_env_value(key: str, value: str) -> None:
    """.env 파일 특정 키 업데이트"""
    lines: list[str] = []
    if _ENV_PATH.exists():
        lines = _ENV_PATH.read_text(encoding="utf-8").splitlines()

    pattern = re.compile(rf"^{re.escape(key)}=")
    found = False
    new_lines = []
    for line in lines:
        if pattern.match(line):
            new_lines.append(f"{key}={value}")
            found = True
        else:
            new_lines.append(line)
    if not found:
        new_lines.append(f"{key}={value}")

    _ENV_PATH.write_text("\n".join(new_lines) + "\n", encoding="utf-8")
    os.environ[key] = value


@router.get("")
async def settings_page(request: Request):
    """SCR-006 설정 화면"""
    return templates.TemplateResponse(
        request,
        "settings.html",
        {
            "active_page": "settings",
            "settings": _read_settings(),
        },
    )


@router.get("/api")
async def api_get_settings():
    """설정값 조회 JSON"""
    return _read_settings()


@router.put("/api")
async def api_update_settings(body: SettingsUpdate):
    """설정 저장"""
    try:
        if body.gemini_api_key and body.gemini_api_key != "***":
            _update_env_value("GEMINI_API_KEY", body.gemini_api_key)
            config.GEMINI_API_KEY = body.gemini_api_key
            checklist.reset_gemini_client()
        if body.gemini_model:
            _update_env_value("GEMINI_MODEL", body.gemini_model)
            config.GEMINI_MODEL = body.gemini_model
        if body.upload_path:
            _update_env_value("UPLOAD_PATH", body.upload_path)
            config.UPLOAD_PATH = body.upload_path
        return {"success": True, "message": "설정이 저장되었습니다."}
    except Exception as exc:
        logger.error("설정 저장 실패: %s", exc)
        return {"success": False, "message": str(exc)}


@router.post("/api/test-gemini")
async def api_test_gemini(body: GeminiTestRequest | None = None):
    """Gemini API 연결 테스트 (입력란 키 또는 .env 반영)"""
    try:
        config.reload_env_settings()
        checklist.reset_gemini_client()

        input_key = (body.gemini_api_key or "").strip() if body else ""
        if input_key and input_key != "***":
            config.GEMINI_API_KEY = input_key
            checklist.reset_gemini_client()

        if not config.GEMINI_API_KEY:
            return {
                "success": False,
                "message": "GEMINI_API_KEY가 설정되지 않았습니다. API 키를 입력하거나 .env 파일을 확인하세요.",
            }

        response = checklist.test_gemini_connection()
        return {"success": True, "message": response}
    except Exception as exc:
        return {"success": False, "message": str(exc)}


@router.post("/api/test-db")
async def api_test_db():
    """MariaDB 연결 테스트"""
    try:
        conn = config.get_db_connection()
        with conn.cursor() as cursor:
            cursor.execute("SELECT 1")
        conn.close()
        return {"success": True, "message": "DB 연결 성공"}
    except Exception as exc:
        return {"success": False, "message": str(exc)}


@router.post("/api/reset-db")
async def api_reset_db(body: ResetRequest):
    """DB 초기화 (확인 문구 필요)"""
    if body.confirm_text != "초기화":
        return {"success": False, "message": "'초기화'를 정확히 입력하세요."}

    connection = None
    try:
        connection = config.get_db_connection()
        with connection.cursor() as cursor:
            for table in [
                "tb_review_detail", "tb_duplicate_detect",
                "tb_review", "tb_access_log",
                "tb_checklist_item", "tb_checklist",
            ]:
                cursor.execute(f"DELETE FROM {table}")
            connection.commit()
        return {"success": True, "message": "DB가 초기화되었습니다."}
    except Exception as exc:
        if connection:
            connection.rollback()
        return {"success": False, "message": str(exc)}
    finally:
        if connection:
            connection.close()
