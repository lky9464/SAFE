"""
파일 업로드 모듈
파일 유효성 검사, 로컬 임시 저장, 자동 정리
"""

import inspect
import logging
import os
import shutil
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, BinaryIO

import config

logger = logging.getLogger(__name__)

# 자료유형별 허용 확장자
ALLOWED_EXTENSIONS: dict[str, list[str]] = {
    "1": [".pdf", ".hwp"],                              # 사업계획서
    "2": [".pdf", ".hwp", ".xlsx", ".xls"],             # 집행내역서
    "3": [".pdf", ".jpg", ".jpeg", ".png", ".tiff", ".zip"],    # 지출증빙 (ZIP 묶음)
    "4": [".pdf", ".hwp", ".xlsx", ".xls"],             # 정산보고서
}

MAX_FILE_SIZE_MB: int = config.MAX_FILE_SIZE_MB
MAX_FILE_SIZE_BYTES: int = MAX_FILE_SIZE_MB * 1024 * 1024

MAX_ZIP_BUNDLE_SIZE_MB: int = config.MAX_ZIP_BUNDLE_SIZE_MB
MAX_ZIP_BUNDLE_SIZE_BYTES: int = MAX_ZIP_BUNDLE_SIZE_MB * 1024 * 1024


def get_max_file_size_bytes(data_type: str, extension: str) -> tuple[int, int]:
    """자료유형·확장자별 최대 업로드 크기 (bytes, MB 표시용)"""
    if data_type == "3" and extension == ".zip":
        return MAX_ZIP_BUNDLE_SIZE_BYTES, MAX_ZIP_BUNDLE_SIZE_MB
    return MAX_FILE_SIZE_BYTES, MAX_FILE_SIZE_MB


def _get_upload_root() -> Path:
    """업로드 루트 경로 반환"""
    return Path(config.UPLOAD_PATH)


def _normalize_file(file: Any) -> tuple[str, bytes]:
    """
    다양한 입력 형식을 (파일명, 바이트)로 변환.
    지원: Path, str 경로, (filename, bytes) 튜플, file-like 객체
    """
    if isinstance(file, tuple) and len(file) == 2:
        filename, content = file
        if isinstance(content, str):
            content = content.encode("utf-8")
        return str(filename), bytes(content)

    if isinstance(file, (str, Path)):
        path = Path(file)
        if not path.is_file():
            raise FileNotFoundError(f"파일을 찾을 수 없습니다: {path}")
        return path.name, path.read_bytes()

    if hasattr(file, "read"):
        filename = getattr(file, "filename", None) or getattr(file, "name", None)
        if not filename:
            raise ValueError("파일명을 확인할 수 없습니다.")
        content = file.read()
        if inspect.iscoroutine(content):
            raise TypeError(
                "비동기 업로드 파일은 await file.read() 후 (filename, bytes) 형태로 전달하세요."
            )
        if isinstance(content, str):
            content = content.encode("utf-8")
        if hasattr(file, "seek"):
            try:
                file.seek(0)
            except Exception:
                pass
        return Path(filename).name, bytes(content)

    raise TypeError("지원하지 않는 파일 입력 형식입니다.")


def _get_extension(filename: str) -> str:
    """소문자 확장자 반환"""
    return Path(filename).suffix.lower()


def validate_file(file: Any, data_type: str) -> dict[str, Any]:
    """
    파일 형식·크기 유효성 검사.

    Args:
        file: 업로드 파일 (경로, 튜플, file-like 객체)
        data_type: 자료유형 "1"~"4"

    Returns:
        검증 결과 dict (filename, size, extension)

    Raises:
        ValueError: 유효성 검사 실패
    """
    if data_type not in ALLOWED_EXTENSIONS:
        raise ValueError(f"지원하지 않는 자료유형입니다: {data_type}")

    try:
        filename, content = _normalize_file(file)
    except Exception as exc:
        logger.error("파일 읽기 실패: %s", exc)
        raise ValueError(f"파일을 읽을 수 없습니다: {exc}") from exc

    extension = _get_extension(filename)
    allowed = ALLOWED_EXTENSIONS[data_type]

    if extension not in allowed:
        raise ValueError(
            f"허용되지 않는 파일 형식입니다: {extension} "
            f"(자료유형 {data_type} 허용: {', '.join(allowed)})"
        )

    file_size = len(content)
    if file_size == 0:
        raise ValueError("빈 파일은 업로드할 수 없습니다.")

    max_bytes, max_mb = get_max_file_size_bytes(data_type, extension)
    if file_size > max_bytes:
        raise ValueError(
            f"파일 크기가 제한을 초과했습니다: "
            f"{file_size / 1024 / 1024:.1f}MB (최대 {max_mb}MB)"
        )

    zip_meta: dict[str, Any] | None = None
    if extension == ".zip" and data_type == "3":
        from bundle import validate_zip_bundle_content

        zip_meta = validate_zip_bundle_content(content, data_type)

    # MIME 타입 추가 검증 (python-magic-bin 설치 시)
    try:
        import magic

        mime = magic.from_buffer(content[:2048], mime=True)
        logger.debug("MIME 타입: %s (%s)", mime, filename)
    except ImportError:
        logger.debug("python-magic 미설치 — 확장자 검증만 수행")
    except Exception as exc:
        logger.warning("MIME 타입 검증 실패 (건너뜀): %s", exc)

    logger.info("파일 유효성 검사 통과: %s (%d bytes)", filename, file_size)
    result = {
        "filename": filename,
        "size": file_size,
        "extension": extension,
    }
    if zip_meta:
        result.update(zip_meta)
    return result


def save_upload(file: Any, data_type: str) -> str:
    """
    파일을 uploads/{YYYYMMDD}/{timestamp}_{원본파일명} 에 저장.

    Args:
        file: 업로드 파일
        data_type: 자료유형 "1"~"4"

    Returns:
        저장된 파일의 전체 경로
    """
    validation = validate_file(file, data_type)
    filename = validation["filename"]
    _, content = _normalize_file(file)

    today = datetime.now().strftime("%Y%m%d")
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    save_dir = _get_upload_root() / today
    save_dir.mkdir(parents=True, exist_ok=True)

    safe_name = Path(filename).name
    stored_name = f"{timestamp}_{safe_name}"
    save_path = save_dir / stored_name

    try:
        save_path.write_bytes(content)
        logger.info("파일 저장 완료: %s", save_path)
        return str(save_path)
    except OSError as exc:
        logger.error("파일 저장 실패: %s", exc)
        raise RuntimeError(f"파일 저장에 실패했습니다: {exc}") from exc


def get_upload_path(filename: str) -> str | None:
    """
    저장된 파일명(또는 일부)으로 업로드 경로 검색.

    Args:
        filename: 저장 파일명 또는 원본 파일명 일부

    Returns:
        찾은 파일의 전체 경로, 없으면 None
    """
    root = _get_upload_root()
    if not root.exists():
        return None

    # 정확한 파일명 매칭
    for path in root.rglob(filename):
        if path.is_file():
            return str(path)

    # 부분 매칭 (timestamp_원본파일명 형식)
    for path in root.rglob(f"*{filename}"):
        if path.is_file():
            return str(path)

    logger.warning("업로드 파일을 찾을 수 없습니다: %s", filename)
    return None


def delete_upload(filename: str) -> bool:
    """
    업로드된 임시 파일 삭제.

    Args:
        filename: 저장 파일명 또는 검색 키워드

    Returns:
        삭제 성공 여부
    """
    path_str = get_upload_path(filename)
    if not path_str:
        logger.warning("삭제 대상 파일을 찾을 수 없습니다: %s", filename)
        return False

    try:
        Path(path_str).unlink()
        logger.info("업로드 파일 삭제 완료: %s", path_str)
        return True
    except OSError as exc:
        logger.error("파일 삭제 실패: %s", exc)
        raise RuntimeError(f"파일 삭제에 실패했습니다: {exc}") from exc


def auto_clean_uploads(days: int = 7) -> int:
    """
    N일이 지난 업로드 파일 자동 삭제.

    Args:
        days: 보관 일수 (기본 7일)

    Returns:
        삭제된 파일 수
    """
    root = _get_upload_root()
    if not root.exists():
        return 0

    cutoff = time.time() - (days * 86400)
    deleted_count = 0

    try:
        for path in root.rglob("*"):
            if not path.is_file():
                continue
            if path.stat().st_mtime < cutoff:
                path.unlink()
                deleted_count += 1
                logger.debug("오래된 파일 삭제: %s", path)

        # 빈 날짜 폴더 정리
        for dir_path in sorted(root.rglob("*"), reverse=True):
            if dir_path.is_dir() and not any(dir_path.iterdir()):
                dir_path.rmdir()
                logger.debug("빈 폴더 삭제: %s", dir_path)

        logger.info("업로드 자동 정리 완료 — %d개 파일 삭제 (%d일 초과)", deleted_count, days)
        return deleted_count

    except OSError as exc:
        logger.error("업로드 자동 정리 실패: %s", exc)
        raise RuntimeError(f"업로드 자동 정리에 실패했습니다: {exc}") from exc
