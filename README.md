# SAFE

지방보조금 부정수급 검토지원 시스템 (로컬 전용)

- 웹 UI: `http://127.0.0.1:8000`
- 상세 설치·사용: [manual.md](manual.md)

## 빠른 시작

1. `.env.example`을 `.env`로 복사 후 API 키·DB 비밀번호·경로 설정
2. MariaDB 기동 (`MariaDB_시작.bat` 또는 자체 설치본)
3. DB 스키마 적용 (`sql/`, `setup_db_*.sql` — SQL의 `CHANGE_ME`를 `.env`의 `DB_PASSWORD`와 동일하게)
4. `pip install -r requirements.txt`
5. Tesseract OCR 언어 데이터(`kor`/`eng`)를 `tessdata/`에 배치
6. `SAFE_시작.bat` 또는 `python main.py`

## 보안

- **`.env`는 커밋하지 마세요** (API 키·DB 비밀번호)
- `uploads/`, `reports/`, `open_docs/` 실데이터는 Git에 포함되지 않습니다
