"""Focused unit tests for L04 using synthetic arrays only."""
import numpy as np
import geopandas as gpd
import pytest
import rasterio
from affine import Affine
from shapely.geometry import LineString, Point

from src.common.crs import CANONICAL_PROJECTED_CRS_STR
from src.hazards.landslide import (
    LandslideDataPendingError,
    LandslideModelError,
    audit_l04_data_readiness,
    build_provenance_metadata,
    compute_landslide_baseline,
    drainage_proximity_factor,
    inventory_evidence,
    ml_eligibility_gate,
    normalize_continuous,
    reclassify_categorical,
    reclassify_slope,
    road_proximity_factor,
    run_landslide_baseline,
    slope_factor_from_dem,
    validate_landslide_inventory,
    validate_weights,
    weighted_combine,
    write_landslide_hazard_raster,
    _read_aligned_raster,
)
from src.spatial.grid import DEFAULT_NODATA_FLOAT, create_canonical_grid


def test_normalization_bounds_and_constant_values():
    normalized = normalize_continuous(np.array([[2.0, 4.0, 6.0, DEFAULT_NODATA_FLOAT]]))
    assert np.allclose(normalized[0, :3], [0.0, 0.5, 1.0])
    assert normalized[0, 3] == DEFAULT_NODATA_FLOAT
    assert np.all(normalize_continuous(np.ones((2, 2)) * 4.0) == 0.0)


def test_categorical_reclassification_is_explicit():
    output = reclassify_categorical(np.array([[1, 2, 9]]), {1: 0.2, 2: 0.8})
    assert np.allclose(output[0, :2], [0.2, 0.8])
    assert output[0, 2] == DEFAULT_NODATA_FLOAT


def test_categorical_mapping_validation_and_determinism():
    values = np.array([[1, 2, 3]])
    first = reclassify_categorical(values, {1: 0.1, 2: 0.8, 3: 0.4})
    second = reclassify_categorical(values, {1: 0.1, 2: 0.8, 3: 0.4})
    assert np.array_equal(first, second)
    with pytest.raises(LandslideModelError, match="must be within"):
        reclassify_categorical(values, {1: 1.1})
    with pytest.raises(LandslideModelError, match="must be numeric"):
        reclassify_categorical(values, {1: "high"})
    with pytest.raises(LandslideModelError, match="must not be empty"):
        reclassify_categorical(values, {})
    result = reclassify_categorical(values, {1: 0.1})
    assert result[0, 1] == DEFAULT_NODATA_FLOAT
    assert result[0, 2] == DEFAULT_NODATA_FLOAT


def test_weight_validation_and_weighted_combination():
    weights = validate_weights({"slope": 0.25, "lulc": 0.75})
    result, contributions = weighted_combine({"slope": np.ones((1, 2)), "lulc": np.zeros((1, 2))}, weights)
    assert np.allclose(result, 0.25)
    assert np.allclose(contributions["slope"], 0.25)
    try:
        validate_weights({"a": 0.5})
        assert False
    except ValueError:
        pass


def test_weighted_combination_propagates_nodata_and_is_reproducible():
    factors = {"slope": np.array([[0.2, DEFAULT_NODATA_FLOAT]]), "lulc": np.array([[0.8, 0.3]])}
    first, _ = weighted_combine(factors, {"slope": 0.5, "lulc": 0.5})
    second, _ = weighted_combine(factors, {"slope": 0.5, "lulc": 0.5})
    assert first[0, 1] == DEFAULT_NODATA_FLOAT
    assert np.array_equal(first, second)


def test_weighted_combination_renormalizes_omitted_factors():
    factors = {"slope": np.array([[1.0]]), "lulc": np.array([[0.0]])}
    result, _ = weighted_combine(factors, {"slope": 0.35, "lulc": 0.20, "geology": 0.15, "drainage": 0.10, "roads": 0.10, "inventory": 0.10})
    assert result[0, 0] == pytest.approx(0.35 / 0.55)


@pytest.mark.parametrize("bad", [np.array([[1.1]]), np.array([[-0.1]]), np.array([[np.nan]]), np.array([[np.inf]])])
def test_weighted_combination_rejects_invalid_factor_values(bad):
    with pytest.raises(LandslideModelError):
        weighted_combine({"slope": bad}, {"slope": 1.0})


def test_weight_validation_rejects_zero_and_unknown_weights():
    with pytest.raises(LandslideModelError, match="positive"):
        validate_weights({"slope": 0.0, "lulc": 1.0})
    with pytest.raises(LandslideModelError, match="Unknown"):
        validate_weights({"other": 1.0})
    with pytest.raises(LandslideModelError):
        weighted_combine({}, {"slope": 1.0})


def test_slope_interval_boundaries_are_explicit():
    classes = [
        {"min_degrees": 0.0, "max_degrees": 15.0, "score": 0.0},
        {"min_degrees": 15.0, "max_degrees": 30.0, "score": 0.25},
        {"min_degrees": 30.0, "max_degrees": 45.0, "score": 0.6},
        {"min_degrees": 45.0, "max_degrees": 90.0, "score": 1.0},
    ]
    result = reclassify_slope(np.array([[0.0, 14.999, 15.0, 29.999, 30.0, 44.999, 45.0, 89.999, 90.0]]), classes)
    assert np.allclose(result, [[0.0, 0.0, 0.25, 0.25, 0.6, 0.6, 1.0, 1.0, 1.0]])
    with pytest.raises(LandslideModelError):
        reclassify_slope(np.array([[90.1]]), classes)


def test_l03_slope_integration():
    dem = np.add.outer(np.arange(5, dtype=np.float32), np.arange(5, dtype=np.float32))
    factor, slope = slope_factor_from_dem(dem, dx=30.0, dy=30.0)
    assert factor[2, 2] != DEFAULT_NODATA_FLOAT
    assert slope[2, 2] > 0.0


def test_inventory_validation_and_density():
    inventory = gpd.GeoDataFrame({"id": [1, 2], "geometry": [Point(15, -15), Point(15, -15)]}, crs=CANONICAL_PROJECTED_CRS_STR)
    validated = validate_landslide_inventory(inventory)
    assert validated.report["removed_records"] == 1
    evidence = inventory_evidence(validated.inventory, (2, 2), Affine(30, 0, 0, 0, -30, 0))
    assert evidence.status == "valid_overlap"
    assert evidence.evidence.shape == (2, 2)
    assert float(evidence.evidence.max()) == 1.0


def test_inventory_empty_and_no_overlap_are_distinct():
    empty = gpd.GeoDataFrame({"geometry": []}, geometry="geometry", crs=CANONICAL_PROJECTED_CRS_STR)
    empty_result = inventory_evidence(empty, (2, 2), Affine(30, 0, 0, 0, -30, 0))
    assert empty_result.status == "empty_inventory"
    assert np.all(empty_result.evidence == DEFAULT_NODATA_FLOAT)

    outside = gpd.GeoDataFrame({"geometry": [Point(1000, 1000)]}, crs=CANONICAL_PROJECTED_CRS_STR)
    with pytest.raises(LandslideModelError, match="no spatial overlap"):
        inventory_evidence(outside, (2, 2), Affine(30, 0, 0, 0, -30, 0))


def test_proximity_factors_use_explicit_projected_distance():
    grid = create_canonical_grid((500000, 3000000, 500090, 3000090))
    source = gpd.GeoDataFrame({"geometry": [LineString([(500000, 3000045), (500090, 3000045)])]}, crs=CANONICAL_PROJECTED_CRS_STR)
    drainage = drainage_proximity_factor(source, grid, max_distance_m=30.0)
    roads = road_proximity_factor(source, grid, max_distance_m=30.0)
    assert np.allclose(drainage, roads)
    assert drainage[1, 1] == pytest.approx(1.0)
    assert drainage[0, 1] == pytest.approx(0.0)
    assert drainage[1, 0] > drainage[0, 0]
    assert np.array_equal(drainage, drainage_proximity_factor(source, grid, max_distance_m=30.0))
    with pytest.raises(LandslideModelError, match="max_distance_m"):
        drainage_proximity_factor(source, grid, max_distance_m=None)
    with pytest.raises(LandslideModelError, match="positive"):
        road_proximity_factor(source, grid, max_distance_m=0.0)


def test_proximity_requires_crs():
    grid = create_canonical_grid((500000, 3000000, 500090, 3000090))
    source = gpd.GeoDataFrame({"geometry": [Point(500000, 3000045)]}, crs=None)
    with pytest.raises(LandslideModelError, match="no defined CRS"):
        drainage_proximity_factor(source, grid, max_distance_m=30.0)


def test_ml_gate_and_absent_data_behavior(tmp_path):
    gate = ml_eligibility_gate(0, 0, 0, False, False, False, True)
    assert gate.eligible is False
    audit = audit_l04_data_readiness(tmp_path)
    assert audit["real_data_available"] is False
    assert all(not entry["present"] for entry in audit["datasets"].values())


def test_provenance_metadata(tmp_path):
    source = tmp_path / "dem.tif"
    source.write_bytes(b"synthetic test fixture")
    metadata = build_provenance_metadata({"dem": source}, {"slope": 1.0})
    assert metadata["layer"] == "L04"
    assert metadata["inputs"]["dem"]["checksum_sha256"]


def test_baseline_metadata_and_bounds():
    result = compute_landslide_baseline({"slope": np.array([[0.0, 1.0]])}, {"slope": 1.0})
    assert np.all((result.hazard >= 0.0) & (result.hazard <= 1.0))
    assert result.metadata["layer"] == "L04"


def test_write_landslide_hazard_raster_metadata(tmp_path):
    grid = create_canonical_grid((500000, 3000000, 500060, 3000060))
    result = compute_landslide_baseline({"slope": np.array([[0.0, 1.0, 0.5], [0.5, DEFAULT_NODATA_FLOAT, 1.0]])}, {"slope": 1.0})
    output = write_landslide_hazard_raster(tmp_path / "landslide.tif", result, grid)
    with rasterio.open(output) as dataset:
        assert dataset.crs.to_epsg() == 32644
        assert (dataset.width, dataset.height) == (grid.width, grid.height)
        assert dataset.transform == grid.transform
        assert dataset.res == (30.0, 30.0)
        assert dataset.dtypes[0] == "float32"
        assert dataset.nodata == DEFAULT_NODATA_FLOAT
        values = dataset.read(1)
        valid = values[values != DEFAULT_NODATA_FLOAT]
        assert np.all((valid >= 0.0) & (valid <= 1.0))


def test_orchestration_fails_when_required_real_data_are_absent(tmp_path):
    grid = create_canonical_grid((500000, 3000000, 500060, 3000060))
    with pytest.raises(LandslideDataPendingError, match="Required L04 real inputs"):
        run_landslide_baseline({}, grid, tmp_path / "not_created.tif")

def test_aligned_raster_requires_explicit_nodata(tmp_path):
    grid = create_canonical_grid((500000, 3000000, 500060, 3000060))
    raster = tmp_path / "aligned_without_nodata.tif"
    with rasterio.open(
        raster,
        "w",
        driver="GTiff",
        height=grid.height,
        width=grid.width,
        count=1,
        dtype="float32",
        crs=grid.crs,
        transform=grid.transform,
    ) as dataset:
        dataset.write(np.ones((grid.height, grid.width), dtype=np.float32), 1)
    with pytest.raises(LandslideModelError, match="explicit NoData"):
        _read_aligned_raster(raster, grid, categorical=False, workspace=tmp_path)


def test_orchestration_rejects_unknown_input_names(tmp_path):
    grid = create_canonical_grid((500000, 3000000, 500060, 3000060))
    with pytest.raises(LandslideModelError, match="Unknown L04 input names"):
        run_landslide_baseline({"bogus": tmp_path / "ignored.tif"}, grid, tmp_path / "not_created.tif")
