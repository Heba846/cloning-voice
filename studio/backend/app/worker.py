"""Tiny in-process job queue (thread pool + SQLite). Enough for a single-server launch;
swap for Celery/RQ + Redis when you scale to several GPU workers."""
from __future__ import annotations

import logging
import queue
import threading
from datetime import datetime, timezone

from .config import settings
from .db import SessionLocal
from .models import Job, User
from .services import credits
from .services.pipeline import RUNNERS

log = logging.getLogger("sawtak.worker")
_q: "queue.Queue[str]" = queue.Queue()
_started = False


def enqueue(job_id: str) -> None:
    _q.put(job_id)


def _run(job_id: str) -> None:
    db = SessionLocal()
    try:
        job = db.get(Job, job_id)
        if not job or job.status != "queued":
            return
        job.status, job.progress = "running", 0.02
        db.commit()
        try:
            out = RUNNERS[job.kind](job, db)
            job.output_path, job.status, job.progress, job.message = str(out), "done", 1.0, "تم ✓"
        except Exception as e:  # noqa: BLE001
            log.exception("job %s failed", job_id)
            job.status, job.message = "failed", str(e)[:500]
            if job.credits_cost:
                credits.refund(db, db.get(User, job.user_id), job.credits_cost, job.id)
        job.finished_at = datetime.now(timezone.utc)
        db.commit()
    finally:
        db.close()


def _loop() -> None:
    while True:
        job_id = _q.get()
        try:
            _run(job_id)
        finally:
            _q.task_done()


def start() -> None:
    global _started
    if _started:
        return
    _started = True
    # re-queue anything left over from a previous process
    db = SessionLocal()
    try:
        for job in db.query(Job).filter(Job.status.in_(["queued", "running"])).all():
            job.status = "queued"
            db.commit()
            _q.put(job.id)
    finally:
        db.close()
    for i in range(settings.WORKER_THREADS):
        threading.Thread(target=_loop, name=f"sawtak-worker-{i}", daemon=True).start()
