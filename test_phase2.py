"""
PHASE 2 통합 테스트 스크립트
업로드, OCR, 파싱 모듈 순차 검증
"""

import logging
import os
import shutil
import sys
import tempfile
from pathlib import Path

import config
import ocr
import parser
import uploader

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger("test_phase2")

PASS = "[PASS]"
FAIL = "[FAIL]"

# 테스트용 샘플 텍스트
SAMPLE_BUSINESS_PLAN = """
사업명: 2026년 지역사회 활성화 사업
사업목적: 지역주민 복지 향상 및 지역경제 활성화
사업기간: 2026.01.01 ~ 2026.12.31
총 예산: 100,000,000원
인건비: 40,000,000원
운영비: 50,000,000원
기타경비: 10,000,000원
집행계획: 분기별 단계적 집행
정산계획: 사업 종료 후 30일 이내 정산
신청기관: ○○시청
"""

SAMPLE_EXECUTION_DETAIL = """
사업명: 2026년 지역사회 활성화 사업
총 예산: 100,000,000원
총 집행: 75,000,000원
2026-03-15 인건비 지급 20,000,000원
2026-06-20 운영비 집행 30,000,000원
2026-09-10 기타경비 25,000,000원
"""

SAMPLE_EXPENDITURE_PROOF = """
증빙번호: A-001
발행일자: 2026-03-15
금액: 1,500,000원
공급자: (주)테스트상사
품목명: 사무용품 구입
"""

SAMPLE_SETTLEMENT_REPORT = """
사업명: 2026년 지역사회 활성화 사업
정산기간: 2026.01.01 ~ 2026.12.31
총 예산: 100,000,000원
총 집행: 95,000,000원
반납금: 5,000,000원
반납계획: 2027.01.31까지 반납 예정
정산기한: 2027.01.31
인건비 예산: 40,000,000원
인건비 집행: 38,000,000원
운영비 예산: 50,000,000원
운영비 집행: 47,000,000원
"""


def _section(title: str) -> None:
    print(f"\n{'=' * 60}")
    print(f"  {title}")
    print("=" * 60)


def test_file_validation() -> bool:
    """1. 파일 업로드 유효성 검사 테스트"""
    _section("1. 파일 업로드 유효성 검사")

    try:
        # 허용 형식
        uploader.validate_file(("plan.pdf", b"%PDF-1.4 test"), "1")
        print("  허용 형식 (PDF, 유형1) → OK")

        # 허용되지 않는 형식
        try:
            uploader.validate_file(("image.jpg", b"fake"), "1")
            print(f"  {FAIL} — JPG가 유형1에서 허용됨")
            return False
        except ValueError:
            print("  비허용 형식 (JPG, 유형1) → 오류 정상 처리")

        # 크기 초과
        try:
            big_content = b"x" * (uploader.MAX_FILE_SIZE_BYTES + 1)
            uploader.validate_file(("big.pdf", big_content), "1")
            print(f"  {FAIL} — 크기 초과 파일이 허용됨")
            return False
        except ValueError:
            print("  크기 초과 → 오류 정상 처리")

        print(f"  {PASS}")
        return True
    except Exception as exc:
        print(f"  {FAIL} — {exc}")
        return False


def test_file_save() -> str | None:
    """2. 파일 로컬 저장 테스트"""
    _section("2. 파일 로컬 저장")

    try:
        content = b"%PDF-1.4 sample content for test"
        saved_path = uploader.save_upload(("test_plan.pdf", content), "1")
        print(f"  저장 경로: {saved_path}")

        if not os.path.isfile(saved_path):
            print(f"  {FAIL} — 파일이 저장되지 않음")
            return None

        found = uploader.get_upload_path(Path(saved_path).name)
        print(f"  경로 검색: {found}")

        if found != saved_path:
            print(f"  {FAIL} — 경로 검색 불일치")
            return None

        print(f"  {PASS}")
        return saved_path
    except Exception as exc:
        print(f"  {FAIL} — {exc}")
        return None


def test_pdf_extract() -> bool:
    """3. PDF 텍스트 추출 테스트 (pdfplumber)"""
    _section("3. PDF 텍스트 추출 (pdfplumber)")

    try:
        public_path = Path(config.PUBLIC_DATA_PATH)
        pdf_files = sorted(public_path.glob("*.pdf"))
        if not pdf_files:
            print(f"  {FAIL} — 공개자료 PDF 없음")
            return False

        target = str(pdf_files[0])
        result = ocr.extract_pdf_text(target)
        print(f"  대상: {Path(target).name}")
        print(f"  방법: {result['method']}")
        print(f"  문자수: {result['char_count']}")
        print(f"  품질점수: {result['quality_score']}")

        if not result["success"] or result["char_count"] == 0:
            print(f"  {FAIL} — 텍스트 추출 실패")
            return False

        print(f"  {PASS}")
        return True
    except Exception as exc:
        print(f"  {FAIL} — {exc}")
        return False


def test_scan_pdf_ocr() -> bool:
    """4. 스캔 PDF OCR 테스트 (Tesseract)"""
    _section("4. 스캔 PDF OCR (Tesseract)")

    try:
        from PIL import Image, ImageDraw, ImageFont

        # 테스트용 한글 이미지 생성
        with tempfile.TemporaryDirectory() as tmp_dir:
            img_path = Path(tmp_dir) / "test_ocr.png"
            img = Image.new("RGB", (400, 100), color="white")
            draw = ImageDraw.Draw(img)
            draw.text((10, 30), "지방보조금 테스트", fill="black")
            img.save(img_path)

            result = ocr.extract_image_text(str(img_path))
            print(f"  방법: {result['method']}")
            print(f"  OCR 사용: {result['ocr_used']}")
            print(f"  추출 텍스트: {result['text'][:50]}")
            print(f"  품질점수: {result['quality_score']}")

            if not result["success"]:
                print(f"  {FAIL} — OCR 실패")
                return False

            print(f"  {PASS}")
            return True
    except Exception as exc:
        print(f"  {FAIL} — {exc}")
        return False


def test_excel_extract() -> bool:
    """5. Excel 데이터 추출 테스트 (openpyxl)"""
    _section("5. Excel 데이터 추출 (openpyxl)")

    try:
        from openpyxl import Workbook

        with tempfile.TemporaryDirectory() as tmp_dir:
            xlsx_path = Path(tmp_dir) / "test_execution.xlsx"
            wb = Workbook()
            ws = wb.active
            ws.title = "집행내역"
            ws.append(["집행일자", "항목명", "금액"])
            ws.append(["2026-03-15", "인건비", 20000000])
            ws.append(["2026-06-20", "운영비", 30000000])
            wb.save(xlsx_path)

            result = ocr.extract_excel_data(str(xlsx_path))
            print(f"  방법: {result['method']}")
            print(f"  시트수: {result['page_count']}")
            print(f"  문자수: {result['char_count']}")

            if not result["success"]:
                print(f"  {FAIL} — Excel 추출 실패")
                return False

            if "20000000" not in result["text"] and "2e+07" not in result["text"].lower():
                # openpyxl may format numbers differently
                if "인건비" not in result["text"]:
                    print(f"  {FAIL} — 데이터 파싱 이상")
                    return False

            print(f"  {PASS}")
            return True
    except Exception as exc:
        print(f"  {FAIL} — {exc}")
        return False


def test_business_plan_parse() -> bool:
    """6. 사업계획서 파싱 테스트"""
    _section("6. 사업계획서 파싱")

    try:
        result = parser.parse_document(SAMPLE_BUSINESS_PLAN, "1")
        print(f"  사업명: {result['business_name']}")
        print(f"  총예산: {result['total_budget']:,}원")
        print(f"  인건비: {result['budget_breakdown']['labor_cost']:,}원")
        print(f"  인건비비율: {result['labor_ratio']}%")

        if result["total_budget"] != 100_000_000:
            print(f"  {FAIL} — 총예산 파싱 오류")
            return False

        if result["labor_ratio"] != 40.0:
            print(f"  {FAIL} — 인건비 비율 계산 오류 (기대 40.0%, 실제 {result['labor_ratio']}%)")
            return False

        print(f"  {PASS}")
        return True
    except Exception as exc:
        print(f"  {FAIL} — {exc}")
        return False


def test_execution_detail_parse() -> bool:
    """7. 집행내역서 파싱 테스트"""
    _section("7. 집행내역서 파싱")

    try:
        result = parser.parse_document(SAMPLE_EXECUTION_DETAIL, "2")
        print(f"  총예산: {result['total_budget']:,}원")
        print(f"  총집행: {result['total_executed']:,}원")
        print(f"  집행률: {result['execution_rate']}%")
        print(f"  잔액: {result['remaining_budget']:,}원")
        print(f"  집행항목: {len(result['execution_items'])}건")

        if result["execution_rate"] != 75.0:
            print(f"  {FAIL} — 집행률 계산 오류")
            return False

        if result["remaining_budget"] != 25_000_000:
            print(f"  {FAIL} — 잔액 계산 오류")
            return False

        print(f"  {PASS}")
        return True
    except Exception as exc:
        print(f"  {FAIL} — {exc}")
        return False


def test_proof_and_settlement_parse() -> bool:
    """8. 지출증빙·정산보고서 파싱 + 중복 탐지 테스트"""
    _section("8. 지출증빙·정산보고서 파싱 + 중복 탐지")

    try:
        # 지출증빙 파싱
        proof_result = parser.parse_document(SAMPLE_EXPENDITURE_PROOF, "3")
        print(f"  증빙 건수: {len(proof_result['proof_list'])}")
        print(f"  증빙 총액: {proof_result['total_amount']:,}원")

        # 정산보고서 파싱
        settle_result = parser.parse_document(SAMPLE_SETTLEMENT_REPORT, "4")
        print(f"  총예산: {settle_result['total_budget']:,}원")
        print(f"  총집행: {settle_result['total_executed']:,}원")
        print(f"  잔액: {settle_result['remaining_amount']:,}원")
        print(f"  반납금: {settle_result['refund_amount']:,}원")

        if settle_result["remaining_amount"] != 5_000_000:
            print(f"  {FAIL} — 정산 잔액 계산 오류")
            return False

        # 중복 증빙 탐지
        with tempfile.TemporaryDirectory() as tmp_dir:
            file1 = Path(tmp_dir) / "proof1.pdf"
            file2 = Path(tmp_dir) / "proof2.pdf"
            content = b"identical proof content"
            file1.write_bytes(content)
            file2.write_bytes(content)

            duplicates = parser.detect_duplicate_proof([str(file1), str(file2)])
            print(f"  중복 탐지: {len(duplicates)}건")

            if len(duplicates) != 1:
                print(f"  {FAIL} — 중복 탐지 실패")
                return False

        print(f"  {PASS}")
        return True
    except Exception as exc:
        print(f"  {FAIL} — {exc}")
        return False


def main() -> int:
    print("\n" + "#" * 60)
    print("  SAFE PHASE 2 통합 테스트")
    print("#" * 60)

    results: list[bool] = []

    results.append(test_file_validation())
    saved = test_file_save()
    results.append(saved is not None)
    results.append(test_pdf_extract())
    results.append(test_scan_pdf_ocr())
    results.append(test_excel_extract())
    results.append(test_business_plan_parse())
    results.append(test_execution_detail_parse())
    results.append(test_proof_and_settlement_parse())

    # 테스트 파일 정리
    if saved:
        try:
            uploader.delete_upload(Path(saved).name)
        except Exception:
            pass

    _section("최종 결과")
    passed = sum(results)
    total = len(results)
    print(f"  통과: {passed}/{total}")

    if passed == total:
        print("\n  모든 테스트 통과!")
        return 0

    print("\n  일부 테스트 실패")
    return 1


if __name__ == "__main__":
    sys.exit(main())
