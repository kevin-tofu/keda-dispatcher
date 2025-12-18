
[![PyPI version](https://img.shields.io/pypi/v/keda_dispatcher.svg?cacheSeconds=60)](https://pypi.org/project/keda_dispatcher/)
[![License: Apache-2.0](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)
[![Python Version](https://img.shields.io/pypi/pyversions/keda_dispatcher.svg)](https://pypi.org/project/keda_dispatcher/)
[![PyPI Downloads](https://static.pepy.tech/badge/keda_dispatcher)](https://pepy.tech/projects/keda_dispatcher)
![CI](https://github.com/kevin-tofu/keda_dispatcher/actions/workflows/python-tests.yml/badge.svg)


# keda-dispatcher

Local dev setup with FastAPI/Redis/S3-compatible storage.

## Built-in routes

`create_app` always includes the built-in `/proc` routes (see `keda_dispatcher/api/proc.py`). Passing `extra_routers` just adds more routers on top; it does not remove the defaults.

## Configuration (env vars)

These map directly to `keda_dispatcher.settings.Settings`:

| Env | Default | Notes |
| --- | --- | --- |
| APP_TITLE | ProcGate | API title |
| APP_VERSION | package `__version__` | API version |
| ENABLE_DOCS | false | Set to `true` to show Swagger/Redoc |
| ROOT_PATH | (empty) | Prefix for reverse proxies (e.g. `/api`) |
| HOST | 0.0.0.0 | Uvicorn host |
| PORT | 8080 | Uvicorn port |
| WORKERS | 1 | Uvicorn workers |
| LOG_LEVEL | info | Uvicorn log level |
| RELOAD | false | Uvicorn reload flag |
| REDIS_URL | redis://localhost:6379/0 | **Required** |
| QUEUE_KEY | queue:jobs | Redis list key for jobs |
| R2_ENDPOINT_URL | (empty) | Cloudflare R2 endpoint |
| R2_ACCESS_KEY_ID | (empty) | R2 access key |
| R2_SECRET_ACCESS_KEY | (empty) | R2 secret key |
| R2_BUCKET | proc-data | R2 bucket |
| EXTRA_API_MODULES | (empty) | Comma-separated `pkg.module:router_or_factory` list |

CLI flags (e.g. `--host`, `--port`, `--workers`, `--log-level`, `--reload`, `--extra-router`) override env values at startup.

## Adding external APIs (APIRouter)

Pass routers via CLI (no env needed):

```bash
poetry run keda-dispatcher \
  --extra-router myapp.extra:router \
  --extra-router myapp.health:get_router \
  --host 0.0.0.0 --port 8080
```

- `router_or_factory` can be an `APIRouter` instance or a zero-arg factory returning one.
- `--extra-router` is repeatable; values are passed to `create_app` as `extra_routers`.

### Example: start from an external script `__main__`

Minimal `__main__` that injects extra routers and runs uvicorn:

```python
# myservice/__main__.py
import uvicorn
from keda_dispatcher.settings import Settings
from keda_dispatcher.app_factory import create_app
from myapp.api import router as custom_router
from myapp.health import get_router

def main():
    settings = Settings.from_env()
    extra = [custom_router, get_router()]
    app = create_app(settings, extra_routers=extra)

    uvicorn.run(app, host=settings.host, port=settings.port, reload=settings.reload)

if __name__ == "__main__":
    main()
```

Run:
```bash
python -m myservice
```

### Quick demo

Run:

```bash
bash run_demo.sh
```

Details and code live in `tutorials/external_api.md`, `tutorials/custom_api.py`, `tutorials/health.py`, and `run_demo.sh`.

## Data handling and lifecycle

- `POST /proc/` — issue a `process_id` and store metadata in Redis (`status=created`).
- `GET /proc/` — list processes; optional `status` filter.
- `PUT /proc/{id}/data` or `/data/json` — upload bytes/JSON to R2 at `proc/{id}/input`; metadata becomes `uploaded`.
- `POST /proc/{id}/run` — enqueue a job into Redis list `QUEUE_KEY` (default `queue:jobs`); metadata becomes `queued`.
- `DELETE /proc/{id}/queue` — remove a queued job for this `process_id` from Redis and reset status (`uploaded` if data exists, otherwise `created`).
- `GET /proc/{id}/status` — returns Redis metadata (status, timestamps, r2_key, etc.).
- `DELETE /proc/{id}/data` — delete R2 object `proc/{id}/input` and reset metadata (`status=deleted`, r2_key/bucket cleared). Process ID remains.
- `DELETE /proc/{id}/kill` — mark metadata as `killed` (does not remove queue entries; workers should honor status).
- `DELETE /proc/{id}` — remove R2 object (if present) and delete metadata from Redis. Fails if status is `queued` or `running`.
- `GET /proc/healthz` — health check (Redis ping; R2 connectivity if configured).

Note: both binary and JSON uploads share the same R2 key `proc/{id}/input`, so `/data` deletion removes either.

## Architecture (Mermaid)

```mermaid
flowchart LR
    client((Client))
    api["FastAPI /proc (keda-dispatcher)"]
    redis["Redis meta + queue"]
    r2["Cloudflare R2 proc/{id}/input"]
    worker["Worker (your impl)"]
    keda["KEDA ScaledObject (Redis scaler)"]

    client --> api
    api -->|metadata| redis
    api -->|enqueue| redis
    api -->|upload| r2

    redis <-. monitor .-> keda
    keda -->|scale| worker
    worker -->|dequeue/process| redis
    worker -->|read input| r2
    worker -->|update status| redis
```

## KEDA ScaledObject example

See `k8s/keda-scaledobject.yaml` for a Redis scaler sample. Key points:
- `listName` must match `QUEUE_KEY` (default `queue:jobs`).
- `address` should point to your Redis service (e.g., `redis.default.svc.cluster.local:6379`).
- If Redis auth is enabled, set `usernameFromEnv` / `passwordFromEnv` env vars on the worker Deployment and uncomment in the ScaledObject.
- `scaleTargetRef.name` should be the Deployment that dequeues jobs.

## CI/CD

- Tests: `.github/workflows/test.yml` (runs on `main`/`dev` and PRs, matrix on Python 3.10–3.12, executes `poetry run pytest`)
- Publish: `.github/workflows/publish.yml` (runs on GitHub Releases published event; `poetry publish --build` to PyPI)
- Publishing needs a repo secret `PYPI_API_TOKEN` (a PyPI token like `pypi-AgENd...`). If the token is missing, publish is skipped with a log message.
