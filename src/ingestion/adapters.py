"""
Multi-format Data Ingestion Adapters.
Parses CSV, GeoJSON, Shapefile, GeoPackage, and GeoTIFF into in-memory pandas/geopandas/metadata objects.
"""
from pathlib import Path
from typing import Any, Dict, Optional, Tuple, Union
import pandas as pd
import geopandas as gpd

class BaseAdapter:
    """Base class for all ingestion adapters."""

    def __init__(self, file_path: Path):
        self.file_path = Path(file_path)
        if not self.file_path.exists():
            raise FileNotFoundError(f"Source file does not exist: {self.file_path}")

class CsvAdapter(BaseAdapter):
    """Adapter for tabular CSV datasets."""

    def read(self, **kwargs) -> pd.DataFrame:
        return pd.read_csv(self.file_path, **kwargs)

class GeoJsonAdapter(BaseAdapter):
    """Adapter for GeoJSON vector layers."""

    def read(self, **kwargs) -> gpd.GeoDataFrame:
        return gpd.read_file(self.file_path, driver="GeoJSON", **kwargs)

class ShapefileAdapter(BaseAdapter):
    """Adapter for ESRI Shapefile vector layers."""

    def read(self, **kwargs) -> gpd.GeoDataFrame:
        return gpd.read_file(self.file_path, **kwargs)

class GeoPackageAdapter(BaseAdapter):
    """Adapter for OGC GeoPackage vector layers."""

    def read(self, layer: Optional[str] = None, **kwargs) -> gpd.GeoDataFrame:
        return gpd.read_file(self.file_path, layer=layer, **kwargs)

def get_adapter_for_file(file_path: Union[str, Path]) -> BaseAdapter:
    """Factory returning the appropriate adapter based on file extension."""
    p = Path(file_path)
    suffix = p.suffix.lower()

    if suffix == ".csv":
        return CsvAdapter(p)
    elif suffix in (".geojson", ".json"):
        return GeoJsonAdapter(p)
    elif suffix == ".shp":
        return ShapefileAdapter(p)
    elif suffix == ".gpkg":
        return GeoPackageAdapter(p)
    else:
        raise ValueError(f"Unsupported file format '{suffix}' for file: {p.name}")
