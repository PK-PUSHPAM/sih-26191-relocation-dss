"""Focused L05 tests using synthetic in-memory fixtures only."""
import numpy as np
import geopandas as gpd
import pandas as pd
import pytest
import rasterio
from affine import Affine
from shapely.geometry import LineString, Point, Polygon

from src.common.crs import CANONICAL_PROJECTED_CRS_STR
from src.hazards.flood import (
    FloodDataPendingError,
    FloodModelError,
    audit_l05_data_readiness,
    build_flood_provenance,
    compute_flood_baseline,
    flood_proximity_factor,
    normalize_flood_factor,
    observed_flood_extent_evidence,
    run_flood_baseline,
    validate_flood_inventory,
    validate_flood_weights,
    validate_hydrological_observations,
    weighted_flood_combine,
    write_flood_hazard_raster,
)
from src.spatial.grid import DEFAULT_NODATA_FLOAT, create_canonical_grid


def test_factor_normalization_and_invalid_values():
    values = normalize_flood_factor(np.array([[0.0, 0.5, 1.0, DEFAULT_NODATA_FLOAT]]))
    assert np.array_equal(values, [[0.0, 0.5, 1.0, DEFAULT_NODATA_FLOAT]])
    for invalid in (np.array([[1.1]]), np.array([[-0.1]]), np.array([[np.nan]]), np.array([[np.inf]])):
        with pytest.raises(FloodModelError):
            normalize_flood_factor(invalid)


def test_weight_validation_and_omitted_factor_renormalization():
    assert validate_flood_weights({"river_proximity": 1.0}) == {"river_proximity": 1.0}
    result, contributions = weighted_flood_combine(
        {"river_proximity": np.array([[1.0]]), "observed_extent": np.array([[0.0]])},
        {"river_proximity": 0.75, "observed_extent": 0.25},
    )
    assert result[0, 0] == pytest.approx(0.75)
    omitted, _ = weighted_flood_combine(
        {"river_proximity": np.array([[1.0]])},
        {"river_proximity": 0.75, "observed_extent": 0.25},
    )
    assert omitted[0, 0] == pytest.approx(1.0)
    with pytest.raises(FloodModelError):
        validate_flood_weights({"river_proximity": 0.0, "observed_extent": 1.0})
    with pytest.raises(FloodModelError, match="Unknown"):
        validate_flood_weights({"rainfall": 1.0})
    with pytest.raises(FloodModelError):
        weighted_flood_combine({}, {"river_proximity": 1.0})


def test_nodata_propagation_and_reproducibility():
    factors = {
        "river_proximity": np.array([[0.2, DEFAULT_NODATA_FLOAT]]),
        "observed_extent": np.array([[0.8, 0.2]]),
    }
    first, _ = weighted_flood_combine(factors, {"river_proximity": 0.5, "observed_extent": 0.5})
    second, _ = weighted_flood_combine(factors, {"river_proximity": 0.5, "observed_extent": 0.5})
    assert first[0, 1] == DEFAULT_NODATA_FLOAT
    assert np.array_equal(first, second)


def test_distance_transformation_and_invalid_parameter():
    grid = create_canonical_grid((500000, 3000000, 500090, 3000090))
    river = gpd.GeoDataFrame({"geometry": [LineString([(500000, 3000045), (500090, 3000045)])]}, crs=CANONICAL_PROJECTED_CRS_STR)
    factor = flood_proximity_factor(river, grid, 30.0)
    assert factor[1, 1] == pytest.approx(1.0)
    assert factor[0, 1] == pytest.approx(0.0)
    assert factor[1, 0] > factor[0, 0]
    assert np.array_equal(factor, flood_proximity_factor(river, grid, 30.0))
    with pytest.raises(FloodModelError, match="max_distance_m"):
        flood_proximity_factor(river, grid, None)
    with pytest.raises(FloodModelError, match="positive"):
        flood_proximity_factor(river, grid, 0.0)
    no_crs = gpd.GeoDataFrame({"geometry": [Point(500000, 3000045)]}, crs=None)
    with pytest.raises(FloodModelError, match="no defined CRS"):
        flood_proximity_factor(no_crs, grid, 30.0)


def test_inventory_empty_overlap_and_invalid_geometry():
    transform = Affine(30, 0, 0, 0, -30, 0)
    empty = gpd.GeoDataFrame({"geometry": []}, geometry="geometry", crs=CANONICAL_PROJECTED_CRS_STR)
    empty_result = observed_flood_extent_evidence(empty, (2, 2), transform)
    assert empty_result.status == "empty_inventory"
    assert np.all(empty_result.evidence == DEFAULT_NODATA_FLOAT)

    outside = gpd.GeoDataFrame({"geometry": [Point(1000, 1000)]}, crs=CANONICAL_PROJECTED_CRS_STR)
    with pytest.raises(FloodModelError, match="no spatial overlap"):
        observed_flood_extent_evidence(outside, (2, 2), transform)

    invalid = Polygon([(0, 0), (60, 60), (0, 60), (60, 0), (0, 0)])
    source = gpd.GeoDataFrame({"geometry": [invalid]}, crs=CANONICAL_PROJECTED_CRS_STR)
    prepared, report = validate_flood_inventory(source)
    assert report["output_records"] == 1
    assert prepared.geometry.iloc[0].is_valid
    valid_result = observed_flood_extent_evidence(prepared, (2, 2), transform)
    assert valid_result.status == "valid_overlap"
    assert valid_result.overlapping_records == 1
    assert np.all((valid_result.evidence >= 0.0) & (valid_result.evidence <= 1.0))


def test_inventory_crs_transformation():
    source = gpd.GeoDataFrame({"geometry": [Point(79.35, 30.4)]}, crs="EPSG:4326")
    prepared, _ = validate_flood_inventory(source)
    assert prepared.crs.to_epsg() == 32644


def test_hydrological_observation_validation():
    observations = pd.DataFrame({"station_id": ["S1", "S1"], "timestamp": ["2024-01-01T00:00:00Z", "2024-01-01T01:00:00Z"], "discharge": [10.0, 12.0]})
    result = validate_hydrological_observations(observations)
    assert result.report["records"] == 2
    assert result.observations["timestamp"].dt.tz is not None
    for bad in (
        pd.DataFrame({"station_id": ["S1"], "timestamp": ["not-a-date"], "discharge": [1.0]}),
        pd.DataFrame({"station_id": ["S1"], "timestamp": ["2024-01-01"], "discharge": [-1.0]}),
        pd.DataFrame({"station_id": ["S1"], "timestamp": ["2024-01-01"], "water_level": [np.nan]}),
    ):
        with pytest.raises(FloodModelError):
            validate_hydrological_observations(bad)


def test_dem_is_not_an_implicit_l05_factor():
    result = compute_flood_baseline({"river_proximity": np.array([[0.2, 0.8]])}, {"river_proximity": 1.0})
    assert np.allclose(result.hazard, [[0.2, 0.8]])
    assert "dem" not in result.factors


def test_geotiff_contract_and_provenance(tmp_path):
    grid = create_canonical_grid((500000, 3000000, 500060, 3000060))
    result = compute_flood_baseline({"river_proximity": np.array([[0.0, 0.5, 1.0], [0.2, DEFAULT_NODATA_FLOAT, 0.8]])}, {"river_proximity": 1.0})
    output = write_flood_hazard_raster(tmp_path / "flood.tif", result, grid)
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
    metadata = build_flood_provenance({}, {"river_proximity": 1.0}, grid, {"max_distance_m": 30.0})
    assert metadata["layer"] == "L05"
    assert metadata["crs"] == CANONICAL_PROJECTED_CRS_STR


def test_missing_data_and_readiness(tmp_path):
    grid = create_canonical_grid((500000, 3000000, 500060, 3000060))
    with pytest.raises(FloodDataPendingError, match="Required L05 real inputs"):
        run_flood_baseline({}, grid, tmp_path / "not-created.tif", max_distance_m=30.0)
    audit = audit_l05_data_readiness(tmp_path)
    assert audit["real_data_available"] is False
    assert audit["flash_flood_supported"] is False
    assert all(not entry["present"] for entry in audit["datasets"].values())


def test_run_rejects_unknown_input_names(tmp_path):
    grid = create_canonical_grid((500000, 3000000, 500060, 3000060))
    with pytest.raises(FloodModelError, match="Unknown L05 input names"):
        run_flood_baseline({"bogus": tmp_path / "x"}, grid, tmp_path / "out.tif", max_distance_m=30.0)


def test_hydrological_observations_reject_empty_and_missing_station_id():
    empty = pd.DataFrame({"station_id": [], "timestamp": [], "discharge": []})
    with pytest.raises(FloodModelError, match="empty"):
        validate_hydrological_observations(empty)

    missing_station = pd.DataFrame({
        "station_id": ["S1", None],
        "timestamp": ["2024-01-01T00:00:00Z", "2024-01-01T01:00:00Z"],
        "discharge": [1.0, 2.0],
    })
    with pytest.raises(FloodModelError, match="station_id"):
        validate_hydrological_observations(missing_station)


def test_run_rejects_unknown_weight_names(tmp_path):
    grid = create_canonical_grid((500000, 3000000, 500060, 3000060))
    with pytest.raises(FloodModelError, match="Unknown L05 factor weights"):
        run_flood_baseline(
            {"study_area": tmp_path / "missing", "river_network": tmp_path / "missing2"},
            grid,
            tmp_path / "out.tif",
            max_distance_m=30.0,
            weights={"river_proximity": 1.0, "rainfall": 0.1},
        )
