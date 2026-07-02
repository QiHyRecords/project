from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from backend.config import settings
from backend.core.logger import get_logger
from backend.routes import (
    auth_routes,
    upload_routes,
    analyze_routes,
    separate_routes,
    job_routes,
    admin_routes,
)

logger = get_logger("main")

app = FastAPI(title=settings.app_name)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_routes.router, prefix="/api")
app.include_router(upload_routes.router)
app.include_router(analyze_routes.router)
app.include_router(separate_routes.router)
app.include_router(job_routes.router)
app.include_router(admin_routes.router)

# Phục vụ frontend tĩnh (HTML/CSS/JS) tại /
app.mount("/", StaticFiles(directory="frontend", html=True), name="frontend")


@app.on_event("startup")
def on_startup():
    logger.info(f"{settings.app_name} đã khởi động.")
