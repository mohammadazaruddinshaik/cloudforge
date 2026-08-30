from pathlib import Path

from app.analysis.repository import analyze_repository
from app.containerization.planner import ContainerizationPlanner
from app.planning.planner import DeploymentPlanner


def _plan_from_fixture(fixtures_dir: Path, fixture_name: str):
    analysis = analyze_repository(fixtures_dir / fixture_name)
    return DeploymentPlanner().plan(analysis)


def test_node_express_service_containerization_plan(fixtures_dir: Path):
    plan = _plan_from_fixture(fixtures_dir, "mern")
    container_plan = ContainerizationPlanner().plan(plan)

    backend = next(service for service in container_plan["services"] if service["service_name"] == "backend")

    assert backend["runtime"] == "Node.js"
    assert backend["framework"] == "Express"
    assert backend["dependency_install_command"] == "npm install"
    assert backend["build_command"] is None
    assert backend["start_command"] == "node server.js"
    assert backend["entry_point"] == "server.js"
    assert backend["application_port"] == 5000
    assert backend["production_serving_strategy"] == "node-process"
    assert backend["containerization_readiness"] == "ready"


def test_python_fastapi_service_containerization_plan(fixtures_dir: Path):
    plan = _plan_from_fixture(fixtures_dir, "fastapi")
    container_plan = ContainerizationPlanner().plan(plan)

    service = container_plan["services"][0]
    assert service["service_name"] == "fastapi"
    assert service["runtime"] == "Python"
    assert service["framework"] == "FastAPI"
    assert service["dependency_install_command"] == "pip install -r requirements.txt"
    assert service["build_command"] is None
    assert service["start_command"] == "uvicorn app.main:app --host 0.0.0.0 --port 8000"
    assert service["production_serving_strategy"] == "uvicorn"
    assert service["application_port"] == 8000
    assert service["containerization_readiness"] == "ready"


def test_unresolved_frontend_serving_strategy_stays_unknown(fixtures_dir: Path):
    plan = _plan_from_fixture(fixtures_dir, "mern")
    container_plan = ContainerizationPlanner().plan(plan)

    frontend = next(service for service in container_plan["services"] if service["service_name"] == "frontend")
    assert frontend["runtime"] == "Node.js"
    assert frontend["framework"] == "React"
    assert frontend["application_port"] is None
    assert frontend["production_serving_strategy"] == "unknown"
    assert frontend["containerization_readiness"] == "requires_confirmation"


def test_missing_port_remains_unknown_and_requires_confirmation():
    deployment_plan = {
        "repository": {"name": "example", "path": "/tmp/example"},
        "services": [{
            "name": "worker",
            "service_path": "/tmp/example/worker",
            "runtime": "Python",
            "framework": "Python",
            "dependency_install_command": "pip install -r requirements.txt",
            "build_command": None,
            "start_command": "python app.py",
            "production_serving_strategy": "python-process",
            "entry_point": "app.py",
            "port": None,
            "required_environment_variables": [],
            "deployment_type": "container",
            "deployment_readiness": "requires_confirmation",
            "deployment_ready": False,
            "warnings": ["No reliable application port was detected for this service."],
            "container_requirements": {"runtime": "Python", "working_directory": "/app", "port": None, "entry_point": "app.py", "build_command": None, "start_command": "python app.py"},
        }],
        "external_dependencies": [],
        "networking": {"service_ports": [], "service_to_service_communication": [], "external_access": [], "dependency_connectivity": [], "notes": []},
        "environment": {"variables": []},
        "container_requirements": {"services": []},
        "aws_target": {"provider": "AWS", "registry": "ECR", "compute": "ECS"},
        "assumptions": [],
        "warnings": ["worker: no reliable port was detected."],
        "validation": {"valid": False, "warnings": [], "blockers": []},
        "deployment_readiness": "requires_confirmation",
        "deployment_ready": False,
    }

    container_plan = ContainerizationPlanner().plan(deployment_plan)
    worker = container_plan["services"][0]
    assert worker["application_port"] is None
    assert worker["containerization_readiness"] == "requires_confirmation"


def test_unknown_runtime_information_remains_unknown_and_blocked():
    deployment_plan = {
        "repository": {"name": "example", "path": "/tmp/example"},
        "services": [{
            "name": "service",
            "service_path": "/tmp/example/service",
            "runtime": "Unknown",
            "framework": "Unknown",
            "dependency_install_command": None,
            "build_command": None,
            "start_command": "python app.py",
            "production_serving_strategy": "python-process",
            "entry_point": "app.py",
            "port": 9000,
            "required_environment_variables": [],
            "deployment_type": "container",
            "deployment_readiness": "blocked",
            "deployment_ready": False,
            "warnings": ["Unknown runtime information."],
            "container_requirements": {"runtime": "Unknown", "working_directory": "/app", "port": 9000, "entry_point": "app.py", "build_command": None, "start_command": "python app.py"},
        }],
        "external_dependencies": [],
        "networking": {"service_ports": [], "service_to_service_communication": [], "external_access": [], "dependency_connectivity": [], "notes": []},
        "environment": {"variables": []},
        "container_requirements": {"services": []},
        "aws_target": {"provider": "AWS", "registry": "ECR", "compute": "ECS"},
        "assumptions": [],
        "warnings": ["Unknown runtime information."],
        "validation": {"valid": False, "warnings": [], "blockers": ["service: runtime is missing."]},
        "deployment_readiness": "blocked",
        "deployment_ready": False,
    }

    container_plan = ContainerizationPlanner().plan(deployment_plan)
    service = container_plan["services"][0]
    assert service["runtime"] is None
    assert service["base_runtime_requirement"] is None
    assert service["containerization_readiness"] == "blocked"


def test_phase2_warnings_and_blockers_propagate_to_containerization_plan(fixtures_dir: Path):
    plan = _plan_from_fixture(fixtures_dir, "mern")
    container_plan = ContainerizationPlanner().plan(plan)

    frontend = next(service for service in container_plan["services"] if service["service_name"] == "frontend")
    assert any("serving strategy" in warning.lower() for warning in frontend["warnings"])
    assert any("serving strategy" in warning.lower() for warning in container_plan["warnings"])
    assert container_plan["containerization_readiness"] == "requires_confirmation"


def test_secret_values_never_appear_in_containerization_plan(fixtures_dir: Path):
    plan = _plan_from_fixture(fixtures_dir, "mern")
    container_plan = ContainerizationPlanner().plan(plan)

    backend = next(service for service in container_plan["services"] if service["service_name"] == "backend")
    rendered = str(backend).lower()
    assert "mongodb://" not in rendered
    assert any(env["secret"] for env in backend["environment_variable_requirements"])
    assert all(env.get("value") is None for env in backend["environment_variable_requirements"])


def test_multiple_services_are_planned_separately(fixtures_dir: Path):
    plan = _plan_from_fixture(fixtures_dir, "multi_service")
    container_plan = ContainerizationPlanner().plan(plan)

    assert {service["service_name"] for service in container_plan["services"]} >= {"frontend", "backend", "worker"}
    assert len(container_plan["services"]) == 3
    assert container_plan["containerization_readiness"] in {"ready", "requires_confirmation", "blocked"}


def test_fully_resolvable_service_becomes_containerization_ready(fixtures_dir: Path):
    deployment_plan = _plan_from_fixture(fixtures_dir, "fastapi")
    container_plan = ContainerizationPlanner().plan(deployment_plan)

    service = container_plan["services"][0]
    assert service["containerization_readiness"] == "ready"
    assert service["containerization_ready"] is True
    assert container_plan["containerization_readiness"] == "ready"
    assert container_plan["containerization_ready"] is True


def test_unresolved_service_remains_requires_confirmation_or_blocked(fixtures_dir: Path):
    plan = _plan_from_fixture(fixtures_dir, "mern")
    container_plan = ContainerizationPlanner().plan(plan)

    frontend = next(service for service in container_plan["services"] if service["service_name"] == "frontend")
    assert frontend["containerization_readiness"] in {"requires_confirmation", "blocked"}
    assert frontend["containerization_ready"] is False


def test_existing_phase_1_and_2_behavior_remains_unchanged(fixtures_dir: Path):
    analysis = analyze_repository(fixtures_dir / "fastapi")
    deployment_plan = DeploymentPlanner().plan(analysis)
    container_plan = ContainerizationPlanner().plan(deployment_plan)

    assert deployment_plan["deployment_readiness"] == "ready"
    assert deployment_plan["deployment_ready"] is True
    assert container_plan["services"][0]["service_name"] == "fastapi"
    assert container_plan["repository"]["name"] == "fastapi"
