"""
Job Queue: không xử lý request trực tiếp trong request handler.
Mọi tác vụ nặng (separate, analyze) được đẩy vào queue và xử lý bởi worker chạy nền.
Lưu trạng thái job vào jobs.json (flat-file) để admin xem lịch sử / GET /job/{id} tra cứu được.
"""
import json
import queue
import threading
import uuid
from datetime import datetime
from enum import Enum
from typing import Callable, Optional

from pydantic import BaseModel

from backend.config import settings
from backend.core.logger import get_logger

logger = get_logger("job_queue")


class JobStatus(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"


class Job(BaseModel):
    id: str
    user: str
    file: str
    model: str
    job_type: str
    status: JobStatus = JobStatus.QUEUED
    progress: int = 0
    created_time: str
    finished_time: Optional[str] = None
    result: Optional[dict] = None
    error: Optional[str] = None


class JobQueue:
    def __init__(self, num_workers: int = 2):
        self._q: "queue.Queue[tuple[Job, Callable]]" = queue.Queue()
        self._jobs: dict[str, Job] = self._load()
        self._lock = threading.Lock()
        self._workers = [
            threading.Thread(target=self._worker_loop, daemon=True) for _ in range(num_workers)
        ]
        for w in self._workers:
            w.start()

    def _load(self) -> dict[str, Job]:
        path = settings.jobs_db_file
        if not path.exists():
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("{}", encoding="utf-8")
            return {}
        raw = json.loads(path.read_text(encoding="utf-8"))
        return {k: Job(**v) for k, v in raw.items()}

    def _persist(self):
        with self._lock:
            data = {k: v.model_dump() for k, v in self._jobs.items()}
            settings.jobs_db_file.write_text(
                json.dumps(data, indent=2, ensure_ascii=False, default=str), encoding="utf-8"
            )

    def submit(self, user: str, file: str, model: str, job_type: str, handler: Callable) -> Job:
        job = Job(
            id=str(uuid.uuid4()),
            user=user,
            file=file,
            model=model,
            job_type=job_type,
            created_time=datetime.utcnow().isoformat(),
        )
        self._jobs[job.id] = job
        self._persist()
        self._q.put((job, handler))
        logger.info(f"Job {job.id} ({job_type}) đã được đưa vào queue bởi {user}")
        return job

    def get(self, job_id: str) -> Optional[Job]:
        return self._jobs.get(job_id)

    def list_all(self) -> list[Job]:
        return list(self._jobs.values())

    def _worker_loop(self):
        while True:
            job, handler = self._q.get()
            self._update(job.id, status=JobStatus.RUNNING, progress=1)
            try:
                result = handler(job, self._make_progress_cb(job.id))
                self._update(
                    job.id,
                    status=JobStatus.DONE,
                    progress=100,
                    result=result,
                    finished_time=datetime.utcnow().isoformat(),
                )
                logger.info(f"Job {job.id} hoàn thành")
            except Exception as e:
                self._update(
                    job.id,
                    status=JobStatus.FAILED,
                    error=str(e),
                    finished_time=datetime.utcnow().isoformat(),
                )
                logger.error(f"Job {job.id} lỗi: {e}")
            finally:
                self._q.task_done()

    def _make_progress_cb(self, job_id: str):
        def cb(percent: int):
            self._update(job_id, progress=percent)
        return cb

    def _update(self, job_id: str, **kwargs):
        job = self._jobs.get(job_id)
        if not job:
            return
        for k, v in kwargs.items():
            setattr(job, k, v)
        self._persist()


job_queue = JobQueue(num_workers=settings.job_queue_workers)
