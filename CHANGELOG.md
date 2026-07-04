# Changelog

이 프로젝트의 주요 변경 이력입니다.

형식은 [Keep a Changelog](https://keepachangelog.com/ko/1.1.0/)를 참고합니다.

---

## [1.0.0] — 2026-07-04

**기준(직전 버전):** 로컬 `safe-main(20260630_back-up)`  
**대상:** GitHub [`lky9464/SAFE`](https://github.com/lky9464/SAFE) `main` 최초 공개본

### 추가

#### 도메인·검토 기능 (Phase 2~3)

- **일제점검 통합 체크리스트** (47항목 + 교차 X07)
  - `checklists/checklist_inspection.json`
  - `inspection_checklist.py`, `scripts/seed_inspection_checklist.py`
- **N/A(해당없음) 판정 엔진** (`na_engine.py`, 판정 코드 `A`)
  - 사업 프로필(제출 자료·집행 세목)에 따른 항목 적용/제외
- **사업 단위 통합 검토** (`run_case_review_pipeline`)
  - 일제점검 선택 시 ①~④ 다중 업로드 → OCR·파싱 병합 후 1회 비교
- **교차 검토 규칙** (`cross_rules.py` — JC-01, X07 등)
- **집행내역서(엑셀) 파싱 강화** (`parser.py` — 열 매핑·세목·금액)
- 검토 결과 화면: **N/A 건수·사업 프로필 요약** 표시
- 회귀 테스트: `test_inspection_na.py`, `test_cross_rules.py`

#### 문서·산출물

- `docs/phase1/` — 사업검토 정의, 골든케이스, 편성목, 분류체계, 매핑·매트릭스 등
- `docs/phase2/`, `docs/phase3/` — 일제점검 연동·사업 통합 검토 진행 현황
- `docs/참고자료/` — 일제점검 실시계획 체크리스트(원본·PDF)
- `scripts/build_phase1_xlsx.py` 등 Phase 1 Excel 생성 스크립트

#### 운영·배포

- `README.md` — 신규 PC용 사전 설치·구축 안내
- `SAFE_restart.bat` — 포트 점유 프로세스 종료 후 서버 재기동
- `open_docs/`, `uploads/`, `reports/` 폴더용 `.gitkeep` (실데이터는 Git 제외)

### 변경

- `checker.py` — `case_profile` 연동, N/A·교차·스니펫(검토내용 발췌) 처리
- `routers/review_router.py` — 일제점검/프로필 페이로드, 케이스 파이프라인
- `logger.py` — 프로필 remark 저장, 상세 조회 시 `na_cnt`·`case_profile` 복원
- `templates/review.html`, `static/js/review.js` — 프로필 UI(세목·자료 슬롯), 일제점검 기본 선택
- `templates/result.html` — N/A·프로필 요약 UI
- `MariaDB_시작.bat`, `SAFE_시작.bat` — 경로 일반화, MariaDB 프로세스 콘솔 분리(창 종료 가능), UTF-8 출력
- `.env.example` — 플레이스홀더 경로·비밀번호 안내
- `.gitignore` — `.env`, 업로드/보고서/지식DB 실파일, tessdata 언어팩 제외
- `sql/01_create_user.sql`, `setup_db_init.sql` — DB 비밀번호를 `CHANGE_ME`로 교체 (실비밀번호 미포함)

### 제거·정리

- 인코딩이 깨진 중복 문서명(`docs/#U...`) 삭제 (한글 파일명본만 유지)
- Phase 1 Excel 영문 별칭 파일 제거 및 재생성 시 자동 정리 (`build_phase1_xlsx.py`)

### 참고 (직전 백업에 이미 포함)

다음 항목은 `20260630_back-up`에도 동일하게 존재하며, 이번 구간 **신규 변경은 아닙니다.**

- 검토 이력 **선택 삭제 / 전체 삭제** UI·API
- 이력 No 표시·정렬(오래된 검토 = 1) 관련 로직

---

## 버전 표기

| 태그 | 설명 |
|------|------|
| `v1.0.0` | 2026-06-30 백업 대비 기능·문서·GitHub 공개 정리본 |
