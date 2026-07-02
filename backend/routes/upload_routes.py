from fastapi import APIRouter, Depends, UploadFile, File, HTTPException

from backend.core.auth import get_current_user, TokenData
from backend.core.storage import save_upload

router = APIRouter(prefix="/api", tags=["upload"])


@router.post("/upload")
async def upload_file(file: UploadFile = File(...), current_user: TokenData = Depends(get_current_user)):
    try:
        dest = await save_upload(file)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"filename": dest.name, "path": str(dest)}
