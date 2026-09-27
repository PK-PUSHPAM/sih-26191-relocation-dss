import pytest

fastapi = pytest.importorskip("fastapi")
from fastapi.testclient import TestClient

from src.api.app import app


def test_health():
    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_openapi_contains_versioned_routes():
    client = TestClient(app)
    paths = client.get("/openapi.json").json()["paths"]
    expected = {
        "/api/v1/admin-units",
        "/api/v1/habitations",
        "/api/v1/habitations/{habitation_id}",
        "/api/v1/hazards",
        "/api/v1/risk/map",
        "/api/v1/sites",
        "/api/v1/sites/{site_id}/capacity",
        "/api/v1/priorities",
        "/api/v1/optimize",
        "/api/v1/runs/{run_id}",
        "/api/v1/reports/{run_id}",
    }
    assert expected.issubset(paths)


def test_optimize_rejects_bad_distance_key():
    client = TestClient(app)
    payload = {
        "habitations": [{"habitation_id": "H1", "exposed_population": 10}],
        "sites": [{
            "site_id": "S1", "effective_capacity": 10, "hazard": 0,
            "feasible_habitations": ["H1"]
        }],
        "distances": {"bad-key": 10},
        "distance_weight": 1,
        "unmet_penalty": 100,
        "hazard_weight": 0,
    }
    assert client.post("/api/v1/optimize", json=payload).status_code == 422


def test_cors_allows_local_dashboard_origin():
    client = TestClient(app)
    response = client.options(
        "/health",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:3000"


def test_hazards_endpoint_matches_hazard_layer_schema():
    client = TestClient(app)
    response = client.get("/api/v1/hazards")
    assert response.status_code == 200
    payload = response.json()
    assert payload["items"] == []
