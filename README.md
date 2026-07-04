# SAFE

지방보조금 부정수급 검토지원 시스템 (로컬 전용)

- 웹 UI: `http://127.0.0.1:8000`
- 상세 운영 매뉴얼: [manual.md](manual.md)
- **변경 이력** (직전 백업 `20260630` 대비): [CHANGELOG.md](CHANGELOG.md)

GitHub에서 코드를 받더라도 **아래 환경은 PC에 별도로 설치·설정**해야 합니다.  
(저장소에는 소스·문서·시드 체크리스트만 포함되며, DB·OCR·API 키·업무 파일은 포함되지 않습니다.)

---

## 사전 준비 (개별 설치)

| # | 항목 | 필수 | 용도 |
|---|------|------|------|
| 1 | **Windows 10/11** (권장) | 권장 | `.bat` 스크립트·경로 예시는 Windows 기준 |
| 2 | **Python 3.12** | 필수 | 앱 실행 (`python`, `pip`) |
| 3 | **MariaDB** (또는 MySQL 호환) | 필수 | 검토 이력·체크리스트 저장 (`localhost:3306`) |
| 4 | **Tesseract OCR** + 언어팩 | 필수 | PDF/이미지 문자 인식 (`kor`, `eng`) |
| 5 | **Poppler** | 필수 | PDF → 이미지 변환 (OCR 전처리) |
| 6 | **Gemini API 키** | 선택 | 지식DB 기반 체크리스트 **생성**·결과 화면 **추가분석**만 사용. 자료 검토(OCR·비교) 자체는 로컬만으로 동작 |
| 7 | **Git** | 선택 | `git clone` 시. ZIP 다운로드만 하면 불필요 |

> 내부 사업자료는 외부로 전송되지 않습니다. Gemini는 공개 법령·점검항목명 등 제한된 용도에만 쓰입니다.

---

## 1. 코드 받기

```bash
git clone https://github.com/lky9464/SAFE.git
cd SAFE
```

또는 [Releases/Code → Download ZIP](https://github.com/lky9464/SAFE) 후 압축 해제.

---

## 2. Python

1. [Python 3.12](https://www.python.org/downloads/) 설치  
   - 설치 시 **“Add python.exe to PATH”** 체크
2. 프로젝트 폴더에서 가상환경(권장) 및 패키지 설치:

```bash
cd SAFE
python -m venv .venv

# Windows
.venv\Scripts\activate

pip install -r requirements.txt
```

- 최초 실행 시 **임베딩 모델**(Sentence Transformers)을 Hugging Face에서 받을 수 있습니다. 인터넷이 필요하며, 수 분·수백 MB 정도 소요될 수 있습니다.

---

## 3. MariaDB

1. [MariaDB](https://mariadb.org/download/) 설치 (또는 Portable 배포본)
2. 서비스/프로세스가 **`localhost:3306`** 에서 기동되는지 확인
3. 이 저장소의 `MariaDB_시작.bat`은 **본인 PC의 MariaDB 경로**를 가정합니다.  
   - 기본: `%USERPROFILE%\mariadb\mariadb-12.3.2-winx64`  
   - 경로가 다르면 bat 파일의 `BASE`, `INI`를 수정하거나, 직접 `mysqld`를 기동

### DB·계정·스키마 생성

관리자(root 등)로 MariaDB에 접속한 뒤, **순서대로** 실행합니다.

1. `sql/00_create_database.sql` — DB `safe_db` 생성  
2. `sql/01_create_user.sql` — 사용자 `safe_user` 생성  
   - 파일 안의 `CHANGE_ME`를 **본인이 정한 비밀번호**로 바꾼 뒤 실행  
3. `sql/02_schema.sql` — 테이블 생성  

또는 루트의 `setup_db_init.sql` + `setup_db_schema.sql`을 사용해도 됩니다.  
(`setup_db_init.sql`의 `CHANGE_ME`도 동일하게 변경)

비밀번호는 다음 단계 `.env`의 `DB_PASSWORD`와 **반드시 동일**해야 합니다.

---

## 4. Tesseract OCR

1. [Tesseract for Windows](https://github.com/UB-Mannheim/tesseract/wiki) 설치  
   - 기본 경로 예: `C:\Program Files\Tesseract-OCR\tesseract.exe`
2. 설치 시 또는 [tessdata](https://github.com/tesseract-ocr/tessdata)에서 언어 데이터 확보:
   - `kor.traineddata`
   - `eng.traineddata`
3. 프로젝트의 `tessdata/` 폴더에 위 파일을 넣습니다.  
   (저장소에는 용량 때문에 `.traineddata`가 **포함되어 있지 않습니다**.)

`.env` 예:

```env
TESSERACT_PATH=C:/Program Files/Tesseract-OCR/tesseract.exe
TESSDATA_PREFIX=./tessdata/
```

---

## 5. Poppler

PDF 페이지를 이미지로 바꿀 때 필요합니다.

1. Windows용 Poppler 바이너리 설치 (예: WinGet, 또는 [poppler-windows](https://github.com/oschwartz10612/poppler-windows) 릴리스)
2. `Library\bin` (또는 `bin`) 경로를 `.env`의 `POPPLER_PATH`에 지정

```env
POPPLER_PATH=C:/path/to/poppler/Library/bin
```

---

## 6. 환경 설정 파일 (`.env`)

```bash
copy .env.example .env
```

`.env`를 열어 최소한 다음을 채웁니다.

| 변수 | 설명 |
|------|------|
| `DB_USER` / `DB_PASSWORD` | MariaDB 계정 (SQL에서 만든 값) |
| `DB_HOST` / `DB_PORT` / `DB_NAME` | 기본 `localhost` / `3306` / `safe_db` |
| `TESSERACT_PATH` | `tesseract.exe` 전체 경로 |
| `TESSDATA_PREFIX` | `kor`/`eng` traineddata가 있는 폴더 |
| `POPPLER_PATH` | Poppler `bin` 폴더 |
| `UPLOAD_PATH` | 업로드 저장 위치 (기본 `./uploads`) |
| `PUBLIC_DATA_PATH` | 지식DB(공개 PDF) 폴더 (기본 `./open_docs`) |
| `GEMINI_API_KEY` | [Google AI Studio](https://aistudio.google.com/apikey)에서 발급 (선택) |

**`.env`는 Git에 올리지 마세요.**

---

## 7. (선택) 지식DB·체크리스트 시드

| 목적 | 방법 |
|------|------|
| 지식DB에서 체크리스트 생성 | 공개 법령·지침 PDF를 `open_docs/`에 넣고, UI **지식DB** 메뉴에서 생성 (`GEMINI_API_KEY` 필요) |
| 일제점검 체크리스트 시드 | `python scripts/seed_inspection_checklist.py` (문서·시드 JSON 기반, Gemini 불필요) |

`open_docs/`, `uploads/`, `reports/`의 **실파일은 저장소에 없습니다.** 폴더만 비어 있는 상태로 준비됩니다.

---

## 8. 실행

1. MariaDB가 떠 있는지 확인 (`MariaDB_시작.bat` 또는 서비스)
2. 앱 기동:

```bash
# Windows — 배치 파일
SAFE_시작.bat

# 또는
python main.py
```

3. 브라우저: [http://127.0.0.1:8000](http://127.0.0.1:8000)
4. **설정** 메뉴에서 DB·Gemini 연결 테스트

포트·호스트는 `.env`의 `PORT`, `HOST`로 변경할 수 있습니다.

---

## 설치 체크리스트 (요약)

- [ ] Python 3.12 + `pip install -r requirements.txt`
- [ ] MariaDB 기동 + `safe_db` / `safe_user` / 스키마
- [ ] `.env` 작성 (DB·Tesseract·Poppler 경로)
- [ ] `tessdata/kor.traineddata`, `eng.traineddata`
- [ ] Poppler `bin` 경로
- [ ] (선택) Gemini API 키
- [ ] `python main.py` 후 `http://127.0.0.1:8000` 접속

---

## 보안

- **`.env`는 커밋하지 마세요** (API 키·DB 비밀번호)
- `uploads/`, `reports/`, `open_docs/` 실데이터는 Git에 포함되지 않습니다
- 모든 검토 처리는 **로컬 PC**에서 수행됩니다

---

## 문제 해결 (자주 발생)

| 증상 | 확인 |
|------|------|
| DB 연결 실패 | MariaDB 기동 여부, `.env` 비밀번호 = SQL `IDENTIFIED BY` |
| OCR/PDF 오류 | `TESSERACT_PATH`, `TESSDATA_PREFIX`, `POPPLER_PATH` |
| `python` 명령을 찾을 수 없음 | PATH 등록 또는 `SAFE_시작.bat`의 Python 경로 수정 |
| Gemini 오류 | API 키·네트워크 (검토 파이프라인 자체는 Gemini 없이 동작 가능) |
| 첫 실행이 매우 느림 | 임베딩 모델 최초 다운로드 중일 수 있음 |

운영 화면·업무 절차는 [manual.md](manual.md)를 참고하세요.
