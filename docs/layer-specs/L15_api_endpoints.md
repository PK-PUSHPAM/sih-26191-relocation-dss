# L15 — FastAPI Integration Layer

**Status:** IMPLEMENTED — verification pending local full-suite re-run  
**Model:** `L15-fastapi-integration-1.0`

## Frozen API contract

All versioned routes use `/api/v1/...` and JSON keys are snake_case. GeoJSON responses use EPSG:4326 at the API boundary; analytical processing remains EPSG:32644.

Implemented endpoints:
- `GET /api/v1/admin-units`
- `GET /api/v1/habitations`
- `GET /api/v1/habitations/{habitation_id}`
- `GET /api/v1/hazards`
- `GET /api/v1/risk/map`
- `GET /api/v1/sites`
- `GET /api/v1/sites/{site_id}/capacity`
- `GET /api/v1/priorities`
- `POST /api/v1/optimize`
- `GET /api/v1/runs/{run_id}`
- `GET /api/v1/reports/{run_id}`

The endpoint set follows the L15 API architecture documented in `docs/ARCHITECTURE.md`.

## Boundaries

- L15 reads persisted analytical outputs through the existing SQLAlchemy/PostGIS session layer.
- L15 invokes the frozen L13 solver only for an explicit optimization request.
- L15 does not implement hazard/vulnerability/suitability/capacity/priority formulas.
- L15 does not perform migrations or write analytical results.
- PDF/Markdown report rendering remains a later L16 responsibility.
- GeoJSON is transformed to EPSG:4326 only for API delivery.

## Missing data / errors

- Missing database records return HTTP 404 where an individual resource is requested.
- Database connectivity/errors are not converted to fabricated empty analytical results.
- Invalid optimization payloads return HTTP 422.
- Missing distance for a declared feasible pair is rejected by L13 and surfaced as HTTP 422.

## Verification acceptance

- FastAPI app imports successfully.
- OpenAPI exposes all frozen L15 routes.
- Health endpoint returns service status.
- Invalid optimization payload shape is rejected.
- Full project suite must be rerun with FastAPI installed; otherwise L15 tests are skipped and L15 is not considered verified.
