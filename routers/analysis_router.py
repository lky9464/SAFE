"""
SAFE 추가분석 라우터
부적합·주의 항목에 대한 Gemini API 법령 해석 (내부자료 미포함)
"""

import logging

from fastapi import APIRouter, HTTPException
from google import genai
from pydantic import BaseModel, Field

import config

logger = logging.getLogger(__name__)
router = APIRouter()

DATA_TYPE_LABELS = {
    "1": "사업계획서",
    "2": "집행내역서",
    "3": "지출증빙자료",
    "4": "정산보고서",
}

RESULT_LABELS = {
    "P": "적합",
    "W": "주의",
    "F": "부적합",
}

_client: genai.Client | None = None


class AnalysisRequest(BaseModel):
    """추가분석 요청 — 내부자료 필드 없음"""

    category: str = Field(..., description="점검 분류")
    item_content: str = Field(..., description="점검항목 내용")
    judge_result: str = Field(..., description="판정 결과 P/W/F")
    data_type: str = Field(..., description="자료유형 1~4")


def build_analysis_prompt(
    category: str,
    item_content: str,
    judge_result: str,
    data_type: str,
) -> str:
    """
    내부자료 미포함 — 점검항목명과 분류만 사용
    """
    data_type_nm = DATA_TYPE_LABELS.get(data_type, "지방보조금 자료")
    result_nm = RESULT_LABELS.get(judge_result, judge_result)

    return f"""
지방보조금 {data_type_nm} 검토 항목에 대한 법령 해석을 요청합니다.

[점검 분류]: {category}
[점검 항목]: {item_content}
[판정 결과]: {result_nm}

아래 내용을 지방자치단체 보조금 관리에 관한 법률 및 관련 지침을 근거로 답변해주세요:

1. **법적 근거**: 해당 항목의 근거 법령 조항 (법률명·조항 번호 명시)
2. **기준치·판단 기준**: 구체적인 수치 기준이 있다면 명시 (예: 인건비 70% 이내)
3. **위반 시 제재**: 부적합 판정 시 적용될 수 있는 제재 내용
4. **조치 방법**: 담당자가 취해야 할 구체적인 조치 방법
5. **유사 감사 사례**: 감사원 또는 지방자치단체 감사에서 지적된 유사 사례 (알고 있는 경우)

답변은 한국어로, 담당 공무원이 바로 활용할 수 있도록 실무적으로 작성해주세요.
"""


def _get_client() -> genai.Client:
    global _client
    if _client is None:
        if not config.GEMINI_API_KEY:
            raise ValueError("GEMINI_API_KEY가 설정되지 않았습니다.")
        _client = genai.Client(api_key=config.GEMINI_API_KEY)
    return _client


@router.post("/api/analysis/ask")
async def ask_gemini_analysis(req: AnalysisRequest):
    """
    Gemini에게 법령 해석 추가분석 요청.
    내부자료(사업명·금액·단체명) 미포함 — 항목명·분류만 전송.
    """
    if req.data_type not in DATA_TYPE_LABELS:
        raise HTTPException(status_code=400, detail="유효하지 않은 자료유형입니다.")
    if req.judge_result not in RESULT_LABELS:
        raise HTTPException(status_code=400, detail="유효하지 않은 판정 결과입니다.")

    try:
        prompt = build_analysis_prompt(
            req.category,
            req.item_content,
            req.judge_result,
            req.data_type,
        )
        client = _get_client()
        response = client.models.generate_content(
            model=config.GEMINI_MODEL,
            contents=prompt,
        )
        analysis_text = (response.text or "").strip()
        if not analysis_text:
            raise ValueError("Gemini 응답이 비어 있습니다.")

        logger.info(
            "Gemini 추가분석 완료 — 유형:%s 분류:%s",
            req.data_type,
            req.category,
        )
        return {
            "success": True,
            "analysis": analysis_text,
            "item_content": req.item_content,
            "category": req.category,
        }
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Gemini 추가분석 실패: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc
