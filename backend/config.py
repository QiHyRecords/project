"""
Cấu hình trung tâm của toàn bộ backend.
Tất cả đường dẫn thư mục storage được khai báo tại đây, không hardcode rải rác trong code.
"""
from pathlib import Path
from pydantic_settings import BaseSettings

BASE_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    app_name: str = "Audio AI Suite"
    secret_key: str = "CHANGE_ME_IN_PRODUCTION_ENV"  # nạp từ biến môi trường khi deploy
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 60 * 12

    base_dir: Path = BASE_DIR
    storage_dir: Path = BASE_DIR / "storage"
    uploads_dir: Path = BASE_DIR / "storage" / "uploads"
    outputs_dir: Path = BASE_DIR / "storage" / "outputs"
    models_dir: Path = BASE_DIR / "models"
    logs_dir: Path = BASE_DIR / "storage" / "logs"
    jobs_dir: Path = BASE_DIR / "storage" / "jobs"
    temp_dir: Path = BASE_DIR / "storage" / "temp"

    allowed_extensions: set[str] = {".mp3", ".wav", ".flac", ".ogg", ".m4a"}
    max_upload_size_mb: int = 200

    # Giới hạn tài nguyên — quan trọng khi chạy trên môi trường RAM thấp (vd Railway Trial).
    # Phân tích chỉ xử lý tối đa N giây đầu bài hát để tránh OOM với bài quá dài.
    max_analysis_seconds: int = 240
    analysis_sample_rate: int = 22050
    max_separation_seconds: int = 360  # Demucs nặng RAM hơn Music Analyzer
    job_queue_workers: int = 1  # chạy tuần tự để không cộng dồn RAM giữa các job nặng

    model_registry_file: Path = BASE_DIR / "models" / "registry.json"
    users_file: Path = BASE_DIR / "backend" / "core" / "users.json"
    jobs_db_file: Path = BASE_DIR / "storage" / "jobs" / "jobs.json"
    torch_cache_dir: Path = BASE_DIR / "models" / "torch_cache"

    class Config:
        env_prefix = "AAS_"


settings = Settings()

for d in [
    settings.uploads_dir,
    settings.outputs_dir,
    settings.models_dir,
    settings.logs_dir,
    settings.jobs_dir,
    settings.temp_dir,
    settings.torch_cache_dir,
]:
    d.mkdir(parents=True, exist_ok=True)

# Demucs/torch.hub tải trọng số model về $TORCH_HOME/hub/checkpoints.
# Trỏ vào models/torch_cache để weights nằm trong Volume (nếu admin gắn Volume vào /app/models),
# không bị mất khi Railway redeploy.
import os  # noqa: E402
os.environ.setdefault("TORCH_HOME", str(settings.torch_cache_dir))
