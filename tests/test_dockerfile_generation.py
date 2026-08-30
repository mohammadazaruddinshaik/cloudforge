from pathlib import Path

from app.analysis.repository import analyze_repository
from app.containerization.dockerfile_generator import DockerfileGenerator
from app.containerization.planner import ContainerizationPlanner
from app.planning.planner import DeploymentPlanner


def _container_plan(repo: Path):
    analysis = analyze_repository(repo)
    deployment_plan = DeploymentPlanner().plan(analysis)
    return ContainerizationPlanner().plan(deployment_plan)


def test_node_express_dockerfile_generation(fixtures_dir: Path):
    plan = _container_plan(fixtures_dir / "mern")
    generated = DockerfileGenerator().generate(plan)

    backend = next(service for service in generated["services"] if service["service_name"] == "backend")
    assert backend["generation_readiness"] == "ready"
    assert "FROM node" in backend["dockerfile_content"]
    assert "WORKDIR /app" in backend["dockerfile_content"]
    assert "RUN npm install" in backend["dockerfile_content"]
    assert "COPY package*.json ./" in backend["dockerfile_content"]
    assert "EXPOSE 5000" in backend["dockerfile_content"]
    assert 'CMD ["node", "server.js"]' in backend["dockerfile_content"]
    assert "mongodb://" not in backend["dockerfile_content"].lower()


def test_python_fastapi_dockerfile_generation(fixtures_dir: Path):
    plan = _container_plan(fixtures_dir / "fastapi")
    generated = DockerfileGenerator().generate(plan)

    service = generated["services"][0]
    assert service["generation_readiness"] == "ready"
    assert "FROM python" in service["dockerfile_content"]
    assert "WORKDIR /app" in service["dockerfile_content"]
    assert "RUN pip install -r requirements.txt" in service["dockerfile_content"]
    assert "EXPOSE 8000" in service["dockerfile_content"]
    assert 'CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]' in service["dockerfile_content"]


def test_dependency_installation_and_build_step_are_separate(fixtures_dir: Path):
    plan = _container_plan(fixtures_dir / "mern")
    generated = DockerfileGenerator().generate(plan)

    backend = next(service for service in generated["services"] if service["service_name"] == "backend")
    assert "RUN npm install" in backend["dockerfile_content"]
    assert "RUN npm run build" not in backend["dockerfile_content"]
    assert "build_command" in str(backend.get("build_steps", [])) or not backend["build_steps"]


def test_port_exposure_is_only_generated_when_known(fixtures_dir: Path):
    plan = _container_plan(fixtures_dir / "mern")
    generated = DockerfileGenerator().generate(plan)

    frontend = next(service for service in generated["services"] if service["service_name"] == "frontend")
    assert frontend["generation_readiness"] == "requires_confirmation"
    assert "EXPOSE" not in frontend["dockerfile_content"]


def test_no_invented_runtime_version_or_secret_values(fixtures_dir: Path):
    plan = _container_plan(fixtures_dir / "mern")
    generated = DockerfileGenerator().generate(plan)

    backend = next(service for service in generated["services"] if service["service_name"] == "backend")
    assert ":20" not in backend["dockerfile_content"]
    assert ":3." not in backend["dockerfile_content"]
    assert "MONGO_URI" not in backend["dockerfile_content"]
    assert "mongodb://" not in backend["dockerfile_content"].lower()
    assert ".env" not in backend["dockerfile_content"]


def test_react_frontend_generation_requires_confirmation_not_nginx(fixtures_dir: Path):
    plan = _container_plan(fixtures_dir / "mern")
    generated = DockerfileGenerator().generate(plan)

    frontend = next(service for service in generated["services"] if service["service_name"] == "frontend")
    assert frontend["generation_readiness"] == "requires_confirmation"
    assert "nginx" not in frontend["dockerfile_content"].lower()
    assert "Production serving strategy is unknown." in "\n".join(frontend["warnings"]) or "production serving strategy" in "\n".join(frontend["warnings"]).lower()


def test_dockerfile_generation_validation_honors_readiness(fixtures_dir: Path):
    plan = _container_plan(fixtures_dir / "mern")
    generated = DockerfileGenerator().generate(plan)

    backend = next(service for service in generated["services"] if service["service_name"] == "backend")
    assert backend["generation_readiness"] == "ready"
    assert backend["dockerfile_content"]
    assert generated["dockerfile_generation_readiness"] == "requires_confirmation"


def test_multiple_services_generate_independent_dockerfiles(fixtures_dir: Path):
    plan = _container_plan(fixtures_dir / "multi_service")
    generated = DockerfileGenerator().generate(plan)

    assert len(generated["services"]) == 3
    names = {service["service_name"] for service in generated["services"]}
    assert {"frontend", "backend", "worker"}.issubset(names)


def test_validated_generated_dockerfiles_are_safe(fixtures_dir: Path):
    plan = _container_plan(fixtures_dir / "fastapi")
    generated = DockerfileGenerator().generate(plan)

    validation = generated["validation"]
    assert validation["valid"] is True
    assert validation["warnings"] == []


def test_existing_phase_1_2_3_1_tests_remain_unchanged(fixtures_dir: Path):
    plan = _container_plan(fixtures_dir / "fastapi")
    generated = DockerfileGenerator().generate(plan)

    assert plan["containerization_readiness"] == "ready"
    assert generated["services"][0]["service_name"] == "fastapi"
    assert generated["services"][0]["generation_readiness"] == "ready"
