# api-white-template

Production-grade FastAPI service that wraps the **`lgd_forward_looking`**
Python library to compute Loss Given Default (fully and partially
unsecured) and torsion factors from a list of `ExcelInput` records.
Every call is persisted to PostgreSQL and can be replayed from the
history endpoints.

## Endpoints

| Method | Path                                    | Payload         | Description                                              |
|--------|-----------------------------------------|-----------------|----------------------------------------------------------|
| POST   | `/api/v1/lgd/fully-unsecured`           | `.xlsx` upload  | Delegates to `lgd_forward_looking.compute_lgd_fully_unsecured`.     |
| POST   | `/api/v1/lgd/partially-unsecured`       | `.xlsx` upload  | Delegates to `lgd_forward_looking.compute_lgd_partially_unsecured`. |
| POST   | `/api/v1/lgd/torsion-factors`           | JSON body       | Delegates to `lgd_forward_looking.compute_torsion_factors`.         |
| GET    | `/api/v1/lgd/history`                   | —               | List past computations (filter by method, paginated).    |
| GET    | `/api/v1/lgd/history/{computation_id}`  | —               | Retrieve a past computation (with DataFrame-as-JSON).    |
| GET    | `/api/v1/health`                        | —               | Liveness + database probe.                               |

### `ExcelInput` record

Every `ExcelInput` carries the fixed scenario columns plus an open-ended
list of macro-economic variables:

```json
{
  "Year": 2023,
  "Year_proj": 2024,
  "Shif": 1,
  "macro_vars": [
    {"name": "gov_eur_10y_raw", "value": 3.25},
    {"name": "dji_index_Var_lag_fut", "value": 0.015}
  ]
}
```

At the JSON → DataFrame boundary, each `macro_vars` entry is spread into
its own column named after `name`, so the library receives a DataFrame
shaped like `Year, Year_proj, Shif, gov_eur_10y_raw, dji_index_Var_lag_fut, ...`.
Records that omit a given variable get `NaN` for that column.

### XLSX upload format

`fully-unsecured` and `partially-unsecured` accept a `multipart/form-data`
upload with a single `file` field pointing at an `.xlsx` workbook.

* One sheet per scenario, named `MS01`, `MS02`, ... (sorted numerically).
* Every scenario sheet must have the fixed columns `Year`, `Year_proj`,
  `Shif`.
* Every other column is treated as a macro variable — its header becomes
  `MacroVar.name`, its cell value becomes `MacroVar.value`.
* Blank cells in macro columns are skipped for that row.
* Sheets whose name does not match `MS\d+` (e.g. `README`, `Summary`) are
  ignored.

Example with curl:

```bash
curl -X POST http://localhost:8000/api/v1/lgd/fully-unsecured \
  -F "file=@scenarios.xlsx"
```

The parser lives in `app/services/excel_parser.py` and returns a flat
`list[ExcelInput]` that the rest of the pipeline processes as before.

### JSON ↔ DataFrame boundary

The three library methods require `pandas.DataFrame` input and return
`pandas.DataFrame` output. The service layer (`app/services/lgd.py`) is
responsible for:

1. `rows_to_dataframe(payload)` — converts the JSON body into a DataFrame.
2. `adapter.compute_*(df)` — invokes the library via the thin adapter in
   `app/services/lgd_forward_looking.py`.
3. `dataframe_to_records(df)` — converts the DataFrame back to a
   JSON-serialisable list of records (NaN → null).

The result DataFrame (as records) is stored verbatim in the
`lgd_computations.result_json` column, so `GET /history/{id}` returns
exactly what the library produced.

## Architecture

```
app/
  api/v1/endpoints/          # FastAPI routers (health, lgd)
  core/                      # config (pydantic-settings) and logging
  crud/                      # SQLAlchemy data-access layer
  db/                        # engine, session, declarative Base
  models/                    # ORM tables (LgdComputation)
  schemas/                   # Pydantic request/response models
  services/
    excel_parser.py          # XLSX -> list[ExcelInput] (MS** sheets)
    lgd.py                   # JSON <-> DataFrame orchestration
    lgd_forward_looking.py   # adapter over the library
  main.py                    # FastAPI application factory
tests/                       # pytest suite; injects a fake library
```

## Running locally (Docker)

```bash
cp .env.example .env
docker compose up --build
```

Swagger UI: <http://localhost:8000/docs>.

## Running locally (venv)

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
export DATABASE_URL=postgresql+psycopg2://postgres:postgres@localhost:5432/lgd
uvicorn app.main:app --reload
```

`lgd_forward_looking` must be importable. In test / CI environments it
is substituted by an in-process fake (see `tests/_fake_lgd_forward_looking.py`)
that implements the same three methods.

## Tests

```bash
pip install -r requirements-dev.txt
pytest
```

Tests run against an in-memory SQLite database (via FastAPI dependency
overrides) and a fake `lgd_forward_looking` module installed in
`sys.modules` by the `conftest.py`, so no PostgreSQL or external library
is required.
