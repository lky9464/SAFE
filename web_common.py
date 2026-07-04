"""FastAPI 웹 공통 객체 (템플릿 등)"""

from pathlib import Path

from fastapi.templating import Jinja2Templates

import config

_BASE_DIR = Path(__file__).resolve().parent
templates = Jinja2Templates(directory=str(_BASE_DIR / "templates"))

# 자료유형 라벨
DATA_TYPE_LABELS = {
    "0": "일제점검(통합)",
    "1": "사업계획서",
    "2": "집행내역서",
    "3": "지출증빙자료",
    "4": "정산보고서",
}

RESULT_LABELS = {
    "P": "적합",
    "W": "주의",
    "F": "부적합",
    "A": "해당없음",
}


def get_upload_limits() -> dict[str, int]:
    """자료 검토 화면 업로드 한도 (서버 설정과 동기화)"""
    return {
        "max_file_mb": config.MAX_FILE_SIZE_MB,
        "max_zip_mb": config.MAX_ZIP_BUNDLE_SIZE_MB,
        "max_zip_files": config.MAX_ZIP_BUNDLE_FILES,
    }


def get_static_version(relative_path: str) -> int:
    """정적 파일 캐시 무효화용 버전 (mtime)"""
    path = _BASE_DIR / relative_path
    return int(path.stat().st_mtime) if path.is_file() else 0
