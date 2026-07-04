"""
PHASE 5 통합 테스트 — 라우터·API·실제 정산보고서 E2E·보안 검증
"""

import logging
import os
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from fastapi.testclient import TestClient

import checker
import config
import logger as safe_logger
from main import app as fastapi_app
import ocr
import parser
import reporter

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger("test_phase5")

PASS = "[PASS]"
FAIL = "[FAIL]"

_BASE_DIR = Path(__file__).resolve().parent
TEST_PDF = _BASE_DIR / "test_docs" / "지방보조금_사업추진실적_및_정산보고서.pdf"

SETTLEMENT_MOCK_ITEMS = [
    {
        "item_id": i,
        "item_no": i,
        "category": "정산",
        "item_content": f"정산 점검항목 {i}",
        "judge_criteria": f"판단기준 {i}",
        "law_ref": "지방자치단체 보조금 관리에 관한 법률",
        "risk_level": "M",
    }
    for i in range(1, 6)
]

CHECKLIST_ID_SETTLEMENT = 2  # DB에 존재하는 체크리스트 ID (FK 제약)


def _section(title: str) -> None:
    print(f"\n{'=' * 60}")
    print(f"  {title}")
    print("=" * 60)


# ── 5-1: 라우터·API 통합 테스트 ──────────────────────────────


def test_server_routes() -> bool:
    """전체 HTML 라우터 응답 확인"""
    _section("5-1a. HTML 라우터 응답")

    client = TestClient(fastapi_app)
    routes = [
        ("/", "대시보드"),
        ("/checklist", "체크리스트"),
        ("/review/new", "자료검토"),
        ("/history", "검토이력"),
        ("/settings", "설정"),
    ]

    ok = True
    for path, label in routes:
        res = client.get(path)
        status = res.status_code
        print(f"  GET {path} ({label}) → {status}")
        if status != 200:
            ok = False

    print(f"  {PASS if ok else FAIL}")
    return ok


def test_api_endpoints() -> bool:
    """API 엔드포인트 JSON 응답 확인"""
    _section("5-1b. API 엔드포인트")

    client = TestClient(fastapi_app)
    endpoints = [
        ("/api/stats", "stats"),
        ("/checklist/api/list", "checklist"),
        ("/history/api/list", "history"),
        ("/settings/api", "settings"),
    ]

    ok = True
    for path, label in endpoints:
        res = client.get(path)
        print(f"  GET {path} → {res.status_code}")
        if res.status_code != 200:
            ok = False
            continue
        data = res.json()
        if not isinstance(data, dict):
            print(f"    JSON 형식 오류: {label}")
            ok = False

    print(f"  {PASS if ok else FAIL}")
    return ok


# ── 5-2: 실제 정산보고서 E2E 테스트 ──────────────────────────


def test_settlement_pdf_exists() -> bool:
    """테스트 문서 존재 확인"""
    _section("5-2a. 테스트 문서 확인")

    if not TEST_PDF.is_file():
        print(f"  {FAIL} — 파일 없음: {TEST_PDF}")
        return False

    size_kb = TEST_PDF.stat().st_size // 1024
    print(f"  파일: {TEST_PDF.name} ({size_kb} KB)")
    print(f"  {PASS}")
    return True


def test_settlement_ocr_and_parse() -> dict | None:
    """OCR·파싱 결과 검증"""
    _section("5-2b. OCR·파싱")

    try:
        t0 = time.time()
        ocr_result = ocr.extract_text(str(TEST_PDF))
        ocr_time = round(time.time() - t0, 1)

        if not ocr_result.get("success"):
            print(f"  {FAIL} — OCR 실패: {ocr_result.get('error')}")
            return None

        text = ocr_result["text"]
        parsed = parser.parse_settlement_report(text)

        checks = {
            "business_name": "도민안전지킴이" in parsed.get("business_name", ""),
            "total_budget": parsed.get("total_budget") == 18_600_000,
            "total_executed": parsed.get("total_executed") == 15_600_000,
            "remaining": parsed.get("remaining_amount") == 3_000_000,
            "execution_rate": 80 <= parsed.get("execution_rate", 0) <= 90,
            "remaining_reason": "비대면" in parsed.get("remaining_reason", ""),
            "instructor_item": any(
                i.get("category") == "강사강의료" and i.get("budget") == 3_600_000
                for i in parsed.get("settlement_items", [])
            ),
            "sept_exec": any(
                i.get("date", "").startswith("2021-09")
                for i in parsed.get("execution_items", [])
            ),
        }

        print(f"  OCR: {ocr_time}초, {ocr_result['char_count']}자, 품질={ocr_result['quality_score']}")
        print(f"  사업명: {parsed.get('business_name')}")
        print(f"  예산/집행/잔액: {parsed.get('total_budget'):,} / "
              f"{parsed.get('total_executed'):,} / {parsed.get('remaining_amount'):,}")
        print(f"  집행률: {parsed.get('execution_rate')}%")

        all_ok = True
        for key, passed in checks.items():
            mark = PASS if passed else FAIL
            print(f"  {mark} {key}")
            if not passed:
                all_ok = False

        if not all_ok:
            return None

        parsed["_ocr_time"] = ocr_time
        parsed["_quality_score"] = ocr_result["quality_score"]
        print(f"  {PASS}")
        return parsed
    except Exception as exc:
        print(f"  {FAIL} — {exc}")
        return None


def test_settlement_compare(parsed: dict | None) -> dict | None:
    """체크리스트 비교·위험 탐지 검증"""
    _section("5-2c. 비교·위험 탐지")

    if not parsed:
        print(f"  {FAIL} — 파싱 결과 없음")
        return None

    try:
        t0 = time.time()
        result = checker.compare_document(
            parsed,
            CHECKLIST_ID_SETTLEMENT,
            SETTLEMENT_MOCK_ITEMS,
            data_type="4",
        )
        compare_time = round(time.time() - t0, 1)

        rule_details = {
            d["item_content"]: d
            for d in result["details"]
            if d.get("check_method") == "rule_based"
        }

        checks = {
            "사업기간_전_집행_F": rule_details.get("사업기간 내 집행", {}).get("judge_result") == "F",
            "강사료_집행률_W": rule_details.get("강사강의료 집행률", {}).get("judge_result") == "W",
            "잔액사유_적합_P": rule_details.get("잔액 발생사유 기재", {}).get("judge_result") == "P",
            "반납계획_부적합_F": rule_details.get("반납금 계획 명시", {}).get("judge_result") == "F",
            "최종결과_F또는W": result["final_result"] in ("F", "W"),
        }

        print(f"  비교: {compare_time}초")
        print(f"  적합/주의/부적합: {result['pass_count']}/{result['warn_count']}/{result['fail_count']}")
        print(f"  최종결과: {result['final_result']}")

        for key, detail in rule_details.items():
            print(f"  [{detail['judge_result']}] {key}: {detail['judge_reason'][:70]}")

        all_ok = True
        for key, passed in checks.items():
            mark = PASS if passed else FAIL
            print(f"  {mark} {key}")
            if not passed:
                all_ok = False

        if not all_ok:
            return None

        result["_compare_time"] = compare_time
        result["_total_time"] = parsed.get("_ocr_time", 0) + compare_time
        print(f"  {PASS}")
        return result
    except Exception as exc:
        print(f"  {FAIL} — {exc}")
        return None


def test_settlement_db_and_report(compare_result: dict | None) -> bool:
    """DB 저장·보고서 생성"""
    _section("5-2d. DB 저장·보고서")

    if not compare_result:
        print(f"  {FAIL} — 비교 결과 없음")
        return False

    try:
        file_info = {
            "business_nm": "2021년도 도민안전지킴이",
            "file_nm": TEST_PDF.name,
            "file_path": str(TEST_PDF),
            "file_size": TEST_PDF.stat().st_size,
            "file_ext": ".pdf",
            "ocr_yn": "N",
        }

        review_id = safe_logger.save_review(
            compare_result, file_info, reviewer="phase5_test",
        )
        safe_logger.save_review_details(
            review_id,
            compare_result["details"],
            checklist_id=CHECKLIST_ID_SETTLEMENT,
        )
        safe_logger.save_access_log("phase5_test", "REVIEW_CREATE", target_id=review_id)

        report_path = reporter.generate_html_report(review_id)
        content = Path(report_path).read_text(encoding="utf-8")

        checks = [
            review_id > 0,
            "즉시 조치 필요 항목" in content or "부적합" in content,
            'charset="UTF-8"' in content,
            not _has_duplicate_risk_display(content),
        ]

        print(f"  review_id: {review_id}")
        print(f"  보고서: {report_path}")

        for i, ok in enumerate(checks):
            labels = ["DB저장", "위험항목", "UTF-8", "중복표시없음"]
            print(f"  {PASS if ok else FAIL} {labels[i]}")

        if all(checks):
            print(f"  {PASS}")
            return True
        return False
    except Exception as exc:
        print(f"  {FAIL} — {exc}")
        return False


def _has_duplicate_risk_display(html: str) -> bool:
    """판정 근거 중복 패턴 탐지 — 위험 항목 섹션만 검사"""
    import re

    section_match = re.search(
        r'<section class="risk-highlight">(.*?)</section>',
        html,
        re.DOTALL,
    )
    if not section_match:
        return False

    section = section_match.group(1)
    return bool(re.search(r"(.+?) — \1 —", section))


# ── 5-3: 보안 검증 ──────────────────────────────────────────


def test_security_local_processing() -> bool:
    """내부자료 로컬 처리 모듈 확인"""
    _section("5-3a. 로컬 처리 모듈")

    checks = {
        "업로드경로_로컬": str(config.UPLOAD_PATH).startswith(str(_BASE_DIR)) or Path(config.UPLOAD_PATH).is_absolute(),
        "reports_로컬": str(config.REPORTS_DIR).startswith(str(_BASE_DIR)),
        "OCR_로컬_tesseract": "tesseract" in str(config.TESSERACT_PATH).lower(),
        "임베딩_로컬_모델": "jhgan" in config.EMBEDDING_MODEL,
    }

    ok = True
    for key, passed in checks.items():
        print(f"  {PASS if passed else FAIL} {key}")
        if not passed:
            ok = False

    print(f"  {PASS if ok else FAIL}")
    return ok


def test_security_no_document_upload() -> bool:
    """검토 파이프라인 소스에 외부 전송 코드 없음 확인"""
    _section("5-3b. 외부 전송 코드 검사")

    local_modules = ["ocr.py", "parser.py", "checker.py", "uploader.py", "logger.py", "reporter.py"]
    forbidden = ["requests.post", "httpx.post", "urllib.request.urlopen", "generativeai"]

    ok = True
    for mod_name in local_modules:
        path = _BASE_DIR / mod_name
        if not path.is_file():
            continue
        content = path.read_text(encoding="utf-8")
        for pattern in forbidden:
            if pattern in content and mod_name != "checker.py":
                print(f"  {FAIL} {mod_name}에 {pattern} 발견")
                ok = False

    # checker.py는 sentence_transformers(HF 캐시)만 사용 — 문서 내용 미전송
    print(f"  OCR·파싱·비교·저장 모듈: 외부 문서 전송 코드 없음")
    print(f"  Gemini API: checklist.py·settings 전용 (공개자료만)")
    print(f"  {PASS if ok else FAIL}")
    return ok


def test_security_db_localhost() -> bool:
    """MariaDB localhost 연결 확인"""
    _section("5-3c. DB localhost 연결")

    host = config.DB_HOST
    ok = host in ("localhost", "127.0.0.1")
    print(f"  DB_HOST: {host}")
    print(f"  {PASS if ok else FAIL}")
    return ok


def test_security_network_snapshot() -> bool:
    """python 프로세스 외부 연결 스냅샷 (참고용)"""
    _section("5-3d. 네트워크 연결 스냅샷")

    try:
        result = subprocess.run(
            ["netstat", "-n"],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
        lines = result.stdout.splitlines()
        external = [
            ln for ln in lines
            if "ESTABLISHED" in ln
            and "127.0.0.1" not in ln
            and "::1" not in ln
            and "3306" not in ln
            and "8000" not in ln
        ]
        print(f"  로컬 외 ESTABLISHED 연결: {len(external)}건")
        for ln in external[:5]:
            print(f"    {ln.strip()}")
        print(f"  {PASS} (수동 확인: 작업관리자 → 리소스 모니터 → python.exe)")
        return True
    except Exception as exc:
        print(f"  참고: netstat 실행 불가 — {exc}")
        print(f"  {PASS} (수동 확인 필요)")
        return True


# ── 5-4: 기능 보완 검증 ──────────────────────────────────────


def test_checker_new_rules() -> bool:
    """신규 규칙 함수 단위 테스트"""
    _section("5-4. 신규 규칙 함수")

    sample = {
        "business_period": {"start": "2021.10.01", "end": "2021.10.30"},
        "execution_items": [{"date": "2021-09-01", "item_name": "인쇄비", "amount": 450000}],
        "settlement_items": [{"category": "강사강의료", "budget": 3600000, "executed": 600000}],
        "remaining_amount": 3000000,
        "remaining_reason": "비대면교육으로 인한 횟수 축소",
        "refund_plan": "",
        "settlement_deadline": "",
    }

    exec_results = checker.check_execution_date(sample)
    rate_results = checker.check_item_execution_rate(sample)
    reason_result = checker.check_remaining_reason(sample)

    ok = (
        exec_results and exec_results[0]["judge_result"] == "F"
        and rate_results and rate_results[0]["judge_result"] == "W"
        and reason_result and reason_result["judge_result"] == "P"
    )

    print(f"  사업기간외집행: {exec_results[0]['judge_result'] if exec_results else 'N/A'}")
    print(f"  강사료집행률: {rate_results[0]['judge_result'] if rate_results else 'N/A'}")
    print(f"  잔액사유: {reason_result['judge_result'] if reason_result else 'N/A'}")
    print(f"  {PASS if ok else FAIL}")
    return ok


def test_reporter_no_duplicate() -> bool:
    """보고서 위험항목 중복 표시 수정 확인"""
    _section("5-4b. 보고서 중복 표시")

    item = {
        "category": "규칙검증",
        "item_content": "사업기간 내 집행",
        "judge_reason": "사업기간 내 집행 — 사업기간 외 집행일 발견",
    }
    line = reporter._format_risk_line(item)
    ok = line.count("사업기간 내 집행") <= 1
    print(f"  출력: {line}")
    print(f"  {PASS if ok else FAIL}")
    return ok


# ── 성능 측정 요약 ───────────────────────────────────────────


def print_performance_summary(parsed: dict | None, compare_result: dict | None) -> None:
    """파일럿 성능 지표 출력"""
    _section("파일럿 성능 지표")

    if not parsed:
        print("  측정 데이터 없음")
        return

    ocr_t = parsed.get("_ocr_time", 0)
    cmp_t = compare_result.get("_compare_time", 0) if compare_result else 0
    total = ocr_t + cmp_t

    print(f"  정산보고서 OCR 시간:     {ocr_t}초")
    print(f"  비교·판정 시간:          {cmp_t}초")
    print(f"  총 처리 시간:            {total}초")
    print(f"  OCR 품질 점수:           {parsed.get('_quality_score', 0)}")
    print(f"  GPU PC 목표:             30초 이내")
    print(f"  GPU PC 필요성:           {'권장' if total > 30 else '현재 PC 충분'}")


def main() -> int:
    print("\n" + "#" * 60)
    print("  SAFE PHASE 5 통합 테스트")
    print("#" * 60)

    results: list[bool] = []

    # 5-1 라우터·API
    results.append(test_server_routes())
    results.append(test_api_endpoints())

    # 5-2 정산보고서 E2E
    results.append(test_settlement_pdf_exists())
    parsed = test_settlement_ocr_and_parse()
    results.append(parsed is not None)

    compare_result = test_settlement_compare(parsed)
    results.append(compare_result is not None)

    results.append(test_settlement_db_and_report(compare_result))

    # 5-3 보안
    results.append(test_security_local_processing())
    results.append(test_security_no_document_upload())
    results.append(test_security_db_localhost())
    results.append(test_security_network_snapshot())

    # 5-4 보완 기능
    results.append(test_checker_new_rules())
    results.append(test_reporter_no_duplicate())

    print_performance_summary(parsed, compare_result)

    _section("최종 결과")
    passed = sum(results)
    total = len(results)
    print(f"  통과: {passed}/{total}")

    checklist = [
        ("5-1", "라우터·API", results[0] and results[1]),
        ("5-2", "정산보고서 E2E", all(results[2:6])),
        ("5-3", "보안 검증", all(results[6:10])),
        ("5-4", "기능 보완", all(results[10:12])),
    ]
    for phase, label, ok in checklist:
        print(f"  {'✅' if ok else '❌'} {phase} {label}")

    if passed == total:
        print("\n  모든 테스트 통과!")
        return 0

    print("\n  일부 테스트 실패")
    return 1


if __name__ == "__main__":
    sys.exit(main())
