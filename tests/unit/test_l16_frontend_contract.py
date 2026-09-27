from pathlib import Path

ROOT = Path(__file__).parents[2]
FRONTEND = ROOT / "frontend"

def test_l16_has_required_dashboard_screens():
    app = (FRONTEND / "src" / "App.jsx").read_text(encoding="utf-8")
    required = ["\"overview\"", "\"hazards\"", "\"red-zones\"", "\"habitations\"", "\"sites\"", "\"capacity\"", "\"planner\"", "\"allocations\"", "\"methodology\"", "\"reports\""]
    for item in required:
        assert item in app

def test_l16_api_client_exposes_required_routes():
    api = (FRONTEND / "src" / "api.js").read_text(encoding="utf-8")
    for route in ["/api/v1/admin-units", "/api/v1/habitations", "/api/v1/hazards", "/api/v1/risk/map", "/api/v1/sites", "/api/v1/priorities", "/api/v1/optimize", "/api/v1/reports/"]:
        assert route in api

def test_l16_has_maplibre_and_report_exports():
    main = (FRONTEND / "src" / "main.jsx").read_text(encoding="utf-8")
    map_view = (FRONTEND / "src" / "map" / "MapView.jsx").read_text(encoding="utf-8")
    export_js = (FRONTEND / "src" / "export.js").read_text(encoding="utf-8")
    assert "maplibre-gl" in main
    assert "maplibregl.Map" in map_view
    assert "downloadMarkdown" in export_js
    assert "printReport" in export_js

def test_l16_package_has_build_script():
    package = (FRONTEND / "package.json").read_text(encoding="utf-8")
    assert '"build": "vite build"' in package
