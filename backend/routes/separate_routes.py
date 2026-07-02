"""
Vocal Remover route — chạy inference thật bằng Demucs (backend/core/separation.py).
Model không hardcode: bất kỳ model nào trong registry có type "vocal-separation"
và status "installed" đều dùng được, tên hiển thị do admin đặt lúc install.
"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from backend.config import settings
from backend.core.auth import get_current_user, TokenData
from backend.core.model_registry import get_model
from backend.core.job_queue import job_queue, Job
from backend.core.separation import separate_audio

router = APIRouter(prefix="/api", tags=["separate"])


class SeparateRequest(BaseModel):
    filename: str
    model: str  # tên model đã đăng ký trong Model Manager, vd "VS-HsBtl"


def _separation_handler(job: Job, progress_cb, demucs_tag: str):
    input_path = settings.uploads_dir / job.file
    out_dir = settings.outputs_dir / job.id
    stems = separate_audio(
        input_path=str(input_path),
        model_tag=demucs_tag,
        output_dir=str(out_dir),
        progress_cb=progress_cb,
    )
    return {f"{name}_path": path for name, path in stems.items()}


@router.post("/separate")
def separate(req: SeparateRequest, current_user: TokenData = Depends(get_current_user)):
    file_path = settings.uploads_dir / req.filename
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File không tồn tại, hãy upload trước")

    model_info = get_model(req.model)
    if not model_info or model_info.type != "vocal-separation":
        raise HTTPException(status_code=400, detail=f"Model không tồn tại: {req.model}")
    if model_info.status != "installed":
        raise HTTPException(
            status_code=409,
            detail=f"Model '{req.model}' chưa được cài đặt. Admin cần install model này trước.",
        )

    demucs_tag = model_info.version  # được lưu lúc install_demucs_model()

    def handler(job: Job, progress_cb):
        return _separation_handler(job, progress_cb, demucs_tag)

    job = job_queue.submit(
        user=current_user.username,
        file=req.filename,
        model=req.model,
        job_type="separate",
        handler=handler,
    )
    return {"job_id": job.id, "status": job.status}
