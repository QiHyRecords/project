from fastapi import APIRouter, Depends, UploadFile, File, HTTPException

from backend.core.auth import get_current_user, TokenData
from backend.core.storage import save_upload
from backend.core.model_registry import list_models

router = APIRouter(prefix="/api", tags=["upload"])


@router.get("/models/vocal-separation")
def available_separation_models(current_user: TokenData = Depends(get_current_user)):
    """Danh sách model tách vocal đã cài và sẵn sàng dùng — không hardcode ở frontend."""
    return [
        {"name": m.name, "status": m.status}
        for m in list_models()
        if m.type == "vocal-separation" and m.status == "installed"
    ]


@router.post("/upload")
async def upload_file(file: UploadFile = File(...), current_user: TokenData = Depends(get_current_user)):
    try:
        dest = await save_upload(file)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"filename": dest.name, "path": str(dest)}
