from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from backend.core.auth import require_admin, TokenData, create_user
from backend.core.model_registry import (
    list_models, install_model_from_url, install_demucs_model, remove_model, reload_model,
)
from backend.core.job_queue import job_queue
from backend.core.system_stats import get_system_stats

router = APIRouter(prefix="/api/admin", tags=["admin"])


@router.get("/dashboard")
def dashboard(current_user: TokenData = Depends(require_admin)):
    return get_system_stats()


@router.get("/models")
def models(current_user: TokenData = Depends(require_admin)):
    return list_models()


class InstallModelRequest(BaseModel):
    name: str
    type: str
    url: str


@router.post("/install-model")
def install_model(req: InstallModelRequest, current_user: TokenData = Depends(require_admin)):
    try:
        return install_model_from_url(req.name, req.type, req.url)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Cài model thất bại: {e}")


class InstallDemucsRequest(BaseModel):
    name: str          # tên hiển thị trong hệ thống, vd "VS-HsBtl" hoặc "Demucs-4stem"
    demucs_tag: str     # tag thật của Demucs: "htdemucs" | "htdemucs_ft" | "mdx" | "mdx_extra"


@router.post("/install-demucs-model")
def install_demucs(req: InstallDemucsRequest, current_user: TokenData = Depends(require_admin)):
    """
    Cài model Demucs mã nguồn mở — không cần URL, Demucs tự tải trọng số.
    Có thể mất vài phút cho lần đầu (weights vài trăm MB).
    """
    try:
        return install_demucs_model(req.name, req.demucs_tag)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Cài Demucs model thất bại: {e}")


class ModelNameRequest(BaseModel):
    name: str


@router.post("/remove-model")
def remove_model_route(req: ModelNameRequest, current_user: TokenData = Depends(require_admin)):
    ok = remove_model(req.name)
    if not ok:
        raise HTTPException(status_code=404, detail="Model không tồn tại")
    return {"removed": req.name}


@router.post("/reload-model")
def reload_model_route(req: ModelNameRequest, current_user: TokenData = Depends(require_admin)):
    info = reload_model(req.name)
    if not info:
        raise HTTPException(status_code=404, detail="Model không tồn tại")
    return info


@router.get("/jobs")
def all_jobs(current_user: TokenData = Depends(require_admin)):
    return job_queue.list_all()


class CreateUserRequest(BaseModel):
    username: str
    password: str
    role: str = "user"


@router.post("/create-user")
def admin_create_user(req: CreateUserRequest, current_user: TokenData = Depends(require_admin)):
    create_user(req.username, req.password, req.role)
    return {"created": req.username, "role": req.role}
