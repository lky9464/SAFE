# Phase 2 — 일제점검 연동 (완료)

> **전제:** Phase 1 문서 7/7 완료, 일제점검 PDF 47항목만 우선 (세목 보완은 추후)

## 확정 방침 (2026-07-02)

| 항목 | 결정 |
|------|------|
| 체크리스트 기준 | `일제점검 실시계획_체크리스트.pdf` 47항목 (+ X07 교차) |
| 프로필 최소 세트 | 일제점검 **10개 세목** (`inspection_checklist.INSPECTION_SEOMOKS`) |
| ① 예산집행계획 입력 | **1차: 검토 시 수동(프로필 UI)** — 자동 파싱은 추후 |
| N/A 판정 코드 | `A` = 해당없음 (DB CHAR(1)) |

## 구현 현황

| # | 작업 | 상태 |
|---|------|------|
| 2-1 | 47항목 → `checklists/checklist_inspection.json` | ✅ |
| 2-2 | 메타데이터 (`law_ref`=항목ID, `inspection_checklist.py`) | ✅ |
| 2-4 | N/A 엔진 (`na_engine.py`) + `checker.compare_document(case_profile=)` | ✅ |
| 2-5 | 골든 G1/G4/G5/G6 회귀 (`test_inspection_na.py`) | ✅ |
| 2-3 | 프로필 UI (블록 B·C) | ✅ 검토 화면 STEP 3 |
| 2-3b | `review_router` → `CaseProfile` 연동 | ✅ |
| DB 시드 | `python scripts/seed_inspection_checklist.py` | ✅ checklist_id=9 |
| 결과 화면 | N/A 건수·프로필 요약 | ✅ |
| FAISS 캐시 | `index.ntotal` len 오류 수정 | ✅ |

## 사용

```powershell
# JSON 생성
python scripts/seed_inspection_checklist.py --json-only

# DB 시드 (MariaDB 실행 중)
python scripts/seed_inspection_checklist.py

# N/A 골든 테스트
python test_inspection_na.py
```

## 다음

**Phase 3** (`docs/phase3/README.md`) — 사업 1건 · ①~④ 통합 검토
