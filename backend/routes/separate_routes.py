"""
Vocal Remover route.
LƯU Ý: Đây là khung xử lý qua Job Queue + Model Registry, đúng kiến trúc yêu cầu.
Việc load trọng số MDX-Net / Demucs (VS-HsBtl) thật và chạy inference PyTorch
sẽ được cắm vào `_run_separation_model()` ở Giai đoạn 2 — không giả lập kết quả ở đây,
nếu model chưa được cài, API trả lỗi rõ ràng thay vì xuất file rác.
"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from backend.config import settings
from backend.core.auth import get_current_user, TokenData
from backend.core.model_registry import get_model
from backend.core.job_queue import job_queue, Job

router = APIRouter(prefix="/api", tags=["separate"])

SUPPORTED_MODELS = {"MDX-Net", "VS-HsBtl"}


class SeparateRequest(BaseModel):
    filename: str
    model: str  # "MDX-Net" | "VS-HsBtl"


def _run_separation_model(job: Job, progress_cb, model_info) -> dict:
    """
    Placeholder có chủ đích cho Giai đoạn 2: sẽ load model_info.path bằng torch.load(),
    chạy STFT -> mask prediction -> ISTFT để tách vocal/instrumental (+ bass/drums/other nếu
    model hỗ trợ 4-stem). Hiện tại hàm này raise lỗi rõ ràng thay vì trả kết quả giả.
    """
    raise NotImplementedError(
        "Model inference engine sẽ được triển khai ở Giai đoạn 2. "
        "Model đã đăng ký nhưng chưa có pipeline inference thật."
    )


@router.post("/separate")
def separate(req: SeparateRequest, current_user: TokenData = Depends(get_current_user)):
    if req.model not in SUPPORTED_MODELS:
        raise HTTPException(status_code=400, detail=f"Model không hỗ trợ: {req.model}")

    file_path = settings.uploads_dir / req.filename
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File không tồn tại, hãy upload trước")

    model_info = get_model(req.model)
    if not model_info or model_info.status != "installed":
        raise HTTPException(
            status_code=409,
            detail=f"Model '{req.model}' chưa được cài đặt. Admin cần install model này trước.",
        )

    def handler(job: Job, progress_cb):
        return _run_separation_model(job, progress_cb, model_info)

    job = job_queue.submit(
        user=current_user.username,
        file=req.filename,
        model=req.model,
        job_type="separate",
        handler=handler,
    )
    return {"job_id": job.id, "status": job.status}
