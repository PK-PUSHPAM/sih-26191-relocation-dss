"""
Unified Validation Engine.
Coordinates schema, tabular, spatial, and constraint checks to produce a comprehensive ValidationReport.
"""
from typing import Any, Union
import pandas as pd
import geopandas as gpd

from .models import (
    DatasetSchemaContract,
    ValidationIssue,
    ValidationReport,
    ValidationSeverity,
)
from .tabular import (
    validate_empty_dataframe,
    validate_required_columns,
    validate_null_rates,
    validate_primary_key_duplicates,
    validate_column_ranges_and_values,
)
from .spatial import (
    validate_crs_presence_and_validity,
    validate_geometry_integrity,
    validate_geometry_types,
    validate_spatial_bounding_box,
)

class ValidationEngine:
    """Executes multi-level validation rules on tabular and spatial datasets."""

    @staticmethod
    def validate(
        data: Union[pd.DataFrame, gpd.GeoDataFrame],
        contract: DatasetSchemaContract,
    ) -> ValidationReport:
        report = ValidationReport(
            dataset_id=contract.dataset_id,
            is_valid=True,
        )

        # 1. Empty Check
        empty_issue = validate_empty_dataframe(data)
        report.total_checks += 1
        if empty_issue:
            report.add_issue(empty_issue)
            report.summary = "Validation FAILED: Dataset is empty."
            return report
        report.passed_checks += 1

        # 2. Required Columns Presence
        report.total_checks += 1
        col_issues = validate_required_columns(data, contract)
        if col_issues:
            for iss in col_issues:
                report.add_issue(iss)
        else:
            report.passed_checks += 1

        # 3. Null Rate Checks
        report.total_checks += 1
        null_issues = validate_null_rates(data, contract)
        if null_issues:
            for iss in null_issues:
                report.add_issue(iss)
        else:
            report.passed_checks += 1

        # 4. Primary Key & Duplicate Checks
        report.total_checks += 1
        dup_issues = validate_primary_key_duplicates(data, contract)
        if dup_issues:
            for iss in dup_issues:
                report.add_issue(iss)
        else:
            report.passed_checks += 1

        # 5. Value Ranges and Allowed Vocabularies
        report.total_checks += 1
        range_issues = validate_column_ranges_and_values(data, contract)
        if range_issues:
            for iss in range_issues:
                report.add_issue(iss)
        else:
            report.passed_checks += 1

        # 6. Spatial Validations (if GeoDataFrame)
        if isinstance(data, gpd.GeoDataFrame):
            # CRS Presence & Validity
            report.total_checks += 1
            crs_issues = validate_crs_presence_and_validity(data, contract)
            if crs_issues:
                for iss in crs_issues:
                    report.add_issue(iss)
            else:
                report.passed_checks += 1

            # Geometry Integrity
            report.total_checks += 1
            geom_issues = validate_geometry_integrity(data)
            if geom_issues:
                for iss in geom_issues:
                    report.add_issue(iss)
            else:
                report.passed_checks += 1

            # Geometry Types
            report.total_checks += 1
            type_issues = validate_geometry_types(data, contract)
            if type_issues:
                for iss in type_issues:
                    report.add_issue(iss)
            else:
                report.passed_checks += 1

            # Bounding Box Sanity Check
            report.total_checks += 1
            bbox_issues = validate_spatial_bounding_box(data)
            if bbox_issues:
                for iss in bbox_issues:
                    report.add_issue(iss)
            else:
                report.passed_checks += 1

        # Summary computation
        if report.errors_count == 0:
            report.is_valid = True
            report.summary = (
                f"Validation PASSED ({report.passed_checks}/{report.total_checks} checks passed, "
                f"{report.warnings_count} warnings)."
            )
        else:
            report.is_valid = False
            report.summary = (
                f"Validation FAILED ({report.errors_count} critical errors, "
                f"{report.warnings_count} warnings)."
            )

        return report
