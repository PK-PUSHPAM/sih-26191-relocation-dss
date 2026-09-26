"""
Cryptographic Provenance and Manifest Generator.
Generates SHA-256 checksums, metadata payloads, and audit trails for ingested datasets.
"""
import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

class ProvenanceRecord(BaseModel):
    dataset_id: str
    source_id: str
    source_url: Optional[str] = None
    retrieval_timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    source_version: str = "v1.0"
    local_raw_path: str
    file_format: str
    file_size_bytes: int
    checksum_sha256: str
    original_crs: Optional[str] = None
    target_crs: Optional[str] = None
    geometry_type: Optional[str] = None
    spatial_extent: Optional[Dict[str, float]] = None
    temporal_extent: Optional[Dict[str, Optional[str]]] = None
    row_count: Optional[int] = None
    validation_status: str = "PENDING"  # PASSED, FAILED, WARNINGS
    warnings: List[str] = Field(default_factory=list)
    errors: List[str] = Field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return self.model_dump()

    def save_json(self, output_path: Path) -> None:
        """Save the provenance manifest to a JSON file."""
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, indent=2)

def compute_sha256(file_path: Path, chunk_size: int = 65536) -> str:
    """Compute SHA-256 checksum of any file."""
    if not file_path.exists():
        raise FileNotFoundError(f"Cannot compute checksum, file not found: {file_path}")
    
    hasher = hashlib.sha256()
    with open(file_path, "rb") as f:
        while chunk := f.read(chunk_size):
            hasher.update(chunk)
    return hasher.hexdigest()

def generate_provenance_record(
    dataset_id: str,
    source_id: str,
    raw_file_path: Path,
    file_format: str,
    source_url: Optional[str] = None,
    source_version: str = "1.0",
    original_crs: Optional[str] = None,
    target_crs: Optional[str] = None,
    geometry_type: Optional[str] = None,
    spatial_extent: Optional[Dict[str, float]] = None,
    temporal_extent: Optional[Dict[str, Optional[str]]] = None,
    row_count: Optional[int] = None,
) -> ProvenanceRecord:
    """
    Construct a complete ProvenanceRecord for an ingested raw file.
    """
    size_bytes = raw_file_path.stat().st_size
    checksum = compute_sha256(raw_file_path)

    return ProvenanceRecord(
        dataset_id=dataset_id,
        source_id=source_id,
        source_url=source_url,
        source_version=source_version,
        local_raw_path=str(raw_file_path.as_posix()),
        file_format=file_format.upper(),
        file_size_bytes=size_bytes,
        checksum_sha256=checksum,
        original_crs=original_crs,
        target_crs=target_crs,
        geometry_type=geometry_type,
        spatial_extent=spatial_extent,
        temporal_extent=temporal_extent,
        row_count=row_count,
    )
