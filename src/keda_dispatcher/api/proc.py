from __future__ import annotations


from fastapi import APIRouter, Body, Depends, File, UploadFile

from keda_dispatcher.deps import get_r2_client, get_redis, get_settings
from keda_dispatcher.schemas import ProcDataResponse, ProcStatusResponse, RunRequest, RunResponse, HealthStatus
from keda_dispatcher.services.proc import (
    create_process_meta,
    load_meta,
    save_bytes_to_r2_and_meta,
    save_json_to_r2_and_meta,
    delete_process,
    kill_process,
    delete_process_data,
    list_processes,
)
from keda_dispatcher.services.queue import enqueue_job, remove_job_from_queue
from keda_dispatcher.settings import Settings
import boto3
from botocore.config import Config
from botocore.exceptions import BotoCoreError


router = APIRouter(prefix="/proc", tags=["proc"])


@router.post("/", response_model=ProcDataResponse)
def proc_data_create(
    rds=Depends(get_redis),
):
    return create_process_meta(rds=rds)


@router.get("/", response_model=list[ProcStatusResponse])
def proc_list(
    status: str | None = None,
    rds=Depends(get_redis),
):
    return list_processes(rds=rds, status=status)


@router.put("/{process_id}/data", response_model=ProcDataResponse)
async def proc_data_put(
    process_id: str,
    file: UploadFile = File(...),
    rds=Depends(get_redis),
    s3=Depends(get_r2_client),
    settings: Settings = Depends(get_settings),
):
    data = await file.read()
    return save_bytes_to_r2_and_meta(
        rds=rds,
        s3=s3,
        settings=settings,
        process_id=process_id,
        data=data,
        content_type=file.content_type or "application/octet-stream",
        original_filename=file.filename or "",
    )


@router.put("/{process_id}/data/json", response_model=ProcDataResponse)
async def proc_data_put_json(
    process_id: str,
    payload: dict = Body(...),
    rds=Depends(get_redis),
    s3=Depends(get_r2_client),
    settings: Settings = Depends(get_settings),
):
    return save_json_to_r2_and_meta(
        rds=rds,
        s3=s3,
        settings=settings,
        process_id=process_id,
        payload=payload,
    )


@router.post("/{process_id}/run", response_model=RunResponse)
def proc_run(
    process_id: str,
    req: RunRequest,
    rds=Depends(get_redis),
    settings: Settings = Depends(get_settings),
):
    return enqueue_job(
        rds=rds,
        queue_key=settings.queue_key,
        process_id=process_id,
        job_type=req.job_type,
        params=req.params,
    )


@router.delete("/{process_id}/queue", response_model=RunResponse)
def proc_queue_delete(
    process_id: str,
    rds=Depends(get_redis),
    settings: Settings = Depends(get_settings),
):
    """
    Remove the job for this process_id from the Redis queue (if present) and reset status.
    """
    return remove_job_from_queue(
        rds=rds,
        settings=settings,
        process_id=process_id,
    )


@router.get("/{process_id}/status", response_model=ProcStatusResponse)
def proc_status(
    process_id: str,
    rds=Depends(get_redis),
):
    return load_meta(rds=rds, pid=process_id)


@router.delete("/{process_id}", status_code=204)
def proc_data_delete(
    process_id: str,
    rds=Depends(get_redis),
    s3=Depends(get_r2_client),
    settings: Settings = Depends(get_settings),
):
    delete_process(
        rds=rds,
        s3=s3,
        settings=settings,
        process_id=process_id,
    )


@router.delete("/{process_id}/data", response_model=ProcStatusResponse)
def proc_data_delete_only(
    process_id: str,
    rds=Depends(get_redis),
    s3=Depends(get_r2_client),
    settings: Settings = Depends(get_settings),
):
    """
    Delete uploaded data in R2 and reset metadata (status=deleted). Does not remove the process itself.
    """
    return delete_process_data(
        rds=rds,
        s3=s3,
        settings=settings,
        process_id=process_id,
    )


@router.delete("/{process_id}/kill", response_model=ProcStatusResponse)
def proc_kill(
    process_id: str,
    reason: str | None = None,
    rds=Depends(get_redis),
    settings: Settings = Depends(get_settings),
    remove_from_queue: bool = True,
):
    """
    Mark a process as killed (status="killed"). By default also removes the queued job (if present).
    """
    return kill_process(
        rds=rds,
        settings=settings,
        process_id=process_id,
        reason=reason,
        remove_from_queue=remove_from_queue,
    )


@router.get("/healthz", response_model=HealthStatus)
def proc_healthz(
    settings: Settings = Depends(get_settings),
):
    # Redis: simple ping
    redis_ok = False
    try:
        rds = get_redis(settings)  # type: ignore
        redis_ok = bool(rds.ping())
    except Exception:
        redis_ok = False

    # R2: only check if configured
    r2_ok: bool | None = None
    if settings.r2_endpoint_url and settings.r2_access_key_id and settings.r2_secret_access_key:
        try:
            s3 = boto3.client(
                "s3",
                endpoint_url=settings.r2_endpoint_url,
                aws_access_key_id=settings.r2_access_key_id,
                aws_secret_access_key=settings.r2_secret_access_key,
                config=Config(signature_version="s3v4"),
                region_name="auto",
            )
            s3.list_buckets()
            r2_ok = True
        except Exception:
            r2_ok = False

    return HealthStatus(redis_ok=redis_ok, r2_ok=r2_ok)
