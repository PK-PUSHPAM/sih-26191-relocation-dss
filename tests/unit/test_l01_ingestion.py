"""
Unit Tests for Layer L01 — Data Ingestion and Validation Foundation.
Tests schema checks, null rates, duplicate detection, geometry validity, CRS rules, and provenance generation.
"""
import json
import shutil
import tempfile
from pathlib import Path
import pytest
import pandas as pd
import geopandas as gpd
from shapely.geometry import Point, Polygon

from src.common.crs import CANONICAL_PROJECTED_CRS_STR, validate_crs_string
from src.common.provenance import compute_sha256, generate_provenance_record
from src.validation.models import (
    ColumnContract,
    DatasetSchemaContract,
    ValidationSeverity,
)
from src.validation.engine import ValidationEngine
from src.ingestion.adapters import get_adapter_for_file
from src.ingestion.pipeline import IngestionPipeline


@pytest.fixture
def temp_workspace():
    """Create a temporary workspace directory for test data lifecycle."""
    temp_dir = tempfile.mkdtemp(prefix="sih_test_l01_")
    yield Path(temp_dir)
    shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.fixture
def sample_village_contract():
    """Contract for sample demographic tabular dataset."""
    return DatasetSchemaContract(
        dataset_id="test_village_pca",
        expected_format="CSV",
        primary_key="village_code",
        required_columns=[
            ColumnContract(name="village_code", dtype="str", required=True, nullable=False),
            ColumnContract(name="village_name", dtype="str", required=True, nullable=False),
            ColumnContract(name="population_2011", dtype="int", required=True, nullable=False, min_value=0),
            ColumnContract(name="households_2011", dtype="int", required=True, nullable=False, min_value=0),
            ColumnContract(
                name="amenity_category",
                dtype="str",
                required=False,
                nullable=True,
                max_null_rate=0.5,
                allowed_values=["HIGH", "MEDIUM", "LOW"],
            ),
        ],
    )


@pytest.fixture
def sample_spatial_contract():
    """Contract for sample spatial vector dataset in Chamoli bounds."""
    return DatasetSchemaContract(
        dataset_id="test_admin_boundary",
        expected_format="GEOJSON",
        primary_key="unit_id",
        expected_geometry_type="Polygon",
        expected_crs="EPSG:4326",
        required_columns=[
            ColumnContract(name="unit_id", dtype="str", required=True, nullable=False),
            ColumnContract(name="unit_name", dtype="str", required=True, nullable=False),
        ],
    )


# ==============================================================================
# 1. Checksum & Provenance Tests
# ==============================================================================

def test_sha256_checksum_computation(temp_workspace):
    test_file = temp_workspace / "sample.txt"
    test_file.write_text("SIH 26191 Chamoli DSS", encoding="utf-8")
    
    checksum = compute_sha256(test_file)
    assert len(checksum) == 64
    assert isinstance(checksum, str)

    # Identical content yields identical hash
    checksum_2 = compute_sha256(test_file)
    assert checksum == checksum_2


# ==============================================================================
# 2. Tabular Validation Tests
# ==============================================================================

def test_valid_csv_validation(sample_village_contract):
    df = pd.DataFrame({
        "village_code": ["V001", "V002", "V003"],
        "village_name": ["Joshimath_A", "Gopeshwar_B", "Pipalkoti_C"],
        "population_2011": [1200, 3500, 850],
        "households_2011": [250, 700, 180],
        "amenity_category": ["HIGH", "MEDIUM", "LOW"],
    })

    report = ValidationEngine.validate(df, sample_village_contract)
    assert report.is_valid is True
    assert report.errors_count == 0


def test_empty_dataframe_fails_validation(sample_village_contract):
    empty_df = pd.DataFrame()
    report = ValidationEngine.validate(empty_df, sample_village_contract)
    assert report.is_valid is False
    assert report.errors_count > 0
    assert any(iss.check_name == "empty_dataset_check" for iss in report.issues)


def test_missing_required_column_fails_validation(sample_village_contract):
    # Missing households_2011
    df = pd.DataFrame({
        "village_code": ["V001", "V002"],
        "village_name": ["Joshimath_A", "Gopeshwar_B"],
        "population_2011": [1200, 3500],
    })

    report = ValidationEngine.validate(df, sample_village_contract)
    assert report.is_valid is False
    assert any(iss.column == "households_2011" for iss in report.issues)


def test_null_rate_violation_fails_validation(sample_village_contract):
    # village_name is non-nullable, but has null
    df = pd.DataFrame({
        "village_code": ["V001", "V002"],
        "village_name": ["Joshimath_A", None],
        "population_2011": [1200, 3500],
        "households_2011": [250, 700],
        "amenity_category": ["HIGH", "LOW"],
    })

    report = ValidationEngine.validate(df, sample_village_contract)
    assert report.is_valid is False
    assert any(iss.check_name == "null_value_violation" for iss in report.issues)


def test_duplicate_primary_key_fails_validation(sample_village_contract):
    # Duplicate village_code 'V001'
    df = pd.DataFrame({
        "village_code": ["V001", "V001"],
        "village_name": ["Joshimath_A", "Joshimath_B"],
        "population_2011": [1200, 1500],
        "households_2011": [250, 300],
        "amenity_category": ["HIGH", "LOW"],
    })

    report = ValidationEngine.validate(df, sample_village_contract)
    assert report.is_valid is False
    assert any(iss.check_name == "primary_key_uniqueness" for iss in report.issues)


def test_numeric_min_range_and_allowed_vocab_violations(sample_village_contract):
    # Negative population (-50) and invalid category ('UNKNOWN')
    df = pd.DataFrame({
        "village_code": ["V001"],
        "village_name": ["Joshimath_A"],
        "population_2011": [-50],
        "households_2011": [20],
        "amenity_category": ["INVALID_CAT"],
    })

    report = ValidationEngine.validate(df, sample_village_contract)
    assert report.is_valid is False
    assert any(iss.check_name == "numeric_min_range_violation" for iss in report.issues)
    assert any(iss.check_name == "categorical_vocabulary_violation" for iss in report.issues)


# ==============================================================================
# 3. Spatial Validation Tests
# ==============================================================================

def test_valid_spatial_vector_validation(sample_spatial_contract):
    # Polygon within Chamoli envelope (approx 79.5°E, 30.5°N)
    poly = Polygon([(79.4, 30.4), (79.6, 30.4), (79.6, 30.6), (79.4, 30.6), (79.4, 30.4)])
    gdf = gpd.GeoDataFrame(
        {"unit_id": ["U01"], "unit_name": ["Chamoli_Block_1"]},
        geometry=[poly],
        crs="EPSG:4326",
    )

    report = ValidationEngine.validate(gdf, sample_spatial_contract)
    assert report.is_valid is True
    assert report.errors_count == 0


def test_missing_crs_fails_spatial_validation(sample_spatial_contract):
    poly = Polygon([(79.4, 30.4), (79.6, 30.4), (79.6, 30.6), (79.4, 30.6), (79.4, 30.4)])
    gdf = gpd.GeoDataFrame(
        {"unit_id": ["U01"], "unit_name": ["Chamoli_Block_1"]},
        geometry=[poly],
        crs=None,  # Missing CRS
    )

    report = ValidationEngine.validate(gdf, sample_spatial_contract)
    assert report.is_valid is False
    assert any(iss.check_name == "spatial_crs_presence" for iss in report.issues)


def test_invalid_bowtie_geometry_fails_validation(sample_spatial_contract):
    # Self-intersecting bowtie polygon
    bowtie = Polygon([(0, 0), (2, 2), (2, 0), (0, 2), (0, 0)])
    gdf = gpd.GeoDataFrame(
        {"unit_id": ["U01"], "unit_name": ["Bad_Geometry"]},
        geometry=[bowtie],
        crs="EPSG:4326",
    )

    report = ValidationEngine.validate(gdf, sample_spatial_contract)
    assert report.is_valid is False
    assert any(iss.check_name == "spatial_geometry_validity" for iss in report.issues)


def test_bounding_box_outside_study_area_fails_validation(sample_spatial_contract):
    # Polygon in South India (approx 77°E, 12°N - Bangalore)
    poly_south = Polygon([(77.5, 12.9), (77.6, 12.9), (77.6, 13.0), (77.5, 13.0), (77.5, 12.9)])
    gdf = gpd.GeoDataFrame(
        {"unit_id": ["U01"], "unit_name": ["South_India_Block"]},
        geometry=[poly_south],
        crs="EPSG:4326",
    )

    report = ValidationEngine.validate(gdf, sample_spatial_contract)
    assert report.is_valid is False
    assert any(iss.check_name == "spatial_extent_bounding_box" for iss in report.issues)


# ==============================================================================
# 4. Pipeline & Lifecycle Promotion Tests
# ==============================================================================

def test_pipeline_promotes_valid_dataset_to_curated(temp_workspace, sample_village_contract):
    pipeline = IngestionPipeline(repo_root=temp_workspace)

    # Create raw CSV file
    raw_file = temp_workspace / "data" / "raw" / "villages.csv"
    raw_file.parent.mkdir(parents=True, exist_ok=True)
    df = pd.DataFrame({
        "village_code": ["V01", "V02"],
        "village_name": ["Village_1", "Village_2"],
        "population_2011": [500, 900],
        "households_2011": [100, 180],
        "amenity_category": ["HIGH", "LOW"],
    })
    df.to_csv(raw_file, index=False)

    is_promoted, report, prov = pipeline.process_dataset(
        raw_file_path=raw_file,
        contract=sample_village_contract,
        source_id="census_2011_chamoli_dchb_b",
    )

    assert is_promoted is True
    assert report.is_valid is True
    assert prov.validation_status == "PASSED"

    # Verify curated artifact and manifest exist
    curated_file = temp_workspace / "data" / "curated" / "test_village_pca.csv"
    manifest_file = temp_workspace / "data" / "curated" / "test_village_pca_manifest.json"
    assert curated_file.exists()
    assert manifest_file.exists()

    # Verify manifest contents
    with open(manifest_file, "r", encoding="utf-8") as f:
        manifest_data = json.load(f)
    assert manifest_data["dataset_id"] == "test_village_pca"
    assert manifest_data["checksum_sha256"] == prov.checksum_sha256


def test_pipeline_blocks_invalid_dataset_from_curated(temp_workspace, sample_village_contract):
    pipeline = IngestionPipeline(repo_root=temp_workspace)

    # Create invalid raw CSV file (missing households column)
    raw_file = temp_workspace / "data" / "raw" / "bad_villages.csv"
    raw_file.parent.mkdir(parents=True, exist_ok=True)
    df = pd.DataFrame({
        "village_code": ["V01"],
        "village_name": ["Village_1"],
        "population_2011": [500],
    })
    df.to_csv(raw_file, index=False)

    is_promoted, report, prov = pipeline.process_dataset(
        raw_file_path=raw_file,
        contract=sample_village_contract,
    )

    assert is_promoted is False
    assert report.is_valid is False
    assert prov.validation_status == "FAILED"

    # Curated file must NOT exist
    curated_file = temp_workspace / "data" / "curated" / "test_village_pca.csv"
    assert not curated_file.exists()


    # Staging error report should exist
    staging_report = temp_workspace / "data" / "staging" / "test_village_pca_validation_report.json"
    assert staging_report.exists()


def test_unsupported_format_raises_value_error(temp_workspace):
    dummy_file = temp_workspace / "test.unknown_ext"
    dummy_file.write_text("sample", encoding="utf-8")
    with pytest.raises(ValueError, match="Unsupported file format"):
        get_adapter_for_file(dummy_file)
