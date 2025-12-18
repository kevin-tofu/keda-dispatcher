import sys
from pathlib import Path

# Ensure src is importable when running tests
ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from keda_dispatcher.settings import Settings  # noqa: E402
from keda_dispatcher.services.proc import (  # noqa: E402
    create_process_meta,
    load_meta,
    save_json_to_r2_and_meta,
    kill_process,
    delete_process_data,
)
from keda_dispatcher.services.queue import enqueue_job  # noqa: E402


class FakeRedis:
    def __init__(self) -> None:
        self.store = {}
        self.lists = {}

    def hset(self, key, mapping=None, **kwargs):
        mapping = mapping or {}
        self.store.setdefault(key, {}).update(mapping)

    def hget(self, key, field):
        return self.store.get(key, {}).get(field)

    def hgetall(self, key):
        return self.store.get(key, {})

    def exists(self, key):
        return key in self.store

    def rpush(self, key, value):
        self.lists.setdefault(key, []).append(value)

    def delete(self, key):
        self.store.pop(key, None)


class FakeS3:
    def __init__(self) -> None:
        self.objects = {}

    def put_object(self, Bucket, Key, Body, ContentType, Metadata):
        self.objects[(Bucket, Key)] = {
            "Body": Body,
            "ContentType": ContentType,
            "Metadata": Metadata,
        }

    def delete_object(self, Bucket, Key):
        self.objects.pop((Bucket, Key), None)


def build_settings() -> Settings:
    return Settings(
        app_title="Test",
        app_version="0.0.1",
        enable_docs=False,
        root_path="",
        host="0.0.0.0",
        port=3333,
        workers=1,
        log_level="info",
        reload=False,
        redis_url="redis://localhost:6379/0",
        queue_key="queue:jobs",
        r2_endpoint_url="http://localhost:9000",
        r2_access_key_id="minioadmin",
        r2_secret_access_key="minioadmin",
        r2_bucket="proc-data",
    )


def test_service_end_to_end_flow():
    rds = FakeRedis()
    s3 = FakeS3()
    settings = build_settings()

    # 1) create process metadata
    create_res = create_process_meta(rds=rds)
    pid = create_res.process_id
    meta_key = f"proc:meta:{pid}"
    assert rds.exists(meta_key)
    assert rds.hget(meta_key, "status") == "created"

    # 2) upload JSON payload
    payload = {"message": "hello"}
    save_json_to_r2_and_meta(
        rds=rds,
        s3=s3,
        settings=settings,
        process_id=pid,
        payload=payload,
    )
    assert (settings.r2_bucket, f"proc/{pid}/input") in s3.objects
    assert rds.hget(meta_key, "status") == "uploaded"

    # 3) enqueue job
    enqueue_job(
        rds=rds,
        queue_key=settings.queue_key,
        process_id=pid,
        job_type="default",
        params={"x": 1},
    )
    assert settings.queue_key in rds.lists
    assert len(rds.lists[settings.queue_key]) == 1

    # 4) load meta reflects queued status
    meta = load_meta(rds=rds, pid=pid)
    assert meta.status == "queued"
    assert meta.process_id == pid


def test_kill_process_sets_status():
    rds = FakeRedis()
    settings = build_settings()

    create_res = create_process_meta(rds=rds)
    pid = create_res.process_id
    kill_process(rds=rds, process_id=pid, reason="user requested")

    meta = load_meta(rds=rds, pid=pid)
    assert meta.status == "killed"
    assert meta.error == "user requested"


def test_delete_process_data_resets_meta_and_removes_object():
    rds = FakeRedis()
    s3 = FakeS3()
    settings = build_settings()

    create_res = create_process_meta(rds=rds)
    pid = create_res.process_id

    payload = {"message": "hello"}
    save_json_to_r2_and_meta(
        rds=rds,
        s3=s3,
        settings=settings,
        process_id=pid,
        payload=payload,
    )

    # Ensure object exists
    assert (settings.r2_bucket, f"proc/{pid}/input") in s3.objects

    meta = delete_process_data(
        rds=rds,
        s3=s3,
        settings=settings,
        process_id=pid,
    )

    assert meta.status == "deleted"
    assert meta.r2_key == ""
    assert meta.r2_bucket == ""
    assert (settings.r2_bucket, f"proc/{pid}/input") not in s3.objects
