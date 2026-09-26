"""
Data Ingestion and Curation Pipeline.
Implements the Raw -> Staging -> Validation -> Curated lifecycle with full cryptographic provenance.
"""
import json
import logging
from pathlib import Path
from typing import Optional, Tuple, Union
import pandas as pd
import geopandas as gpd

from src.common.config import REPO_ROOT, get_source_by_id
from src.common.provenance import generate_provenance_record, ProvenanceRecord
from src.common.crs import CANONICAL_PROJECTED_CRS_STR
from src.validation.models import DatasetSchemaContract, ValidationReport
from src.validation.engine import ValidationEngine
from .adapters import get_adapter_for_file

logger = logging.getLogger(__name__)

class IngestionPipeline:
    """Manages the full validation and curation lifecycle for a source dataset."""

    def __init__(self, repo_root: Optional[Path] = None):
        self.root = repo_root or REPO_ROOT
        self.raw_dir = self.root / "data" / "raw"
        self.staging_dir = self.root / "data" / "staging"
        self.curated_dir = self.root / "data" / "curated"

        # Ensure directory structure exists
        self.raw_dir.mkdir(parents=True, exist_ok=True)
        self.staging_dir.mkdir(parents=True, exist_ok=True)
        self.curated_dir.mkdir(parents=True, exist_ok=True)

    def process_dataset(
        self,
        raw_file_path: Path,
        contract: DatasetSchemaContract,
        source_id: Optional[str] = None,
        source_version: str = "1.0",
        target_crs: Optional[str] = None,
    ) -> Tuple[bool, ValidationReport, ProvenanceRecord]:
        """
        Ingests a raw dataset, validates it against the contract, and promotes to curated if valid.
        Returns (is_promoted, validation_report, provenance_record).
        """
        raw_path = Path(raw_file_path)
        if not raw_path.exists():
            raise FileNotFoundError(f"Raw file not found: {raw_path}")

        source_meta = get_source_by_id(source_id or contract.dataset_id) or {}
        source_url = source_meta.get("official_url")

        logger.info(f"Starting ingestion pipeline for dataset: {contract.dataset_id} from {raw_path.name}")

        # 1. Adapt and load raw file into staging object
        adapter = get_adapter_for_file(raw_path)
        data: Union[pd.DataFrame, gpd.GeoDataFrame] = adapter.read()

        # 2. Extract spatial and temporal metadata
        original_crs = None
        geometry_type = None
        spatial_extent = None
        row_count = len(data)

        if isinstance(data, gpd.GeoDataFrame):
            if data.crs:
                original_crs = str(data.crs)
            if "geometry" in data.columns and not data.empty:
                geometry_type = str(data.geometry.dropna().iloc[0].geom_type)
                tb = data.total_bounds
                spatial_extent = {
                    "min_x": float(tb[0]),
                    "min_y": float(tb[1]),
                    "max_x": float(tb[2]),
                    "max_y": float(tb[3]),
                }

        # 3. Generate initial provenance record
        provenance = generate_provenance_record(
            dataset_id=contract.dataset_id,
            source_id=source_id or contract.dataset_id,
            raw_file_path=raw_path,
            file_format=contract.expected_format,
            source_url=source_url,
            source_version=source_version,
            original_crs=original_crs,
            target_crs=target_crs,
            geometry_type=geometry_type,
            spatial_extent=spatial_extent,
            row_count=row_count,
        )

        # 4. Execute Validation Engine
        validation_report = ValidationEngine.validate(data, contract)

        # Attach validation outcomes to provenance
        provenance.warnings = [iss.message for iss in validation_report.issues if iss.severity == "WARNING"]
        provenance.errors = [iss.message for iss in validation_report.issues if iss.severity == "ERROR"]

        if not validation_report.is_valid:
            provenance.validation_status = "FAILED"
            logger.error(
                f"Validation FAILED for {contract.dataset_id}. {validation_report.errors_count} critical errors found. "
                "Promotion to curated is BLOCKED."
            )
            # Save staging report
            staging_report_path = self.staging_dir / f"{contract.dataset_id}_validation_report.json"
            with open(staging_report_path, "w", encoding="utf-8") as f:
                json.dump(validation_report.model_dump(), f, indent=2)

            return False, validation_report, provenance

        # 5. Promotion to Curated
        provenance.validation_status = "PASSED"
        logger.info(f"Validation PASSED for {contract.dataset_id}. Promoting to curated.")

        # If spatial and target_crs specified, handle explicit reprojection for curated artifact
        curated_data = data.copy()
        if isinstance(curated_data, gpd.GeoDataFrame) and target_crs:
            if curated_data.crs and str(curated_data.crs) != target_crs:
                curated_data = curated_data.to_crs(target_crs)
                provenance.target_crs = target_crs

        # Save curated artifact
        if isinstance(curated_data, gpd.GeoDataFrame):
            curated_path = self.curated_dir / f"{contract.dataset_id}.geojson"
            curated_data.to_file(curated_path, driver="GeoJSON")
        else:
            curated_path = self.curated_dir / f"{contract.dataset_id}.csv"
            curated_data.to_csv(curated_path, index=False)


        # Save provenance manifest alongside curated dataset
        manifest_path = self.curated_dir / f"{contract.dataset_id}_manifest.json"
        provenance.save_json(manifest_path)

        logger.info(f"Curated artifact successfully saved to: {curated_path.name}")
        return True, validation_report, provenance
