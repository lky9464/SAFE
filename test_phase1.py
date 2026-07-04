"""
PHASE 1 통합 테스트 스크립트
환경설정, DB, PDF, Gemini, 체크리스트 생성·저장·조회 순서로 검증
"""

import logging
import os
import sys
from pathlib import Path

import config
import checklist
import checklist_db

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger("test_phase1")

PASS = "[PASS]"
FAIL = "[FAIL]"


def _section(title: str) -> None:
    """테스트 구간 구분선 출력"""
    print(f"\n{'=' * 60}")
    print(f"  {title}")
    print("=" * 60)


def test_env_load() -> bool:
    """1. .env 로드 및 설정값 출력 확인"""
    _section("1. .env 로드 및 설정값 확인")

    try:
        print(f"  DB_HOST         : {config.DB_HOST}")
        print(f"  DB_PORT         : {config.DB_PORT}")
        print(f"  DB_NAME         : {config.DB_NAME}")
        print(f"  DB_USER         : {config.DB_USER}")
        print(f"  DB_PASSWORD     : {'*' * len(config.DB_PASSWORD) if config.DB_PASSWORD else '(미설정)'}")
        print(f"  GEMINI_API_KEY  : {'설정됨' if config.GEMINI_API_KEY else '(미설정)'}")
        print(f"  UPLOAD_PATH     : {config.UPLOAD_PATH}")
        print(f"  PUBLIC_DATA_PATH: {config.PUBLIC_DATA_PATH}")
        print(f"  TESSERACT_PATH  : {config.TESSERACT_PATH}")
        print(f"  CHECKLIST_DIR   : {config.CHECKLIST_DIR}")
        print(f"  GEMINI_MODEL    : {config.GEMINI_MODEL}")

        if not config.GEMINI_API_KEY:
            print(f"  {FAIL} — GEMINI_API_KEY 미설정")
            return False

        print(f"  {PASS}")
        return True
    except Exception as exc:
        print(f"  {FAIL} — {exc}")
        return False


def test_db_connection() -> bool:
    """2. MariaDB 연결 테스트"""
    _section("2. MariaDB 연결 테스트")

    connection = None
    try:
        connection = config.get_db_connection()
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1 AS result")
            row = cursor.fetchone()
            print(f"  쿼리 결과: {row}")
        print(f"  {PASS}")
        return True
    except Exception as exc:
        print(f"  {FAIL} — {exc}")
        return False
    finally:
        if connection:
            connection.close()


def test_public_pdf_list() -> list[str]:
    """3. 공개자료 폴더 내 PDF 파일 목록 출력"""
    _section("3. 공개자료 PDF 목록")

    try:
        pdf_files = checklist.list_public_pdfs()
        for idx, pdf in enumerate(pdf_files, start=1):
            print(f"  [{idx:02d}] {Path(pdf).name}")
        print(f"\n  총 {len(pdf_files)}개 PDF")
        print(f"  {PASS}")
        return pdf_files
    except Exception as exc:
        print(f"  {FAIL} — {exc}")
        return []


def test_pdf_text_extract(pdf_files: list[str]) -> bool:
    """4. PDF 1개 텍스트 추출 테스트 (pdfplumber)"""
    _section("4. PDF 텍스트 추출 테스트")

    if not pdf_files:
        print(f"  {FAIL} — PDF 파일이 없습니다.")
        return False

    target = pdf_files[0]
    try:
        text = checklist.extract_pdf_text(target, max_length=500)
        preview = text[:200].replace("\n", " ")
        print(f"  대상 파일: {Path(target).name}")
        print(f"  추출 길이: {len(text)}자")
        print(f"  미리보기 : {preview}...")
        print(f"  {PASS}")
        return True
    except Exception as exc:
        print(f"  {FAIL} — {exc}")
        return False


def test_gemini_connection() -> bool:
    """5. Gemini API 연결 테스트"""
    _section("5. Gemini API 연결 테스트")

    try:
        response = checklist.test_gemini_connection()
        print(f"  응답: {response}")
        print(f"  {PASS}")
        return True
    except Exception as exc:
        print(f"  {FAIL} — {exc}")
        return False


def test_checklist_generate_type1() -> tuple[bool, dict | None]:
    """6. 사업계획서용 체크리스트 생성 테스트 (1종만)"""
    _section("6. 사업계획서 체크리스트 생성 (유형 1)")

    try:
        result = checklist.generate_checklist("1")
        item_count = len(result.get("items", []))
        print(f"  체크리스트명: {result.get('checklist_nm')}")
        print(f"  항목 수     : {item_count}개")
        if item_count > 0:
            first = result["items"][0]
            print(f"  첫 항목     : [{first.get('category')}] {first.get('item_content')}")
        print(f"  {PASS}")
        return True, result
    except Exception as exc:
        print(f"  {FAIL} — {exc}")
        return False, None


def test_json_save(checklist_data: dict | None = None) -> str | None:
    """7. JSON 파일 저장 확인"""
    _section("7. JSON 파일 저장 확인")

    try:
        if checklist_data is None:
            checklist_data = checklist.generate_checklist("1")

        output_path = checklist.save_checklist_json(checklist_data, "1")
        file_size = os.path.getsize(output_path)
        print(f"  저장 경로: {output_path}")
        print(f"  파일 크기: {file_size:,} bytes")
        print(f"  {PASS}")
        return output_path
    except Exception as exc:
        print(f"  {FAIL} — {exc}")
        return None


def test_db_save_and_query(json_path: str | None) -> bool:
    """8. DB 저장 및 조회 확인"""
    _section("8. DB 저장 및 조회 확인")

    if not json_path or not os.path.isfile(json_path):
        print(f"  {FAIL} — JSON 파일이 없습니다.")
        return False

    try:
        checklist_id = checklist_db.save_checklist(json_path, created_by="test_phase1")
        print(f"  저장된 checklist_id: {checklist_id}")

        # 목록 조회
        type1_list = checklist_db.get_checklist_list(data_type="1")
        print(f"  유형1 목록 건수: {len(type1_list)}건")

        # 상세 조회
        detail = checklist_db.get_checklist_detail(checklist_id)
        if detail:
            print(f"  상세 조회 — 항목 {len(detail.get('items', []))}개")

        # 검토용 로드
        review = checklist_db.load_checklist_for_review(checklist_id)
        print(f"  검토용 로드 — {review['checklist_nm']} ({review['item_cnt']}항목)")

        print(f"  {PASS}")
        return True
    except Exception as exc:
        print(f"  {FAIL} — {exc}")
        return False


def main() -> int:
    """전체 테스트 실행"""
    print("\n" + "#" * 60)
    print("  SAFE PHASE 1 통합 테스트")
    print("#" * 60)

    results: list[bool] = []
    json_path: str | None = None
    checklist_data: dict | None = None

    # 1. 환경설정
    results.append(test_env_load())

    # 2. DB 연결
    results.append(test_db_connection())

    # 3. PDF 목록
    pdf_files = test_public_pdf_list()
    results.append(len(pdf_files) > 0)

    # 4. PDF 텍스트 추출
    results.append(test_pdf_text_extract(pdf_files))

    # 5. Gemini 연결
    results.append(test_gemini_connection())

    # 6. 체크리스트 생성 (유형1)
    gen_ok, checklist_data = test_checklist_generate_type1()
    results.append(gen_ok)

    # 7. JSON 저장 (6단계에서 생성한 데이터 재사용)
    if gen_ok:
        json_path = test_json_save(checklist_data)
        results.append(json_path is not None)
    else:
        _section("7. JSON 파일 저장 확인")
        print(f"  {FAIL} — 이전 단계 실패로 건너뜀")
        results.append(False)

    # 8. DB 저장 및 조회
    results.append(test_db_save_and_query(json_path))

    # 최종 결과
    _section("최종 결과")
    passed = sum(results)
    total = len(results)
    print(f"  통과: {passed}/{total}")

    if passed == total:
        print(f"\n  모든 테스트 통과!")
        return 0

    print(f"\n  일부 테스트 실패")
    return 1


if __name__ == "__main__":
    sys.exit(main())
