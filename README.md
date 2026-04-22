# api-white-template

Production-grade FastAPI service for computing **Loss Given Default (LGD)** on
the `ExcelInput` ingestion schema, persisting every computation into
PostgreSQL and exposing a history endpoint.

## Endpoints

| Method | Path                                    | Description                                     |
|--------|-----------------------------------------|-------------------------------------------------|
| POST   | `/api/v1/lgd/fully-unsecured`           | Compute LGD for a fully unsecured exposure.     |
| POST   | `/api/v1/lgd/partially-unsecured`       | Compute LGD for a partially secured exposure.   |
| GET    | `/api/v1/lgd/history`                   | List past computations (filter / paginate).     |
| GET    | `/api/v1/lgd/history/{computation_id}`  | Retrieve a past computation with per-row rows.  |
| GET    | `/api/v1/health`                        | Liveness + database probe.                      |

The two compute endpoints accept a **list** of `ExcelInput` records:

```json
[
  {
    "Year": 2023,
    "Year_proj": 2024,
    "Shif": 1,
    "gov_eur_10y_raw": 3.25,
    "dji_index_Var_lag_fut": 0.015
  }
]
```

Each call persists a parent `lgd_computations` row plus one
`lgd_computation_items` row per input, so the batch is always reconstructible
from `/lgd/history/{id}`.

## Architecture

```
app/
  api/v1/endpoints/   # FastAPI routers (health, lgd)
  core/               # config (pydantic-settings) and logging
  crud/               # SQLAlchemy data-access layer
  db/                 # engine, session, declarative Base
  models/             # ORM tables
  schemas/            # Pydantic request/response models
  services/           # pure LGD computation logic
  main.py             # FastAPI application factory
tests/                # pytest suite (SQLite in-memory, no Postgres needed)
```

## Running locally (Docker)

```bash
cp .env.example .env
docker compose up --build
```

The API is then available at `http://localhost:8000` and Swagger UI at
`http://localhost:8000/docs`.

## Running locally (venv)

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
export DATABASE_URL=postgresql+psycopg2://postgres:postgres@localhost:5432/lgd
uvicorn app.main:app --reload
```

## Tests

```bash
pip install -r requirements-dev.txt
pytest
```

Tests use an in-memory SQLite database via FastAPI dependency overrides, so
no PostgreSQL instance is required.

## LGD model

For each record the linear predictor

```
z = b0 + b_gov * gov_eur_10y_raw + b_dji * dji_index_Var_lag_fut + b_shift * Shif
```

is passed through a sigmoid to yield an unsecured LGD in `(0, 1)`. The
partial endpoint nets a collateral share against a fixed haircut:

```
LGD_partial = (1 - c) * LGD_unsecured + c * haircut
```

All coefficients live in `Settings` and can be tuned from environment
variables (see `.env.example`) without touching code.
