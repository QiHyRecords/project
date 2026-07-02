import psutil

from backend.config import settings
from backend.core.model_registry import list_models
from backend.core.job_queue import job_queue, JobStatus


def get_system_stats() -> dict:
    disk = psutil.disk_usage(str(settings.base_dir))
    jobs = job_queue.list_all()
    return {
        "cpu_percent": psutil.cpu_percent(interval=0.3),
        "ram_percent": psutil.virtual_memory().percent,
        "ram_used_gb": round(psutil.virtual_memory().used / 1e9, 2),
        "ram_total_gb": round(psutil.virtual_memory().total / 1e9, 2),
        "disk_percent": disk.percent,
        "disk_used_gb": round(disk.used / 1e9, 2),
        "disk_total_gb": round(disk.total / 1e9, 2),
        "models_installed": len(list_models()),
        "jobs_running": len([j for j in jobs if j.status == JobStatus.RUNNING]),
        "jobs_completed": len([j for j in jobs if j.status == JobStatus.DONE]),
        "jobs_failed": len([j for j in jobs if j.status == JobStatus.FAILED]),
    }
