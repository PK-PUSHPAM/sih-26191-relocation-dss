"""
Configuration Loader and Registry.
Loads and caches YAML configurations from config/ directory.
"""
from pathlib import Path
from typing import Any, Dict, Optional
import yaml
import logging

logger = logging.getLogger(__name__)

# Base path resolution
REPO_ROOT = Path(__file__).resolve().parent.parent.parent
CONFIG_DIR = REPO_ROOT / "config"

_CONFIG_CACHE: Dict[str, Dict[str, Any]] = {}

def get_config_dir() -> Path:
    return CONFIG_DIR

def load_yaml_config(filename: str, use_cache: bool = True) -> Dict[str, Any]:
    """
    Load a YAML configuration file from the config directory.
    """
    if use_cache and filename in _CONFIG_CACHE:
        return _CONFIG_CACHE[filename]

    file_path = CONFIG_DIR / filename
    if not file_path.exists():
        raise FileNotFoundError(f"Configuration file not found: {file_path}")

    with open(file_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}

    if use_cache:
        _CONFIG_CACHE[filename] = data
    return data

def get_sources_config() -> Dict[str, Any]:
    return load_yaml_config("sources.yaml")

def get_hazards_config() -> Dict[str, Any]:
    return load_yaml_config("hazards.yaml")

def get_weights_config() -> Dict[str, Any]:
    return load_yaml_config("weights.yaml")

def get_thresholds_config() -> Dict[str, Any]:
    return load_yaml_config("thresholds.yaml")

def get_source_by_id(source_id: str) -> Optional[Dict[str, Any]]:
    """Retrieve metadata for a specific source_id from sources.yaml."""
    cfg = get_sources_config()
    for s in cfg.get("sources", []):
        if s.get("source_id") == source_id:
            return s
    return None
