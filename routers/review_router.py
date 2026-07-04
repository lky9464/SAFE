"""자료 검토 라우터 — 업로드·비동기 검토 파이프라인"""

import logging
import uuid
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, File, Form, Request, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel

import checker
import checklist_db
import config
import inspection_checklist
import logger as safe_logger
import ocr
import parser
import reporter
import uploader
from na_engine import CaseProfile, profile_to_snapshot
from web_common import DATA_TYPE_LABELS, RESULT_LABELS, get_static_version, get_upload_limits, templates

_DOC_LABELS = {"1": "① 사업계획서", "2": "② 집행내역서", "3": "③ 지출증빙", "4": "④ 정산보고서"}

logger = logging.getLogger(__name__)
router = APIRouter()

# 메모리 내 태스크 상태
task_status: dict[str, dict] = {}


class CaseProfilePayload(BaseModel):
    """일제점검 N/A용 사업 프로필 (검토 화면 입력)."""

    enabled: bool = True
    has_plan: bool = True
    has_execution: bool = True
    has_proof: bool = True
    has_settlement: bool = True
    executed_seomoks: list[str] = []
    operating_grant_only: bool = False


class CaseFilePayload(BaseModel):
    """사업 통합 검토용 자료 1건 (①~④)."""

    data_type: str
    file_path: str
    file_nm: str = ""


class ReviewStartRequest(BaseModel):
    task_id: str = ""
    data_type: str = "0"
    file_path: str = ""
    business_nm: str = ""
    checklist_id: int | None = None  # None 또는 -1이면 "전체" 모드
    reviewer: str = "담당자"
    case_profile: CaseProfilePayload | None = None
    case_files: list[CaseFilePayload] | None = None  # Phase 3: ①~④ 다중 업로드


def _update_task(task_id: str, **kwargs) -> None:
    """태스크 상태 업데이트"""
    if task_id not in task_status:
        task_status[task_id] = {}
    task_status[task_id].update(kwargs)


def _is_inspection_checklist(checklist_id: int) -> bool:
    detail = checklist_db.get_checklist_detail(checklist_id)
    return bool(detail and str(detail.get("data_type")) == inspection_checklist.INSPECTION_DATA_TYPE)


def _case_file_types(data: dict) -> set[str]:
    """업로드된 사업 통합 자료유형 집합."""
    types: set[str] = set()
    for cf in data.get("case_files") or []:
        if isinstance(cf, CaseFilePayload):
            types.add(str(cf.data_type))
        elif isinstance(cf, dict) and cf.get("data_type"):
            types.add(str(cf["data_type"]))
    return types


def _build_case_profile(data: dict, checklist_id: int) -> CaseProfile | None:
    """요청 본문 + 체크리스트 유형에 따라 CaseProfile 생성."""
    use_inspection = _is_inspection_checklist(checklist_id)
    raw = data.get("case_profile")
    uploaded = _case_file_types(data)

    if raw is None:
        if not use_inspection:
            return None
        if uploaded:
            return CaseProfile(
                has_plan="1" in uploaded,
                has_execution="2" in uploaded,
                has_proof="3" in uploaded,
                has_settlement="4" in uploaded,
            )
        return CaseProfile()

    if isinstance(raw, CaseProfilePayload):
        payload = raw
    elif isinstance(raw, dict):
        payload = CaseProfilePayload(**raw)
    else:
        return CaseProfile() if use_inspection else None

    if not payload.enabled and not use_inspection:
        return None
    if not payload.enabled and use_inspection:
        return None

    # 다중 업로드가 있으면 제출 자료 유무는 실제 파일 기준
    if uploaded:
        return CaseProfile(
            has_plan="1" in uploaded,
            has_execution="2" in uploaded,
            has_proof="3" in uploaded,
            has_settlement="4" in uploaded,
            executed_seomoks=frozenset(payload.executed_seomoks),
            operating_grant_only=payload.operating_grant_only,
        )

    return CaseProfile(
        has_plan=payload.has_plan,
        has_execution=payload.has_execution,
        has_proof=payload.has_proof,
        has_settlement=payload.has_settlement,
        executed_seomoks=frozenset(payload.executed_seomoks),
        operating_grant_only=payload.operating_grant_only,
    )


def _merge_case_parsed(
    per_doc: dict[str, dict],
    business_nm: str,
) -> dict:
    """①~④ 파싱 결과를 유사도 비교용 단일 dict 로 병합."""
    sections: list[str] = []
    name = business_nm
    for dt in ("1", "2", "3", "4"):
        parsed = per_doc.get(dt)
        if not parsed:
            continue
        label = DATA_TYPE_LABELS.get(dt, dt)
        sections.append(f"=== {label} ===\n{checker._parsed_data_to_text(parsed)}")
        if not name and parsed.get("business_name"):
            name = parsed["business_name"]
    merged: dict = {
        "business_name": name or "미상",
        "case_mode": True,
        "uploaded_docs": sorted(per_doc.keys()),
        "combined_text": "\n\n".join(sections),
    }
    # ① 사업계획 — 교차 규칙(JC-01, X07)용
    if "1" in per_doc:
        p1 = per_doc["1"]
        merged["business_period"] = p1.get("business_period") or {}
        merged["plan_total_budget"] = p1.get("total_budget") or 0
        merged["budget_breakdown"] = p1.get("budget_breakdown") or {}
        merged["budget_plan_items"] = p1.get("budget_plan_items") or []
        merged["labor_ratio"] = p1.get("labor_ratio")
        merged["settlement_plan"] = p1.get("settlement_plan")
        if merged["budget_plan_items"] and not merged["plan_total_budget"]:
            merged["plan_total_budget"] = sum(
                int(i.get("amount", 0)) for i in merged["budget_plan_items"]
            )
    # ② 집행내역
    if "2" in per_doc:
        p2 = per_doc["2"]
        merged["total_executed"] = p2.get("total_executed") or 0
        merged["execution_items"] = p2.get("execution_items") or []
        merged["out_of_budget_items"] = p2.get("out_of_budget_items") or []
        merged["execution_rate"] = p2.get("execution_rate")
        merged["execution_file_path"] = p2.get("_source_file") or ""
        if not merged.get("plan_total_budget"):
            # ①에 예산이 없을 때만 ② 기재 예산 참고
            merged["exec_stated_budget"] = p2.get("total_budget") or 0
        item_sum = sum(int(i.get("amount", 0)) for i in merged["execution_items"])
        if item_sum > merged["total_executed"]:
            merged["total_executed"] = item_sum
    # ④ 정산 — 사업기간 보완
    if "4" in per_doc:
        p4 = per_doc["4"]
        period = merged.get("business_period") or {}
        if not period.get("start"):
            merged["business_period"] = (
                p4.get("business_period") or p4.get("settlement_period") or {}
            )
        merged["settlement_items"] = p4.get("settlement_items") or []
    return merged


def run_case_review_pipeline(task_id: str, data: dict) -> None:
    """
    사업 1건 통합 검토 (Phase 3).
    ①~④ 중 업로드된 자료를 OCR·파싱 후 일제점검 체크리스트 1회 비교.
    """
    try:
        case_files = data.get("case_files") or []
        if not case_files:
            raise ValueError("업로드된 사업 자료가 없습니다.")

        checklist_id = data.get("checklist_id")
        if not checklist_id or checklist_id <= 0:
            raise ValueError("사업 통합 검토는 일제점검 체크리스트를 선택해야 합니다.")
        if not _is_inspection_checklist(checklist_id):
            raise ValueError("사업 통합 검토는 일제점검(통합) 체크리스트만 지원합니다.")

        reviewer = data.get("reviewer", "담당자")
        business_nm = data.get("business_nm", "")

        _update_task(
            task_id,
            step=1, progress=5, status="processing",
            steps={"upload": "done", "ocr": "waiting", "parse": "waiting",
                   "compare": "waiting", "save": "waiting"},
            message="사업 자료 수신 완료",
        )

        per_doc: dict[str, dict] = {}
        file_names: list[str] = []
        primary_path = ""
        any_ocr = False
        total = len(case_files)

        for idx, cf in enumerate(case_files):
            if isinstance(cf, CaseFilePayload):
                dt, fpath, fnm = cf.data_type, cf.file_path, cf.file_nm
            else:
                dt = str(cf["data_type"])
                fpath = cf["file_path"]
                fnm = cf.get("file_nm") or Path(fpath).name

            if not primary_path:
                primary_path = fpath
            file_names.append(fnm or Path(fpath).name)

            pct = 10 + int(50 * idx / total)
            _update_task(
                task_id, step=2, progress=pct,
                steps={"upload": "done", "ocr": "processing", "parse": "processing",
                       "compare": "waiting", "save": "waiting"},
                message=f"자료 {DATA_TYPE_LABELS.get(dt, dt)} 처리 중 ({idx + 1}/{total})...",
            )

            ocr_result = ocr.extract_text(fpath, data_type=dt)
            if not ocr_result["success"]:
                raise RuntimeError(
                    f"{DATA_TYPE_LABELS.get(dt, dt)} OCR 실패: "
                    f"{ocr_result.get('error', '알 수 없음')}"
                )
            if ocr_result.get("ocr_used"):
                any_ocr = True

            parsed = parser.parse_document(ocr_result["text"], dt, fpath)
            parsed["_source_file"] = fpath
            per_doc[dt] = parsed
            if dt == "2":
                n_exec = len(parsed.get("execution_items") or [])
                logger.info("② 집행내역 파싱 결과 — %d건, file=%s", n_exec, fpath)
                if n_exec == 0:
                    logger.warning("② 집행거래일자/금액을 읽지 못함 — X07·JC-01 주의 가능")
            if not business_nm and parsed.get("business_name"):
                business_nm = parsed["business_name"]

        if not business_nm:
            business_nm = Path(primary_path).stem if primary_path else "미상"

        merged = _merge_case_parsed(per_doc, business_nm)

        _update_task(
            task_id, step=4, progress=70,
            steps={"upload": "done", "ocr": "done", "parse": "done",
                   "compare": "processing", "save": "waiting"},
            message="일제점검 체크리스트 비교 중...",
        )

        compare_result = _compare_with_profile(merged, checklist_id, data)
        compare_result["data_type"] = inspection_checklist.INSPECTION_DATA_TYPE

        _update_task(
            task_id, step=5, progress=90,
            steps={"upload": "done", "ocr": "done", "parse": "done",
                   "compare": "done", "save": "processing"},
            message="결과 저장 중...",
        )

        total_size = 0
        for cf in case_files:
            p = Path(cf.file_path if isinstance(cf, CaseFilePayload) else cf["file_path"])
            try:
                total_size += p.stat().st_size
            except OSError:
                pass

        file_info = {
            "business_nm": business_nm,
            "file_nm": " + ".join(file_names),
            "file_path": primary_path,
            "file_size": total_size,
            "file_ext": Path(primary_path).suffix if primary_path else "",
            "ocr_yn": "Y" if any_ocr else "N",
        }
        review_id = safe_logger.save_review(compare_result, file_info, reviewer)
        safe_logger.save_review_details(
            review_id, compare_result["details"], checklist_id=checklist_id,
        )

        _update_task(
            task_id,
            step=5, progress=100, status="done",
            review_id=review_id,
            steps={"upload": "done", "ocr": "done", "parse": "done",
                   "compare": "done", "save": "done"},
            message="사업 통합 검토 완료",
        )
        logger.info(
            "사업 통합 검토 완료 — task=%s, review_id=%d, docs=%s",
            task_id, review_id, sorted(per_doc.keys()),
        )

    except Exception as exc:
        logger.error("사업 통합 검토 실패 [%s]: %s", task_id, exc)
        _update_task(task_id, status="error", error_msg=str(exc), message="오류 발생")


def _compare_with_profile(
    parsed: dict,
    checklist_id: int,
    data: dict,
) -> dict:
    profile = _build_case_profile(data, checklist_id)
    result = checker.compare_document(parsed, checklist_id, case_profile=profile)
    if profile is not None:
        result["case_profile"] = profile_to_snapshot(profile)
    return result


def _format_profile_summary(snapshot: dict | None) -> dict | None:
    """결과 화면용 프로필 표시 문구."""
    if not snapshot:
        return None
    docs = [_DOC_LABELS[d] for d in snapshot.get("docs", []) if d in _DOC_LABELS]
    labels = inspection_checklist.INSPECTION_SEOMOK_LABELS
    seomoks = [
        f"{code} {labels.get(code, '')}".strip()
        for code in snapshot.get("seomoks", [])
    ]
    return {
        "docs_text": ", ".join(docs) if docs else "없음",
        "seomoks_text": ", ".join(seomoks) if seomoks else "없음",
        "operating_grant_only": bool(snapshot.get("operating_grant_only")),
    }


def _resolve_checklist_id(data_type: str, checklist_id: int | None) -> int:
    """자료유형에 맞는 체크리스트 ID 결정 (-1/None이면 해당 유형 첫 체크리스트)"""
    if checklist_id is not None and checklist_id > 0:
        return checklist_id
    items = checklist_db.get_checklist_list(data_type)
    if not items:
        raise ValueError(f"자료유형 {data_type}에 등록된 체크리스트가 없습니다.")
    return items[0]["checklist_id"]


def run_review_pipeline(task_id: str, data: dict) -> None:
    """
    검토 파이프라인 (백그라운드 실행)
    1.파일확인 → 2.OCR → 3.파싱 → 4.비교 → 5.DB저장
    """
    try:
        data_type = data["data_type"]
        file_path = data["file_path"]
        reviewer = data.get("reviewer", "담당자")
        business_nm = data.get("business_nm", "")

        _update_task(
            task_id,
            step=1, progress=10, status="processing",
            steps={"upload": "done", "ocr": "waiting", "parse": "waiting",
                   "compare": "waiting", "save": "waiting"},
            message="파일 수신 완료",
        )

        # STEP 2: OCR
        _update_task(task_id, step=2, progress=25,
                     steps={"upload": "done", "ocr": "processing",
                            "parse": "waiting", "compare": "waiting", "save": "waiting"},
                     message="OCR 처리 중...")
        ocr_result = ocr.extract_text(file_path, data_type=data_type)
        if not ocr_result["success"]:
            raise RuntimeError(ocr_result.get("error", "OCR 실패"))

        _update_task(task_id, progress=45,
                     steps={"upload": "done", "ocr": "done", "parse": "processing",
                            "compare": "waiting", "save": "waiting"},
                     message="항목 파싱 중...")

        # STEP 3: 파싱
        parsed = parser.parse_document(ocr_result["text"], data_type, file_path)
        if business_nm:
            parsed["business_name"] = business_nm
        elif parsed.get("business_name"):
            business_nm = parsed["business_name"]
        else:
            business_nm = Path(file_path).stem

        _update_task(task_id, step=4, progress=65,
                     steps={"upload": "done", "ocr": "done", "parse": "done",
                            "compare": "processing", "save": "waiting"},
                     message="체크리스트 비교 중...")

        # STEP 4: 비교
        checklist_id = _resolve_checklist_id(data_type, data.get("checklist_id"))
        compare_result = _compare_with_profile(parsed, checklist_id, data)

        _update_task(task_id, step=5, progress=85,
                     steps={"upload": "done", "ocr": "done", "parse": "done",
                            "compare": "done", "save": "processing"},
                     message="결과 저장 중...")

        # STEP 5: DB 저장
        file_info = {
            "business_nm": business_nm,
            "file_nm": Path(file_path).name,
            "file_path": file_path,
            "file_size": Path(file_path).stat().st_size,
            "file_ext": Path(file_path).suffix,
            "ocr_yn": "Y" if ocr_result.get("ocr_used") else "N",
        }
        review_id = safe_logger.save_review(compare_result, file_info, reviewer)
        safe_logger.save_review_details(
            review_id, compare_result["details"], checklist_id=checklist_id,
        )

        # 중복 증빙 저장 (유형3)
        if data_type == "3" and parsed.get("duplicate_detected"):
            safe_logger.save_duplicate_detect(review_id, parsed["duplicate_detected"])

        _update_task(
            task_id,
            step=5, progress=100, status="done",
            review_id=review_id,
            steps={"upload": "done", "ocr": "done", "parse": "done",
                   "compare": "done", "save": "done"},
            message="검토 완료",
        )
        logger.info("검토 파이프라인 완료 — task=%s, review_id=%d", task_id, review_id)

    except Exception as exc:
        logger.error("검토 파이프라인 실패 [%s]: %s", task_id, exc)
        _update_task(task_id, status="error", error_msg=str(exc), message="오류 발생")


def run_review_pipeline_all(task_id: str, data: dict) -> None:
    """
    전체 체크리스트 일괄 점검 파이프라인 (백그라운드 실행).
    자료유형에 속한 모든 체크리스트를 순차 실행 후 리뷰 ID 목록 반환.
    """
    try:
        data_type = data["data_type"]
        file_path = data["file_path"]
        reviewer = data.get("reviewer", "담당자")
        business_nm = data.get("business_nm", "")

        _update_task(
            task_id,
            step=1, progress=5, status="processing",
            steps={"upload": "done", "ocr": "waiting", "parse": "waiting",
                   "compare": "waiting", "save": "waiting"},
            message="파일 수신 완료 (전체 점검 모드)",
        )

        # OCR
        _update_task(task_id, step=2, progress=20,
                     steps={"upload": "done", "ocr": "processing",
                            "parse": "waiting", "compare": "waiting", "save": "waiting"},
                     message="OCR 처리 중...")
        ocr_result = ocr.extract_text(file_path, data_type=data_type)
        if not ocr_result["success"]:
            raise RuntimeError(ocr_result.get("error", "OCR 실패"))

        # 파싱
        _update_task(task_id, progress=35,
                     steps={"upload": "done", "ocr": "done", "parse": "processing",
                            "compare": "waiting", "save": "waiting"},
                     message="항목 파싱 중...")
        parsed = parser.parse_document(ocr_result["text"], data_type, file_path)
        if business_nm:
            parsed["business_name"] = business_nm
        elif parsed.get("business_name"):
            business_nm = parsed["business_name"]
        else:
            business_nm = Path(file_path).stem

        # 해당 자료유형의 전체 체크리스트 목록 조회
        all_checklists = checklist_db.get_checklist_list(data_type)
        if not all_checklists:
            raise ValueError(f"자료유형 {data_type}에 등록된 체크리스트가 없습니다.")

        total = len(all_checklists)
        review_ids: list[int] = []
        file_info = {
            "business_nm": business_nm,
            "file_nm": Path(file_path).name,
            "file_path": file_path,
            "file_size": Path(file_path).stat().st_size,
            "file_ext": Path(file_path).suffix,
            "ocr_yn": "Y" if ocr_result.get("ocr_used") else "N",
        }

        for idx, cl in enumerate(all_checklists, start=1):
            cl_id = cl["checklist_id"]
            _update_task(
                task_id, progress=35 + int(55 * idx / total),
                steps={"upload": "done", "ocr": "done", "parse": "done",
                       "compare": "processing", "save": "waiting"},
                message=f"체크리스트 {idx}/{total} 비교 중... ({cl['checklist_nm']})",
            )

            compare_result = _compare_with_profile(parsed, cl_id, data)
            review_id = safe_logger.save_review(compare_result, file_info, reviewer)
            safe_logger.save_review_details(
                review_id, compare_result["details"], checklist_id=cl_id,
            )
            if data_type == "3" and parsed.get("duplicate_detected"):
                safe_logger.save_duplicate_detect(review_id, parsed["duplicate_detected"])
            review_ids.append(review_id)

        _update_task(
            task_id,
            step=5, progress=100, status="done",
            review_id=review_ids[0] if review_ids else None,  # 첫 번째 결과 대표
            review_ids=review_ids,
            total_checklists=total,
            steps={"upload": "done", "ocr": "done", "parse": "done",
                   "compare": "done", "save": "done"},
            message=f"전체 점검 완료 ({total}개 체크리스트)",
        )
        logger.info(
            "전체 점검 파이프라인 완료 — task=%s, 체크리스트=%d개, review_ids=%s",
            task_id, total, review_ids,
        )

    except Exception as exc:
        logger.error("전체 점검 파이프라인 실패 [%s]: %s", task_id, exc)
        _update_task(task_id, status="error", error_msg=str(exc), message="오류 발생")


@router.get("/new")
async def review_new_page(request: Request):
    """SCR-003 검토 시작 화면"""
    try:
        checklists = checklist_db.get_checklist_list()
    except Exception as exc:
        logger.error("체크리스트 목록 조회 실패: %s", exc)
        return templates.TemplateResponse(
            request,
            "review.html",
            {
                "active_page": "review",
                "data_types": {k: v for k, v in DATA_TYPE_LABELS.items() if k != "0"},
                "checklists": [],
                "profile_seomoks": inspection_checklist.get_profile_schema(),
                "upload_limits": get_upload_limits(),
                "static_ver": get_static_version("static/js/review.js"),
                "page_error": (
                    "체크리스트를 불러오지 못했습니다. MariaDB가 실행 중인지 확인하세요."
                ),
            },
            status_code=503,
        )

    for c in checklists:
        c["data_type_nm"] = DATA_TYPE_LABELS.get(c["data_type"], c["data_type"])
    # 업로드 유형 카드에는 1~4만 표시
    upload_data_types = {
        k: v for k, v in DATA_TYPE_LABELS.items() if k != inspection_checklist.INSPECTION_DATA_TYPE
    }
    return templates.TemplateResponse(
        request,
        "review.html",
        {
            "active_page": "review",
            "data_types": upload_data_types,
            "checklists": checklists,
            "profile_seomoks": inspection_checklist.get_profile_schema(),
            "upload_limits": get_upload_limits(),
            "static_ver": get_static_version("static/js/review.js"),
            "page_error": None,
        },
    )


@router.post("/api/upload")
async def api_upload(
    file: UploadFile = File(...),
    data_type: str = Form(...),
):
    """파일 업로드"""
    try:
        content = await file.read()
        if not file.filename:
            raise ValueError("파일명을 확인할 수 없습니다.")
        validation = uploader.validate_file((file.filename, content), data_type)
        saved_path = uploader.save_upload((file.filename, content), data_type)
        resp = {
            "success": True,
            "file_path": saved_path,
            "file_nm": Path(saved_path).name,
            "file_size": Path(saved_path).stat().st_size,
        }
        if Path(saved_path).suffix.lower() == ".zip":
            resp["is_zip_bundle"] = True
            eligible = validation.get("eligible_count", 0)
            skipped = validation.get("skipped_count", 0)
            resp["bundle_file_count"] = eligible
            resp["message"] = (
                f"ZIP 묶음 업로드 완료 (처리 대상 {eligible}개"
                + (f", 제외 {skipped}개" if skipped else "")
                + "). 검토 시 순차 처리합니다."
            )
        return resp
    except Exception as exc:
        logger.error("업로드 실패: %s", exc)
        return {"success": False, "message": str(exc)}


@router.post("/api/start")
async def api_start_review(body: ReviewStartRequest, background_tasks: BackgroundTasks):
    """
    검토 실행 (비동기).
    checklist_id가 None 또는 -1이면 전체 체크리스트 일괄 점검 모드.
    """
    task_id = str(uuid.uuid4())
    task_status[task_id] = {
        "step": 0, "progress": 0, "status": "processing",
        "review_id": None, "review_ids": None, "error_msg": None,
        "steps": {"upload": "waiting", "ocr": "waiting", "parse": "waiting",
                  "compare": "waiting", "save": "waiting"},
        "message": "검토 시작",
    }

    payload = body.model_dump()
    is_case_mode = bool(body.case_files)
    is_all_mode = (body.checklist_id is None or body.checklist_id == -1) and not is_case_mode

    if is_case_mode:
        background_tasks.add_task(run_case_review_pipeline, task_id, payload)
    elif is_all_mode:
        background_tasks.add_task(run_review_pipeline_all, task_id, payload)
    else:
        background_tasks.add_task(run_review_pipeline, task_id, payload)

    return {"task_id": task_id, "all_mode": is_all_mode, "case_mode": is_case_mode}


@router.get("/api/status/{task_id}")
async def api_review_status(task_id: str):
    """처리 진행 상태 폴링"""
    return task_status.get(task_id, {"status": "not_found", "message": "태스크를 찾을 수 없습니다."})


@router.get("/{review_id}/result")
async def review_result_page(request: Request, review_id: int):
    """SCR-004 검토 결과 상세 화면"""
    detail = safe_logger.get_review_detail(review_id)
    if not detail:
        return templates.TemplateResponse(
            request,
            "result.html",
            {"active_page": "review", "error": "검토 결과를 찾을 수 없습니다."},
            status_code=404,
        )

    detail["data_type_nm"] = DATA_TYPE_LABELS.get(detail["data_type"], detail["data_type"])
    detail["final_result_nm"] = RESULT_LABELS.get(detail["final_result"], detail["final_result"])
    for d in detail.get("details", []):
        d["extracted_val"] = checker.humanize_extracted_val(d)
    risk_items = [d for d in detail.get("details", []) if d.get("judge_result") == "F"]
    warn_items = [d for d in detail.get("details", []) if d.get("judge_result") == "W"]
    profile_summary = _format_profile_summary(detail.get("case_profile"))

    return templates.TemplateResponse(
        request,
        "result.html",
        {
            "active_page": "review",
            "review": detail,
            "risk_items": risk_items,
            "warn_items": warn_items,
            "profile_summary": profile_summary,
        },
    )


@router.get("/{review_id}/api/detail")
async def api_review_detail(review_id: int):
    """결과 상세 JSON"""
    detail = safe_logger.get_review_detail(review_id)
    if not detail:
        return {"error": "검토 결과를 찾을 수 없습니다."}
    for k, v in detail.items():
        if hasattr(v, "isoformat"):
            detail[k] = v.isoformat()
    return detail


@router.get("/{review_id}/report")
async def download_report(review_id: int):
    """HTML 보고서 다운로드"""
    report_path = reporter.generate_html_report(review_id)
    return FileResponse(
        report_path,
        media_type="text/html",
        filename=Path(report_path).name,
    )
