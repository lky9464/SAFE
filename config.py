"""
SAFE 시스템 환경 설정 모듈
.env 파일 로드, 상수 정의, MariaDB 연결, Tesseract 경로 설정
"""

import logging
import os
import shutil
from pathlib import Path

import pymysql
import pytesseract
from dotenv import load_dotenv

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

# 프로젝트 루트 기준 .env 로드
_BASE_DIR = Path(__file__).resolve().parent
_ENV_PATH = _BASE_DIR / ".env"

if _ENV_PATH.exists():
    load_dotenv(_ENV_PATH)
    logger.info(".env 파일 로드 완료: %s", _ENV_PATH)
else:
    logger.warning(".env 파일을 찾을 수 없습니다: %s", _ENV_PATH)

# --- API 키 ---
GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")

# --- 데이터베이스 ---
DB_HOST: str = os.getenv("DB_HOST", "localhost")
DB_PORT: int = int(os.getenv("DB_PORT", "3306"))
DB_NAME: str = os.getenv("DB_NAME", "safe_db")
DB_USER: str = os.getenv("DB_USER", "")
DB_PASSWORD: str = os.getenv("DB_PASSWORD", "")

# --- 경로 ---
UPLOAD_PATH: str = os.getenv("UPLOAD_PATH", str(_BASE_DIR / "uploads"))
PUBLIC_DATA_PATH: str = os.getenv(
    "PUBLIC_DATA_PATH",
    str(_BASE_DIR / "open_docs"),
)
TESSERACT_PATH: str = os.getenv(
    "TESSERACT_PATH",
    r"C:\Program Files\Tesseract-OCR\tesseract.exe",
)
TESSDATA_PREFIX: str = os.getenv("TESSDATA_PREFIX", "")


def _resolve_poppler_path() -> str:
    """Poppler(pdftoppm) bin 디렉터리 탐색 — pdf2image OCR용"""
    env_path = os.getenv("POPPLER_PATH", "").strip()
    if env_path:
        path = Path(env_path)
        if (path / "pdftoppm.exe").is_file() or (path / "pdftoppm").is_file():
            return str(path)
        if path.is_file():
            return str(path.parent)

    which = shutil.which("pdftoppm")
    if which:
        return str(Path(which).parent)

    local_app = os.environ.get("LOCALAPPDATA", "")
    if local_app:
        winget_packages = Path(local_app) / "Microsoft" / "WinGet" / "Packages"
        if winget_packages.is_dir():
            candidates = sorted(
                winget_packages.glob("*Poppler*/poppler-*/Library/bin"),
                key=lambda p: p.stat().st_mtime,
                reverse=True,
            )
            for candidate in candidates:
                if (candidate / "pdftoppm.exe").is_file():
                    return str(candidate)

    return ""


def _resolve_libreoffice_path() -> str:
    """LibreOffice soffice.exe 경로 탐색"""
    env_path = os.getenv("LIBREOFFICE_PATH", "").strip()
    if env_path:
        path = Path(env_path)
        if path.is_file():
            return str(path)
        candidate = path / "soffice.exe"
        if candidate.is_file():
            return str(candidate)

    for candidate in (
        r"C:\Program Files\LibreOffice\program\soffice.exe",
        r"C:\Program Files (x86)\LibreOffice\program\soffice.exe",
    ):
        if Path(candidate).is_file():
            return candidate

    which = shutil.which("soffice")
    return which or ""


LIBREOFFICE_PATH: str = _resolve_libreoffice_path()

POPPLER_PATH: str = _resolve_poppler_path()

CHECKLIST_DIR: str = str(_BASE_DIR / "checklists")

# --- PHASE 3 경로 ---
FAISS_INDEX_DIR: str = str(_BASE_DIR / "faiss_index")
REPORTS_DIR: str = str(_BASE_DIR / "reports")

# --- 임베딩 모델 (로컬) ---
EMBEDDING_MODEL: str = os.getenv(
    "EMBEDDING_MODEL",
    "jhgan/ko-sroberta-multitask",
)

# --- Gemini 모델 (.env에서 로드, 기본값: gemini-2.5-flash) ---
GEMINI_MODEL: str = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

# --- API 호출 간격 (429 방지, 초) ---
GEMINI_CALL_INTERVAL: int = 5

# --- PDF 텍스트 최대 길이 (Gemini 토큰 절약) ---
PDF_TEXT_MAX_LENGTH: int = 5000

# --- 체크리스트 최소 항목 수 ---
CHECKLIST_MIN_ITEMS: int = 20

# --- 업로드 한도 ---
MAX_FILE_SIZE_MB: int = int(os.getenv("MAX_FILE_SIZE_MB", "100"))
MAX_ZIP_BUNDLE_SIZE_MB: int = int(os.getenv("MAX_ZIP_BUNDLE_SIZE_MB", "500"))
MAX_ZIP_BUNDLE_FILES: int = int(os.getenv("MAX_ZIP_BUNDLE_FILES", "400"))
MAX_ZIP_UNCOMPRESSED_MB: int = int(os.getenv("MAX_ZIP_UNCOMPRESSED_MB", "1024"))

# --- 서버 포트 ---
SERVER_PORT: int = int(os.getenv("PORT", "8000"))
SERVER_HOST: str = os.getenv("HOST", "127.0.0.1")


def reload_env_settings() -> None:
    """.env 변경 사항을 실행 중인 프로세스에 반영"""
    global GEMINI_API_KEY, GEMINI_MODEL, DB_PASSWORD, UPLOAD_PATH, PUBLIC_DATA_PATH

    if _ENV_PATH.exists():
        load_dotenv(_ENV_PATH, override=True)

    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
    GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
    DB_PASSWORD = os.getenv("DB_PASSWORD", "")
    UPLOAD_PATH = os.getenv("UPLOAD_PATH", str(_BASE_DIR / "uploads"))
    PUBLIC_DATA_PATH = os.getenv(
        "PUBLIC_DATA_PATH",
        str(_BASE_DIR / "open_docs"),
    )


# Tesseract 실행 파일·언어팩 경로 자동 설정
if os.path.isfile(TESSERACT_PATH):
    pytesseract.pytesseract.tesseract_cmd = TESSERACT_PATH
    logger.info("Tesseract 경로 설정 완료: %s", TESSERACT_PATH)
else:
    logger.warning("Tesseract 실행 파일을 찾을 수 없습니다: %s", TESSERACT_PATH)

_tessdata_prefix = TESSDATA_PREFIX.strip()
if not _tessdata_prefix and (_BASE_DIR / "tessdata" / "kor.traineddata").is_file():
    _tessdata_prefix = str(_BASE_DIR / "tessdata")
if _tessdata_prefix:
    os.environ["TESSDATA_PREFIX"] = _tessdata_prefix.rstrip("/\\") + os.sep
    logger.info("Tesseract tessdata 경로: %s", os.environ["TESSDATA_PREFIX"])

if POPPLER_PATH:
    poppler_bin = POPPLER_PATH
    if poppler_bin not in os.environ.get("PATH", ""):
        os.environ["PATH"] = poppler_bin + os.pathsep + os.environ.get("PATH", "")
    logger.info("Poppler 경로 설정 완료: %s", POPPLER_PATH)
else:
    logger.warning(
        "Poppler(pdftoppm)를 찾을 수 없습니다. "
        "스캔 PDF OCR 시 오류가 날 수 있습니다. POPPLER_PATH를 .env에 설정하세요."
    )


def get_db_connection():
    """
    MariaDB(safe_db) 연결 객체 반환.
    사용 후 반드시 connection.close() 호출 필요.
    """
    try:
        connection = pymysql.connect(
            host=DB_HOST,
            port=DB_PORT,
            user=DB_USER,
            password=DB_PASSWORD,
            database=DB_NAME,
            charset="utf8mb4",
            cursorclass=pymysql.cursors.DictCursor,
            autocommit=False,
        )
        logger.debug("MariaDB 연결 성공: %s@%s:%s/%s", DB_USER, DB_HOST, DB_PORT, DB_NAME)
        return connection
    except pymysql.MySQLError as exc:
        logger.error("MariaDB 연결 실패: %s", exc)
        raise ConnectionError(f"데이터베이스 연결에 실패했습니다: {exc}") from exc


def ensure_directories() -> None:
    """업로드·체크리스트·인덱스·보고서 디렉터리가 없으면 생성"""
    for path in (UPLOAD_PATH, CHECKLIST_DIR, FAISS_INDEX_DIR, REPORTS_DIR, PUBLIC_DATA_PATH):
        os.makedirs(path, exist_ok=True)
        logger.debug("디렉터리 확인: %s", path)
