from __future__ import annotations
import json
from dataclasses import asdict
from fastapi import HTTPException
from keda_dispatcher.schemas import RunResponse, JobMessage
from keda_dispatcher.services.proc import meta_key, now_iso
from keda_dispatcher.settings import Settings

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


def remove_job_from_queue(
    *,
    rds,
    settings: Settings,
    process_id: str,
    update_status: bool = True,
    raise_if_missing: bool = True,
) -> RunResponse:
    pid = process_id
    key = meta_key(pid)
    if not rds.exists(key):
        raise HTTPException(status_code=404, detail="process_id not found")

    queue_key = settings.queue_key
    entries = rds.lrange(queue_key, 0, -1)
    removed = False
    for entry in entries:
        try:
            data = json.loads(entry)
        except Exception:
            continue
        if data.get("process_id") == pid:
            rds.lrem(queue_key, 1, entry)
            removed = True
            break

    if not removed:
        if raise_if_missing:
            raise HTTPException(status_code=404, detail="no queued job found for process_id")
        return RunResponse(enqueued=False, process_id=pid, queue_key=queue_key)

    if update_status:
        # Reset status to uploaded/created depending on meta content
        meta = rds.hgetall(key)
        new_status = "uploaded" if meta.get("r2_key") else "created"
        rds.hset(key, mapping={"status": new_status, "updated_at": now_iso()})

    return RunResponse(enqueued=False, process_id=pid, queue_key=queue_key)
