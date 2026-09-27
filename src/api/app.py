"""L15 FastAPI integration layer.

Routes expose persisted analytical outputs and the L13 optimization engine.
L15 performs no authoritative mathematical recalculation except invoking the
already-frozen L13 solver for an explicit optimization request.
"""
from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, Depends, FastAPI, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.orm import Session

from src.db.session import get_db
from src.optimization.l13 import CandidateSite, HabitationDemand, run_l13


API_VERSION = "1.0"
router = APIRouter(prefix="/api/v1")


def _db_session():
    with get_db() as session:
        yield session


def _geojson_rows(session: Session, sql: str, params: dict[str, Any]) -> dict[str, Any]:
    rows = session.execute(text(sql), params).mappings().all()
    features = []
    for row in rows:
        item = dict(row)
        geometry = item.pop("geometry", None)
        features.append({
            "type": "Feature",
            "geometry": geometry,
            "properties": item,
        })
    return {"type": "FeatureCollection", "features": features}


@router.get("/admin-units")
def admin_units(
    unit_type: Optional[str] = Query(default=None),
    session: Session = Depends(_db_session),
):
    sql = """
        SELECT unit_id, type, parent_id, name, code,
               ST_AsGeoJSON(ST_Transform(geom, 4326))::json AS geometry
        FROM admin_unit
        WHERE (:unit_type IS NULL OR type = :unit_type)
        ORDER BY name
    """
    return _geojson_rows(session, sql, {"unit_type": unit_type})


@router.get("/habitations")
def habitations(
    admin_unit_id: Optional[str] = Query(default=None),
    limit: int = Query(default=100, ge=1, le=1000),
    session: Session = Depends(_db_session),
):
    sql = """
        SELECT h.habitation_id, h.admin_unit_id, h.name, h.population,
               h.households, h.population_year,
               v.vulnerability, p.priority_score, p.tier,
               ST_AsGeoJSON(ST_Transform(h.geom, 4326))::json AS geometry
        FROM habitation h
        LEFT JOIN vulnerability v ON v.habitation_id = h.habitation_id
        LEFT JOIN priority p ON p.habitation_id = h.habitation_id
        WHERE (:admin_unit_id IS NULL OR h.admin_unit_id = :admin_unit_id)
        ORDER BY h.name
        LIMIT :limit
    """
    return _geojson_rows(session, sql, {"admin_unit_id": admin_unit_id, "limit": limit})


@router.get("/habitations/{habitation_id}")
def habitation_detail(habitation_id: str, session: Session = Depends(_db_session)):
    row = session.execute(text("""
        SELECT h.habitation_id, h.admin_unit_id, h.name, h.population,
               h.households, h.population_year,
               v.population_exposure, v.social_score, v.access_score,
               v.infra_score, v.recurrence_score, v.vulnerability,
               v.missing_data_penalty,
               p.risk, p.exposed_pop, p.vulnerability AS priority_vulnerability,
               p.response_difficulty, p.recurrence, p.priority_score, p.tier
        FROM habitation h
        LEFT JOIN vulnerability v ON v.habitation_id = h.habitation_id
        LEFT JOIN priority p ON p.habitation_id = h.habitation_id
        WHERE h.habitation_id = :id
    """), {"id": habitation_id}).mappings().first()
    if row is None:
        raise HTTPException(status_code=404, detail="habitation not found")
    return dict(row)


@router.get("/hazards")
def hazards(session: Session = Depends(_db_session)):
    rows = session.execute(text("""
        SELECT hazard_id, source_id, hazard_type, model_version,
               valid_from, valid_to, quality_flag, created_at
        FROM hazard_layer
        ORDER BY created_at DESC
    """)).mappings().all()
    return {"items": [dict(row) for row in rows]}


@router.get("/risk/map")
def risk_map(session: Session = Depends(_db_session)):
    sql = """
        SELECT cell_id, combined_risk, red_zone, risk_tier,
               ST_AsGeoJSON(ST_Transform(geom, 4326))::json AS geometry
        FROM risk_cell
        ORDER BY cell_id
    """
    return _geojson_rows(session, sql, {})


@router.get("/sites")
def sites(
    status: Optional[str] = Query(default=None),
    session: Session = Depends(_db_session),
):
    sql = """
        SELECT site_id, area, suitability, status, explanation_json,
               ST_AsGeoJSON(ST_Transform(geom, 4326))::json AS geometry
        FROM candidate_site
        WHERE (:status IS NULL OR status = :status)
        ORDER BY suitability DESC NULLS LAST, site_id
    """
    return _geojson_rows(session, sql, {"status": status})


@router.get("/sites/{site_id}/capacity")
def site_capacity(site_id: str, session: Session = Depends(_db_session)):
    row = session.execute(text("""
        SELECT c.site_id, c.land_cap, c.water_cap, c.sanitation_cap,
               c.health_cap, c.access_cap, c.binding_bottleneck, c.effective_cap,
               s.suitability, s.status
        FROM capacity c
        JOIN candidate_site s ON s.site_id = c.site_id
        WHERE c.site_id = :id
    """), {"id": site_id}).mappings().first()
    if row is None:
        raise HTTPException(status_code=404, detail="site capacity not found")
    return dict(row)


@router.get("/priorities")
def priorities(
    tier: Optional[str] = Query(default=None),
    limit: int = Query(default=100, ge=1, le=1000),
    session: Session = Depends(_db_session),
):
    rows = session.execute(text("""
        SELECT p.habitation_id, h.name, p.risk, p.exposed_pop,
               p.vulnerability, p.response_difficulty, p.recurrence,
               p.priority_score, p.tier
        FROM priority p
        JOIN habitation h ON h.habitation_id = p.habitation_id
        WHERE (:tier IS NULL OR p.tier = :tier)
        ORDER BY p.priority_score DESC NULLS LAST, p.habitation_id
        LIMIT :limit
    """), {"tier": tier, "limit": limit}).mappings().all()
    return {"items": [dict(row) for row in rows]}


class OptimizeHabitation(BaseModel):
    habitation_id: str
    exposed_population: int = Field(ge=0)


class OptimizeSite(BaseModel):
    site_id: str
    effective_capacity: int = Field(ge=0)
    hazard: float = Field(ge=0, le=1)
    feasible_habitations: list[str]
    suitability: Optional[float] = Field(default=None, ge=0, le=1)


class OptimizeRequest(BaseModel):
    habitations: list[OptimizeHabitation]
    sites: list[OptimizeSite]
    distances: dict[str, float]
    distance_weight: float = Field(gt=0)
    unmet_penalty: float = Field(gt=0)
    hazard_weight: float = Field(ge=0)
    time_limit_seconds: float = Field(default=30, gt=0)
    num_workers: int = Field(default=1, gt=0)


def _distance_map(values: dict[str, float]) -> dict[tuple[str, str], float]:
    result = {}
    for key, value in values.items():
        parts = key.split("::", 1)
        if len(parts) != 2:
            raise HTTPException(
                status_code=422,
                detail="distance keys must use 'habitation_id::site_id'",
            )
        result[(parts[0], parts[1])] = value
    return result


@router.post("/optimize")
def optimize(request: OptimizeRequest):
    try:
        result = run_l13(
            [HabitationDemand(x.habitation_id, x.exposed_population) for x in request.habitations],
            [CandidateSite(
                x.site_id, x.effective_capacity, x.hazard,
                tuple(x.feasible_habitations), x.suitability,
            ) for x in request.sites],
            _distance_map(request.distances),
            distance_weight=request.distance_weight,
            unmet_penalty=request.unmet_penalty,
            hazard_weight=request.hazard_weight,
            time_limit_seconds=request.time_limit_seconds,
            num_workers=request.num_workers,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {
        "status": result.status,
        "objective_value": result.objective_value,
        "allocations": [x.to_dict() for x in result.allocations],
        "unmet": [x.__dict__ for x in result.unmet],
        "metadata": result.metadata,
    }


@router.get("/runs/{run_id}")
def run_detail(run_id: str, session: Session = Depends(_db_session)):
    row = session.execute(text("""
        SELECT run_id, model_version, config_version, input_versions,
               started_at, finished_at, status, logs_or_error
        FROM model_run
        WHERE run_id = :id
    """), {"id": run_id}).mappings().first()
    if row is None:
        raise HTTPException(status_code=404, detail="run not found")
    return dict(row)


@router.get("/reports/{run_id}")
def report_payload(run_id: str, session: Session = Depends(_db_session)):
    run = session.execute(text("""
        SELECT run_id, model_version, config_version, input_versions,
               started_at, finished_at, status
        FROM model_run WHERE run_id = :id
    """), {"id": run_id}).mappings().first()
    if run is None:
        raise HTTPException(status_code=404, detail="run not found")

    allocation_rows = session.execute(text("""
        SELECT habitation_id, site_id, allocated_population, distance,
               constraint_flags
        FROM allocation
        WHERE run_id = :id
        ORDER BY habitation_id, site_id
    """), {"id": run_id}).mappings().all()

    return {
        "run": dict(run),
        "allocations": [dict(row) for row in allocation_rows],
        "format": "json",
        "note": "L15 exposes report data; PDF/Markdown rendering belongs to L16.",
    }


app = FastAPI(
    title="SIH 26191 Relocation DSS API",
    version=API_VERSION,
    description="Versioned REST API for backend analytical outputs.",
)
app.include_router(router)


@app.get("/health")
def health():
    return {"status": "ok", "service": "sih-26191-relocation-dss", "api_version": API_VERSION}
