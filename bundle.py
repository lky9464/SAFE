"""
ZIP 묶음 자료 처리 (지출증빙자료 등)
압축 해제 후 내부 파일을 순차 OCR·텍스트 병합
"""

import io
import logging
import tempfile
import zipfile
from pathlib import Path
from typing import Any

import config

logger = logging.getLogger(__name__)

# ZIP 내부 허용 확장자 (자료유형별)
ZIP_INNER_EXTENSIONS: dict[str, list[str]] = {
    "3": [".pdf", ".jpg", ".jpeg", ".png", ".tiff"],
}


def max_zip_files() -> int:
    return config.MAX_ZIP_BUNDLE_FILES


def max_zip_uncompressed_bytes() -> int:
    return config.MAX_ZIP_UNCOMPRESSED_MB * 1024 * 1024


def is_zip_archive(file_path: str) -> bool:
    return Path(file_path).suffix.lower() == ".zip"


def _eligible_zip_members(zf: zipfile.ZipFile, allowed_extensions: list[str]) -> list[zipfile.ZipInfo]:
    """ZIP 내 처리 대상 파일만 (허용 확장자, 디렉터리 제외)"""
    eligible: list[zipfile.ZipInfo] = []
    for info in zf.infolist():
        if info.is_dir():
            continue
        name = info.filename.replace("\\", "/")
        if name.endswith("/"):
            continue
        if Path(name).suffix.lower() in allowed_extensions:
            eligible.append(info)
    return eligible


def validate_zip_bundle_content(content: bytes, data_type: str) -> dict[str, Any]:
    """
    업로드 시 ZIP 내부 파일 수·형식 사전 검증.
    Returns: {eligible_count, skipped_count}
    """
    allowed = ZIP_INNER_EXTENSIONS.get(data_type)
    if not allowed:
        raise ValueError(f"자료유형 {data_type}에서는 ZIP 묶음 업로드를 지원하지 않습니다.")

    try:
        with zipfile.ZipFile(io.BytesIO(content), "r") as zf:
            all_files = [m for m in zf.infolist() if not m.is_dir()]
            eligible = _eligible_zip_members(zf, allowed)
    except zipfile.BadZipFile as exc:
        raise ValueError(f"손상되었거나 ZIP 형식이 아닙니다: {exc}") from exc

    if not eligible:
        raise ValueError(
            "ZIP 안에 처리 가능한 파일이 없습니다. "
            f"(허용: {', '.join(allowed)})"
        )

    limit = max_zip_files()
    allowed_label = ", ".join(allowed)
    if len(eligible) > limit:
        raise ValueError(
            f"ZIP 내부 처리 대상 파일이 너무 많습니다 "
            f"({len(eligible)}개, 최대 {limit}개 — {allowed_label}만 집계)"
        )

    return {
        "eligible_count": len(eligible),
        "skipped_count": len(all_files) - len(eligible),
    }


def _safe_member_path(dest_dir: Path, name: str) -> Path | None:
    """Zip Slip 방지 — dest_dir 밖으로 나가는 경로 거부"""
    target = (dest_dir / name).resolve()
    try:
        target.relative_to(dest_dir.resolve())
    except ValueError:
        logger.warning("ZIP 경로 탈출 시도 차단: %s", name)
        return None
    return target


def extract_zip_members(
    zip_path: Path,
    dest_dir: Path,
    allowed_extensions: list[str],
) -> list[Path]:
    """
    ZIP을 dest_dir에 안전하게 풀고, 허용 확장자 파일 경로 목록 반환.
    """
    extracted: list[Path] = []
    total_uncompressed = 0
    limit = max_zip_files()
    max_bytes = max_zip_uncompressed_bytes()

    with zipfile.ZipFile(zip_path, "r") as zf:
        members = _eligible_zip_members(zf, allowed_extensions)
        if len(members) > limit:
            raise ValueError(
                f"ZIP 내부 처리 대상 파일이 너무 많습니다 "
                f"({len(members)}개, 최대 {limit}개 — {', '.join(allowed_extensions)}만 집계)"
            )

        for info in members:
            total_uncompressed += info.file_size
            if total_uncompressed > max_bytes:
                raise ValueError(
                    f"ZIP 압축 해제 용량이 제한을 초과합니다 "
                    f"(최대 {config.MAX_ZIP_UNCOMPRESSED_MB}MB)"
                )

            name = info.filename.replace("\\", "/")
            suffix = Path(name).suffix.lower()
            if suffix not in allowed_extensions:
                continue

            target = _safe_member_path(dest_dir, name)
            if target is None:
                continue

            target.parent.mkdir(parents=True, exist_ok=True)
            with zf.open(info) as src, open(target, "wb") as dst:
                dst.write(src.read())
            extracted.append(target)

    return sorted(extracted, key=lambda p: str(p).lower())


def extract_zip_bundle_text(archive_path: str, data_type: str) -> dict[str, Any]:
    """
    ZIP 묶음에서 지원 형식 파일만 추출·OCR 후 텍스트 병합.

    Returns:
        ocr.extract_text와 동일한 형식 (+ bundle_file_count, bundle_files)
    """
    from ocr import _empty_result, _extract_single_file, _success_result

    path = Path(archive_path)
    if not path.is_file():
        return _empty_result(f"ZIP 파일을 찾을 수 없습니다: {archive_path}")

    allowed = ZIP_INNER_EXTENSIONS.get(data_type)
    if not allowed:
        return _empty_result(
            f"자료유형 {data_type}에서는 ZIP 묶음 업로드를 지원하지 않습니다."
        )

    try:
        with tempfile.TemporaryDirectory(prefix="safe_zip_") as tmp:
            inner_files = extract_zip_members(path, Path(tmp), allowed)
            if not inner_files:
                return _empty_result(
                    "ZIP 안에 처리 가능한 파일이 없습니다. "
                    f"(허용: {', '.join(allowed)})"
                )

            text_parts: list[str] = []
            processed_names: list[str] = []
            ocr_used = False
            page_count = 0
            failed: list[str] = []

            for inner in inner_files:
                result = _extract_single_file(str(inner))
                if result.get("success") and (result.get("text") or "").strip():
                    text_parts.append(f"===== {inner.name} =====\n{result['text'].strip()}")
                    processed_names.append(inner.name)
                    ocr_used = ocr_used or bool(result.get("ocr_used"))
                    page_count += int(result.get("page_count") or 0)
                else:
                    failed.append(inner.name)
                    logger.warning(
                        "ZIP 내부 파일 텍스트 추출 실패: %s — %s",
                        inner.name,
                        result.get("error"),
                    )

            full_text = "\n\n".join(text_parts).strip()
            if not full_text:
                return _empty_result(
                    "ZIP 내 파일에서 텍스트를 추출하지 못했습니다. "
                    + (f"(실패 {len(failed)}건)" if failed else "")
                )

            out = _success_result(
                full_text,
                "zip_bundle",
                page_count=page_count,
                ocr_used=ocr_used,
            )
            out["bundle_file_count"] = len(processed_names)
            out["bundle_files"] = processed_names
            out["bundle_failed"] = failed
            logger.info(
                "ZIP 묶음 OCR 완료 — %s, 처리 %d/%d 파일",
                path.name,
                len(processed_names),
                len(inner_files),
            )
            return out

    except zipfile.BadZipFile as exc:
        return _empty_result(f"손상되었거나 ZIP 형식이 아닙니다: {exc}")
    except ValueError as exc:
        return _empty_result(str(exc))
    except Exception as exc:
        logger.error("ZIP 묶음 처리 실패 [%s]: %s", archive_path, exc)
        return _empty_result(f"ZIP 처리에 실패했습니다: {exc}")
