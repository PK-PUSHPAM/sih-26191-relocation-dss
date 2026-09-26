"""
Tabular Data Validation Functions.
Validates pandas DataFrames against ColumnContract and DatasetSchemaContract.
"""
from typing import List, Optional
import numpy as np
import pandas as pd
from .models import (
    ColumnContract,
    DatasetSchemaContract,
    ValidationIssue,
    ValidationSeverity,
)

def validate_empty_dataframe(df: pd.DataFrame, check_name: str = "empty_dataset_check") -> Optional[ValidationIssue]:
    """Check if the DataFrame is completely empty."""
    if df is None or df.empty or len(df) == 0:
        return ValidationIssue(
            check_name=check_name,
            severity=ValidationSeverity.ERROR,
            message="Dataset is empty (0 rows).",
        )
    return None

def validate_required_columns(
    df: pd.DataFrame, contract: DatasetSchemaContract
) -> List[ValidationIssue]:
    """Verify that all mandatory columns exist in the DataFrame."""
    issues = []
    df_columns = set(df.columns)
    for col_contract in contract.required_columns:
        if col_contract.required and col_contract.name not in df_columns:
            issues.append(
                ValidationIssue(
                    check_name="required_column_presence",
                    severity=ValidationSeverity.ERROR,
                    column=col_contract.name,
                    message=f"Missing mandatory column '{col_contract.name}'.",
                )
            )
    return issues

def validate_null_rates(
    df: pd.DataFrame, contract: DatasetSchemaContract
) -> List[ValidationIssue]:
    """Check null rates for each column against its contract."""
    issues = []
    total_rows = len(df)
    if total_rows == 0:
        return issues

    for col_contract in contract.required_columns:
        if col_contract.name not in df.columns:
            continue
        
        series = df[col_contract.name]
        null_count = int(series.isna().sum())
        null_rate = null_count / total_rows

        if not col_contract.nullable and null_count > 0:
            null_indices = list(df.index[series.isna()][:10])  # first 10 sample indices
            issues.append(
                ValidationIssue(
                    check_name="null_value_violation",
                    severity=ValidationSeverity.ERROR,
                    column=col_contract.name,
                    row_indices=null_indices,
                    message=f"Non-nullable column '{col_contract.name}' has {null_count} nulls ({null_rate:.1%}).",
                    details={"null_count": null_count, "null_rate": null_rate},
                )
            )
        elif null_rate > col_contract.max_null_rate:
            severity = (
                ValidationSeverity.ERROR if col_contract.required else ValidationSeverity.WARNING
            )
            issues.append(
                ValidationIssue(
                    check_name="null_rate_threshold_exceeded",
                    severity=severity,
                    column=col_contract.name,
                    message=(
                        f"Column '{col_contract.name}' null rate {null_rate:.1%} "
                        f"exceeds allowed limit of {col_contract.max_null_rate:.1%}."
                    ),
                    details={"null_count": null_count, "null_rate": null_rate, "max_allowed": col_contract.max_null_rate},
                )
            )
    return issues

def validate_primary_key_duplicates(
    df: pd.DataFrame, contract: DatasetSchemaContract
) -> List[ValidationIssue]:
    """Check uniqueness of primary key or identifier columns."""
    issues = []
    if not contract.primary_key or contract.primary_key not in df.columns:
        return issues

    pk = contract.primary_key
    duplicated_mask = df[pk].duplicated(keep=False)
    duplicate_count = int(duplicated_mask.sum())

    if duplicate_count > 0:
        dup_indices = list(df.index[duplicated_mask][:10])
        issues.append(
            ValidationIssue(
                check_name="primary_key_uniqueness",
                severity=ValidationSeverity.ERROR,
                column=pk,
                row_indices=dup_indices,
                message=f"Primary key '{pk}' contains {duplicate_count} duplicate entries.",
                details={"duplicate_count": duplicate_count},
            )
        )
    return issues

def validate_column_ranges_and_values(
    df: pd.DataFrame, contract: DatasetSchemaContract
) -> List[ValidationIssue]:
    """Validate numeric ranges and categorical vocabularies."""
    issues = []
    for col_contract in contract.required_columns:
        col = col_contract.name
        if col not in df.columns:
            continue

        series = df[col].dropna()
        if len(series) == 0:
            continue

        # Numeric Range Check
        if col_contract.min_value is not None:
            below_min = series < col_contract.min_value
            if below_min.any():
                bad_count = int(below_min.sum())
                issues.append(
                    ValidationIssue(
                        check_name="numeric_min_range_violation",
                        severity=ValidationSeverity.ERROR,
                        column=col,
                        message=f"Column '{col}' has {bad_count} values below minimum {col_contract.min_value}.",
                        details={"violations_count": bad_count, "min_allowed": col_contract.min_value},
                    )
                )

        if col_contract.max_value is not None:
            above_max = series > col_contract.max_value
            if above_max.any():
                bad_count = int(above_max.sum())
                issues.append(
                    ValidationIssue(
                        check_name="numeric_max_range_violation",
                        severity=ValidationSeverity.ERROR,
                        column=col,
                        message=f"Column '{col}' has {bad_count} values above maximum {col_contract.max_value}.",
                        details={"violations_count": bad_count, "max_allowed": col_contract.max_value},
                    )
                )

        # Categorical Vocabulary Check
        if col_contract.allowed_values is not None:
            allowed_set = set(col_contract.allowed_values)
            invalid_mask = ~series.isin(allowed_set)
            if invalid_mask.any():
                bad_count = int(invalid_mask.sum())
                sample_invalid = list(series[invalid_mask].unique()[:5])
                issues.append(
                    ValidationIssue(
                        check_name="categorical_vocabulary_violation",
                        severity=ValidationSeverity.ERROR,
                        column=col,
                        message=f"Column '{col}' has {bad_count} values outside allowed vocabulary. Invalid samples: {sample_invalid}",
                        details={"violations_count": bad_count, "invalid_samples": sample_invalid},
                    )
                )
    return issues
