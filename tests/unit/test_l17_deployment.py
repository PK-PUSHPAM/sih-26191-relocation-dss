from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_backend_runtime_contract():
    requirements = (ROOT / "requirements.txt").read_text(encoding="utf-8")
    dockerfile = (ROOT / "docker" / "Dockerfile.backend").read_text(encoding="utf-8")

    assert "fastapi==" in requirements
    assert "uvicorn[standard]==" in requirements
    assert "SQLAlchemy==" in requirements
    assert "GeoAlchemy2==" in requirements
    assert "ortools==" in requirements
    assert "COPY requirements.txt ./" in dockerfile
    assert "pip install --no-cache-dir -r requirements.txt" in dockerfile
    assert "src.api.app:app" in dockerfile
    assert "|| true" not in dockerfile
    assert "HEALTHCHECK" in dockerfile


def test_frontend_runtime_contract():
    dockerfile = (ROOT / "docker" / "Dockerfile.frontend").read_text(encoding="utf-8")
    package_json = (ROOT / "frontend" / "package.json").read_text(encoding="utf-8")

    assert '"build": "vite build"' in package_json
    assert "npm install --no-audit --no-fund" in dockerfile
    assert 'CMD ["npm", "run", "dev"]' in dockerfile
    assert "|| true" not in dockerfile


def test_compose_contract():
    compose = (ROOT / "docker-compose.yml").read_text(encoding="utf-8")

    assert "postgis/postgis:16-3.4" in compose
    assert "docker/Dockerfile.backend" in compose
    assert "docker/Dockerfile.frontend" in compose
    assert "condition: service_healthy" in compose
    assert "8000:8000" in compose
    assert "3000:3000" in compose


def test_ci_contract():
    workflow = ROOT / ".github" / "workflows" / "ci.yml"
    assert workflow.exists()
    content = workflow.read_text(encoding="utf-8")

    assert "python -m pytest -q" in content
    assert "npm run build" in content
    assert "docker compose config" in content


def test_l17_documentation_exists():
    spec = ROOT / "docs" / "layer-specs" / "L17_testing_deploy.md"
    assert spec.exists()
    content = spec.read_text(encoding="utf-8")

    for required in ("pytest", "Docker Compose", "frontend", "backend", "audit"):
        assert required.lower() in content.lower()
