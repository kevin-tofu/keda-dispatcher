from __future__ import annotations

import redis
import boto3
from botocore.config import Config
from fastapi import Depends

from keda_dispatcher.settings import Settings


def get_settings() -> Settings:
    """
    FastAPI dependency 用 Settings。
    server.py とは独立して、API層から参照できるようにする。
    """
    return Settings.from_env()


def get_redis(
    settings: Settings = Depends(get_settings),
) -> redis.Redis:
    return redis.Redis.from_url(
        settings.redis_url,
        decode_responses=True,
    )


def get_r2_client(
    settings: Settings = Depends(get_settings),
):
    if not (
        settings.r2_endpoint_url
        and settings.r2_access_key_id
        and settings.r2_secret_access_key
    ):
        raise RuntimeError("R2 env is not configured")

    return boto3.client(
        "s3",
        endpoint_url=settings.r2_endpoint_url,
        aws_access_key_id=settings.r2_access_key_id,
        aws_secret_access_key=settings.r2_secret_access_key,
        config=Config(signature_version="s3v4"),
        region_name="auto",
    )
