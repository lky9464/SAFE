# 2024년 강북구 자치행정과 종합감사 (보조금 관리 분야)
# docs/자치행정과_종합감사_체크리스트.md

GANGBUK_AUDIT_ITEMS: dict[str, list[dict[str, str]]] = {
    "1": [
        {"category": "교부결정", "item_content": "연간 1,000만 원 이상 보조 시 지원표지판 설치 의무를 교부결정서에 통지하였는가?",
         "judge_criteria": "표지판 설치 통지", "law_ref": "강북구 지방보조금 지원표지판 조례", "risk_level": "M", "case_ref": "지적10"},
        {"category": "교부신청", "item_content": "보조금 관리지침(강사비·식비·홍보비 증빙 기준)을 교부 시 안내하였는가?",
         "judge_criteria": "관리지침 교육·안내", "law_ref": "지방보조금 관리기준", "risk_level": "M", "case_ref": "지적15"},
    ],
    "2": [
        {"category": "집행관리", "item_content": "보조금과 자부담금을 별도 계좌로 구분 관리하도록 지도하였는가?",
         "judge_criteria": "관리통장 통합관리", "law_ref": "지방보조금 관리기준 제10조", "risk_level": "H", "case_ref": "지적12"},
        {"category": "자부담", "item_content": "자부담금을 보조금보다 우선 집행하도록 하였는가?",
         "judge_criteria": "자부담 우선집행", "law_ref": "강북구 지방보조금 관리지침", "risk_level": "H", "case_ref": "지적13"},
        {"category": "집행항목", "item_content": "식비 지출 시 1인 기준액(8,000원)을 초과하지 않았는가?",
         "judge_criteria": "식비 기준액", "law_ref": "강북구 지방보조금 관리지침", "risk_level": "M", "case_ref": "지적15"},
        {"category": "지출방법", "item_content": "보조금 카드 사용 인센티브(포인트)를 개인이 아닌 행정용도로 사용하였는가?",
         "judge_criteria": "카드 인센티브 행정용", "law_ref": "지방자치단체 세출예산 집행기준", "risk_level": "M", "case_ref": "지적14"},
    ],
    "3": [
        {"category": "증빙 완전성", "item_content": "강사비 지출 시 강의 확인서·참석자 명단이 구비되어 있는가?",
         "judge_criteria": "강사비 증빙", "law_ref": "강북구 지방보조금 관리지침", "risk_level": "H", "case_ref": "지적15"},
        {"category": "증빙 완전성", "item_content": "물품구입 시 견적서·비교견적서·물품사진·배부계획서가 첨부되어 있는가?",
         "judge_criteria": "물품구입 증빙", "law_ref": "강북구 지방보조금 관리지침", "risk_level": "H", "case_ref": "지적15"},
        {"category": "원천징수", "item_content": "강사비 지급 시 소득세법에 따른 원천징수를 실시하였는가?",
         "judge_criteria": "강사료 원천징수", "law_ref": "소득세법", "risk_level": "H", "case_ref": "지적15"},
        {"category": "증빙 완전성", "item_content": "200만 원 이상 지출 시 표준계약서 및 상세 내역이 구비되어 있는가?",
         "judge_criteria": "표준계약서", "law_ref": "지방계약법", "risk_level": "H", "case_ref": "지적15"},
    ],
    "4": [
        {"category": "정산검사", "item_content": "실적보고서 미제출 보조사업자에 대해 보완·시정 조치 후 정산하였는가?",
         "judge_criteria": "미제출 시 시정", "law_ref": "지방자치단체 보조금 관리에 관한 법률 제17조", "risk_level": "H", "case_ref": "지적11"},
        {"category": "정산검사", "item_content": "자부담 집행 비율이 계획보다 낮을 때 총집행액 기준으로 재정산·환수하였는가?",
         "judge_criteria": "자부담 비율 재정산", "law_ref": "강북구 지방보조금 관리지침", "risk_level": "H", "case_ref": "지적13"},
        {"category": "정산검사", "item_content": "사업 완료 후 실적보고서 대 장부·증빙 대조 심사를 실시하였는가?",
         "judge_criteria": "정산 지도점검", "law_ref": "지방자치단체 보조금 관리에 관한 법률 제19조", "risk_level": "H", "case_ref": "지적15"},
        {"category": "정산검사", "item_content": "정산 검사 시 보완 요청 증빙이 미제출된 경우 정산을 보류·시정하였는가?",
         "judge_criteria": "증빙 보완 미이행", "law_ref": "지방보조금 관리기준", "risk_level": "H", "case_ref": "지적15"},
    ],
}
