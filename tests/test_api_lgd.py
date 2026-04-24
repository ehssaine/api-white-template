from __future__ import annotations

from fastapi import status

from tests._xlsx_factory import build_xlsx, default_scenario_sheets

_XLSX_CT = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def _upload(client, path: str, xlsx_bytes: bytes, filename: str = "scenarios.xlsx"):
    return client.post(
        path,
        files={"file": (filename, xlsx_bytes, _XLSX_CT)},
    )


def test_health_endpoint(client) -> None:
    response = client.get("/api/v1/health")
    assert response.status_code == status.HTTP_200_OK
    body = response.json()
    assert body["status"] == "ok"
    assert "version" in body


def test_fully_unsecured_accepts_xlsx_upload(client) -> None:
    xlsx = build_xlsx(default_scenario_sheets())
    response = _upload(client, "/api/v1/lgd/fully-unsecured", xlsx)
    assert response.status_code == status.HTTP_201_CREATED, response.text
    body = response.json()
    assert body["method"] == "fully_unsecured"
    assert body["count"] == 3  # 2 rows from MS01 + 1 from MS02
    assert body["average_lgd"] == 0.6
    for item in body["results"]:
        assert item["lgd"] == 0.6
        assert "recovery_rate" in item
        assert item["Year"] == 2023


def test_partially_unsecured_accepts_xlsx_upload(client) -> None:
    xlsx = build_xlsx(default_scenario_sheets())
    response = _upload(client, "/api/v1/lgd/partially-unsecured", xlsx)
    assert response.status_code == status.HTTP_201_CREATED
    body = response.json()
    assert body["method"] == "partially_unsecured"
    assert body["count"] == 3
    assert body["average_lgd"] == 0.3


def test_non_xlsx_filename_rejected(client) -> None:
    response = client.post(
        "/api/v1/lgd/fully-unsecured",
        files={"file": ("scenarios.csv", b"irrelevant", "text/csv")},
    )
    assert response.status_code == status.HTTP_415_UNSUPPORTED_MEDIA_TYPE


def test_empty_file_rejected(client) -> None:
    response = _upload(client, "/api/v1/lgd/fully-unsecured", b"")
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


def test_corrupt_xlsx_rejected_with_422(client) -> None:
    response = _upload(client, "/api/v1/lgd/fully-unsecured", b"not a real xlsx")
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
    assert "Failed to read XLSX" in response.text


def test_xlsx_without_scenario_sheet_rejected(client) -> None:
    xlsx = build_xlsx(
        {
            "Summary": [
                {"Year": 2023, "Year_proj": 2024, "Shif": 1, "macro_a": 1.0}
            ]
        }
    )
    response = _upload(client, "/api/v1/lgd/fully-unsecured", xlsx)
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
    assert "No scenario sheets" in response.text


def test_torsion_factors_still_accepts_json(client) -> None:
    payload = [
        {
            "Year": 2023,
            "Year_proj": 2024,
            "Shif": 1,
            "macro_vars": [
                {"name": "gov_eur_10y_raw", "value": 3.25},
                {"name": "dji_index_Var_lag_fut", "value": 0.015},
            ],
        }
    ]
    response = client.post("/api/v1/lgd/torsion-factors", json=payload)
    assert response.status_code == status.HTTP_201_CREATED
    body = response.json()
    assert body["method"] == "torsion_factors"
    assert body["results"][0]["torsion_factor"] == 0.1


def test_history_lists_previous_computations(client) -> None:
    xlsx = build_xlsx(default_scenario_sheets())
    _upload(client, "/api/v1/lgd/fully-unsecured", xlsx)
    _upload(client, "/api/v1/lgd/partially-unsecured", xlsx)

    response = client.get("/api/v1/lgd/history")
    assert response.status_code == status.HTTP_200_OK
    history = response.json()
    assert len(history) == 2
    methods = {entry["method"] for entry in history}
    assert methods == {"fully_unsecured", "partially_unsecured"}


def test_history_filter_by_method(client) -> None:
    xlsx = build_xlsx(default_scenario_sheets())
    _upload(client, "/api/v1/lgd/fully-unsecured", xlsx)
    _upload(client, "/api/v1/lgd/partially-unsecured", xlsx)

    response = client.get(
        "/api/v1/lgd/history", params={"method": "partially_unsecured"}
    )
    assert response.status_code == status.HTTP_200_OK
    body = response.json()
    assert len(body) == 1
    assert body[0]["method"] == "partially_unsecured"


def test_history_detail_returns_rows(client) -> None:
    xlsx = build_xlsx(default_scenario_sheets())
    created = _upload(client, "/api/v1/lgd/fully-unsecured", xlsx).json()
    cid = created["computation_id"]

    response = client.get(f"/api/v1/lgd/history/{cid}")
    assert response.status_code == status.HTTP_200_OK
    body = response.json()
    assert body["computation_id"] == cid
    assert body["count"] == 3
    assert len(body["results"]) == 3
    assert body["results"][0]["lgd"] == 0.6


def test_history_detail_not_found(client) -> None:
    response = client.get("/api/v1/lgd/history/987654")
    assert response.status_code == status.HTTP_404_NOT_FOUND


def test_library_failure_returns_502(client) -> None:
    from app.api.deps import get_lgd_service
    from app.services.lgd import LgdService
    from app.services.lgd_forward_looking import LgdForwardLookingAdapter

    class _Boom:
        def compute_lgd_fully_unsecured(self, df):  # noqa: ARG002
            raise RuntimeError("library exploded")

        def compute_lgd_partially_unsecured(self, df):  # noqa: ARG002
            raise RuntimeError("nope")

        def compute_torsion_factors(self, df):  # noqa: ARG002
            raise RuntimeError("nope")

    boom_service = LgdService(adapter=LgdForwardLookingAdapter(module=_Boom()))

    app = client.app
    app.dependency_overrides[get_lgd_service] = lambda: boom_service
    try:
        xlsx = build_xlsx(default_scenario_sheets())
        response = _upload(client, "/api/v1/lgd/fully-unsecured", xlsx)
        assert response.status_code == status.HTTP_502_BAD_GATEWAY
        assert "library exploded" in response.text
    finally:
        app.dependency_overrides.pop(get_lgd_service, None)


def test_batch_size_enforced(client) -> None:
    from app.core.config import Settings, get_settings

    app = client.app
    app.dependency_overrides[get_settings] = lambda: Settings(
        environment="test", max_batch_size=1
    )
    try:
        xlsx = build_xlsx(default_scenario_sheets())
        response = _upload(client, "/api/v1/lgd/fully-unsecured", xlsx)
        assert response.status_code == status.HTTP_413_REQUEST_ENTITY_TOO_LARGE
    finally:
        app.dependency_overrides.pop(get_settings, None)
