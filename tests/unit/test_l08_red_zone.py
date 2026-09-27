"""Unit tests for L08 Red‑Zone Engine (layer L08)."""

import numpy as np
import pytest
from affine import Affine

from src.spatial.grid import create_canonical_grid, CANONICAL_RESOLUTION_METERS, DEFAULT_NODATA_FLOAT, CanonicalGridDefinition
from src.risk.l08_red_zone import run_l08, RiskTier, RedZoneRecord, RED_ZONE_THRESHOLD, AMBER_THRESHOLD
from src.risk.multi_hazard import RiskCellRecord, QualityState

# Helper to build a minimal 2 × 2 grid covering a dummy bbox.
BBox = (0.0, 0.0, CANONICAL_RESOLUTION_METERS * 2, CANONICAL_RESOLUTION_METERS * 2)
GRID = create_canonical_grid(BBox)

def test_hard_exclusion_true_nodata():
    """Case T‑01 – hard exclusion true + NoData combined risk.
    Expected: red_zone=True, tier=RED, quality=NON_EVALUABLE.
    """
    combined = np.full((2, 2), DEFAULT_NODATA_FLOAT, dtype=np.float32)
    hard_ex = np.full((2, 2), True, dtype=bool)
    result = run_l08(GRID, combined, hard_ex)
    assert result.red_zone.all()
    # risk_tier array holds string values after conversion in run_l08
    assert (result.risk_tier == RiskTier.RED.value).all()
    for rec in result.records:
        assert rec.quality_flag.value == "non_evaluable"
        assert rec.risk_tier == RiskTier.RED

def test_hard_exclusion_false_nodata():
    """Case T‑05 – NoData without hard exclusion.
    Expected: red_zone=False, tier=LOWER_RISK, quality=NON_EVALUABLE.
    """
    combined = np.full((2, 2), DEFAULT_NODATA_FLOAT, dtype=np.float32)
    hard_ex = np.full((2, 2), False, dtype=bool)
    result = run_l08(GRID, combined, hard_ex)
    assert not result.red_zone.any()
    assert (result.risk_tier == RiskTier.LOWER_RISK.value).all()
    for rec in result.records:
        assert rec.quality_flag.value == "non_evaluable"
        assert rec.risk_tier == RiskTier.LOWER_RISK

@pytest.mark.parametrize(
    "h_val,expected_tier",
    [
        (0.0, RiskTier.LOWER_RISK),
        (0.5499, RiskTier.LOWER_RISK),
        (0.55, RiskTier.AMBER),
        (0.6999, RiskTier.AMBER),
        (0.70, RiskTier.RED),
        (1.0, RiskTier.RED),
    ],
)
def test_threshold_boundaries(h_val, expected_tier):
    """Boundary tests for combined risk values.
    Hard exclusion is False for these cells.
    """
    combined = np.full((2, 2), DEFAULT_NODATA_FLOAT, dtype=np.float32)
    combined[0, 0] = h_val
    hard_ex = np.full((2, 2), False, dtype=bool)
    result = run_l08(GRID, combined, hard_ex)
    assert result.red_zone[0, 0] == (h_val >= RED_ZONE_THRESHOLD)
    assert result.risk_tier[0, 0] == expected_tier.value
    rec = result.records[0]
    assert rec.risk_tier == expected_tier
    assert rec.quality_flag.value == "complete"

def test_invalid_combined_risk_handling():
    """Invalid combined risk values should produce INVALID quality and appropriate red_zone/tier.
    Tests NaN, +inf, -inf, -0.1, 1.1 with both hard_exclusion True and False.
    """
    invalid_values = [np.nan, np.inf, -np.inf, -0.1, 1.1]
    for val in invalid_values:
        for he_flag, exp_red, exp_tier in [(True, True, RiskTier.RED), (False, False, RiskTier.LOWER_RISK)]:
            combined = np.full((2, 2), DEFAULT_NODATA_FLOAT, dtype=np.float32)
            combined[0, 0] = val
            hard_ex = np.full((2, 2), he_flag, dtype=bool)
            result = run_l08(GRID, combined, hard_ex)
            assert result.red_zone[0, 0] == exp_red
            assert result.risk_tier[0, 0] == exp_tier.value
            rec = result.records[0]
            assert rec.quality_flag.value == "invalid"
            assert rec.risk_tier == exp_tier

def test_spatial_mismatch_raises():
    """Case T‑08 – mismatched grid dimensions raise an error."""
    # Create a grid of a different size.
    other_grid = create_canonical_grid((0, 0, CANONICAL_RESOLUTION_METERS, CANONICAL_RESOLUTION_METERS))
    combined = np.full((2, 2), 0.5, dtype=np.float32)
    hard_ex = np.full((2, 2), False, dtype=bool)
    with pytest.raises(ValueError):
        run_l08(other_grid, combined, hard_ex)


# =========================================================================
# Phase 3 – Canonical spatial validation tests
# =========================================================================

def _make_bad_grid(**overrides) -> CanonicalGridDefinition:
    """Build a CanonicalGridDefinition matching GRID but with selective overrides."""
    defaults = {
        "crs": GRID.crs,
        "resolution": GRID.resolution,
        "x_min": GRID.x_min,
        "y_min": GRID.y_min,
        "x_max": GRID.x_max,
        "y_max": GRID.y_max,
        "width": GRID.width,
        "height": GRID.height,
        "transform": GRID.transform,
    }
    defaults.update(overrides)
    return CanonicalGridDefinition(**defaults)


class TestCRSMismatch:
    """Grid CRS must match the canonical EPSG:32644."""

    def test_wrong_crs_raises(self):
        bad_grid = _make_bad_grid(crs="EPSG:4326")
        combined = np.full((2, 2), 0.5, dtype=np.float32)
        hard_ex = np.full((2, 2), False, dtype=bool)
        with pytest.raises(Exception, match="CRS"):
            run_l08(bad_grid, combined, hard_ex)


class TestResolutionMismatch:
    """Grid resolution must equal the canonical 30 m."""

    def test_wrong_resolution_raises(self):
        # Build a grid with 60 m resolution but same shape
        bad_grid = _make_bad_grid(
            resolution=60.0,
            transform=Affine(60.0, 0.0, GRID.x_min, 0.0, -60.0, GRID.y_max),
        )
        combined = np.full((2, 2), 0.5, dtype=np.float32)
        hard_ex = np.full((2, 2), False, dtype=bool)
        with pytest.raises(Exception, match="30"):
            run_l08(bad_grid, combined, hard_ex)


class TestTransformMismatch:
    """Grid transform must match the canonical unrotated affine."""

    def test_rotated_transform_raises(self):
        # A rotated transform with non-zero b/d coefficients
        bad_transform = Affine(
            CANONICAL_RESOLUTION_METERS, 1.0, GRID.x_min,
            1.0, -CANONICAL_RESOLUTION_METERS, GRID.y_max,
        )
        bad_grid = _make_bad_grid(transform=bad_transform)
        combined = np.full((2, 2), 0.5, dtype=np.float32)
        hard_ex = np.full((2, 2), False, dtype=bool)
        with pytest.raises(Exception, match="transform"):
            run_l08(bad_grid, combined, hard_ex)

    def test_shifted_origin_transform_raises(self):
        # Transform with shifted origin (different x_min)
        bad_transform = Affine(
            CANONICAL_RESOLUTION_METERS, 0.0, GRID.x_min + 15.0,
            0.0, -CANONICAL_RESOLUTION_METERS, GRID.y_max,
        )
        bad_grid = _make_bad_grid(transform=bad_transform)
        combined = np.full((2, 2), 0.5, dtype=np.float32)
        hard_ex = np.full((2, 2), False, dtype=bool)
        with pytest.raises(Exception, match="transform"):
            run_l08(bad_grid, combined, hard_ex)


class TestDimensionMismatch:
    """Raster dimensions must match the grid width × height."""

    def test_combined_risk_wrong_shape_raises(self):
        combined = np.full((3, 3), 0.5, dtype=np.float32)
        hard_ex = np.full((2, 2), False, dtype=bool)
        with pytest.raises(ValueError, match="dimensions"):
            run_l08(GRID, combined, hard_ex)

    def test_hard_exclusion_wrong_shape_raises(self):
        combined = np.full((2, 2), 0.5, dtype=np.float32)
        hard_ex = np.full((3, 3), False, dtype=bool)
        with pytest.raises(ValueError, match="dimensions"):
            run_l08(GRID, combined, hard_ex)


class TestHardExclusionSpatialMismatch:
    """hard_exclusion must match the canonical grid spatially."""

    def test_he_shape_mismatch_raises(self):
        combined = np.full((2, 2), 0.5, dtype=np.float32)
        hard_ex = np.full((4, 4), False, dtype=bool)
        with pytest.raises(ValueError, match="dimensions"):
            run_l08(GRID, combined, hard_ex)


class TestMissingHardExclusion:
    """hard_exclusion=None must raise a clear ValueError."""

    def test_none_hard_exclusion_raises(self):
        combined = np.full((2, 2), 0.5, dtype=np.float32)
        with pytest.raises(ValueError, match="hard_exclusion.*required"):
            run_l08(GRID, combined, None)


class TestNonBooleanHardExclusion:
    """hard_exclusion must be exactly Boolean dtype, not int or float."""

    def test_int_dtype_raises(self):
        combined = np.full((2, 2), 0.5, dtype=np.float32)
        hard_ex = np.full((2, 2), 0, dtype=np.int32)
        with pytest.raises(ValueError, match="Boolean"):
            run_l08(GRID, combined, hard_ex)

    def test_float_dtype_raises(self):
        combined = np.full((2, 2), 0.5, dtype=np.float32)
        hard_ex = np.full((2, 2), 0.0, dtype=np.float64)
        with pytest.raises(ValueError, match="Boolean"):
            run_l08(GRID, combined, hard_ex)

    def test_uint8_dtype_raises(self):
        combined = np.full((2, 2), 0.5, dtype=np.float32)
        hard_ex = np.full((2, 2), 0, dtype=np.uint8)
        with pytest.raises(ValueError, match="Boolean"):
            run_l08(GRID, combined, hard_ex)


# =========================================================================
# Phase 4 – L08Result.to_dict() and record schema
# =========================================================================

class TestToDict:
    """L08Result.to_dict() must succeed and return structured data."""

    def test_to_dict_succeeds(self):
        combined = np.full((2, 2), 0.5, dtype=np.float32)
        hard_ex = np.full((2, 2), False, dtype=bool)
        result = run_l08(GRID, combined, hard_ex)
        d = result.to_dict()
        assert set(d.keys()) == {"red_zone", "risk_tier", "records", "metadata"}
        assert isinstance(d["risk_tier"], list)

    def test_to_dict_risk_tier_values(self):
        combined = np.full((2, 2), 0.75, dtype=np.float32)
        hard_ex = np.full((2, 2), False, dtype=bool)
        result = run_l08(GRID, combined, hard_ex)
        d = result.to_dict()
        for row in d["risk_tier"]:
            for val in row:
                assert val == "red"


class TestRecordSchema:
    """RedZoneRecord.to_dict() must expose exactly the persistence-ready fields."""

    EXPECTED_KEYS = {
        "cell_id", "h_landslide", "h_flood", "h_rain",
        "combined_risk", "red_zone", "risk_tier", "quality_flag", "geometry",
    }

    def test_record_to_dict_keys(self):
        combined = np.full((2, 2), 0.5, dtype=np.float32)
        hard_ex = np.full((2, 2), False, dtype=bool)
        result = run_l08(GRID, combined, hard_ex)
        d = result.records[0].to_dict()
        assert set(d.keys()) == self.EXPECTED_KEYS


# =========================================================================
# Phase 5 – Invalid combined_risk persistence (D2 fix)
# =========================================================================

@pytest.mark.parametrize(
    "h_val",
    [np.nan, np.inf, -np.inf, -0.1, 1.1],
)
def test_invalid_h_record_combined_risk_is_none(h_val):
    """Invalid H values must produce combined_risk=None in the record."""
    combined = np.full((2, 2), DEFAULT_NODATA_FLOAT, dtype=np.float32)
    combined[0, 0] = h_val
    hard_ex = np.full((2, 2), False, dtype=bool)
    result = run_l08(GRID, combined, hard_ex)
    rec = result.records[0]
    assert rec.combined_risk is None
    assert rec.quality_flag == QualityState.INVALID


# =========================================================================
# Phase 6 – combined_risk=None input (D3 fix)
# =========================================================================

class TestMissingCombinedRisk:
    """combined_risk=None must raise a clear ValueError."""

    def test_none_combined_risk_raises(self):
        hard_ex = np.full((2, 2), False, dtype=bool)
        with pytest.raises(ValueError, match="combined_risk.*required"):
            run_l08(GRID, None, hard_ex)


# =========================================================================
# Phase 7 – Mixed-cell per-cell handling
# =========================================================================

class TestMixedCells:
    """A single run must evaluate each cell independently."""

    def test_mixed_nodata_invalid_valid(self):
        """2x2 grid: valid RED, valid AMBER, NoData, invalid (NaN)."""
        combined = np.full((2, 2), DEFAULT_NODATA_FLOAT, dtype=np.float32)
        combined[0, 0] = 0.80   # cell 0: valid RED (row=0, col=0)
        combined[0, 1] = 0.60   # cell 1: valid AMBER (row=0, col=1)
        # cell 2 (row=1, col=0) stays NoData
        combined[1, 1] = np.nan  # cell 3: invalid (row=1, col=1)
        hard_ex = np.full((2, 2), False, dtype=bool)
        result = run_l08(GRID, combined, hard_ex)

        recs = {r.cell_id: r for r in result.records}

        # cell 0: valid RED
        assert np.isclose(recs[0].combined_risk, 0.80, atol=1e-6)
        assert recs[0].red_zone == True
        assert recs[0].risk_tier == RiskTier.RED
        assert recs[0].quality_flag == QualityState.COMPLETE

        # cell 1: valid AMBER
        assert np.isclose(recs[1].combined_risk, 0.60, atol=1e-6)
        assert recs[1].red_zone == False
        assert recs[1].risk_tier == RiskTier.AMBER
        assert recs[1].quality_flag == QualityState.COMPLETE

        # cell 2: NoData
        assert recs[2].combined_risk is None
        assert recs[2].red_zone == False
        assert recs[2].risk_tier == RiskTier.LOWER_RISK
        assert recs[2].quality_flag == QualityState.NON_EVALUABLE

        # cell 3: NaN (invalid)
        assert recs[3].combined_risk is None
        assert recs[3].red_zone == False
        assert recs[3].risk_tier == RiskTier.LOWER_RISK
        assert recs[3].quality_flag == QualityState.INVALID

        # Verify arrays
        assert result.red_zone[0, 0] == True   # valid RED -> red_zone
        assert result.red_zone[0, 1] == False  # valid AMBER -> no red_zone
        assert result.red_zone[1, 0] == False  # NoData -> no red_zone
        assert result.red_zone[1, 1] == False  # NaN -> no red_zone


# =========================================================================
# Phase 8 – L07 immutability
# =========================================================================

class TestL07Immutability:
    """L08 must preserve L07 hazard fields unchanged."""

    def test_l07_fields_preserved(self):
        combined = np.full((2, 2), 0.5, dtype=np.float32)
        hard_ex = np.full((2, 2), False, dtype=bool)

        l07_records = tuple(
            RiskCellRecord(
                cell_id=i,
                h_landslide=0.3,
                h_flood=0.4,
                h_rain=1.0,
                combined_risk=0.5,
                quality_flag=QualityState.COMPLETE,
                geometry=None,
            )
            for i in range(4)
        )
        l07_metadata = {"records": l07_records}
        result = run_l08(GRID, combined, hard_ex, l07_metadata=l07_metadata)

        for i, rec in enumerate(result.records):
            assert rec.h_landslide == 0.3
            assert rec.h_flood == 0.4
            assert rec.h_rain == 1.0
            assert np.isclose(rec.combined_risk, 0.5, atol=1e-6)

        # Verify original L07 records are unchanged
        for i, rec in enumerate(l07_records):
            assert rec.h_landslide == 0.3
            assert rec.h_flood == 0.4
            assert rec.h_rain == 1.0
            assert np.isclose(rec.combined_risk, 0.5, atol=1e-6)


# =========================================================================
# Phase 9 – Provenance completeness
# =========================================================================

class TestProvenance:
    """Metadata must contain required provenance keys with expected values."""

    REQUIRED_KEYS = {
        "layer", "model_version", "rule_identifier",
        "threshold", "amber_threshold", "execution_timestamp",
        "crs", "resolution_m", "grid", "l07_input", "hard_exclusion_input",
    }

    def test_provenance_keys(self):
        combined = np.full((2, 2), 0.5, dtype=np.float32)
        hard_ex = np.full((2, 2), False, dtype=bool)
        result = run_l08(GRID, combined, hard_ex)
        assert set(result.metadata.keys()) == self.REQUIRED_KEYS

    def test_provenance_values(self):
        combined = np.full((2, 2), 0.5, dtype=np.float32)
        hard_ex = np.full((2, 2), False, dtype=bool)
        result = run_l08(GRID, combined, hard_ex)
        meta = result.metadata
        assert meta["layer"] == "L08"
        assert meta["rule_identifier"] == "OD-05"
        assert meta["threshold"] == RED_ZONE_THRESHOLD
        assert meta["amber_threshold"] == AMBER_THRESHOLD
        assert meta["crs"] == "EPSG:32644"
        assert meta["resolution_m"] == CANONICAL_RESOLUTION_METERS


# =========================================================================
# Phase 10 – Output array shapes
# =========================================================================

class TestOutputShapes:
    """red_zone and risk_tier arrays must match canonical grid dimensions."""

    def test_red_zone_shape(self):
        combined = np.full((2, 2), 0.5, dtype=np.float32)
        hard_ex = np.full((2, 2), False, dtype=bool)
        result = run_l08(GRID, combined, hard_ex)
        assert result.red_zone.shape == (GRID.height, GRID.width)

    def test_risk_tier_shape(self):
        combined = np.full((2, 2), 0.5, dtype=np.float32)
        hard_ex = np.full((2, 2), False, dtype=bool)
        result = run_l08(GRID, combined, hard_ex)
        assert result.risk_tier.shape == (GRID.height, GRID.width)


# =========================================================================
# Phase 11 – Hard exclusion precedence with valid H
# =========================================================================

class TestHardExclusionPrecedence:
    """Hard exclusion dominates even when H would not trigger red zone."""

    def test_hard_exclusion_true_valid_h(self):
        """H=0.5 is LOWER_RISK, but hard_exclusion=True forces RED."""
        combined = np.full((2, 2), 0.5, dtype=np.float32)
        hard_ex = np.full((2, 2), True, dtype=bool)
        result = run_l08(GRID, combined, hard_ex)
        assert result.red_zone.all()
        assert (result.risk_tier == RiskTier.RED.value).all()
        for rec in result.records:
            assert rec.red_zone == True
            assert rec.risk_tier == RiskTier.RED
            assert rec.quality_flag == QualityState.COMPLETE
            assert np.isclose(rec.combined_risk, 0.5, atol=1e-6)
