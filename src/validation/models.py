"""
Data Validation Models and Contracts.
Defines structured validation issues, severity levels, and schema contracts.
"""
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

class ValidationSeverity(str, Enum):
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"

class ValidationIssue(BaseModel):
    check_name: str
    severity: ValidationSeverity
    message: str
    column: Optional[str] = None
    row_indices: Optional[List[int]] = None
    details: Optional[Dict[str, Any]] = None

class ValidationReport(BaseModel):
    dataset_id: str
    is_valid: bool  # True if zero ERROR severity issues
    total_checks: int = 0
    passed_checks: int = 0
    errors_count: int = 0
    warnings_count: int = 0
    issues: List[ValidationIssue] = Field(default_factory=list)
    summary: str = ""

    def add_issue(self, issue: ValidationIssue) -> None:
        self.issues.append(issue)
        if issue.severity == ValidationSeverity.ERROR:
            self.errors_count += 1
            self.is_valid = False
        elif issue.severity == ValidationSeverity.WARNING:
            self.warnings_count += 1

class ColumnContract(BaseModel):
    name: str
    dtype: str  # "int", "float", "str", "datetime", "geometry"
    required: bool = True
    nullable: bool = False
    max_null_rate: float = 0.0  # 0.0 means no nulls allowed
    min_value: Optional[float] = None
    max_value: Optional[float] = None
    allowed_values: Optional[List[Any]] = None

class DatasetSchemaContract(BaseModel):
    dataset_id: str
    expected_format: str  # "CSV", "GEOJSON", "SHP", "GPKG", "GEOTIFF"
    primary_key: Optional[str] = None
    required_columns: List[ColumnContract] = Field(default_factory=list)
    allow_extra_columns: bool = True
    expected_geometry_type: Optional[str] = None  # "Point", "Polygon", "MultiPolygon", "LineString"
    expected_crs: Optional[str] = None
    max_allowed_duplicate_rate: float = 0.0
