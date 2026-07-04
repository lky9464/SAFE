"""
2025년 충청남도 지방보조금 감사 사례집 기반 체크리스트 항목
docs/충청남도_감사사례_체크리스트.md
"""

from typing import Any

# 자료유형별 추가 시드 항목 (기존 SEED_ITEMS에 병합)
CHUNGNAM_AUDIT_ITEMS: dict[str, list[dict[str, str]]] = {
    "1": [
        {
            "category": "예산편성",
            "item_content": "자치단체경상보조 예산을 자본형성(시설·인테리어 등) 사업에 편성·집행하지 않았는가?",
            "judge_criteria": "자본적 vs 경상적 지출 구분",
            "law_ref": "지방보조금 관리기준, 예산편성 운영기준",
            "risk_level": "H",
            "case_ref": "사례01·자본/경상혼용",
        },
        {
            "category": "예산편성",
            "item_content": "사회복지시설법정운영비보조(307-10)에 자산취득·경상사업비를 편성하지 않았는가?",
            "judge_criteria": "운영비 외 비목 편성 금지",
            "law_ref": "충남 지방보조금 관리지침",
            "risk_level": "H",
            "case_ref": "사례02·운영비보조남용",
        },
        {
            "category": "예산편성",
            "item_content": "법정 공기관이 아닌 기관에 「공기관 등 경상적 위탁사업비」를 편성하지 않았는가?",
            "judge_criteria": "공기관 요건·위탁 근거",
            "law_ref": "예산편성 운영기준 별표11",
            "risk_level": "H",
            "case_ref": "사례03·위탁사업비",
        },
        {
            "category": "예산편성",
            "item_content": "총사업비 3억 원 이상 행사·축제 사업에 지방재정 투자심사를 실시하였는가?",
            "judge_criteria": "3억~300억 투자심사",
            "law_ref": "지방재정법 제37조",
            "risk_level": "H",
            "case_ref": "사례04·투자심사",
        },
        {
            "category": "예산편성",
            "item_content": "조례·법령 근거 없이 기타보상금(301-14)으로 체류비·식비 등을 편성하지 않았는가?",
            "judge_criteria": "보상금 편성 근거",
            "law_ref": "예산편성 운영기준",
            "risk_level": "H",
            "case_ref": "사례05·기타보상금",
        },
        {
            "category": "예산편성",
            "item_content": "사업별 목적·용도·추진계획을 사전에 구체화하고 포괄 예산 배정을 하지 않았는가?",
            "judge_criteria": "목적·계획 구체성",
            "law_ref": "지방재정법 제38조",
            "risk_level": "M",
            "case_ref": "사례06·목적미구체",
        },
        {
            "category": "교부결정",
            "item_content": "민간 주관 행사비를 민간경상보조(307-02)가 아닌 민간행사사업보조(307-04)로 편성하였는가?",
            "judge_criteria": "307-02 vs 307-04",
            "law_ref": "예산편성 운영기준",
            "risk_level": "M",
            "case_ref": "사례07·행사보조구분",
        },
        {
            "category": "교부결정",
            "item_content": "민간보조 5억 원 이상 결정 시 충남 일상감사 규칙에 따른 감사위원회 검토를 하였는가?",
            "judge_criteria": "5억 이상 일상감사",
            "law_ref": "충남 일상감사 규칙 제3조",
            "risk_level": "H",
            "case_ref": "사례08·일상감사",
        },
    ],
    "2": [
        {
            "category": "용도·변경",
            "item_content": "교부결정 목적과 다른 용도로 보조금을 집행하지 않았는가? (감사사례 05)",
            "judge_criteria": "목적 외 사용",
            "law_ref": "지방자치단체 보조금 관리에 관한 법률 제14조",
            "risk_level": "H",
            "case_ref": "사례05·용도외",
        },
        {
            "category": "계약·지출",
            "item_content": "지방계약법에 따른 계약절차를 준수하였으며 수의계약 사유가 문서화되었는가? (사례 07)",
            "judge_criteria": "계약절차·수의계약",
            "law_ref": "지방계약법",
            "risk_level": "H",
            "case_ref": "사례07·계약위반",
        },
        {
            "category": "용도·변경",
            "item_content": "1사업 1통장 원칙과 보조금 전용카드 집행을 준수하였는가?",
            "judge_criteria": "전용통장·전용카드",
            "law_ref": "충남 업무운영지침",
            "risk_level": "H",
            "case_ref": "사례09·전용계좌",
        },
        {
            "category": "자부담",
            "item_content": "자부담을 보조금보다 우선 집행하였으며 미확보 시 교부를 제한하였는가?",
            "judge_criteria": "자부담 우선집행",
            "law_ref": "충남 업무운영지침 제15조",
            "risk_level": "H",
            "case_ref": "사례10·자부담",
        },
        {
            "category": "집행기간",
            "item_content": "교부결정 전 집행을 보조금으로 보전(소급 인정)하지 않았는가?",
            "judge_criteria": "사전집행 금지",
            "law_ref": "충남 업무운영지침 제12조",
            "risk_level": "H",
            "case_ref": "사례11·소급집행",
        },
        {
            "category": "회계처리",
            "item_content": "보조금을 일괄 인출하여 사후 정산하는 형태의 회계처리를 하지 않았는가?",
            "judge_criteria": "일괄인출 금지",
            "law_ref": "충남 업무운영지침 제11조",
            "risk_level": "H",
            "case_ref": "사례12·일괄인출",
        },
        {
            "category": "집행항목",
            "item_content": "단체운영비(사무실임차료·상근인건비 등)를 보조금으로 집행하지 않았는가?",
            "judge_criteria": "운영비 보조금 집행 금지",
            "law_ref": "충남 지방보조금 관리지침",
            "risk_level": "H",
            "case_ref": "사례13·운영비",
        },
        {
            "category": "이월·잔액",
            "item_content": "보조금 이월 승인 및 집행잔액·이자 반납을 적정하게 처리하였는가?",
            "judge_criteria": "이월·반납",
            "law_ref": "지방자치단체 보조금 관리에 관한 법률",
            "risk_level": "H",
            "case_ref": "사례14·잔액이자",
        },
    ],
    "3": [
        {
            "category": "원천징수",
            "item_content": "강사료·원고료 등에 대해 소득세 원천징수(3.3%/8.8%)를 이행하였는가? (사례 15)",
            "judge_criteria": "원천징수 이행",
            "law_ref": "소득세법",
            "risk_level": "H",
            "case_ref": "사례15·원천징수",
        },
        {
            "category": "증빙 적정성",
            "item_content": "인건비·사무실 임차료 지급이 근로계약서·임대차 계약 및 실제 근무와 일치하는가? (사례 19)",
            "judge_criteria": "인건비·임차 증빙",
            "law_ref": "보조금 관리지침",
            "risk_level": "H",
            "case_ref": "사례19·인건비",
        },
        {
            "category": "증빙 완전성",
            "item_content": "지출증빙(세금계산서·영수증·카드전표·계약서)이 빠짐없이 구비되어 있는가?",
            "judge_criteria": "증빙 완비",
            "law_ref": "충남 업무운영지침",
            "risk_level": "H",
            "case_ref": "사례16·증빙미비",
        },
        {
            "category": "허위 증빙",
            "item_content": "허위·변조 근로계약서 또는 근무일지로 인건비를 청구하지 않았는가?",
            "judge_criteria": "근로계약·일지 대조",
            "law_ref": "지방보조금 관리기준",
            "risk_level": "H",
            "case_ref": "사례17·허위계약",
        },
        {
            "category": "중복 증빙",
            "item_content": "동일 영수증·증빙을 타 기관·타 사업에 중복 제출하여 이중수령하지 않았는가?",
            "judge_criteria": "이중수령·중복증빙",
            "law_ref": "지방자치단체 보조금 관리에 관한 법률 제6조",
            "risk_level": "H",
            "case_ref": "사례18·이중수령",
        },
        {
            "category": "중복 증빙",
            "item_content": "타 기관(해설사·강사 활동비 등)과 근무일이 중복되는 인건비를 이중 지급하지 않았는가?",
            "judge_criteria": "인건비 이중지급",
            "law_ref": "보조금 관리지침",
            "risk_level": "H",
            "case_ref": "사례19·인건비중복",
        },
        {
            "category": "증빙 유효성",
            "item_content": "전자세금계산서·보조금 전용카드 결제 원칙을 준수하였는가?",
            "judge_criteria": "전자증빙·카드",
            "law_ref": "충남 업무운영지침 제11조",
            "risk_level": "M",
            "case_ref": "사례20·전자증빙",
        },
        {
            "category": "증빙 대조",
            "item_content": "계좌 거래내역과 지출결의서(건별 일자·금액)가 일치하는가?",
            "judge_criteria": "계좌-결의서 대조",
            "law_ref": "지방보조금 관리기준",
            "risk_level": "H",
            "case_ref": "사례21·대조",
        },
    ],
    "4": [
        {
            "category": "정산검사",
            "item_content": "실적보고서를 토대로 법령·교부조건 적합성을 심사하고 부적정 시 시정명령을 내렸는가?",
            "judge_criteria": "실적보고 심사·시정",
            "law_ref": "지방자치단체 보조금 관리에 관한 법률 제19·30조",
            "risk_level": "H",
            "case_ref": "사례22·심사소홀",
        },
        {
            "category": "정산검사",
            "item_content": "정산 시 자부담 집행 비율을 재산정하고 미이행분을 환수 조치하였는가?",
            "judge_criteria": "자부담 비율 정산",
            "law_ref": "충남 업무운영지침 제15조",
            "risk_level": "H",
            "case_ref": "사례23·자부담정산",
        },
        {
            "category": "정산검사",
            "item_content": "유사·중복 사업 수혜 및 이중수령 여부를 정산 검사 시 확인하였는가?",
            "judge_criteria": "중복수혜 검증",
            "law_ref": "지방보조금통합관리망",
            "risk_level": "H",
            "case_ref": "사례24·이중수령",
        },
        {
            "category": "회계감사",
            "item_content": "교부 총액 3억 원 이상 시 감사인의 실적보고서 검증을 받았는가?",
            "judge_criteria": "3억 이상 검증",
            "law_ref": "지방자치단체 보조금 관리에 관한 법률 제17조",
            "risk_level": "H",
            "case_ref": "사례25·감사인",
        },
        {
            "category": "회계감사",
            "item_content": "교부 총액 10억 원 이상 시 외부 회계감사 보고서를 제출·확인하였는가?",
            "judge_criteria": "10억 이상 외부감사",
            "law_ref": "지방자치단체 보조금 관리에 관한 법률 제18조",
            "risk_level": "H",
            "case_ref": "사례26·외부감사",
        },
        {
            "category": "정산확정",
            "item_content": "집행잔액 및 발생이자를 계산하여 반납 조치하였는가?",
            "judge_criteria": "잔액·이자 반납",
            "law_ref": "지방자치단체 보조금 관리에 관한 법률 제31조",
            "risk_level": "H",
            "case_ref": "사례27·반납",
        },
        {
            "category": "제재",
            "item_content": "부정수급 확인 시 명단공표·제재부가금 부과를 검토하였는가?",
            "judge_criteria": "명단공표·제재부가금",
            "law_ref": "지방자치단체 보조금 관리에 관한 법률 제30·35조",
            "risk_level": "H",
            "case_ref": "사례28·제재",
        },
        {
            "category": "정산기한",
            "item_content": "실적보고서 제출 지연 시 규정에 따른 삭감·시정 조치를 하였는가?",
            "judge_criteria": "지연 제출 삭감",
            "law_ref": "지방자치단체 보조금 관리에 관한 법률 시행령 제20조",
            "risk_level": "M",
            "case_ref": "사례29·지연삭감",
        },
    ],
}


def merge_chungnam_items(
    base_items: list[dict[str, str]],
    data_type: str,
) -> list[dict[str, str]]:
    """기존 시드 항목에 충남 감사사례 항목 병합 (item_no 재부여)"""
    extra = CHUNGNAM_AUDIT_ITEMS.get(data_type, [])
    merged = [dict(item) for item in base_items]
    start_no = len(merged) + 1
    for idx, raw in enumerate(extra):
        criteria = raw["judge_criteria"]
        case_ref = raw.get("case_ref", "")
        if case_ref:
            criteria = f"{criteria} (출처: 충남감사사례 {case_ref})"
        merged.append({
            "item_no": start_no + idx,
            "category": raw["category"],
            "item_content": raw["item_content"],
            "judge_criteria": criteria,
            "law_ref": raw["law_ref"],
            "risk_level": raw["risk_level"],
        })
    return merged
