"""
체크리스트 비교 엔진
파싱 결과와 체크리스트를 유사도·규칙 기반으로 비교하여 판정
"""

import json
import logging
import pickle
import re
from pathlib import Path
from typing import Any

import faiss
import numpy as np

import config
import checklist_db
from cross_rules import apply_cross_item_rule
from inspection_checklist import enrich_review_item
from na_engine import CaseProfile, apply_cross_doc_w, evaluate_na

logger = logging.getLogger(__name__)

# 판정 임계값
JUDGE_THRESHOLD: dict[str, float] = {
    "PASS": 0.65,
    "WARN": 0.45,
}

# 규칙 기반 판정 정의
RULE_BASED_CHECKS: dict[str, list[dict[str, Any]]] = {
    "1": [
        {
            "item": "인건비 비율",
            "field": "labor_ratio",
            "rule": "<=",
            "threshold": 70.0,
            "warn_threshold": 75.0,
            "law_ref": "지방보조금 관리기준",
            "risk_level": "H",
        },
        {
            "item": "사업기간 명시",
            "field": "business_period",
            "rule": "not_empty",
            "law_ref": "지방자치단체 보조금 관리에 관한 법률",
            "risk_level": "M",
        },
        {
            "item": "정산계획 명시",
            "field": "settlement_plan",
            "rule": "not_empty",
            "law_ref": "지방자치단체 보조금 관리에 관한 법률",
            "risk_level": "H",
        },
    ],
    "2": [
        {
            "item": "집행률",
            "field": "execution_rate",
            "rule": ">=",
            "threshold": 0.0,
            "warn_threshold": 50.0,
            "law_ref": "지방보조금 관리기준",
            "risk_level": "M",
        },
        {
            "item": "예산 외 집행 항목",
            "field": "out_of_budget_items",
            "rule": "empty",
            "law_ref": "지방자치단체 보조금 관리에 관한 법률",
            "risk_level": "H",
        },
    ],
    "3": [
        {
            "item": "중복 증빙",
            "field": "duplicate_detected",
            "rule": "empty",
            "law_ref": "지방보조금 관리기준",
            "risk_level": "H",
        },
    ],
    "4": [
        {
            "item": "반납금 계획 명시",
            "field": "refund_plan",
            "rule": "not_empty",
            "law_ref": "지방자치단체 보조금 관리에 관한 법률",
            "risk_level": "H",
        },
        {
            "item": "정산기한 명시",
            "field": "settlement_deadline",
            "rule": "not_empty",
            "law_ref": "지방자치단체 보조금 관리에 관한 법률",
            "risk_level": "H",
        },
    ],
}

_GRADE_ORDER = {"P": 0, "W": 1, "F": 2}

# FAISS 인덱스 캐시 (동일 체크리스트 재사용)
_faiss_cache: dict[int, tuple[Any, np.ndarray]] = {}

# 싱글톤 임베딩 모델
_embedding_model = None


def load_embedding_model():
    """한국어 임베딩 모델 로드 (최초 1회, 로컬 캐시)"""
    global _embedding_model
    if _embedding_model is None:
        try:
            from sentence_transformers import SentenceTransformer

            logger.info("임베딩 모델 로드 중: %s", config.EMBEDDING_MODEL)
            _embedding_model = SentenceTransformer(config.EMBEDDING_MODEL)
            logger.info("임베딩 모델 로드 완료")
        except Exception as exc:
            logger.error("임베딩 모델 로드 실패: %s", exc)
            raise RuntimeError(f"임베딩 모델 로드에 실패했습니다: {exc}") from exc
    return _embedding_model


def calculate_similarity(text1: str, text2: str) -> float:
    """두 텍스트 유사도 점수 계산 (0~1, 코사인 유사도)"""
    if not text1.strip() or not text2.strip():
        return 0.0

    model = load_embedding_model()
    embeddings = model.encode([text1, text2], normalize_embeddings=True)
    similarity = float(np.dot(embeddings[0], embeddings[1]))
    return round(max(min(similarity, 1.0), 0.0), 4)


def _item_text(item: dict[str, Any]) -> str:
    """체크리스트 항목 텍스트 조합"""
    return f"{item.get('item_content', '')} {item.get('judge_criteria', '')}".strip()


def _index_paths(checklist_id: int) -> tuple[Path, Path]:
    """FAISS 인덱스·메타데이터 경로"""
    base = Path(config.FAISS_INDEX_DIR)
    return base / f"checklist_{checklist_id}.index", base / f"checklist_{checklist_id}.meta"


def build_faiss_index(
    checklist_items: list[dict[str, Any]],
    checklist_id: int | None = None,
) -> tuple[Any, np.ndarray]:
    """
    체크리스트 항목으로 FAISS 인덱스 생성 및 파일 저장.

    Returns:
        (faiss_index, embeddings ndarray)
    """
    if not checklist_items:
        raise ValueError("체크리스트 항목이 비어 있습니다.")

    config.ensure_directories()
    model = load_embedding_model()
    texts = [_item_text(item) for item in checklist_items]
    embeddings = model.encode(texts, normalize_embeddings=True)
    embeddings = np.array(embeddings, dtype="float32")

    dimension = embeddings.shape[1]
    index = faiss.IndexFlatIP(dimension)
    index.add(embeddings)

    if checklist_id is not None:
        index_path, meta_path = _index_paths(checklist_id)
        faiss.write_index(index, str(index_path))
        with open(meta_path, "wb") as f:
            pickle.dump({"items": checklist_items, "texts": texts}, f)
        logger.info(
            "FAISS 인덱스 저장 — checklist_id=%d, 항목=%d, 차원=%d",
            checklist_id,
            len(checklist_items),
            dimension,
        )

    return index, embeddings


def _load_faiss_index(checklist_id: int, checklist_items: list[dict[str, Any]]) -> tuple[Any, np.ndarray]:
    """저장된 FAISS 인덱스 로드 또는 신규 생성 (메모리 캐시 우선)"""
    if checklist_id in _faiss_cache:
        cached_items_len = _faiss_cache[checklist_id][0].ntotal
        if cached_items_len == len(checklist_items):
            logger.info("FAISS 인덱스 캐시 사용 — checklist_id=%d", checklist_id)
            return _faiss_cache[checklist_id]

    index_path, meta_path = _index_paths(checklist_id)

    if index_path.is_file() and meta_path.is_file():
        try:
            index = faiss.read_index(str(index_path))
            with open(meta_path, "rb") as f:
                meta = pickle.load(f)
            if len(meta.get("items", [])) == len(checklist_items):
                model = load_embedding_model()
                texts = [_item_text(item) for item in checklist_items]
                embeddings = model.encode(texts, normalize_embeddings=True)
                embeddings = np.array(embeddings, dtype="float32")
                logger.info("FAISS 인덱스 로드 — checklist_id=%d", checklist_id)
                _faiss_cache[checklist_id] = (index, embeddings)
                return index, embeddings
        except Exception as exc:
            logger.warning("FAISS 인덱스 로드 실패, 재생성: %s", exc)

    result = build_faiss_index(checklist_items, checklist_id)
    _faiss_cache[checklist_id] = result
    return result


def _parsed_data_to_text(parsed_data: dict[str, Any]) -> str:
    """파싱 결과를 비교용 텍스트로 변환"""
    parts: list[str] = []
    for key, value in parsed_data.items():
        if isinstance(value, dict):
            parts.append(f"{key}: {json.dumps(value, ensure_ascii=False)}")
        elif isinstance(value, list):
            parts.append(f"{key}: {json.dumps(value, ensure_ascii=False)}")
        else:
            parts.append(f"{key}: {value}")
    return "\n".join(parts)


def _similarity_to_grade(similarity: float) -> str:
    """유사도 → 판정 등급"""
    if similarity >= JUDGE_THRESHOLD["PASS"]:
        return "P"
    if similarity >= JUDGE_THRESHOLD["WARN"]:
        return "W"
    return "F"


def judge_item(
    parsed_value: str,
    checklist_item: dict[str, Any],
    similarity: float | None = None,
) -> dict[str, Any]:
    """단일 항목 판정 (적합/주의/부적합)"""
    if similarity is None:
        item_text = _item_text(checklist_item)
        similarity = calculate_similarity(parsed_value, item_text)

    grade = _similarity_to_grade(similarity)
    grade_label = {"P": "적합", "W": "주의", "F": "부적합"}[grade]

    return {
        "judge_result": grade,
        "judge_reason": (
            f"{checklist_item.get('item_content', '')} — {grade_label} "
            f"(유사도: {similarity:.2f})"
        ),
        "similarity": similarity,
        "check_method": "similarity",
    }


def _worse_grade(grade_a: str, grade_b: str) -> str:
    """두 등급 중 낮은(더 나쁜) 등급 반환"""
    return grade_a if _GRADE_ORDER[grade_a] >= _GRADE_ORDER[grade_b] else grade_b


def _evaluate_rule(rule: dict[str, Any], parsed_data: dict[str, Any]) -> dict[str, Any]:
    """단일 규칙 판정"""
    field = rule["field"]
    value = parsed_data.get(field)
    rule_type = rule["rule"]
    grade = "P"
    reason = ""

    if rule_type == "not_empty":
        if isinstance(value, dict):
            is_empty = not any(v for v in value.values() if v)
        else:
            is_empty = not value or str(value).strip() == ""
        grade = "F" if is_empty else "P"
        reason = f"{rule['item']}: {'미기재' if is_empty else '기재 확인'}"

    elif rule_type == "empty":
        is_empty = not value or (isinstance(value, list) and len(value) == 0)
        grade = "P" if is_empty else "F"
        reason = f"{rule['item']}: {'없음(적합)' if is_empty else '발견(부적합)'}"

    elif rule_type == "<=":
        num_val = float(value) if value is not None else 999.0
        threshold = rule["threshold"]
        warn_threshold = rule.get("warn_threshold", threshold)
        if num_val <= threshold:
            grade = "P"
            reason = f"{rule['item']}: {num_val}% (기준 {threshold}% 이하 → 적합)"
        elif num_val <= warn_threshold:
            grade = "W"
            reason = f"{rule['item']}: {num_val}% (주의 구간 {threshold}~{warn_threshold}%)"
        else:
            grade = "F"
            reason = f"{rule['item']}: {num_val}% (기준 {warn_threshold}% 초과 → 부적합)"

    elif rule_type == ">=":
        num_val = float(value) if value is not None else 0.0
        warn_threshold = rule.get("warn_threshold", 50.0)
        if num_val < warn_threshold:
            grade = "W"
            reason = f"{rule['item']}: {num_val}% ({warn_threshold}% 미만 → 주의)"
        else:
            grade = "P"
            reason = f"{rule['item']}: {num_val}% (적합)"

    grade_label = {"P": "적합", "W": "주의", "F": "부적합"}[grade]
    return {
        "item": rule["item"],
        "field": field,
        "judge_result": grade,
        "judge_reason": f"{reason} ({grade_label})",
        "law_ref": rule.get("law_ref", ""),
        "risk_level": rule.get("risk_level", "M"),
        "extracted_val": str(value) if value is not None else "",
        "similarity": None,
        "check_method": "rule_based",
    }


def apply_rule_based_check(
    parsed_data: dict[str, Any],
    data_type: str,
) -> list[dict[str, Any]]:
    """수치·필수항목 기반 규칙 판정"""
    rules = RULE_BASED_CHECKS.get(data_type, [])
    results = []
    for rule in rules:
        results.append(_evaluate_rule(rule, parsed_data))

    if data_type == "4":
        results.extend(check_execution_date(parsed_data))
        results.extend(check_item_execution_rate(parsed_data))
        remaining_check = check_remaining_reason(parsed_data)
        if remaining_check:
            results.append(remaining_check)

    logger.info("규칙 기반 판정 완료 — 유형 %s, %d건", data_type, len(results))
    return results


def _normalize_date(date_str: str) -> str | None:
    """다양한 날짜 형식을 YYYY-MM-DD로 정규화"""
    if not date_str:
        return None
    import re as _re

    match = _re.search(
        r"(\d{4})[.\-/년\s]*(\d{1,2})[.\-/월\s]*(\d{1,2})",
        date_str.strip(),
    )
    if match:
        y, m, d = int(match.group(1)), int(match.group(2)), int(match.group(3))
        return f"{y:04d}-{m:02d}-{d:02d}"
    return None


def check_execution_date(parsed_data: dict[str, Any]) -> list[dict[str, Any]]:
    """집행일자가 사업기간 외인지 확인"""
    business_period = parsed_data.get("business_period") or parsed_data.get("settlement_period", {})
    start_raw = business_period.get("start", "")
    end_raw = business_period.get("end", "")
    start = _normalize_date(start_raw)
    end = _normalize_date(end_raw)

    execution_items = parsed_data.get("execution_items", [])
    if not start or not end or not execution_items:
        return []

    violations: list[dict[str, Any]] = []
    checked: set[str] = set()

    for item in execution_items:
        exec_date = item.get("date") or _normalize_date(item.get("raw_date", ""))
        if not exec_date or exec_date in checked:
            continue
        checked.add(exec_date)

        if exec_date < start or exec_date > end:
            violations.append({
                "item": "사업기간 내 집행",
                "field": "execution_items",
                "judge_result": "F",
                "judge_reason": (
                    f"사업기간({start_raw}~{end_raw}) 외 집행일({exec_date}) 발견 "
                    f"— {item.get('item_name', '')} {item.get('amount', 0):,}원"
                ),
                "law_ref": "지방자치단체 보조금 관리에 관한 법률",
                "risk_level": "H",
                "extracted_val": exec_date,
                "similarity": None,
                "check_method": "rule_based",
            })

    if violations:
        return violations

    return [{
        "item": "사업기간 내 집행",
        "field": "execution_items",
        "judge_result": "P",
        "judge_reason": f"사업기간({start_raw}~{end_raw}) 내 집행 확인",
        "law_ref": "지방자치단체 보조금 관리에 관한 법률",
        "risk_level": "H",
        "extracted_val": f"{len(execution_items)}건",
        "similarity": None,
        "check_method": "rule_based",
    }]


def check_item_execution_rate(parsed_data: dict[str, Any]) -> list[dict[str, Any]]:
    """단일 항목 집행률 50% 미만 시 주의 판정"""
    results: list[dict[str, Any]] = []
    for item in parsed_data.get("settlement_items", []):
        budget = int(item.get("budget", 0) or 0)
        executed = int(item.get("executed", 0) or 0)
        if budget <= 0:
            continue
        rate = round(executed / budget * 100, 1)
        if rate < 50:
            results.append({
                "item": f"{item.get('category', '')} 집행률",
                "field": "settlement_items",
                "judge_result": "W",
                "judge_reason": (
                    f"{item.get('category', '')}: 계획 {budget:,}원 대비 "
                    f"집행 {executed:,}원 ({rate}%) — 50% 미만 주의"
                ),
                "law_ref": "지방보조금 관리기준",
                "risk_level": "M",
                "extracted_val": f"{rate}%",
                "similarity": None,
                "check_method": "rule_based",
            })
    return results


def check_remaining_reason(parsed_data: dict[str, Any]) -> dict[str, Any] | None:
    """집행잔액 발생사유 기재 여부 확인"""
    remaining = int(parsed_data.get("remaining_amount", 0) or 0)
    reason = str(parsed_data.get("remaining_reason", "")).strip()

    if remaining <= 0:
        return None

    if reason:
        return {
            "item": "잔액 발생사유 기재",
            "field": "remaining_reason",
            "judge_result": "P",
            "judge_reason": f"잔액 발생사유 기재 확인 — {reason}",
            "law_ref": "지방보조금 관리기준",
            "risk_level": "M",
            "extracted_val": reason,
            "similarity": None,
            "check_method": "rule_based",
        }

    return {
        "item": "잔액 발생사유 기재",
        "field": "remaining_reason",
        "judge_result": "W",
        "judge_reason": "집행잔액 발생했으나 사유 미기재",
        "law_ref": "지방보조금 관리기준",
        "risk_level": "M",
        "extracted_val": "",
        "similarity": None,
        "check_method": "rule_based",
    }


_DOC_MARKS = (
    ("has_plan", "①"),
    ("has_execution", "②"),
    ("has_proof", "③"),
    ("has_settlement", "④"),
)

_SECTION_HEADER_RE = re.compile(r"^===\s*(.+?)\s*===\s*$")
_SNIPPET_MAX = 70


def _profile_docs_label(profile: CaseProfile | None) -> str:
    if profile is None:
        return "제출 자료"
    marks = [mark for attr, mark in _DOC_MARKS if getattr(profile, attr, False)]
    return ",".join(marks) if marks else "없음"


def _snippet_source_text(parsed_data: dict[str, Any], doc_text: str) -> str:
    """발췌용 본문 — 사업 통합 시 combined_text 우선."""
    combined = parsed_data.get("combined_text")
    if isinstance(combined, str) and combined.strip():
        return combined
    return doc_text


def _chunk_document(
    doc_text: str,
    *,
    min_len: int = 15,
    max_len: int = 160,
    max_chunks: int = 100,
) -> list[tuple[str, str]]:
    """문서를 (출처, 구간) 목록으로 분할."""
    if not doc_text or not doc_text.strip():
        return []

    chunks: list[tuple[str, str]] = []
    current_source = "제출 자료"
    buffer: list[str] = []

    skip_prefixes = (
        "case_mode:",
        "uploaded_docs:",
        "combined_text:",
        "business_name:",
    )

    def _emit(text: str, source: str) -> None:
        text = re.sub(r"\s+", " ", text).strip()
        if len(text) < min_len:
            return
        if len(text) <= max_len:
            chunks.append((source, text))
            return
        # 긴 문단은 문장 단위로 나눔
        parts = re.split(r"(?<=[.。!?\n])\s+", text)
        buf = ""
        for part in parts:
            part = part.strip()
            if not part:
                continue
            candidate = f"{buf} {part}".strip() if buf else part
            if len(candidate) <= max_len:
                buf = candidate
            else:
                if buf:
                    chunks.append((source, buf))
                buf = part[:max_len]
        if buf and len(buf) >= min_len:
            chunks.append((source, buf))

    def flush() -> None:
        if not buffer:
            return
        _emit(" ".join(buffer), current_source)
        buffer.clear()

    for line in doc_text.splitlines():
        stripped = line.strip()
        header = _SECTION_HEADER_RE.match(stripped)
        if header:
            flush()
            current_source = header.group(1).strip()
            continue
        if not stripped:
            flush()
            continue
        if any(stripped.startswith(p) for p in skip_prefixes):
            continue
        # "key: value" 형태면 value 쪽만 사용
        if ": " in stripped and not stripped.startswith("http"):
            key, _, val = stripped.partition(": ")
            if key.isidentifier() or key.replace("_", "").isalnum():
                if val.startswith("{") or val.startswith("["):
                    continue
                stripped = val
        buffer.append(stripped)

    flush()

    if not chunks:
        compact = re.sub(r"\s+", " ", doc_text).strip()
        step = max(max_len // 2, 40)
        for i in range(0, len(compact), step):
            piece = compact[i : i + max_len]
            if len(piece) >= min_len:
                chunks.append(("제출 자료", piece))

    return chunks[:max_chunks]


def _find_best_snippets(
    doc_text: str,
    item_embeddings: np.ndarray,
    model: Any,
) -> list[tuple[str, str]]:
    """항목 임베딩과 가장 유사한 문서 구간 (출처, 발췌) 목록."""
    n_items = len(item_embeddings)
    empty = [("", "")] * n_items
    chunks = _chunk_document(doc_text)
    if not chunks:
        return empty

    chunk_texts = [text for _, text in chunks]
    chunk_emb = model.encode(chunk_texts, normalize_embeddings=True)
    chunk_emb = np.array(chunk_emb, dtype="float32")
    sims = np.dot(item_embeddings, chunk_emb.T)
    best_idx = sims.argmax(axis=1)
    return [chunks[int(i)] for i in best_idx]


def _shorten_snippet(text: str, max_len: int = _SNIPPET_MAX) -> str:
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) <= max_len:
        return text
    return text[: max_len - 1].rstrip() + "…"


def format_review_content(
    *,
    check_method: str,
    meta: dict[str, Any] | None = None,
    profile: CaseProfile | None = None,
    judge_reason: str = "",
    similarity: float | None = None,
    rule_extracted: str | None = None,
    snippet: str = "",
    snippet_source: str = "",
) -> str:
    """결과 화면 '검토내용' 열용 — 일반 사용자가 읽을 수 있는 요약."""
    meta = meta or {}
    reason = (judge_reason or "").strip()

    if check_method == "na_rule":
        return reason or "해당 없음 (점검 대상 아님)"

    if check_method == "cross_doc":
        docs = _profile_docs_label(profile)
        base = f"{reason} (제출: {docs})" if reason else f"교차 확인 필요 (제출: {docs})"
        if snippet:
            short = _shorten_snippet(snippet)
            src = f"[{snippet_source}] " if snippet_source else ""
            return f"{base} · 참고 {src}「{short}」"
        return base

    if check_method in ("rule_based", "cross_rule"):
        if rule_extracted not in (None, ""):
            return str(rule_extracted)
        return reason or "-"

    # similarity — 관련 구간 발췌 우선
    if snippet:
        short = _shorten_snippet(snippet)
        src = f"[{snippet_source}] " if snippet_source else ""
        bits = [f"{src}「{short}」"]
        if similarity is not None:
            bits.append(f"유사도 {similarity:.0%}")
        return " · ".join(bits)

    docs = _profile_docs_label(profile)
    bits = [f"제출 자료({docs})와 점검항목을 비교"]
    seomok = meta.get("seomok") or ""
    if seomok and seomok != "-":
        bits.append(f"관련 세목 {seomok}")
    if similarity is not None:
        bits.append(f"유사도 {similarity:.0%}")
    return " · ".join(bits)


def humanize_extracted_val(detail: dict[str, Any]) -> str:
    """
    저장된 extracted_val 을 화면용으로 정리.
    과거 검토(원문 덤프)도 읽기 쉬운 문구로 변환.
    """
    val = (detail.get("extracted_val") or "").strip()
    reason = (detail.get("judge_reason") or "").strip()
    grade = detail.get("judge_result")

    if grade == "A":
        return reason or val or "해당 없음 (점검 대상 아님)"

    # 이미 발췌 형식이면 그대로
    if "「" in val or (val.startswith("[") and "」" in val):
        return val

    # 파싱 원문·키=값 덤프로 보이는 경우
    head = val[:100]
    is_raw = (
        val.startswith("===")
        or val.startswith("business_name:")
        or "case_mode:" in head
        or "combined_text:" in head
        or (": {" in head and "\n" in val[:200])
    )
    if is_raw:
        bits = ["제출 자료와 점검항목을 비교"]
        sim = detail.get("similarity")
        if sim is not None:
            try:
                bits.append(f"유사도 {float(sim):.0%}")
            except (TypeError, ValueError):
                pass
        return " · ".join(bits)

    if not val:
        if reason and any(k in reason for k in ("미제출", "교차", "해당", "집행 없음")):
            return reason
        return "-"

    return val


def generate_summary(results: dict[str, Any]) -> dict[str, Any]:
    """전체 판정 결과 요약 생성 (N/A 항목은 집계에서 제외)"""
    details = results.get("details", [])
    applicable = [d for d in details if d.get("judge_result") != "A"]
    pass_count = sum(1 for d in applicable if d["judge_result"] == "P")
    warn_count = sum(1 for d in applicable if d["judge_result"] == "W")
    fail_count = sum(1 for d in applicable if d["judge_result"] == "F")
    na_count = sum(1 for d in details if d.get("judge_result") == "A")

    if fail_count > 0:
        final_result = "F"
    elif warn_count > 0:
        final_result = "W"
    elif applicable:
        final_result = "P"
    else:
        final_result = "W"

    risk_items = [d for d in applicable if d["judge_result"] == "F"]
    warn_items = [d for d in applicable if d["judge_result"] == "W"]

    summary = {
        **results,
        "total_items": len(details),
        "applicable_item_cnt": len(applicable),
        "pass_count": pass_count,
        "warn_count": warn_count,
        "fail_count": fail_count,
        "na_count": na_count,
        "final_result": final_result,
        "risk_items": risk_items,
        "warn_items": warn_items,
    }
    return summary


def compare_document(
    parsed_data: dict[str, Any],
    checklist_id: int,
    checklist_items: list[dict[str, Any]] | None = None,
    data_type: str | None = None,
    case_profile: CaseProfile | None = None,
) -> dict[str, Any]:
    """
    파싱 결과 vs 체크리스트 전체 비교.

    Args:
        parsed_data: parser.py 파싱 결과
        checklist_id: 체크리스트 ID
        checklist_items: DB 대신 직접 항목 지정 (테스트용)
        data_type: 자료유형 (미지정 시 체크리스트에서 추출)
        case_profile: 사업 프로필 (일제점검 N/A 판정용)

    Returns:
        비교·판정 결과 dict
    """
    if checklist_items is None:
        checklist = checklist_db.load_checklist_for_review(checklist_id)
        checklist_items = checklist["items"]
        data_type = data_type or str(checklist["data_type"])
    else:
        data_type = data_type or "1"

    # 일제점검 메타 병합
    enriched_items = [enrich_review_item(item) for item in checklist_items]

    profile = case_profile
    if profile is None and parsed_data.get("case_profile"):
        cp = parsed_data["case_profile"]
        if isinstance(cp, CaseProfile):
            profile = cp
        elif isinstance(cp, dict):
            profile = CaseProfile(**cp)

    doc_text = _parsed_data_to_text(parsed_data)
    _, embeddings = _load_faiss_index(checklist_id, enriched_items)

    model = load_embedding_model()
    doc_embedding = model.encode([doc_text], normalize_embeddings=True)
    doc_embedding = np.array(doc_embedding, dtype="float32")

    similarities = np.dot(embeddings, doc_embedding.T).flatten()

    # 항목별로 가장 관련 있는 제출 자료 구간 발췌
    snippet_text = _snippet_source_text(parsed_data, doc_text)
    best_snippets = _find_best_snippets(snippet_text, embeddings, model)

    details: list[dict[str, Any]] = []
    for idx, item in enumerate(enriched_items):
        meta = {k: item[k] for k in (
            "external_id", "seomok", "required_docs", "na_when", "integration_class",
        ) if k in item}
        snippet_source, snippet = best_snippets[idx] if idx < len(best_snippets) else ("", "")

        if profile and meta.get("external_id"):
            na_result, na_reason = evaluate_na(meta, profile)
            if na_result:
                reason = na_reason or ""
                details.append({
                    "item_id": item.get("item_id", idx + 1),
                    "item_no": item.get("item_no", idx + 1),
                    "category": item.get("category", ""),
                    "item_content": item.get("item_content", ""),
                    "extracted_val": format_review_content(
                        check_method="na_rule",
                        meta=meta,
                        profile=profile,
                        judge_reason=reason,
                    ),
                    "judge_result": na_result,
                    "judge_reason": reason,
                    "law_ref": item.get("law_ref", ""),
                    "similarity": None,
                    "check_method": "na_rule",
                })
                continue

            cross_w = apply_cross_doc_w(meta, profile)
            if cross_w:
                grade, reason = cross_w
                details.append({
                    "item_id": item.get("item_id", idx + 1),
                    "item_no": item.get("item_no", idx + 1),
                    "category": item.get("category", ""),
                    "item_content": item.get("item_content", ""),
                    "extracted_val": format_review_content(
                        check_method="cross_doc",
                        meta=meta,
                        profile=profile,
                        judge_reason=reason,
                        snippet=snippet,
                        snippet_source=snippet_source,
                    ),
                    "judge_result": grade,
                    "judge_reason": reason,
                    "law_ref": item.get("law_ref", ""),
                    "similarity": None,
                    "check_method": "cross_doc",
                })
                continue

            # JC-01, X07 등 수치·기간 교차 규칙
            cross_rule = apply_cross_item_rule(
                meta.get("external_id", ""),
                parsed_data,
                profile,
            )
            if cross_rule:
                details.append({
                    "item_id": item.get("item_id", idx + 1),
                    "item_no": item.get("item_no", idx + 1),
                    "category": item.get("category", ""),
                    "item_content": item.get("item_content", ""),
                    "extracted_val": format_review_content(
                        check_method="cross_rule",
                        judge_reason=cross_rule["judge_reason"],
                        rule_extracted=cross_rule.get("extracted_val"),
                    ),
                    "judge_result": cross_rule["judge_result"],
                    "judge_reason": cross_rule["judge_reason"],
                    "law_ref": cross_rule.get("law_ref", item.get("law_ref", "")),
                    "similarity": None,
                    "check_method": "cross_rule",
                })
                continue

        sim = float(similarities[idx])
        judgment = judge_item(doc_text, item, similarity=sim)
        details.append({
            "item_id": item.get("item_id", idx + 1),
            "item_no": item.get("item_no", idx + 1),
            "category": item.get("category", ""),
            "item_content": item.get("item_content", ""),
            "extracted_val": format_review_content(
                check_method="similarity",
                meta=meta,
                profile=profile,
                judge_reason=judgment["judge_reason"],
                similarity=judgment["similarity"],
                snippet=snippet,
                snippet_source=snippet_source,
            ),
            "judge_result": judgment["judge_result"],
            "judge_reason": judgment["judge_reason"],
            "law_ref": item.get("law_ref", ""),
            "similarity": judgment["similarity"],
            "check_method": "similarity",
        })

    # 규칙 기반 판정 병행
    rule_results = apply_rule_based_check(parsed_data, data_type)
    for rule_result in rule_results:
        details.append({
            "item_id": 0,
            "item_no": 0,
            "category": "규칙검증",
            "item_content": rule_result["item"],
            "extracted_val": format_review_content(
                check_method="rule_based",
                judge_reason=rule_result["judge_reason"],
                rule_extracted=rule_result["extracted_val"],
            ),
            "judge_result": rule_result["judge_result"],
            "judge_reason": rule_result["judge_reason"],
            "law_ref": rule_result["law_ref"],
            "similarity": rule_result.get("similarity"),
            "check_method": "rule_based",
        })

    result = {
        "review_id": None,
        "data_type": data_type,
        "checklist_id": checklist_id,
        "total_items": 0,
        "pass_count": 0,
        "warn_count": 0,
        "fail_count": 0,
        "final_result": "W",
        "details": details,
        "risk_items": [],
        "warn_items": [],
    }

    return generate_summary(result)
