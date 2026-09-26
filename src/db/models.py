"""
SQLAlchemy and GeoAlchemy2 ORM Models for SIH 26191 DSS.
Maps all 12 tables with SRID 32644 spatial geometries, constraints, and relationships.
"""
from datetime import datetime, timezone
from sqlalchemy import (
    Column,
    String,
    Integer,
    Numeric,
    Boolean,
    Text,
    Date,
    DateTime,
    ForeignKey,
    CheckConstraint,
    BigInteger,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
from geoalchemy2 import Geometry

from .session import Base

# ==============================================================================
# 1. Provenance and Metadata
# ==============================================================================

class DataSourceModel(Base):
    __tablename__ = "data_source"

    source_id = Column(String(64), primary_key=True)
    agency = Column(String(255), nullable=False)
    url = Column(Text, nullable=True)
    access_date = Column(Date, nullable=False)
    license = Column(String(128), nullable=False)
    version = Column(String(64), nullable=False)
    checksum = Column(String(128), nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))

    # Relationships
    habitations = relationship("HabitationModel", back_populates="source")
    infrastructure_items = relationship("InfrastructureModel", back_populates="source")
    hazard_layers = relationship("HazardLayerModel", back_populates="source")


class ModelRunModel(Base):
    __tablename__ = "model_run"

    run_id = Column(String(64), primary_key=True)
    model_version = Column(String(64), nullable=False)
    config_version = Column(String(64), nullable=False)
    input_versions = Column(JSONB, nullable=False, default=dict)
    started_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    finished_at = Column(DateTime(timezone=True), nullable=True)
    status = Column(String(32), nullable=False, default="running")
    logs_or_error = Column(Text, nullable=True)

    __table_args__ = (
        CheckConstraint("status IN ('running', 'completed', 'failed')", name="chk_model_run_status"),
    )

    # Relationships (Preserve audit history: no cascade delete)
    allocations = relationship("AllocationModel", back_populates="model_run")


class HazardLayerModel(Base):
    __tablename__ = "hazard_layer"

    hazard_id = Column(String(64), primary_key=True)
    type = Column(String(32), nullable=False)
    date_version = Column(String(64), nullable=False)
    source_id = Column(String(64), ForeignKey("data_source.source_id", ondelete="RESTRICT"), nullable=True)
    model_version = Column(String(64), nullable=False)
    raster_vector_ref = Column(Text, nullable=False)
    is_normalized = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        CheckConstraint("type IN ('landslide', 'flood', 'rainfall')", name="chk_hazard_type"),
    )

    source = relationship("DataSourceModel", back_populates="hazard_layers")


# ==============================================================================
# 2. Core Geographic and Habitation Entities
# ==============================================================================

class AdminUnitModel(Base):
    __tablename__ = "admin_unit"

    unit_id = Column(String(64), primary_key=True)
    type = Column(String(32), nullable=False)
    parent_id = Column(String(64), ForeignKey("admin_unit.unit_id", ondelete="RESTRICT"), nullable=True)
    name = Column(String(255), nullable=False)
    code = Column(String(64), nullable=True)
    geom = Column(Geometry(geometry_type="MULTIPOLYGON", srid=32644), nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        CheckConstraint("type IN ('district', 'block', 'tehsil', 'village')", name="chk_admin_unit_type"),
    )

    parent = relationship("AdminUnitModel", remote_side=[unit_id], backref="children")
    habitations = relationship("HabitationModel", back_populates="admin_unit")


class HabitationModel(Base):
    __tablename__ = "habitation"

    habitation_id = Column(String(64), primary_key=True)
    admin_unit_id = Column(String(64), ForeignKey("admin_unit.unit_id", ondelete="RESTRICT"), nullable=False)
    name = Column(String(255), nullable=False)
    population_year = Column(Integer, nullable=False, default=2011)
    population = Column(Integer, nullable=False)
    households = Column(Integer, nullable=False)
    # Generic Geometry(32644) allows both Point centroids and settlement Polygons per data dictionary
    geom = Column(Geometry(geometry_type="GEOMETRY", srid=32644), nullable=False)
    source_id = Column(String(64), ForeignKey("data_source.source_id", ondelete="RESTRICT"), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        CheckConstraint("population >= 0", name="chk_population_non_negative"),
        CheckConstraint("households >= 0", name="chk_households_non_negative"),
        CheckConstraint("population_year >= 1900 AND population_year <= 2100", name="chk_population_year_valid"),
    )

    admin_unit = relationship("AdminUnitModel", back_populates="habitations")
    source = relationship("DataSourceModel", back_populates="habitations")
    vulnerability = relationship("VulnerabilityModel", back_populates="habitation", uselist=False)
    priority = relationship("PriorityModel", back_populates="habitation", uselist=False)
    allocations = relationship("AllocationModel", back_populates="habitation")


class InfrastructureModel(Base):
    __tablename__ = "infrastructure"

    asset_id = Column(String(64), primary_key=True)
    type = Column(String(64), nullable=False)
    name = Column(String(255), nullable=True)
    capacity_or_proxy = Column(Numeric, nullable=True)
    is_proxy = Column(Boolean, nullable=False, default=True)
    # Generic Geometry(32644) accommodates both facility Points (hospitals, schools) and LineStrings (roads)
    geom = Column(Geometry(geometry_type="GEOMETRY", srid=32644), nullable=False)
    source_id = Column(String(64), ForeignKey("data_source.source_id", ondelete="RESTRICT"), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))

    source = relationship("DataSourceModel", back_populates="infrastructure_items")


# ==============================================================================
# 3. Analytical Persistence Models
# ==============================================================================

class RiskCellModel(Base):
    __tablename__ = "risk_cell"

    cell_id = Column(BigInteger, primary_key=True)
    h_landslide = Column(Numeric(5, 4), nullable=True)
    h_flood = Column(Numeric(5, 4), nullable=True)
    h_rain = Column(Numeric(5, 4), nullable=True)
    combined_risk = Column(Numeric(5, 4), nullable=True)
    red_zone = Column(Boolean, nullable=False, default=False)
    risk_tier = Column(String(32), nullable=False, default="lower_risk")
    quality_flag = Column(String(64), nullable=False, default="UNVERIFIED")
    geom = Column(Geometry(geometry_type="POLYGON", srid=32644), nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        CheckConstraint("h_landslide IS NULL OR (h_landslide >= 0.0 AND h_landslide <= 1.0)", name="chk_h_landslide_range"),
        CheckConstraint("h_flood IS NULL OR (h_flood >= 0.0 AND h_flood <= 1.0)", name="chk_h_flood_range"),
        CheckConstraint("h_rain IS NULL OR (h_rain >= 0.0 AND h_rain <= 1.0)", name="chk_h_rain_range"),
        CheckConstraint("combined_risk IS NULL OR (combined_risk >= 0.0 AND combined_risk <= 1.0)", name="chk_combined_risk_range"),
        CheckConstraint("risk_tier IN ('red', 'amber', 'lower_risk')", name="chk_risk_tier"),
    )


class VulnerabilityModel(Base):
    __tablename__ = "vulnerability"

    habitation_id = Column(String(64), ForeignKey("habitation.habitation_id", ondelete="RESTRICT"), primary_key=True)
    population_exposure = Column(Numeric(5, 4), nullable=True)
    social_score = Column(Numeric(5, 4), nullable=True)
    access_score = Column(Numeric(5, 4), nullable=True)
    infra_score = Column(Numeric(5, 4), nullable=True)
    recurrence_score = Column(Numeric(5, 4), nullable=True)
    vulnerability = Column(Numeric(5, 4), nullable=True)
    missing_data_penalty = Column(Numeric(5, 4), nullable=False, default=0.0)
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        CheckConstraint("vulnerability IS NULL OR (vulnerability >= 0.0 AND vulnerability <= 1.0)", name="chk_vulnerability_range"),
    )

    habitation = relationship("HabitationModel", back_populates="vulnerability")


class CandidateSiteModel(Base):
    __tablename__ = "candidate_site"

    site_id = Column(String(64), primary_key=True)
    # Explicit Polygon geometry per data-dictionary.md (site polygon footprint)
    geom = Column(Geometry(geometry_type="POLYGON", srid=32644), nullable=False)
    area = Column(Numeric, nullable=False)
    suitability = Column(Numeric(5, 4), nullable=True)
    status = Column(String(32), nullable=False, default="eligible")
    explanation_json = Column(JSONB, nullable=False, default=dict)
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        CheckConstraint("area > 0", name="chk_site_area_positive"),
        CheckConstraint("suitability IS NULL OR (suitability >= 0.0 AND suitability <= 1.0)", name="chk_site_suitability_range"),
        CheckConstraint("status IN ('eligible', 'conditional', 'rejected')", name="chk_site_status"),
    )

    capacity = relationship("CapacityModel", back_populates="site", uselist=False)
    allocations = relationship("AllocationModel", back_populates="site")


class CapacityModel(Base):
    __tablename__ = "capacity"

    site_id = Column(String(64), ForeignKey("candidate_site.site_id", ondelete="RESTRICT"), primary_key=True)
    land_cap = Column(Integer, nullable=False, default=0)
    water_cap = Column(Integer, nullable=False, default=0)
    sanitation_cap = Column(Integer, nullable=False, default=0)
    health_cap = Column(Integer, nullable=False, default=0)
    access_cap = Column(Integer, nullable=False, default=0)
    binding_bottleneck = Column(String(64), nullable=False, default="uncalculated")
    effective_cap = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        CheckConstraint("effective_cap >= 0", name="chk_effective_cap_non_negative"),
    )

    site = relationship("CandidateSiteModel", back_populates="capacity")


class PriorityModel(Base):
    __tablename__ = "priority"

    habitation_id = Column(String(64), ForeignKey("habitation.habitation_id", ondelete="RESTRICT"), primary_key=True)
    risk = Column(Numeric(5, 4), nullable=True)
    exposed_pop = Column(Integer, nullable=False, default=0)
    vulnerability = Column(Numeric(5, 4), nullable=True)
    response_difficulty = Column(Numeric(5, 4), nullable=True)
    recurrence = Column(Numeric(5, 4), nullable=True)
    priority_score = Column(Numeric(5, 4), nullable=True)
    tier = Column(String(32), nullable=False, default="Monitor")
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        CheckConstraint("priority_score IS NULL OR (priority_score >= 0.0 AND priority_score <= 1.0)", name="chk_priority_score_range"),
        CheckConstraint("tier IN ('Immediate', 'Short-term', 'Medium-term', 'Monitor')", name="chk_priority_tier"),
    )

    habitation = relationship("HabitationModel", back_populates="priority")


class AllocationModel(Base):
    __tablename__ = "allocation"

    allocation_id = Column(BigInteger, primary_key=True, autoincrement=True)
    run_id = Column(String(64), ForeignKey("model_run.run_id", ondelete="RESTRICT"), nullable=False)
    habitation_id = Column(String(64), ForeignKey("habitation.habitation_id", ondelete="RESTRICT"), nullable=False)
    site_id = Column(String(64), ForeignKey("candidate_site.site_id", ondelete="RESTRICT"), nullable=False)
    allocated_population = Column(Integer, nullable=False)
    distance = Column(Numeric, nullable=False)
    constraint_flags = Column(JSONB, nullable=False, default=dict)
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        CheckConstraint("allocated_population >= 0", name="chk_allocated_population_non_negative"),
        CheckConstraint("distance >= 0.0", name="chk_distance_non_negative"),
    )

    model_run = relationship("ModelRunModel", back_populates="allocations")
    habitation = relationship("HabitationModel", back_populates="allocations")
    site = relationship("CandidateSiteModel", back_populates="allocations")
