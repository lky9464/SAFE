# 감사사례집(배포용) — 세종시체육회 회원종목단체 (보조금·회계 관련)
# docs/감사사례집_체육단체_체크리스트.md

SPORTS_AUDIT_ITEMS: dict[str, list[dict[str, str]]] = {
    "1": [
        {"category": "교부결정", "item_content": "보조금 교부결정 통보에 따른 사업비 사용 계획이 사업계획서와 일치하는가?",
         "judge_criteria": "교부조건·사업계획 일치", "law_ref": "지방자치단체 보조금 관리에 관한 법률", "risk_level": "M", "case_ref": "대회운영예산"},
        {"category": "단체 운영", "item_content": "보조사업 수행 단체의 총회·이사회가 규정에 따라 적법하게 운영되었는가?",
         "judge_criteria": "총회·이사회 운영", "law_ref": "민간단체 운영 규정", "risk_level": "M", "case_ref": "회원종목단체운영"},
    ],
    "2": [
        {"category": "집행항목", "item_content": "보조금을 개인적 용도(훈련비·용품비 등)로 사용하지 않았는가?",
         "judge_criteria": "목적 외·개인용도 금지", "law_ref": "지방자치단체 보조금 관리에 관한 법률 제13조", "risk_level": "H", "case_ref": "훈련비횡령"},
        {"category": "집행항목", "item_content": "대회 임차비 등 용역비가 적정 기간·단가로 집행되었는가?",
         "judge_criteria": "임차비 적정성", "law_ref": "지방보조금 관리기준", "risk_level": "H", "case_ref": "임차비과다"},
        {"category": "계약·지출", "item_content": "수의계약 추진 시 비교견적서 등 절차를 준수하였는가?",
         "judge_criteria": "수의계약 절차", "law_ref": "지방계약법", "risk_level": "H", "case_ref": "회계분야"},
        {"category": "집행항목", "item_content": "자체예산(참가비 등)과 보조금을 구분하여 집행·관리하였는가?",
         "judge_criteria": "자체예산·보조금 구분", "law_ref": "지방보조금 관리기준", "risk_level": "H", "case_ref": "자체예산"},
    ],
    "3": [
        {"category": "증빙 완전성", "item_content": "보조금 회계관련 서류(결의서·카드전표·세금계산서)를 5년간 보관하고 있는가?",
         "judge_criteria": "증빙 5년 보관", "law_ref": "지방자치단체 회계관리 훈령 제112조", "risk_level": "H", "case_ref": "회계서류보관"},
        {"category": "증빙 완전성", "item_content": "자체예산 지출 시 내부결재·지출결의서·입금증 등 증빙이 구비되어 있는가?",
         "judge_criteria": "자체예산 증빙", "law_ref": "지방자치단체 회계관리 훈령", "risk_level": "H", "case_ref": "자체예산증빙"},
        {"category": "증빙 완전성", "item_content": "세입·세출 시 수입·지출결의서와 카드전표·이체확인증을 사업별 편철하였는가?",
         "judge_criteria": "결의서·전표 편철", "law_ref": "지방보조금 관리기준", "risk_level": "H", "case_ref": "회계서류"},
        {"category": "증빙 적정성", "item_content": "예산과목을 구분하여 세입·세출을 관리하고 있는가?",
         "judge_criteria": "예산과목 구분", "law_ref": "지방자치단체 회계관리 훈령", "risk_level": "M", "case_ref": "예산과목"},
    ],
    "4": [
        {"category": "정산검사", "item_content": "보조금 목적 외 사용 및 부당 집행 시 환수·징계 조치를 검토하였는가?",
         "judge_criteria": "부당집행 환수", "law_ref": "지방자치단체 보조금 관리에 관한 법률 제34조", "risk_level": "H", "case_ref": "대회보조금"},
        {"category": "정산검사", "item_content": "과다 집행·부적정 사용 비용에 대해 환수 조치를 하였는가?",
         "judge_criteria": "과다집행 환수", "law_ref": "지방자치단체 보조금 관리에 관한 법률", "risk_level": "H", "case_ref": "임차비환수"},
        {"category": "정산기한", "item_content": "회계연도 종료 후 정기총회에서 결산·감사보고를 이행하였는가?",
         "judge_criteria": "결산·총회 보고", "law_ref": "민간단체 운영 규정", "risk_level": "M", "case_ref": "정기총회"},
        {"category": "제재", "item_content": "위법·부당 사실 확인 시 징계·시정·고발 조치를 검토하였는가?",
         "judge_criteria": "징계·시정", "law_ref": "지방자치단체 보조금 관리에 관한 법률", "risk_level": "H", "case_ref": "체육회감사"},
    ],
}
