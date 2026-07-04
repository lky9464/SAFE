"""
SAFE FastAPI 메인 서버
로컬 웹 UI — Bootstrap 5 + Jinja2
"""

import logging
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

import config
from routers import (
    analysis_router,
    checklist_router,
    dashboard,
    guide_router,
    history_router,
    knowledge_router,
    review_router,
    settings_router,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

_BASE_DIR = Path(__file__).resolve().parent

app = FastAPI(
    title="SAFE",
    description="Local Subsidy AI Fraud Detection System",
    version="1.0.0",
)

# 로컬 전용 CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=[f"http://localhost:{config.SERVER_PORT}",
                   f"http://127.0.0.1:{config.SERVER_PORT}"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# 정적 파일 (uploads는 마운트 금지 — 보안)
app.mount("/static", StaticFiles(directory=str(_BASE_DIR / "static")), name="static")

# 라우터 등록
app.include_router(dashboard.router)
app.include_router(analysis_router.router, tags=["analysis"])
app.include_router(guide_router.router, tags=["guide"])
app.include_router(checklist_router.router, prefix="/checklist", tags=["checklist"])
app.include_router(review_router.router, prefix="/review", tags=["review"])
app.include_router(history_router.router, prefix="/history", tags=["history"])
app.include_router(settings_router.router, prefix="/settings", tags=["settings"])
app.include_router(knowledge_router.router, prefix="/knowledge", tags=["knowledge"])


@app.on_event("startup")
async def startup_event():
    """서버 시작 시 디렉터리 초기화"""
    config.ensure_directories()
    import checklist_db
    checklist_db.ensure_source_file_column()
    logger.info("SAFE 서버 시작 — http://%s:%s", config.SERVER_HOST, config.SERVER_PORT)
    logger.info(
        "업로드 한도 — 일반: %dMB, 지출증빙 ZIP: %dMB / 내부 최대 %d개",
        config.MAX_FILE_SIZE_MB,
        config.MAX_ZIP_BUNDLE_SIZE_MB,
        config.MAX_ZIP_BUNDLE_FILES,
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host=config.SERVER_HOST,
        port=config.SERVER_PORT,
        reload=True,
    )
