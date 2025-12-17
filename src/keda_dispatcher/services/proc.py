from __future__ import annotations

import json
import uuid
from dataclasses import asdict
from datetime import datetime, timezone

from fastapi import HTTPException

from keda_dispatcher.schemas import ProcDataResponse, ProcStatusResponse
from keda_dispatcher.settings import Settings


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def meta_key(pid: str) -> str:
    return f"proc:meta:{pid}"


def r2_object_key(pid: str) -> str:
    return f"proc/{pid}/input"


def create_process_meta(*, rds) -> ProcDataResponse:
    pid = str(uuid.uuid4())

    meta = ProcStatusResponse(
        process_id=pid,
        status="created",
        created_at=now_iso(),
        updated_at=now_iso(),
        content_type="",
        original_filename="",
        r2_bucket="",
        r2_key="",
        error="",
    )

    key = meta_key(pid)
    if rds.exists(key):
        raise HTTPException(status_code=409, detail="process_id already exists")

    rds.hset(key, mapping=asdict(meta))
    return ProcDataResponse(process_id=pid)


def save_bytes_to_r2_and_meta(
    *,
    rds,
    s3,
    settings: Settings,
    process_id: str,
    data: bytes,
    content_type: str,
    original_filename: str,
) -> ProcDataResponse:
    """
    既存 process_id に対してデータをR2へ保存し、メタを uploaded に更新する。
    """
    key = meta_key(process_id)
    if not rds.exists(key):
        raise HTTPException(status_code=404, detail="process_id not found")

    bucket = settings.r2_bucket
    r2_key = r2_object_key(process_id)

    try:
        s3.put_object(
            Bucket=bucket,
            Key=r2_key,
            Body=data,
            ContentType=content_type or "application/octet-stream",
            Metadata={"original_filename": original_filename or ""},
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"failed to upload to R2: {e}")

    rds.hset(
        key,
        mapping={
            "status": "uploaded",
            "updated_at": now_iso(),
            "content_type": content_type or "",
            "original_filename": original_filename or "",
            "r2_bucket": bucket,
            "r2_key": r2_key,
            "error": "",
        },
    )

    return ProcDataResponse(process_id=process_id)


def save_json_to_r2_and_meta(
    *,
    rds,
    s3,
    settings: Settings,
    process_id: str,
    payload,
) -> ProcDataResponse:
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    return save_bytes_to_r2_and_meta(
        rds=rds,
        s3=s3,
        settings=settings,
        process_id=process_id,
        data=body,
        content_type="application/json",
        original_filename="",
    )


def load_meta(*, rds, pid: str) -> ProcStatusResponse:
    key = meta_key(pid)
    if not rds.exists(key):
        raise HTTPException(status_code=404, detail="process_id not found")

    h = rds.hgetall(key)
    return ProcStatusResponse(**h)


def delete_process(
    *,
    rds,
    s3,
    settings: Settings,
    process_id: str,
) -> None:
    key = meta_key(process_id)

    if not rds.exists(key):
        raise HTTPException(status_code=404, detail="process_id not found")

    meta = rds.hgetall(key)
    status = meta.get("status", "")

    if status in {"queued", "running"}:
        raise HTTPException(
            status_code=409,
            detail=f"cannot delete process in status '{status}'",
        )

    # R2 object 削除（存在しなくてもOK）
    bucket = meta.get("r2_bucket") or settings.r2_bucket
    r2_key = meta.get("r2_key")

    if bucket and r2_key:
        try:
            s3.delete_object(Bucket=bucket, Key=r2_key)
        except Exception:
            # delete は冪等にしたいので、基本は握りつぶす
            pass

    # Redis メタ削除
    rds.delete(key)
