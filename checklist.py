"""
체크리스트 자동 생성 모듈
공개자료 PDF를 읽어 Gemini API로 자료유형별 체크리스트를 생성합니다.
"""

import json
import logging
import os
import re
import time
from datetime import date
from pathlib import Path
from typing import Any

import pdfplumber
from google import genai

import config
import checklist_prompts

logger = logging.getLogger(__name__)

# 자료유형별 설정
DATA_TYPE_CONFIG: dict[str, dict[str, Any]] = {
    "1": {
        "checklist_nm": "업무가이드·충남감사사례 기반 사업계획서 체크리스트",
        "data_type": "1",
        "base_law": "지방자치단체 보조금 관리에 관한 법률",
        "criteria": "지방보조금법, 보조금 관리지침",
        "pdf_keywords": ["법률", "시행령", "시행규칙", "관리지침", "가이드", "보조금"],
        "output_file": "checklist_type1.json",
    },
    "2": {
        "checklist_nm": "업무가이드·충남감사사례 기반 집행내역서 체크리스트",
        "data_type": "2",
        "base_law": "지방자치단체 보조금 관리에 관한 법률 시행령",
        "criteria": "보조금 관리지침, 집행기준",
        "pdf_keywords": ["집행", "관리지침", "시행령", "시행규칙", "가이드", "매뉴얼"],
        "output_file": "checklist_type2.json",
    },
    "3": {
        "checklist_nm": "업무가이드·충남감사사례 기반 지출증빙자료 체크리스트",
        "data_type": "3",
        "base_law": "지방자치단체 보조금 관리에 관한 법률",
        "criteria": "지방보조금법, 지침",
        "pdf_keywords": ["증빙", "지출", "법률", "시행령", "시행규칙", "관리지침", "회계"],
        "output_file": "checklist_type3.json",
    },
    "4": {
        "checklist_nm": "업무가이드·충남감사사례 기반 정산보고서 체크리스트",
        "data_type": "4",
        "base_law": "지방자치단체 보조금 관리에 관한 법률",
        "criteria": "감사원 지적사례, 정산기준",
        "pdf_keywords": ["정산", "감사", "보고", "관리지침", "가이드", "시행령"],
        "output_file": "checklist_type4.json",
    },
}

# Gemini 클라이언트 캐시
_client: genai.Client | None = None


def reset_gemini_client() -> None:
    """API 키 변경 시 Gemini 클라이언트 캐시 초기화"""
    global _client
    _client = None


def _get_client() -> genai.Client:
    """Gemini API 클라이언트 반환 (싱글톤)"""
    global _client
    if _client is None:
        if not config.GEMINI_API_KEY:
            raise ValueError("GEMINI_API_KEY가 설정되지 않았습니다. .env 파일을 확인하세요.")
        _client = genai.Client(api_key=config.GEMINI_API_KEY)
        logger.info("Gemini API 클라이언트 초기화 완료")
    return _client


def list_public_pdfs() -> list[str]:
    """공개자료 경로의 PDF 파일 목록 반환"""
    public_path = Path(config.PUBLIC_DATA_PATH)
    if not public_path.is_dir():
        raise FileNotFoundError(
            f"공개자료 경로를 찾을 수 없습니다: {config.PUBLIC_DATA_PATH}"
        )

    pdf_files = sorted(
        str(p) for p in public_path.iterdir() if p.is_file() and p.suffix.lower() == ".pdf"
    )
    logger.info("공개자료 PDF %d개 발견", len(pdf_files))
    return pdf_files


def extract_pdf_text(pdf_path: str, max_length: int | None = None) -> str:
    """
    PDF 파일에서 텍스트 추출.
    max_length 지정 시 해당 길이까지만 반환.
    """
    max_len = max_length or config.PDF_TEXT_MAX_LENGTH
    text_parts: list[str] = []

    try:
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text()
                if page_text:
                    text_parts.append(page_text.strip())
    except Exception as exc:
        logger.error("PDF 텍스트 추출 실패 [%s]: %s", pdf_path, exc)
        raise RuntimeError(f"PDF 텍스트 추출에 실패했습니다: {pdf_path}") from exc

    full_text = "\n".join(text_parts)
    if len(full_text) > max_len:
        logger.debug("PDF 텍스트 %d자 → %d자로 절단", len(full_text), max_len)
        return full_text[:max_len]

    return full_text


def _select_pdfs_for_type(data_type: str, all_pdfs: list[str]) -> list[str]:
    """자료유형에 맞는 PDF 파일 필터링 (키워드 매칭)"""
    type_config = DATA_TYPE_CONFIG[data_type]
    keywords = type_config["pdf_keywords"]

    matched = [
        pdf
        for pdf in all_pdfs
        if any(kw in Path(pdf).name for kw in keywords)
    ]

    # 키워드 매칭 결과가 없으면 전체 PDF 중 상위 3개 사용
    if not matched:
        logger.warning(
            "자료유형 %s에 매칭되는 PDF가 없어 상위 3개 파일을 사용합니다.",
            data_type,
        )
        matched = all_pdfs[:3]

    logger.info("자료유형 %s — 참조 PDF %d개: %s", data_type, len(matched), matched)
    return matched


def _build_reference_text(pdf_paths: list[str]) -> str:
    """여러 PDF에서 참조 텍스트 수집 (파일당 최대 길이 분배)"""
    if not pdf_paths:
        return ""

    per_file_limit = max(config.PDF_TEXT_MAX_LENGTH // len(pdf_paths), 1000)
    sections: list[str] = []

    for pdf_path in pdf_paths:
        try:
            text = extract_pdf_text(pdf_path, max_length=per_file_limit)
            if text:
                file_name = Path(pdf_path).name
                sections.append(f"[출처: {file_name}]\n{text}")
        except Exception as exc:
            logger.warning("PDF 건너뜀 [%s]: %s", pdf_path, exc)

    combined = "\n\n".join(sections)
    if len(combined) > config.PDF_TEXT_MAX_LENGTH:
        combined = combined[: config.PDF_TEXT_MAX_LENGTH]

    return combined


def _build_prompt(data_type: str, reference_text: str) -> str:
    """Gemini API용 체크리스트 생성 프롬프트 구성 (세분화 프롬프트)"""
    type_config = DATA_TYPE_CONFIG[data_type]
    return checklist_prompts.build_checklist_prompt(
        data_type=data_type,
        checklist_nm=type_config["checklist_nm"],
        base_law=type_config["base_law"],
        reference_text=reference_text,
        min_items=config.CHECKLIST_MIN_ITEMS,
    )


def _parse_json_response(response_text: str) -> dict[str, Any]:
    """Gemini 응답에서 JSON 파싱"""
    text = response_text.strip()

    # 마크다운 코드블록 제거
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)

    return json.loads(text)


def _generate_content(prompt: str) -> str:
    """Gemini API 호출 (429 시 1회 재시도)"""
    client = _get_client()
    last_error: Exception | None = None

    for attempt in range(2):
        try:
            response = client.models.generate_content(
                model=config.GEMINI_MODEL,
                contents=prompt,
            )
            logger.info("Gemini 모델 사용: %s", config.GEMINI_MODEL)
            return response.text
        except Exception as exc:
            err_msg = str(exc)
            if "429" in err_msg and attempt == 0:
                logger.warning(
                    "Gemini API 할당량 초과, %d초 후 재시도",
                    config.GEMINI_CALL_INTERVAL,
                )
                time.sleep(config.GEMINI_CALL_INTERVAL)
                last_error = exc
                continue
            raise RuntimeError(f"Gemini API 호출에 실패했습니다: {exc}") from exc

    raise RuntimeError(f"Gemini API 호출에 실패했습니다: {last_error}") from last_error


def _call_gemini(prompt: str, retry: bool = True) -> dict[str, Any]:
    """Gemini API 호출 및 JSON 응답 파싱 (실패 시 1회 재시도)"""
    try:
        result_text = _generate_content(prompt)
        checklist = _parse_json_response(result_text)
        logger.info("Gemini 응답 JSON 파싱 성공")
        return checklist
    except (json.JSONDecodeError, ValueError, AttributeError) as exc:
        if retry:
            logger.warning("JSON 파싱 실패, 1회 재시도: %s", exc)
            retry_prompt = prompt + "\n\n중요: 반드시 유효한 JSON만 출력하세요. 다른 텍스트 금지."
            return _call_gemini(retry_prompt, retry=False)
        logger.error("JSON 파싱 최종 실패: %s", exc)
        raise RuntimeError(f"Gemini 응답 JSON 파싱에 실패했습니다: {exc}") from exc
    except Exception as exc:
        logger.error("Gemini API 호출 실패: %s", exc)
        raise RuntimeError(f"Gemini API 호출에 실패했습니다: {exc}") from exc


def _validate_checklist(checklist: dict[str, Any], data_type: str) -> dict[str, Any]:
    """생성된 체크리스트 유효성 검증 및 보정"""
    type_config = DATA_TYPE_CONFIG[data_type]

    checklist.setdefault("checklist_nm", type_config["checklist_nm"])
    checklist.setdefault("data_type", data_type)
    checklist.setdefault("base_law", type_config["base_law"])
    checklist.setdefault("created_at", date.today().isoformat())

    items = checklist.get("items", [])
    if len(items) < config.CHECKLIST_MIN_ITEMS:
        logger.warning(
            "체크리스트 항목이 %d개로 최소 %d개 미만입니다.",
            len(items),
            config.CHECKLIST_MIN_ITEMS,
        )

    # item_no 순번 보정
    for idx, item in enumerate(items, start=1):
        item["item_no"] = idx
        if item.get("risk_level") not in ("H", "M", "L"):
            item["risk_level"] = "M"

    checklist["items"] = items
    return checklist


def generate_checklist(data_type: str, pdf_paths: list[str] | None = None) -> dict[str, Any]:
    """
    지정 자료유형의 체크리스트 생성.

    Args:
        data_type: "1"~"4" 자료유형 코드
        pdf_paths: 참조 PDF 경로 목록 (None이면 자동 선택)

    Returns:
        생성된 체크리스트 dict
    """
    if data_type not in DATA_TYPE_CONFIG:
        raise ValueError(f"지원하지 않는 자료유형입니다: {data_type}")

    logger.info("체크리스트 생성 시작 — 자료유형: %s", data_type)

    if pdf_paths is None:
        all_pdfs = list_public_pdfs()
        pdf_paths = _select_pdfs_for_type(data_type, all_pdfs)

    reference_text = _build_reference_text(pdf_paths)
    if not reference_text.strip():
        raise RuntimeError("참조 PDF에서 추출된 텍스트가 없습니다.")

    prompt = _build_prompt(data_type, reference_text)
    checklist = _call_gemini(prompt)
    checklist = _validate_checklist(checklist, data_type)

    logger.info(
        "체크리스트 생성 완료 — 유형: %s, 항목 수: %d",
        data_type,
        len(checklist.get("items", [])),
    )
    return checklist


def save_checklist_json(checklist: dict[str, Any], data_type: str) -> str:
    """체크리스트를 JSON 파일로 저장"""
    config.ensure_directories()
    type_config = DATA_TYPE_CONFIG[data_type]
    output_path = os.path.join(config.CHECKLIST_DIR, type_config["output_file"])

    try:
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(checklist, f, ensure_ascii=False, indent=2)
        logger.info("체크리스트 JSON 저장 완료: %s", output_path)
        return output_path
    except OSError as exc:
        logger.error("체크리스트 JSON 저장 실패: %s", exc)
        raise RuntimeError(f"체크리스트 파일 저장에 실패했습니다: {exc}") from exc


def generate_seed_checklist(data_type: str) -> dict[str, Any]:
    """시드 항목 기반 체크리스트 생성 (Gemini API 미사용)"""
    if data_type not in DATA_TYPE_CONFIG:
        raise ValueError(f"지원하지 않는 자료유형입니다: {data_type}")
    checklist = checklist_prompts.build_seed_checklist(data_type)
    return _validate_checklist(checklist, data_type)


def clear_faiss_index() -> int:
    """FAISS 인덱스 파일 초기화"""
    import checker

    faiss_dir = Path(config.FAISS_INDEX_DIR)
    removed = 0
    if faiss_dir.is_dir():
        for f in faiss_dir.iterdir():
            if f.is_file():
                f.unlink()
                removed += 1
    if hasattr(checker, "_faiss_cache"):
        checker._faiss_cache.clear()
    logger.info("FAISS 인덱스 초기화 — %d개 파일 삭제", removed)
    return removed


def save_all_seed_checklists() -> dict[str, str]:
    """4종 시드 체크리스트 JSON 저장 및 DB 적재 (API 미사용)"""
    import checklist_db

    results: dict[str, str] = {}
    for data_type in DATA_TYPE_CONFIG:
        checklist = generate_seed_checklist(data_type)
        output_path = save_checklist_json(checklist, data_type)
        checklist_db.save_checklist(output_path, created_by="seed")
        results[data_type] = output_path
    clear_faiss_index()
    return results


def generate_all_checklists(use_gemini: bool = True) -> dict[str, str]:
    """4종 자료유형 전체 체크리스트 생성 및 저장"""
    results: dict[str, str] = {}

    for idx, data_type in enumerate(DATA_TYPE_CONFIG):
        if idx > 0:
            logger.info("API 호출 간격 대기 (%d초)...", config.GEMINI_CALL_INTERVAL)
            time.sleep(config.GEMINI_CALL_INTERVAL)

        try:
            if use_gemini:
                checklist = generate_checklist(data_type)
            else:
                checklist = generate_seed_checklist(data_type)
            output_path = save_checklist_json(checklist, data_type)
            results[data_type] = output_path
        except Exception as exc:
            if use_gemini:
                logger.warning(
                    "Gemini 생성 실패(유형 %s), 시드 체크리스트로 대체: %s",
                    data_type,
                    exc,
                )
                checklist = generate_seed_checklist(data_type)
                output_path = save_checklist_json(checklist, data_type)
                results[data_type] = output_path
            else:
                logger.error("자료유형 %s 체크리스트 생성 실패: %s", data_type, exc)
                raise

    clear_faiss_index()
    return results


def test_gemini_connection() -> str:
    """Gemini API 연결 테스트 (간단한 질의)"""
    return _generate_content("안녕하세요. '연결 성공'이라고만 답하세요.").strip()


if __name__ == "__main__":
    import argparse

    logging.basicConfig(level=logging.INFO)
    parser = argparse.ArgumentParser(description="SAFE 체크리스트 생성")
    parser.add_argument(
        "--seed",
        action="store_true",
        help="시드 체크리스트만 저장 (Gemini API 미사용)",
    )
    args = parser.parse_args()

    if args.seed:
        paths = save_all_seed_checklists()
    else:
        paths = generate_all_checklists(use_gemini=True)

    for dtype, path in paths.items():
        print(f"[{dtype}] 저장 완료: {path}")
