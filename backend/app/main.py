from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware

from app.api import router
from app.auto_reglue_api import router as auto_reglue_router
from app.site_templates_api import router as site_templates_router
from app.auto_lb_api import router as auto_lb_router
from app.project_pages import router as project_pages_router
from app.showcase_editor import router as showcase_editor_router
from app.project_page_autolink import router as page_autolink_router
from app.article_images_api import router as article_images_router
from app.project_notifications_api import router as project_notifications_router
from app.project_structured_data import router as project_structured_data_router
from app.reglue_journal import router as reglue_journal_router
from app.dashboard_activity import router as dashboard_activity_router
from app.core.config import get_settings
from app.db import init_db
from app.project_state_reports import router as project_reports_router


settings = get_settings()

app = FastAPI(title="PagePilot API", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(GZipMiddleware, minimum_size=1000, compresslevel=6)


@app.on_event("startup")
def on_startup() -> None:
    if not settings.app_skip_db_init:
        init_db()


app.include_router(router, prefix="/api")
app.include_router(auto_reglue_router, prefix="/api")
app.include_router(site_templates_router, prefix="/api")
app.include_router(auto_lb_router, prefix="/api")

app.include_router(project_pages_router, prefix="/api")
app.include_router(showcase_editor_router, prefix="/api")
app.include_router(page_autolink_router, prefix="/api")
app.include_router(article_images_router, prefix="/api")
app.include_router(project_notifications_router, prefix="/api")
app.include_router(project_structured_data_router, prefix="/api")
app.include_router(reglue_journal_router, prefix="/api")
app.include_router(dashboard_activity_router, prefix="/api")

app.include_router(project_reports_router, prefix="/api")
