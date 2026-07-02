import json
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from backend.config import settings
from backend.core.auth import get_current_user, TokenData
from backend.core.analyzer import analyze_audio, format_timeline_txt
from backend.core.job_queue import job_queue, Job

router = APIRouter(prefix="/api", tags=["analyze"])


class AnalyzeRequest(BaseModel):
    filename: str  # tên file đã upload (nằm trong storage/uploads)


def _analyze_handler(job: Job, progress_cb):
    file_path = settings.uploads_dir / job.file
    progress_cb(20)
    result = analyze_audio(str(file_path))
    progress_cb(80)

    out_dir = settings.outputs_dir / job.id
    out_dir.mkdir(parents=True, exist_ok=True)

    json_path = out_dir / "analysis.json"
    txt_path = out_dir / "analysis.txt"
    json_path.write_text(json.dumps(result.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8")
    txt_path.write_text(format_timeline_txt(result), encoding="utf-8")

    progress_cb(100)
    return {
        "json_path": str(json_path),
        "txt_path": str(txt_path),
        "summary": result.to_dict(),
    }


@router.post("/analyze")
def analyze(req: AnalyzeRequest, current_user: TokenData = Depends(get_current_user)):
    file_path = settings.uploads_dir / req.filename
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File không tồn tại, hãy upload trước")

    job = job_queue.submit(
        user=current_user.username,
        file=req.filename,
        model="librosa-analyzer",
        job_type="analyze",
        handler=_analyze_handler,
    )
    return {"job_id": job.id, "status": job.status}
