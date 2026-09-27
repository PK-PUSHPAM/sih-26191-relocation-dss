"""
Layer L08 - Red‑Zone Engine

Consumes the L07 combined multi‑hazard risk raster and a pre‑computed Boolean
hard_exclusion raster and produces red_zone, risk_tier and provenance fields.
All output records are persistence‑ready for the `risk_cell` table.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Mapping, Optional, Tuple, List

import numpy as np
from pyproj import CRS

from src.common.crs import CANONICAL_PROJECTED_CRS_STR
from src.spatial.grid import (
    CANONICAL_RESOLUTION_METERS,
    DEFAULT_NODATA_FLOAT,
    CanonicalGridDefinition,
)
from src.risk.multi_hazard import QualityState, MultiHazardResult, validate_l07_grid

# ---------------------------------------------------------------------------
# Constants – thresholds are frozen by the contract
# ---------------------------------------------------------------------------
RED_ZONE_THRESHOLD = 0.70
AMBER_THRESHOLD = 0.55


class RiskTier(str, Enum):
    """Risk tier identifiers used in persistence records."""

    RED = "red"
    AMBER = "amber"
    LOWER_RISK = "lower_risk"


@dataclass(frozen=True)
class RedZoneRecord:
    """Persistence‑ready record for a single cell after L08 processing.

    All L07 fields are retained unchanged; L08 adds `red_zone`, `risk_tier`
    and updates `quality_flag` where appropriate.
    """

    cell_id: int
    h_landslide: Optional[float]
    h_flood: Optional[float]
    h_rain: Optional[float]
    combined_risk: Optional[float]
    red_zone: bool
    risk_tier: RiskTier
    quality_flag: QualityState
    geometry: Any

    def to_dict(self) -> Mapping[str, Any]:
        return {
            "cell_id": self.cell_id,
            "h_landslide": self.h_landslide,
            "h_flood": self.h_flood,
            "h_rain": self.h_rain,
            "combined_risk": self.combined_risk,
            "red_zone": self.red_zone,
            "risk_tier": self.risk_tier.value,
            "quality_flag": self.quality_flag.value,
            "geometry": self.geometry,
        }


@dataclass(frozen=True)
class L08Result:
    """Container returned by the L08 engine.

    Mirrors the structure of :class:`MultiHazardResult` but adds the L08‑specific
    fields.  The ``metadata`` dictionary contains provenance for both L07 and the
    hard‑exclusion input.
    """

    red_zone: np.ndarray
    risk_tier: np.ndarray
    records: Tuple[RedZoneRecord, ...]
    metadata: Mapping[str, Any]

    def to_dict(self) -> Mapping[str, Any]:
        return {
            "red_zone": self.red_zone.tolist(),
            "risk_tier": self.risk_tier.tolist(),
            "records": [r.to_dict() for r in self.records],
            "metadata": dict(self.metadata),
        }


def _validate_grid(grid: CanonicalGridDefinition) -> None:
    """Validate that *grid* conforms to the L03 canonical definition.

    Re‑uses the L07 validation logic; raises ``ValueError`` with an informative
    message if the contract is violated.
    """

    validate_l07_grid(grid)


def _validate_hard_exclusion_metadata(metadata: Mapping[str, Any]) -> None:
    """Validate that hard-exclusion provenance contains required fields.

    The frozen L08 contract requires the hard-exclusion raster to be traceable to
    a source, checksum, and timestamp. Raises ``ValueError`` if any required
    field is missing.
    """
    if metadata is None:
        raise ValueError("hard_exclusion_metadata is required")
    required = ("source", "checksum", "timestamp")
    missing = [k for k in required if k not in metadata]
    if missing:
        raise ValueError(
            f"hard_exclusion_metadata missing required provenance fields: {missing}"
        )


def _validate_raster(name: str, array: np.ndarray, grid: CanonicalGridDefinition) -> None:
    """Common raster validation.

    * ``array`` must be a 2‑D ``numpy`` array with shape ``(grid.height, grid.width)``.
    * ``combined_risk`` may contain the sentinel ``DEFAULT_NODATA_FLOAT`` and
      any finite or invalid float values (per‑cell handling in ``run_l08``).
    * ``hard_exclusion`` must be a Boolean array (dtype ``bool``) containing only
      ``True``/``False`` – no integer coercion is performed.
    """

    if array.shape != (grid.height, grid.width):
        raise ValueError(
            f"{name} dimensions {array.shape} do not match the canonical grid {grid.height}x{grid.width}"
        )

    if name == "hard_exclusion":
        if array.dtype != np.bool_:
            raise ValueError("hard_exclusion raster must be of Boolean dtype")
        return

    if not np.issubdtype(array.dtype, np.floating):
        raise ValueError("combined_risk raster must be a floating point array")

    # Global NaN/Inf/range checks removed – handled per‑cell in run_l08.


def _tier_from_h(h: Optional[float]) -> RiskTier:
    """Map a valid combined risk value to a :class:`RiskTier`."""

    if h is None:
        return RiskTier.LOWER_RISK
    if h >= RED_ZONE_THRESHOLD:
        return RiskTier.RED
    if h >= AMBER_THRESHOLD:
        return RiskTier.AMBER
    return RiskTier.LOWER_RISK


def run_l08(
    grid: CanonicalGridDefinition,
    combined_risk: np.ndarray,
    hard_exclusion: np.ndarray,
    l07_metadata: Mapping[str, Any] | None = None,
    hard_exclusion_metadata: Mapping[str, Any] | None = None,
) -> L08Result:
    """Execute the L08 red‑zone engine.

    Parameters
    ----------
    grid:
        Canonical grid (must satisfy L03 contract).
    combined_risk:
        Float raster from L07; ``DEFAULT_NODATA_FLOAT`` denotes missing values.
    hard_exclusion:
        Boolean raster indicating hard‑exclusion cells.
    l07_metadata:
        Propagated ``MultiHazardResult.metadata``.
    hard_exclusion_metadata:
        Required provenance for the hard‑exclusion raster; must contain
        ``source``, ``checksum``, and ``timestamp`` keys.
    """

    if combined_risk is None:
        raise ValueError("combined_risk raster is required")

    if hard_exclusion is None:
        raise ValueError("hard_exclusion raster is required")

    _validate_hard_exclusion_metadata(hard_exclusion_metadata)

    _validate_grid(grid)
    _validate_raster("combined_risk", combined_risk, grid)
    _validate_raster("hard_exclusion", hard_exclusion, grid)

    red_zone_arr = np.full((grid.height, grid.width), False, dtype=bool)
    tier_arr = np.full((grid.height, grid.width), RiskTier.LOWER_RISK, dtype=object)
    records: List[RedZoneRecord] = []

    for cell_id in range(grid.total_cells):
        row, col = grid.row_col_from_cell_id(cell_id)
        h_val = combined_risk[row, col]
        he_flag = hard_exclusion[row, col]

        if h_val == DEFAULT_NODATA_FLOAT:
            quality = QualityState.NON_EVALUABLE
            red_zone = bool(he_flag)
            tier = RiskTier.RED if he_flag else RiskTier.LOWER_RISK
        else:
            # Determine if combined risk value is invalid (NaN, +/-inf, out of [0,1] range)
            if (np.isnan(h_val) or np.isinf(h_val) or h_val < 0.0 or h_val > 1.0):
                quality = QualityState.INVALID
                red_zone = bool(he_flag)
                tier = RiskTier.RED if he_flag else RiskTier.LOWER_RISK
            else:
                quality = QualityState.COMPLETE
                red_zone = bool(he_flag) or (h_val >= RED_ZONE_THRESHOLD)
                tier = RiskTier.RED if he_flag else _tier_from_h(h_val)

        red_zone_arr[row, col] = red_zone
        tier_arr[row, col] = tier

        # Preserve L07 hazard values if supplied via metadata.
        h_landslide = h_flood = h_rain = None
        if l07_metadata:
            recs = l07_metadata.get("records")
            if isinstance(recs, (list, tuple)) and len(recs) > cell_id:
                rec = recs[cell_id]
                h_landslide = getattr(rec, "h_landslide", None)
                h_flood = getattr(rec, "h_flood", None)
                h_rain = getattr(rec, "h_rain", None)

        _invalid_or_missing = (
            h_val == DEFAULT_NODATA_FLOAT
            or np.isnan(h_val)
            or np.isinf(h_val)
            or h_val < 0.0
            or h_val > 1.0
        )

        records.append(
            RedZoneRecord(
                cell_id=cell_id,
                h_landslide=h_landslide,
                h_flood=h_flood,
                h_rain=h_rain,
                combined_risk=None if _invalid_or_missing else float(h_val),
                red_zone=red_zone,
                risk_tier=tier,
                quality_flag=quality,
                geometry=grid.cell_polygon(row, col),
            )
        )

    provenance: dict[str, Any] = {
        "layer": "L08",
        "model_version": "L08-v1.0",
        "rule_identifier": "OD-05",
        "threshold": RED_ZONE_THRESHOLD,
        "amber_threshold": AMBER_THRESHOLD,
        "execution_timestamp": datetime.now(timezone.utc).isoformat(),
        "crs": CANONICAL_PROJECTED_CRS_STR,
        "resolution_m": CANONICAL_RESOLUTION_METERS,
        "grid": grid.to_dict(),
        "l07_input": dict(l07_metadata or {}),
        "hard_exclusion_input": dict(hard_exclusion_metadata or {}),
    }

    return L08Result(
        red_zone=red_zone_arr,
        risk_tier=np.vectorize(lambda t: t.value)(tier_arr),
        records=tuple(records),
        metadata=provenance,
    )
