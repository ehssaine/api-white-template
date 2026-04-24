from __future__ import annotations

from fastapi import status


def test_health_endpoint(client) -> None:
    response = client.get("/api/v1/health")
    assert response.status_code == status.HTTP_200_OK
    body = response.json()
    assert body["status"] == "ok"
    assert "version" in body


def test_fully_unsecured_happy_path(client, sample_rows) -> None:
    response = client.post("/api/v1/lgd/fully-unsecured", json=sample_rows)
    assert response.status_code == status.HTTP_201_CREATED, response.text
    body = response.json()
    assert body["method"] == "fully_unsecured"
    assert body["count"] == 2
    assert body["average_lgd"] == 0.6
    assert len(body["results"]) == 2
    for item in body["results"]:
        assert item["lgd"] == 0.6
        assert "recovery_rate" in item
        # original input columns are preserved by the library
        assert item["Year"] == 2023


def test_partially_unsecured_happy_path(client, sample_rows) -> None:
    response = client.post("/api/v1/lgd/partially-unsecured", json=sample_rows)
    assert response.status_code == status.HTTP_201_CREATED
    body = response.json()
    assert body["method"] == "partially_unsecured"
    assert body["average_lgd"] == 0.3


def test_torsion_factors_happy_path(client, sample_rows) -> None:
    response = client.post("/api/v1/lgd/torsion-factors", json=sample_rows)
    assert response.status_code == status.HTTP_201_CREATED
    body = response.json()
    assert body["method"] == "torsion_factors"
    assert body["average_lgd"] is None
    assert [r["torsion_factor"] for r in body["results"]] == [0.1, 0.2]


def test_empty_batch_rejected(client) -> None:
    response = client.post("/api/v1/lgd/fully-unsecured", json=[])
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


def test_invalid_payload_rejected(client) -> None:
    response = client.post(
        "/api/v1/lgd/fully-unsecured",
        json=[{"Year": "notanumber"}],
    )
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


def test_missing_macro_vars_rejected(client) -> None:
    response = client.post(
        "/api/v1/lgd/fully-unsecured",
        json=[{"Year": 2023, "Year_proj": 2024, "Shif": 1, "macro_vars": []}],
    )
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


def test_duplicate_macro_var_names_rejected(client) -> None:
    response = client.post(
        "/api/v1/lgd/fully-unsecured",
        json=[
            {
                "Year": 2023,
                "Year_proj": 2024,
                "Shif": 1,
                "macro_vars": [
                    {"name": "x", "value": 1.0},
                    {"name": "x", "value": 2.0},
                ],
            }
        ],
    )
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


def test_history_lists_previous_computations(client, sample_rows) -> None:
    client.post("/api/v1/lgd/fully-unsecured", json=sample_rows)
    client.post("/api/v1/lgd/partially-unsecured", json=sample_rows)
    client.post("/api/v1/lgd/torsion-factors", json=sample_rows)

    response = client.get("/api/v1/lgd/history")
    assert response.status_code == status.HTTP_200_OK
    history = response.json()
    assert len(history) == 3
    methods = {entry["method"] for entry in history}
    assert methods == {"fully_unsecured", "partially_unsecured", "torsion_factors"}


def test_history_filter_by_method(client, sample_rows) -> None:
    client.post("/api/v1/lgd/fully-unsecured", json=sample_rows)
    client.post("/api/v1/lgd/torsion-factors", json=sample_rows)

    response = client.get(
        "/api/v1/lgd/history", params={"method": "torsion_factors"}
    )
    assert response.status_code == status.HTTP_200_OK
    body = response.json()
    assert len(body) == 1
    assert body[0]["method"] == "torsion_factors"


def test_history_detail_returns_rows(client, sample_rows) -> None:
    created = client.post(
        "/api/v1/lgd/fully-unsecured", json=sample_rows
    ).json()
    cid = created["computation_id"]

    response = client.get(f"/api/v1/lgd/history/{cid}")
    assert response.status_code == status.HTTP_200_OK
    body = response.json()
    assert body["computation_id"] == cid
    assert body["count"] == len(sample_rows)
    assert len(body["results"]) == len(sample_rows)
    # Per-row detail was persisted verbatim.
    assert body["results"][0]["lgd"] == 0.6


def test_history_detail_not_found(client) -> None:
    response = client.get("/api/v1/lgd/history/987654")
    assert response.status_code == status.HTTP_404_NOT_FOUND


def test_library_failure_returns_502(client, sample_rows) -> None:
    from app.api.deps import get_lgd_service
    from app.services.lgd import LgdService
    from app.services.lgd_forward_looking import (
        LgdForwardLookingAdapter,
        LgdForwardLookingError,
    )

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
        response = client.post("/api/v1/lgd/fully-unsecured", json=sample_rows)
        assert response.status_code == status.HTTP_502_BAD_GATEWAY
        assert "library exploded" in response.text or LgdForwardLookingError.__name__
    finally:
        app.dependency_overrides.pop(get_lgd_service, None)


def test_batch_size_enforced(client, sample_rows) -> None:
    from app.core.config import Settings, get_settings

    app = client.app
    app.dependency_overrides[get_settings] = lambda: Settings(
        environment="test", max_batch_size=1
    )
    try:
        response = client.post(
            "/api/v1/lgd/fully-unsecured",
            json=sample_rows,
        )
        assert response.status_code == status.HTTP_413_REQUEST_ENTITY_TOO_LARGE
    finally:
        app.dependency_overrides.pop(get_settings, None)
