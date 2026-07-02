"""
Model Manager / Registry.
Không hardcode model nào trong code — mọi model được đăng ký động vào registry.json.
Admin có thể install (tải từ URL), remove, reload.
"""
import json
import shutil
import threading
from datetime import datetime
from pathlib import Path
from typing import Optional

import requests
from pydantic import BaseModel

from backend.config import settings
from backend.core.logger import get_logger

logger = get_logger("model_registry")
_lock = threading.Lock()


class ModelInfo(BaseModel):
    name: str
    type: str  # ví dụ: "vocal-separation", "chord-detection"
    path: str
    status: str  # "installed" | "downloading" | "error" | "removed"
    version: str = "1.0.0"
    installed_at: Optional[str] = None
    source_url: Optional[str] = None


def _load_registry() -> dict:
    path = settings.model_registry_file
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({}, indent=2), encoding="utf-8")
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _save_registry(data: dict):
    with _lock:
        settings.model_registry_file.write_text(
            json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8"
        )


def list_models() -> list[ModelInfo]:
    reg = _load_registry()
    return [ModelInfo(**v) for v in reg.values()]


def get_model(name: str) -> Optional[ModelInfo]:
    reg = _load_registry()
    entry = reg.get(name)
    return ModelInfo(**entry) if entry else None


def install_model_from_url(name: str, model_type: str, url: str) -> ModelInfo:
    """
    Tải model thật từ URL về models/<name>/.
    LƯU Ý: cần server có kết nối mạng khi chạy thật (môi trường dev hiện tại có thể sandbox
    không có mạng — hãy kiểm tra log nếu tải lỗi).
    """
    reg = _load_registry()
    model_dir: Path = settings.models_dir / name
    model_dir.mkdir(parents=True, exist_ok=True)

    reg[name] = ModelInfo(
        name=name,
        type=model_type,
        path=str(model_dir),
        status="downloading",
        source_url=url,
    ).model_dump()
    _save_registry(reg)

    try:
        filename = url.split("/")[-1] or "model.bin"
        dest = model_dir / filename
        with requests.get(url, stream=True, timeout=60) as r:
            r.raise_for_status()
            with open(dest, "wb") as f:
                for chunk in r.iter_content(chunk_size=8192):
                    f.write(chunk)

        reg[name]["status"] = "installed"
        reg[name]["installed_at"] = datetime.utcnow().isoformat()
        _save_registry(reg)
        logger.info(f"Model '{name}' đã được cài đặt thành công tại {dest}")
        return ModelInfo(**reg[name])
    except Exception as e:
        reg[name]["status"] = "error"
        _save_registry(reg)
        logger.error(f"Lỗi khi tải model '{name}': {e}")
        raise


def remove_model(name: str) -> bool:
    reg = _load_registry()
    if name not in reg:
        return False
    model_dir = Path(reg[name]["path"])
    if model_dir.exists():
        shutil.rmtree(model_dir, ignore_errors=True)
    del reg[name]
    _save_registry(reg)
    logger.info(f"Đã xóa model '{name}'")
    return True


def reload_model(name: str) -> Optional[ModelInfo]:
    """Đánh dấu lại trạng thái model sau khi kiểm tra file tồn tại trên đĩa."""
    reg = _load_registry()
    if name not in reg:
        return None
    model_dir = Path(reg[name]["path"])
    reg[name]["status"] = "installed" if model_dir.exists() and any(model_dir.iterdir()) else "error"
    _save_registry(reg)
    logger.info(f"Reload model '{name}' -> status={reg[name]['status']}")
    return ModelInfo(**reg[name])
