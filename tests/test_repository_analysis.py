from pathlib import Path

from fastapi.testclient import TestClient

from app.analysis.repository import analyze_repository
from app.main import app


def test_manifest_discovery_and_parsing(fixtures_dir: Path):
    repo = fixtures_dir / "fastapi"
    result = analyze_repository(repo)

    assert result["repository"]["name"] == "fastapi"
    assert result["services"]
    assert len(result["services"]) == 1
    service = result["services"][0]
    assert service["name"] == "fastapi"
    assert any(dep["name"] == "fastapi" for dep in service["dependencies"])


def test_mern_service_resolution_and_technology_detection(fixtures_dir: Path):
    repo = fixtures_dir / "mern"
    result = analyze_repository(repo)

    service_names = {svc["name"] for svc in result["services"]}
    assert {"frontend", "backend"}.issubset(service_names)

    frontend = next(s for s in result["services"] if s["name"] == "frontend")
    backend = next(s for s in result["services"] if s["name"] == "backend")

    assert frontend["technology"]["framework"]["value"] == "React"
    assert backend["technology"]["framework"]["value"] == "Express"
    assert backend["ports"][0]["port"] == 5000
    assert any(env["name"] == "MONGO_URI" for env in backend["environment_variables"])
    assert all(env["name"] != "MONGO_URI" for env in frontend["environment_variables"] if "MONGO_URI" in env.get("name", ""))
    assert backend["entry_points"][0]["path"].endswith("server.js")
    assert not any(entry["path"].endswith("App.js") for entry in frontend["entry_points"])
    assert not any(rel["source"] == "frontend" and rel["target"] == "backend" for rel in result["relationships"])
    assert not any(rel["source"] == "backend" and rel["target"] == "frontend" for rel in result["relationships"])
    assert not any(rel["relationship"] == "http_dependency" and rel["source"] == "backend" and rel["target"] == "http_client" for rel in result["relationships"])
    assert any("server.js" in file for file in result["discovered_files"])
    assert any("App.js" in file for file in result["discovered_files"])


def test_python_multi_manifest_service_resolution(fixtures_dir: Path):
    repo = fixtures_dir / "python_multi_manifest"
    result = analyze_repository(repo)

    assert len(result["services"]) == 1
    service = result["services"][0]
    assert service["name"] == "backend"
    assert any(dep["name"] == "fastapi" for dep in service["dependencies"])
    assert service["technology"]["framework"]["value"] == "FastAPI"


def test_nextjs_detection(fixtures_dir: Path):
    repo = fixtures_dir / "nextjs"
    result = analyze_repository(repo)

    service = result["services"][0]
    assert service["technology"]["framework"]["value"] == "Next.js"


def test_unknown_repository_gives_warning(fixtures_dir: Path):
    repo = fixtures_dir / "unknown"
    result = analyze_repository(repo)

    assert result["analysis_warnings"]
    assert result["services"] == []


def test_empty_repository_behavior(fixtures_dir: Path):
    repo = fixtures_dir / "unknown"
    (repo / "README.md").unlink(missing_ok=True)
    result = analyze_repository(repo)

    assert result["repository"]["name"] == "unknown"
    assert result["services"] == []
    assert result["analysis_warnings"]


def test_repository_analysis_api(fixtures_dir: Path):
    client = TestClient(app)
    response = client.post("/repositories/analyze", json={"repository_path": str(fixtures_dir / "fastapi")})

    assert response.status_code == 200
    payload = response.json()
    assert payload["repository"]["name"] == "fastapi"
    assert payload["services"]


def test_malformed_manifest_is_warned_and_ignored(tmp_path: Path):
    repo = tmp_path / "malformed"
    repo.mkdir()
    (repo / "package.json").write_text('{"name": "broken"', encoding="utf-8")

    result = analyze_repository(repo)

    assert result["services"] == []
    assert any("malformed" in warning.lower() or "json" in warning.lower() for warning in result["analysis_warnings"])


def test_env_and_relationships_are_analyzed_for_mern(fixtures_dir: Path):
    repo = fixtures_dir / "mern"
    result = analyze_repository(repo)

    backend = next(s for s in result["services"] if s["name"] == "backend")
    assert any(env["name"] == "MONGO_URI" for env in backend["environment_variables"])
    assert any(rel["relationship"] == "database_dependency" for rel in result["relationships"])


def test_multi_service_repository_keeps_service_boundaries_and_env_scope(fixtures_dir: Path):
    repo = fixtures_dir / "multi_service"
    result = analyze_repository(repo)

    service_names = {svc["name"] for svc in result["services"]}
    assert {"frontend", "backend", "worker"}.issubset(service_names)

    frontend = next(s for s in result["services"] if s["name"] == "frontend")
    backend = next(s for s in result["services"] if s["name"] == "backend")
    worker = next(s for s in result["services"] if s["name"] == "worker")

    assert frontend["technology"]["framework"]["value"] == "React"
    assert backend["technology"]["framework"]["value"] == "Express"
    assert worker["technology"]["framework"]["value"] == "FastAPI" or worker["technology"]["framework"]["value"] == "Python"

    assert not any(env["name"] == "REDIS_URL" for env in frontend["environment_variables"])
    assert not any(env["name"] == "SERVICE_API_URL" for env in backend["environment_variables"])
    assert any(env["name"] == "REDIS_URL" for env in worker["environment_variables"])
    assert not any(rel["source"] == "frontend" and rel["target"] == "backend" for rel in result["relationships"])
    assert not any(rel["source"] == "backend" and rel["target"] == "frontend" for rel in result["relationships"])
