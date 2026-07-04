"""
PHASE 3 통합 테스트 스크립트
비교 엔진, DB 로그, HTML 보고서 순차 검증
"""

import logging
import os
import sys
import tempfile
from pathlib import Path

import checker
import config
import logger as safe_logger
import parser
import reporter

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger("test_phase3")

PASS = "[PASS]"
FAIL = "[FAIL]"

# PHASE 2 샘플 파싱 데이터
SAMPLE_BUSINESS_PLAN = parser.parse_document("""
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
""", "1")

SAMPLE_EXECUTION = parser.parse_document("""
사업명: 2026년 지역사회 활성화 사업
총 예산: 100,000,000원
총 집행: 120,000,000원
2026-03-15 인건비 지급 20,000,000원
""", "2")

SAMPLE_PROOF_OK = parser.parse_document("""
증빙번호: A-001
금액: 1,500,000원
공급자: (주)테스트상사
""", "3")

SAMPLE_PROOF_DUP = {
    **parser.parse_document("증빙번호: A-001\n금액: 1,500,000원", "3"),
    "duplicate_detected": [{"file_hash": "abc123", "files": ["a.pdf", "b.pdf"]}],
}

SAMPLE_SETTLEMENT_OK = parser.parse_document("""
사업명: 2026년 지역사회 활성화 사업
정산기간: 2026.01.01 ~ 2026.12.31
총 예산: 100,000,000원
총 집행: 95,000,000원
반납금: 5,000,000원
반납계획: 2027.01.31까지 반납 예정
정산기한: 2027.01.31
""", "4")

SAMPLE_SETTLEMENT_FAIL = parser.parse_document("""
사업명: 2026년 지역사회 활성화 사업
총 예산: 100,000,000원
총 집행: 95,000,000원
""", "4")

CHECKLIST_ID_TYPE1 = 2  # DB에 저장된 사업계획서 체크리스트


def _section(title: str) -> None:
    print(f"\n{'=' * 60}")
    print(f"  {title}")
    print("=" * 60)


def _mock_items(count: int = 3) -> list[dict]:
    """테스트용 최소 체크리스트 항목"""
    return [
        {
            "item_id": i,
            "item_no": i,
            "category": "테스트",
            "item_content": f"점검항목 {i}",
            "judge_criteria": f"판단기준 {i}",
            "law_ref": "지방보조금 관리기준",
            "risk_level": "M",
        }
        for i in range(1, count + 1)
    ]


def test_embedding_model_load() -> bool:
    """1. 임베딩 모델 로드 테스트"""
    _section("1. 임베딩 모델 로드")

    try:
        model = checker.load_embedding_model()
        dim = model.get_embedding_dimension()
        print(f"  모델: {config.EMBEDDING_MODEL}")
        print(f"  임베딩 차원: {dim}")
        print(f"  {PASS}")
        return True
    except Exception as exc:
        print(f"  {FAIL} — {exc}")
        return False


def test_faiss_index() -> bool:
    """2. FAISS 인덱스 생성 테스트"""
    _section("2. FAISS 인덱스 생성")

    try:
        import checklist_db

        checklist = checklist_db.load_checklist_for_review(CHECKLIST_ID_TYPE1)
        items = checklist["items"]
        index, embeddings = checker.build_faiss_index(items, CHECKLIST_ID_TYPE1)
        print(f"  항목 수: {len(items)}")
        print(f"  인덱스 크기: {index.ntotal}")
        print(f"  임베딩 차원: {embeddings.shape[1]}")
        print(f"  {PASS}")
        return True
    except Exception as exc:
        print(f"  {FAIL} — {exc}")
        return False


def test_similarity() -> bool:
    """3. 유사도 계산 테스트"""
    _section("3. 유사도 계산")

    try:
        text_a = "지방보조금 사업계획서 사업목적 및 예산편성"
        same = checker.calculate_similarity(text_a, text_a)
        diff = checker.calculate_similarity(text_a, "오늘 날씨가 맑습니다")

        print(f"  동일 텍스트 유사도: {same}")
        print(f"  무관 텍스트 유사도: {diff}")

        if same < 0.99:
            print(f"  {FAIL} — 동일 텍스트 유사도가 1.0에 가깝지 않음")
            return False
        if diff > 0.5:
            print(f"  {FAIL} — 무관 텍스트 유사도가 너무 높음")
            return False

        print(f"  {PASS}")
        return True
    except Exception as exc:
        print(f"  {FAIL} — {exc}")
        return False


def test_business_plan_compare() -> dict | None:
    """4. 사업계획서 비교 테스트"""
    _section("4. 사업계획서 비교")

    try:
        result = checker.compare_document(SAMPLE_BUSINESS_PLAN, CHECKLIST_ID_TYPE1)
        print(f"  전체 항목: {result['total_items']}")
        print(f"  적합/주의/부적합: {result['pass_count']}/{result['warn_count']}/{result['fail_count']}")
        print(f"  최종결과: {result['final_result']}")

        # 인건비 비율 규칙 확인 (40% → 적합)
        labor_rule = next(
            (d for d in result["details"] if d["item_content"] == "인건비 비율"),
            None,
        )
        if not labor_rule or labor_rule["judge_result"] != "P":
            print(f"  {FAIL} — 인건비 비율 40% 적합 판정 실패")
            return None

        print(f"  인건비 비율 규칙: {labor_rule['judge_result']} — {labor_rule['judge_reason']}")
        print(f"  {PASS}")
        return result
    except Exception as exc:
        print(f"  {FAIL} — {exc}")
        return None


def test_execution_compare() -> bool:
    """5. 집행내역서 비교 테스트"""
    _section("5. 집행내역서 비교")

    try:
        result = checker.compare_document(
            SAMPLE_EXECUTION,
            checklist_id=99,
            checklist_items=_mock_items(3),
            data_type="2",
        )

        budget_rule = next(
            (d for d in result["details"] if d["item_content"] == "예산 외 집행 항목"),
            None,
        )
        rate_rule = next(
            (d for d in result["details"] if d["item_content"] == "집행률"),
            None,
        )

        print(f"  예산외집행: {budget_rule['judge_result'] if budget_rule else 'N/A'}")
        print(f"  집행률: {rate_rule['judge_result'] if rate_rule else 'N/A'}")

        if not budget_rule or budget_rule["judge_result"] != "F":
            print(f"  {FAIL} — 예산 외 집행 부적합 판정 실패")
            return False

        print(f"  {PASS}")
        return True
    except Exception as exc:
        print(f"  {FAIL} — {exc}")
        return False


def test_proof_compare() -> bool:
    """6. 지출증빙 비교 테스트"""
    _section("6. 지출증빙 비교")

    try:
        result = checker.compare_document(
            SAMPLE_PROOF_DUP,
            checklist_id=98,
            checklist_items=_mock_items(2),
            data_type="3",
        )

        dup_rule = next(
            (d for d in result["details"] if d["item_content"] == "중복 증빙"),
            None,
        )
        print(f"  중복증빙 규칙: {dup_rule['judge_result'] if dup_rule else 'N/A'}")
        print(f"  최종결과: {result['final_result']}")

        if not dup_rule or dup_rule["judge_result"] != "F":
            print(f"  {FAIL} — 중복 증빙 부적합 판정 실패")
            return False
        if result["final_result"] != "F":
            print(f"  {FAIL} — 최종결과 F 기대")
            return False

        print(f"  {PASS}")
        return True
    except Exception as exc:
        print(f"  {FAIL} — {exc}")
        return False


def test_settlement_compare() -> bool:
    """7. 정산보고서 비교 테스트"""
    _section("7. 정산보고서 비교")

    try:
        ok_result = checker.compare_document(
            SAMPLE_SETTLEMENT_OK,
            checklist_id=97,
            checklist_items=_mock_items(2),
            data_type="4",
        )
        fail_result = checker.compare_document(
            SAMPLE_SETTLEMENT_FAIL,
            checklist_id=97,
            checklist_items=_mock_items(2),
            data_type="4",
        )

        refund_ok = next(
            (d for d in ok_result["details"] if d["item_content"] == "반납금 계획 명시"),
            None,
        )
        refund_fail = next(
            (d for d in fail_result["details"] if d["item_content"] == "반납금 계획 명시"),
            None,
        )

        print(f"  반납계획(기재): {refund_ok['judge_result'] if refund_ok else 'N/A'}")
        print(f"  반납계획(미기재): {refund_fail['judge_result'] if refund_fail else 'N/A'}")

        if not refund_ok or refund_ok["judge_result"] != "P":
            print(f"  {FAIL} — 반납계획 기재 적합 판정 실패")
            return False
        if not refund_fail or refund_fail["judge_result"] != "F":
            print(f"  {FAIL} — 반납계획 미기재 부적합 판정 실패")
            return False

        print(f"  {PASS}")
        return True
    except Exception as exc:
        print(f"  {FAIL} — {exc}")
        return False


def test_db_save(compare_result: dict | None) -> int | None:
    """8. MariaDB 저장 테스트"""
    _section("8. MariaDB 저장")

    if not compare_result:
        print(f"  {FAIL} — 비교 결과 없음")
        return None

    try:
        file_info = {
            "business_nm": SAMPLE_BUSINESS_PLAN.get("business_name", "테스트사업"),
            "file_nm": "test_plan.pdf",
            "file_path": "E:/gitSrc/safe/uploads/test_plan.pdf",
            "file_size": 1024,
            "file_ext": ".pdf",
            "ocr_yn": "N",
        }

        review_id = safe_logger.save_review(compare_result, file_info, reviewer="test_phase3")
        detail_cnt = safe_logger.save_review_details(
            review_id,
            compare_result["details"],
            checklist_id=compare_result.get("checklist_id"),
        )
        safe_logger.save_access_log("test_phase3", "CHECKLIST_VIEW", target_id=CHECKLIST_ID_TYPE1)

        print(f"  review_id: {review_id}")
        print(f"  상세 저장: {detail_cnt}건")

        detail = safe_logger.get_review_detail(review_id, user_id="test_phase3")
        if not detail or len(detail.get("details", [])) == 0:
            print(f"  {FAIL} — 상세 조회 실패")
            return None

        print(f"  {PASS}")
        return review_id
    except Exception as exc:
        print(f"  {FAIL} — {exc}")
        return None


def test_list_and_csv(review_id: int | None) -> bool:
    """9. 목록 조회 및 CSV보내기 테스트"""
    _section("9. 목록 조회 및 CSV보내기")

    try:
        all_list = safe_logger.get_review_list()
        print(f"  전체 목록: {all_list['total']}건")

        filtered = safe_logger.get_review_list({"data_type": "1", "page_size": 5})
        print(f"  유형1 필터: {filtered['total']}건")

        with tempfile.TemporaryDirectory() as tmp_dir:
            csv_path = os.path.join(tmp_dir, "review_export.csv")
            safe_logger.export_csv({}, csv_path, user_id="test_phase3")

            if not os.path.isfile(csv_path):
                print(f"  {FAIL} — CSV 파일 미생성")
                return False

            content = Path(csv_path).read_text(encoding="utf-8-sig")
            if "검토ID" not in content:
                print(f"  {FAIL} — CSV 헤더 누락")
                return False

            print(f"  CSV 생성: {csv_path} ({len(content)} bytes)")

        print(f"  {PASS}")
        return True
    except Exception as exc:
        print(f"  {FAIL} — {exc}")
        return False


def test_html_report(review_id: int | None) -> bool:
    """10. HTML 보고서 생성 테스트"""
    _section("10. HTML 보고서 생성")

    if not review_id:
        print(f"  {FAIL} — review_id 없음")
        return False

    try:
        report_path = reporter.generate_html_report(review_id)
        content = Path(report_path).read_text(encoding="utf-8")

        checks = [
            ('charset="UTF-8"' in content or "charset=UTF-8" in content, "UTF-8 메타태그"),
            ("SAFE 검토 결과 보고서" in content, "보고서 제목"),
            ("즉시 조치 필요 항목" in content or "적합" in content, "요약/위험 섹션"),
            (os.path.isfile(report_path), "파일 존재"),
        ]

        for ok, label in checks:
            print(f"  {label}: {'OK' if ok else 'FAIL'}")
            if not ok:
                print(f"  {FAIL}")
                return False

        print(f"  보고서 경로: {report_path}")
        print(f"  {PASS}")
        return True
    except Exception as exc:
        print(f"  {FAIL} — {exc}")
        return False


def main() -> int:
    print("\n" + "#" * 60)
    print("  SAFE PHASE 3 통합 테스트")
    print("#" * 60)

    results: list[bool] = []

    results.append(test_embedding_model_load())
    results.append(test_faiss_index())
    results.append(test_similarity())

    compare_result = test_business_plan_compare()
    results.append(compare_result is not None)

    results.append(test_execution_compare())
    results.append(test_proof_compare())
    results.append(test_settlement_compare())

    review_id = test_db_save(compare_result)
    results.append(review_id is not None)

    results.append(test_list_and_csv(review_id))
    results.append(test_html_report(review_id))

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
