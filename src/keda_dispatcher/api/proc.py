from __future__ import annotations


from fastapi import APIRouter, Body, Depends, File, UploadFile

from keda_dispatcher.deps import get_r2_client, get_redis, get_settings
from keda_dispatcher.schemas import ProcDataResponse, ProcStatusResponse, RunRequest, RunResponse
from keda_dispatcher.services.proc import (
    create_process_meta,
    load_meta,
    save_bytes_to_r2_and_meta,
    save_json_to_r2_and_meta,
    delete_process,
)
from keda_dispatcher.services.queue import enqueue_job
from keda_dispatcher.settings import Settings


router = APIRouter(prefix="/proc", tags=["proc"])


@router.post("/", response_model=ProcDataResponse)
def proc_data_create(
    rds=Depends(get_redis),
):
    return create_process_meta(rds=rds)


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
