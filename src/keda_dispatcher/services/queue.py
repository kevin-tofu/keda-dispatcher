from __future__ import annotations
import json
from dataclasses import asdict
from fastapi import HTTPException
from keda_dispatcher.schemas import RunResponse, JobMessage
from keda_dispatcher.services.proc import meta_key, now_iso

def enqueue_job(*, rds, queue_key: str, process_id: str, job_type: str, params) -> RunResponse:
    pid = process_id
    if not rds.exists(meta_key(pid)):
        raise HTTPException(status_code=404, detail="process_id not found (upload first)")

    job = JobMessage(
        process_id=pid,
        job_type=job_type,
        params=params or {},
        enqueued_at=now_iso(),
        r2_bucket=rds.hget(meta_key(pid), "r2_bucket") or "",
        r2_key=rds.hget(meta_key(pid), "r2_key") or "",
    )

    rds.rpush(queue_key, json.dumps(asdict(job), ensure_ascii=False))
    rds.hset(meta_key(pid), mapping={"status": "queued", "updated_at": now_iso()})

    return RunResponse(enqueued=True, process_id=pid, queue_key=queue_key)
