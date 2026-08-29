from pathlib import Path

from fastapi.testclient import TestClient

from app.analysis.repository import analyze_repository
from app.main import app
from app.planning.planner import DeploymentPlanner
from app.planning.validators import DeploymentPlanValidator


def test_mern_deployment_plan_is_valid(fixtures_dir: Path):
    repo = fixtures_dir / "mern"
    analysis = analyze_repository(repo)

    plan = DeploymentPlanner().plan(analysis)
    validation = DeploymentPlanValidator().validate(plan)

    assert validation["valid"] is True
    assert plan["deployment_readiness"] == "requires_confirmation"
    assert plan["deployment_ready"] is False
    assert {service["name"] for service in plan["services"]} >= {"frontend", "backend"}

    backend = next(service for service in plan["services"] if service["name"] == "backend")
    frontend = next(service for service in plan["services"] if service["name"] == "frontend")

    assert backend["deployment_type"] == "container"
    assert backend["runtime"] == "Node.js"
    assert backend["framework"] == "Express"
    assert backend["port"] == 5000
    assert backend["start_command"] == "node server.js"
    assert backend["dependency_install_command"] == "npm install"
    assert backend["build_command"] is None
    assert any(dep["name"] == "MongoDB" for dep in plan["external_dependencies"])
    assert frontend["port"] is None
    assert frontend["production_serving_strategy"] == "unknown"
    assert frontend["exposure"] == "requires_confirmation"


def test_fastapi_deployment_plan_is_valid(fixtures_dir: Path):
    repo = fixtures_dir / "fastapi"
    analysis = analyze_repository(repo)

    plan = DeploymentPlanner().plan(analysis)
    validation = DeploymentPlanValidator().validate(plan)

    service = plan["services"][0]
    assert validation["valid"] is True
    assert plan["deployment_readiness"] == "ready"
    assert plan["deployment_ready"] is True
    assert service["name"] == "fastapi"
    assert service["runtime"] == "Python"
    assert service["framework"] == "FastAPI"
    assert service["port"] == 8000
    assert service["start_command"] == "uvicorn app.main:app --host 0.0.0.0 --port 8000"
    assert service["production_serving_strategy"] == "uvicorn"
    assert all("MONGO_URI" not in env for env in service["required_environment_variables"])


def test_multi_service_repository_creates_independent_service_plans(fixtures_dir: Path):
    repo = fixtures_dir / "multi_service"
    analysis = analyze_repository(repo)

    plan = DeploymentPlanner().plan(analysis)
    service_names = {service["name"] for service in plan["services"]}

    assert {"frontend", "backend", "worker"}.issubset(service_names)
    assert len(plan["services"]) == 3
    for service in plan["services"]:
        assert service["deployment_type"] == "container"
        assert service["runtime"]


def test_unknown_repository_does_not_invent_deployment_details(fixtures_dir: Path):
    repo = fixtures_dir / "unknown"
    analysis = analyze_repository(repo)

    plan = DeploymentPlanner().plan(analysis)

    assert plan["services"] == []
    assert plan["warnings"]
    assert not plan["deployment_ready"]


def test_missing_port_produces_warning_and_blocker():
    analysis = {
        "repository": {"name": "example", "path": "/tmp/example"},
        "services": [{
            "name": "worker",
            "path": "/tmp/example/worker",
            "technology": {
                "runtime": {"value": "Python"},
                "framework": {"value": "Python"},
                "language": {"value": "Python"},
            },
            "entry_points": [],
            "ports": [],
            "environment_variables": [],
            "manifests": [],
            "dependencies": [],
        }],
        "external_dependencies": [],
        "relationships": [],
        "analysis_warnings": [],
    }

    plan = DeploymentPlanner().plan(analysis)
    validation = DeploymentPlanValidator().validate(plan)

    assert any("port" in warning.lower() for warning in plan["warnings"])
    assert plan["deployment_ready"] is False
    assert plan["deployment_readiness"] in {"requires_confirmation", "blocked"}
    assert validation["valid"] is False


def test_missing_start_command_is_not_fabricated():
    analysis = {
        "repository": {"name": "example", "path": "/tmp/example"},
        "services": [{
            "name": "service",
            "path": "/tmp/example/service",
            "technology": {
                "runtime": {"value": "Node.js"},
                "framework": {"value": "Unknown"},
                "language": {"value": "JavaScript"},
            },
            "entry_points": [],
            "ports": [{"port": 3000, "confidence": 0.7, "source": "source"}],
            "environment_variables": [],
            "manifests": ["/tmp/example/service/package.json"],
            "dependencies": [],
        }],
        "external_dependencies": [],
        "relationships": [],
        "analysis_warnings": [],
    }

    plan = DeploymentPlanner().plan(analysis)
    service = plan["services"][0]

    assert service["start_command"] is None
    assert any("start command" in warning.lower() for warning in plan["warnings"])


def test_environment_variables_are_not_included_as_secret_values(fixtures_dir: Path):
    repo = fixtures_dir / "mern"
    analysis = analyze_repository(repo)

    plan = DeploymentPlanner().plan(analysis)
    backend = next(service for service in plan["services"] if service["name"] == "backend")

    env_names = {entry["name"] for entry in backend["required_environment_variables"]}
    assert "MONGO_URI" in env_names
    assert all("mongodb://" not in str(entry.get("source", "")) or "MONGO_URI" not in entry.get("name", "") for entry in backend["required_environment_variables"])
    assert all(entry.get("value") is None for entry in backend["required_environment_variables"])


def test_frontend_exposure_requires_confirmation_when_serving_is_unknown(fixtures_dir: Path, tmp_path: Path):
    repo = fixtures_dir / "mern"
    analysis = analyze_repository(repo)

    plan = DeploymentPlanner().plan(analysis)
    frontend = next(service for service in plan["services"] if service["name"] == "frontend")

    assert frontend["port"] is None
    assert frontend["production_serving_strategy"] == "unknown"
    assert frontend["exposure"] != "public"
    assert frontend["deployment_readiness"] == "requires_confirmation"
    assert frontend["deployment_ready"] is False
    assert plan["deployment_readiness"] == "requires_confirmation"
    assert plan["deployment_ready"] is False

    service_dir = tmp_path / "public-ui"
    service_dir.mkdir()
    (service_dir / "package.json").write_text(
        '{"scripts": {"start": "vite preview --host 0.0.0.0 --port 4173", "build": "vite build"}}',
        encoding="utf-8",
    )

    service = {
        "name": "public-ui",
        "path": str(service_dir),
        "technology": {
            "runtime": {"value": "Node.js"},
            "framework": {"value": "React"},
            "language": {"value": "JavaScript"},
        },
        "entry_points": [{"path": str(service_dir / "src/index.js"), "confidence": 0.9, "evidence": ["entry"]}],
        "ports": [{"port": 4173, "confidence": 0.9, "source": "source"}],
        "environment_variables": [],
        "manifests": [str(service_dir / "package.json")],
        "dependencies": [],
    }
    service_plan = DeploymentPlanner().plan({
        "repository": {"name": "example", "path": str(tmp_path)},
        "services": [service],
        "external_dependencies": [],
        "relationships": [],
        "analysis_warnings": [],
    })
    public_service = service_plan["services"][0]
    assert public_service["exposure"] == "public"


def test_external_dependencies_are_not_converted_into_services(fixtures_dir: Path):
    repo = fixtures_dir / "mern"
    analysis = analyze_repository(repo)

    plan = DeploymentPlanner().plan(analysis)
    service_names = {service["name"] for service in plan["services"]}
    external_names = {dep["name"] for dep in plan["external_dependencies"]}

    assert "MongoDB" in external_names
    assert "mongodb" not in service_names


def test_relationships_are_preserved_only_when_supported(fixtures_dir: Path):
    repo = fixtures_dir / "mern"
    analysis = analyze_repository(repo)

    plan = DeploymentPlanner().plan(analysis)
    backend = next(service for service in plan["services"] if service["name"] == "backend")
    relationship = backend["service_relationships"][0]

    assert relationship["source"] == "backend"
    assert relationship["target"] in {"mongodb", "MongoDB"}


def test_deployment_plan_api_creates_plan_from_repository_analysis():
    client = TestClient(app)
    response = client.post("/deployments/plan", json={"repository_path": str(Path("tests/fixtures/fastapi"))})

    assert response.status_code == 200
    payload = response.json()
    assert payload["deployment_plan"]["repository"]["name"] == "fastapi"
    assert payload["deployment_plan"]["services"]


def test_integration_phase1_to_phase2_produces_valid_plan(fixtures_dir: Path):
    analysis = analyze_repository(fixtures_dir / "multi_service")
    plan = DeploymentPlanner().plan(analysis)
    validation = DeploymentPlanValidator().validate(plan)

    assert validation["valid"] is True
    assert len(plan["services"]) == 3
    assert plan["aws_target"]["provider"] == "AWS"
    assert plan["aws_target"]["compute"] == "ECS"
    assert plan["aws_target"]["registry"] == "ECR"
