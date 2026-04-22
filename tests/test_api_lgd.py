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
    assert 0.0 <= body["average_lgd"] <= 1.0
    assert len(body["results"]) == 2
    for item in body["results"]:
        assert 0.0 <= item["lgd"] <= 1.0


def test_partially_unsecured_happy_path(client, sample_rows) -> None:
    response = client.post("/api/v1/lgd/partially-unsecured", json=sample_rows)
    assert response.status_code == status.HTTP_201_CREATED
    body = response.json()
    assert body["method"] == "partially_unsecured"
    assert body["count"] == 2


def test_empty_batch_rejected(client) -> None:
    response = client.post("/api/v1/lgd/fully-unsecured", json=[])
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


def test_invalid_payload_rejected(client) -> None:
    response = client.post(
        "/api/v1/lgd/fully-unsecured",
        json=[{"Year": "notanumber"}],
    )
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


def test_history_lists_previous_computations(client, sample_rows) -> None:
    client.post("/api/v1/lgd/fully-unsecured", json=sample_rows)
    client.post("/api/v1/lgd/partially-unsecured", json=sample_rows)

    response = client.get("/api/v1/lgd/history")
    assert response.status_code == status.HTTP_200_OK
    history = response.json()
    assert len(history) == 2
    methods = {entry["method"] for entry in history}
    assert methods == {"fully_unsecured", "partially_unsecured"}


def test_history_filter_by_method(client, sample_rows) -> None:
    client.post("/api/v1/lgd/fully-unsecured", json=sample_rows)
    client.post("/api/v1/lgd/partially-unsecured", json=sample_rows)

    response = client.get(
        "/api/v1/lgd/history", params={"method": "fully_unsecured"}
    )
    assert response.status_code == status.HTTP_200_OK
    assert all(e["method"] == "fully_unsecured" for e in response.json())


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


def test_history_detail_not_found(client) -> None:
    response = client.get("/api/v1/lgd/history/987654")
    assert response.status_code == status.HTTP_404_NOT_FOUND


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
