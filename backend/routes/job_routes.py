from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse

from backend.core.auth import get_current_user, TokenData
from backend.core.job_queue import job_queue

router = APIRouter(prefix="/api", tags=["jobs"])


@router.get("/job/{job_id}")
def job_status(job_id: str, current_user: TokenData = Depends(get_current_user)):
    job = job_queue.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job không tồn tại")
    if current_user.role != "admin" and job.user != current_user.username:
        raise HTTPException(status_code=403, detail="Không có quyền xem job này")
    return job


@router.get("/download/{job_id}")
def download(job_id: str, file: str = "json", current_user: TokenData = Depends(get_current_user)):
    job = job_queue.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job không tồn tại")
    if current_user.role != "admin" and job.user != current_user.username:
        raise HTTPException(status_code=403, detail="Không có quyền tải job này")
    if not job.result:
        raise HTTPException(status_code=400, detail="Job chưa có kết quả")

    key = f"{file}_path"
    path_str = job.result.get(key) or job.result.get(file)
    if not path_str or not Path(path_str).exists():
        raise HTTPException(status_code=404, detail="File kết quả không tồn tại")
    return FileResponse(path_str, filename=Path(path_str).name)
