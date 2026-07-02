"""
Tiện ích thao tác với storage/: uploads, outputs, temp.
Nguyên tắc từ project trường học trước: KHÔNG tạo file/thư mục có ký tự đặc biệt (vd '#')
vì sẽ vỡ URL khi deploy trên Apache/cPanel.
"""
import re
import shutil
import uuid
from pathlib import Path

from fastapi import UploadFile

from backend.config import settings

_SAFE_CHARS = re.compile(r"[^a-zA-Z0-9_.-]")


def safe_filename(filename: str) -> str:
    name = Path(filename).stem
    ext = Path(filename).suffix.lower()
    safe_name = _SAFE_CHARS.sub("_", name)
    return f"{safe_name}_{uuid.uuid4().hex[:8]}{ext}"


async def save_upload(file: UploadFile) -> Path:
    ext = Path(file.filename).suffix.lower()
    if ext not in settings.allowed_extensions:
        raise ValueError(f"Định dạng không được hỗ trợ: {ext}")

    dest = settings.uploads_dir / safe_filename(file.filename)
    with open(dest, "wb") as f:
        while chunk := await file.read(1024 * 1024):
            f.write(chunk)
    return dest


def cleanup_temp():
    for item in settings.temp_dir.iterdir():
        if item.is_file():
            item.unlink(missing_ok=True)
        elif item.is_dir():
            shutil.rmtree(item, ignore_errors=True)
