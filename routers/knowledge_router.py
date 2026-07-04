"""지식DB(공개자료) 파일 관리 라우터

open_docs 폴더 내 공개 파일(감사사례집, 법령 등)을 업로드·조회·삭제합니다.
업로드된 파일은 체크리스트 생성 시 자동으로 참조됩니다.
"""

import logging
import os
import shutil
from pathlib import Path

from fastapi import APIRouter, File, Request, UploadFile
from fastapi.responses import FileResponse

import config
import checklist_db
from web_common import DATA_TYPE_LABELS, templates

logger = logging.getLogger(__name__)
router = APIRouter()

# 허용 확장자
ALLOWED_EXTENSIONS = {".pdf", ".hwp", ".hwpx", ".docx", ".txt"}
MAX_FILE_SIZE_MB = 50

# 체크리스트 상태 코드 (지식DB 목록 표시용)
CHECKLIST_STATUS_LABELS = {
    "not_applicable": "대상 아님",
    "pending": "생성",
    "ready": "재생성",
    "empty": "체크리스트 없음",
}


def resolve_checklist_status(ext: str, info: dict) -> str:
    """파일 확장자·DB 현황으로 체크리스트 상태 코드 반환"""
    if ext != ".pdf":
        return "not_applicable"
    if not info.get("has_checklist"):
        return "pending"
    if (info.get("item_cnt") or 0) == 0:
        return "empty"
    return "ready"


def _get_knowledge_dir() -> Path:
    """지식DB 디렉터리 반환 (없으면 생성)"""
    p = Path(config.PUBLIC_DATA_PATH)
    p.mkdir(parents=True, exist_ok=True)
    return p


def list_knowledge_files() -> list[dict]:
    """지식DB 파일 목록 반환"""
    knowledge_dir = _get_knowledge_dir()
    files = []
    for f in sorted(knowledge_dir.iterdir()):
        if f.is_file() and f.suffix.lower() in ALLOWED_EXTENSIONS:
            stat = f.stat()
            files.append({
                "filename": f.name,
                "ext": f.suffix.lower(),
                "size_kb": round(stat.st_size / 1024, 1),
                "modified": stat.st_mtime,
            })
    return files


# ─────────────────────────────────────────────
# 페이지
# ─────────────────────────────────────────────

@router.get("")
async def knowledge_page(request: Request):
    """지식DB 관리 화면"""
    files = list_knowledge_files()
    return templates.TemplateResponse(
        request,
        "knowledge.html",
        {
            "active_page": "knowledge",
            "files": files,
            "knowledge_dir": config.PUBLIC_DATA_PATH,
            "allowed_ext": ", ".join(sorted(ALLOWED_EXTENSIONS)),
            "data_types": DATA_TYPE_LABELS,
        },
    )


# ─────────────────────────────────────────────
# API
# ─────────────────────────────────────────────

@router.get("/api/files")
async def api_list_files():
    """지식DB 파일 목록 + 체크리스트 생성 현황 JSON"""
    try:
        files = list_knowledge_files()
        filenames = [f["filename"] for f in files]
        status_map = checklist_db.get_source_file_status(filenames)

        for f in files:
            info = status_map.get(f["filename"], {"has_checklist": False})
            f["has_checklist"] = info.get("has_checklist", False)
            f["checklist_id"] = info.get("checklist_id")
            f["checklist_nm"] = info.get("checklist_nm")
            f["checklist_yn_label"] = info.get("use_yn")
            f["item_cnt"] = info.get("item_cnt", 0)
            status = resolve_checklist_status(f["ext"], info)
            f["checklist_status"] = status
            f["status_label"] = CHECKLIST_STATUS_LABELS[status]

        return {"success": True, "files": files, "count": len(files)}
    except Exception as exc:
        logger.error("지식DB 목록 조회 실패: %s", exc)
        return {"success": False, "message": str(exc)}


@router.post("/api/upload")
async def api_upload_knowledge(file: UploadFile = File(...)):
    """지식DB 파일 업로드 (공개자료 추가)"""
    try:
        if not file.filename:
            return {"success": False, "message": "파일명을 확인할 수 없습니다."}

        suffix = Path(file.filename).suffix.lower()
        if suffix not in ALLOWED_EXTENSIONS:
            return {
                "success": False,
                "message": f"허용되지 않는 파일 형식입니다. ({', '.join(sorted(ALLOWED_EXTENSIONS))}만 가능)",
            }

        content = await file.read()
        size_mb = len(content) / (1024 * 1024)
        if size_mb > MAX_FILE_SIZE_MB:
            return {
                "success": False,
                "message": f"파일 크기가 {MAX_FILE_SIZE_MB}MB를 초과합니다. ({size_mb:.1f}MB)",
            }

        knowledge_dir = _get_knowledge_dir()
        save_path = knowledge_dir / file.filename

        # 동일 파일명 존재 시 덮어쓰기 (버전 관리 없음)
        with open(save_path, "wb") as fp:
            fp.write(content)

        logger.info("지식DB 파일 업로드 완료: %s (%.1f KB)", file.filename, len(content) / 1024)
        return {
            "success": True,
            "filename": file.filename,
            "size_kb": round(len(content) / 1024, 1),
            "message": f"'{file.filename}' 파일이 지식DB에 저장되었습니다.",
        }

    except Exception as exc:
        logger.error("지식DB 파일 업로드 실패: %s", exc)
        return {"success": False, "message": str(exc)}


@router.delete("/api/files/{filename}")
async def api_delete_file(filename: str):
    """지식DB 파일 삭제"""
    try:
        # 경로 탐색 방지: 파일명만 추출
        safe_name = Path(filename).name
        file_path = _get_knowledge_dir() / safe_name

        if not file_path.exists():
            return {"success": False, "message": "파일을 찾을 수 없습니다."}

        if file_path.suffix.lower() not in ALLOWED_EXTENSIONS:
            return {"success": False, "message": "삭제 권한이 없는 파일입니다."}

        file_path.unlink()
        logger.info("지식DB 파일 삭제 완료: %s", safe_name)
        return {"success": True, "message": f"'{safe_name}' 파일이 삭제되었습니다."}

    except Exception as exc:
        logger.error("지식DB 파일 삭제 실패: %s", exc)
        return {"success": False, "message": str(exc)}


@router.get("/api/files/{filename}/download")
async def api_download_file(filename: str):
    """지식DB 파일 다운로드"""
    safe_name = Path(filename).name
    file_path = _get_knowledge_dir() / safe_name

    if not file_path.exists():
        return {"error": "파일을 찾을 수 없습니다."}

    return FileResponse(
        str(file_path),
        filename=safe_name,
        media_type="application/octet-stream",
    )
