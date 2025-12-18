
[![PyPI version](https://img.shields.io/pypi/v/keda_dispatcher.svg?cacheSeconds=60)](https://pypi.org/project/keda_dispatcher/)
[![License: Apache-2.0](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)
[![Python Version](https://img.shields.io/pypi/pyversions/keda_dispatcher.svg)](https://pypi.org/project/keda_dispatcher/)
[![PyPI Downloads](https://static.pepy.tech/badge/keda_dispatcher)](https://pepy.tech/projects/keda_dispatcher)
![CI](https://github.com/kevin-tofu/keda_dispatcher/actions/workflows/python-tests.yml/badge.svg)


# keda-dispatcher

Local dev setup with FastAPI/Redis/S3-compatible storage.

## Built-in routes

`create_app` always includes the built-in `/proc` routes (see `keda_dispatcher/api/proc.py`). Passing `extra_routers` just adds more routers on top; it does not remove the defaults.

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

## CI/CD

- Tests: `.github/workflows/test.yml` (runs on `main`/`dev` and PRs, matrix on Python 3.10–3.12, executes `poetry run pytest`)
- Publish: `.github/workflows/publish.yml` (runs on GitHub Releases published event; `poetry publish --build` to PyPI)
- Publishing needs a repo secret `PYPI_API_TOKEN` (a PyPI token like `pypi-AgENd...`)

Poetry installs use the classic `[tool.poetry.dependencies]` section (Python `>=3.10,<3.14`).

## Version bump helper

Update both `pyproject.toml` and `src/keda_dispatcher/__init__.py` in one go:

```bash
python scripts/bump_version.py 0.2.0
```

The script prints the before/after version values for each file.
