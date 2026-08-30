from __future__ import annotations

from pathlib import Path

from app.analysis.repository import analyze_repository
from app.containerization.docker_validator import DockerValidator
from app.containerization.dockerfile_generator import DockerfileGenerator
from app.containerization.planner import ContainerizationPlanner
from app.planning.planner import DeploymentPlanner


class FakeDockerClient:
    def __init__(
        self,
        *,
        available: bool = True,
        build_result: dict | None = None,
        run_result: dict | None = None,
        logs_output: str = "app started",
        stop_result: dict | None = None,
        remove_result: dict | None = None,
    ) -> None:
        self.available = available
        self.build_result = build_result or {
            "success": True,
            "stdout": "Build succeeded",
            "stderr": "",
            "error": None,
            "command": ["docker", "build"],
            "image_tag": "cloudforge-backend:validation",
            "container_id": None,
        }
        self.run_result = run_result or {
            "success": True,
            "stdout": "container-123\n",
            "stderr": "",
            "error": None,
            "command": ["docker", "run"],
            "image_tag": "cloudforge-backend:validation",
            "container_id": "container-123",
        }
        self.logs_output = logs_output
        self.stop_result = stop_result or {"success": True, "stdout": "stopped", "stderr": "", "error": None, "container_id": "container-123"}
        self.remove_result = remove_result or {"success": True, "stdout": "removed", "stderr": "", "error": None, "container_id": "container-123"}
        self.calls: list[dict[str, object]] = []

    def is_available(self) -> bool:
        return self.available

    def build_image(self, dockerfile_path: str, image_tag: str, build_context: str | None = None) -> dict:
        self.calls.append({"kind": "build", "dockerfile_path": dockerfile_path, "image_tag": image_tag, "build_context": build_context})
        result = dict(self.build_result)
        result.setdefault("image_tag", image_tag)
        return result

    def run_container(self, image_tag: str, command: list[str] | None = None, port: int | str | None = None, env: dict[str, str] | None = None, detach: bool = True) -> dict:
        self.calls.append({"kind": "run", "image_tag": image_tag, "command": command, "port": port, "env": env, "detach": detach})
        result = dict(self.run_result)
        result.setdefault("image_tag", image_tag)
        if port is not None and "-p" not in str(result.get("command", [])):
            result["command"] = ["docker", "run", "-d", "-p", f"{port}:{port}", image_tag, *(command or [])]
        return result

    def logs(self, container_id: str) -> dict:
        self.calls.append({"kind": "logs", "container_id": container_id})
        return {"success": True, "stdout": self.logs_output, "stderr": "", "container_id": container_id}

    def stop_container(self, container_id: str) -> dict:
        self.calls.append({"kind": "stop", "container_id": container_id})
        return dict(self.stop_result)

    def remove_container(self, container_id: str, force: bool = True) -> dict:
        self.calls.append({"kind": "remove", "container_id": container_id, "force": force})
        return dict(self.remove_result)

    @staticmethod
    def command_tokens(command: str) -> list[str]:
        return command.split()


def _service(**overrides):
    service = {
        "service_name": "backend",
        "name": "backend",
        "service_path": "/tmp/backend",
        "runtime": "Node.js",
        "framework": "Express",
        "dependency_install_command": "npm install",
        "build_command": None,
        "start_command": "node server.js",
        "production_serving_strategy": "node-process",
        "entry_point": "server.js",
        "application_port": 5000,
        "port": 5000,
        "environment_variable_requirements": [{"name": "MONGO_URI", "service": "backend", "required": True, "secret": True, "value": None}],
        "build_context": "/tmp/backend",
        "containerization_readiness": "ready",
        "containerization_ready": True,
        "warnings": [],
        "blockers": [],
        "assumptions": [],
    }
    service.update(overrides)
    return service


def _plan(*services):
    return {
        "repository": {"name": "demo", "path": "/tmp/demo"},
        "services": list(services),
        "warnings": [],
        "blockers": [],
        "assumptions": [],
        "containerization_readiness": "ready",
        "containerization_ready": True,
    }


def test_docker_validator_successful_image_build_and_secret_skip():
    client = FakeDockerClient()
    validator = DockerValidator(client)
    plan = _plan(_service())

    result = validator.validate(plan)

    assert result.services[0].build_status == "success"
    assert result.services[0].runtime_status == "skipped"
    assert result.services[0].validation_status == "skipped"
    assert result.services[0].valid is False
    assert any("required secret environment variables are unavailable" in warning.lower() for warning in result.services[0].warnings)


def test_docker_validator_failed_image_build_stops_runtime_execution():
    client = FakeDockerClient(build_result={"success": False, "stdout": "", "stderr": "npm install failed", "error": "npm install failed", "command": ["docker", "build"], "image_tag": "cloudforge-backend:validation"})
    validator = DockerValidator(client)
    plan = _plan(_service())

    result = validator.validate(plan)

    assert result.services[0].build_status == "failed"
    assert result.services[0].runtime_status == "skipped"
    assert result.services[0].validation_status == "failed"
    assert "npm install failed" in result.services[0].errors[0]
    assert all(call["kind"] != "run" for call in client.calls)


def test_docker_validator_captures_build_stdout_stderr():
    client = FakeDockerClient(build_result={"success": True, "stdout": "FROM node\nRUN npm install", "stderr": "warning: peer dep", "error": None, "command": ["docker", "build"], "image_tag": "cloudforge-backend:validation"})
    validator = DockerValidator(client)
    plan = _plan(_service())

    result = validator.validate(plan)

    assert "FROM node" in result.services[0].build_logs
    assert "warning: peer dep" in result.services[0].build_logs


def test_docker_validator_successful_runtime_validation_cleans_up():
    client = FakeDockerClient(logs_output="Server started on 5000")
    validator = DockerValidator(client)
    plan = _plan(_service(environment_variable_requirements=[]))

    result = validator.validate(plan)

    assert result.services[0].build_status == "success"
    assert result.services[0].runtime_status == "success"
    assert result.services[0].validation_status == "ready"
    assert result.services[0].cleanup_status == "success"
    assert any(call["kind"] == "stop" for call in client.calls)
    assert any(call["kind"] == "remove" for call in client.calls)


def test_docker_validator_runtime_failure_is_recorded_and_cleanup_runs():
    client = FakeDockerClient(logs_output="Error: cannot start", run_result={"success": True, "stdout": "container-123\n", "stderr": "", "error": None, "command": ["docker", "run"], "image_tag": "cloudforge-backend:validation", "container_id": "container-123"}, stop_result={"success": True, "stdout": "stopped", "stderr": "", "container_id": "container-123"}, remove_result={"success": True, "stdout": "removed", "stderr": "", "container_id": "container-123"})
    validator = DockerValidator(client)
    plan = _plan(_service(environment_variable_requirements=[]))

    result = validator.validate(plan)

    assert result.services[0].runtime_status == "success"
    assert result.services[0].cleanup_status == "success"


def test_docker_validator_cleanup_failure_is_surfaces():
    client = FakeDockerClient(stop_result={"success": False, "stdout": "", "stderr": "stop failed", "error": "stop failed", "container_id": "container-123"}, remove_result={"success": False, "stdout": "", "stderr": "remove failed", "error": "remove failed", "container_id": "container-123"})
    validator = DockerValidator(client)
    plan = _plan(_service(environment_variable_requirements=[]))

    result = validator.validate(plan)

    assert result.services[0].cleanup_status == "failed"
    assert any("stop failed" in message.lower() or "remove failed" in message.lower() for message in result.services[0].errors)


def test_docker_validator_ready_service_proceeds_to_validation():
    client = FakeDockerClient(logs_output="ready")
    validator = DockerValidator(client)
    plan = _plan(_service(environment_variable_requirements=[]))

    result = validator.validate(plan)

    assert result.services[0].validation_status == "ready"
    assert any(call["kind"] == "build" for call in client.calls)
    assert any(call["kind"] == "run" for call in client.calls)


def test_docker_validator_requires_confirmation_service_is_skipped():
    client = FakeDockerClient()
    validator = DockerValidator(client)
    plan = _plan(_service(containerization_readiness="requires_confirmation", application_port=None, port=None, warnings=["frontend requires confirmation"], environment_variable_requirements=[]))

    result = validator.validate(plan)

    assert result.services[0].build_status == "skipped"
    assert result.services[0].runtime_status == "skipped"
    assert result.services[0].validation_status == "skipped"
    assert result.services[0].valid is False
    assert any("requires_confirmation" in warning.lower() for warning in result.services[0].warnings)


def test_docker_validator_blocked_service_is_skipped():
    client = FakeDockerClient()
    validator = DockerValidator(client)
    plan = _plan(_service(containerization_readiness="blocked", blockers=["blocked by policy"]))

    result = validator.validate(plan)

    assert result.services[0].build_status == "blocked"
    assert result.services[0].runtime_status == "skipped"
    assert result.services[0].validation_status == "blocked"
    assert result.services[0].valid is False


def test_docker_validator_unknown_port_never_results_in_guessed_runtime_mapping():
    client = FakeDockerClient()
    validator = DockerValidator(client)
    plan = _plan(_service(application_port=None, port=None, environment_variable_requirements=[]))

    result = validator.validate(plan)

    assert result.services[0].runtime_status == "skipped"
    assert "application port is unknown" in result.services[0].warnings[0].lower()
    assert all(call["kind"] != "run" for call in client.calls)


def test_docker_validator_handles_docker_unavailable():
    client = FakeDockerClient(available=False)
    validator = DockerValidator(client)
    plan = _plan(_service(environment_variable_requirements=[]))

    result = validator.validate(plan)

    assert result.services[0].build_status == "docker_unavailable"
    assert result.services[0].runtime_status == "skipped"
    assert result.services[0].validation_status == "skipped"
    assert "docker daemon is unavailable" in " ".join(result.services[0].errors).lower()


def test_docker_validator_validates_multiple_services_independently():
    client = FakeDockerClient()
    validator = DockerValidator(client)
    plan = _plan(
        _service(service_name="backend", name="backend", environment_variable_requirements=[]),
        _service(service_name="worker", name="worker", start_command="python worker.py", application_port=None, port=None, environment_variable_requirements=[]),
    )

    result = validator.validate(plan)

    names = {item.service_name for item in result.services}
    assert names == {"backend", "worker"}
    assert result.services[0].build_status in {"success", "docker_unavailable"}
    assert any(item.validation_status == "skipped" for item in result.services)
    assert len(result.services) == 2


def test_docker_validator_redacts_secret_values_from_logs_and_results():
    client = FakeDockerClient(logs_output="MONGO_URI=mongodb://secret.example/db\napp started")
    validator = DockerValidator(client)
    plan = _plan(_service(environment_variable_requirements=[]))

    result = validator.validate(plan)

    assert "mongodb://secret.example/db" not in result.services[0].runtime_logs
    assert "[REDACTED]" in result.services[0].runtime_logs
    assert "secret.example" not in result.services[0].runtime_logs


def test_docker_validator_uses_generated_dockerfile_from_phase_3_2():
    real_plan = _plan(_service(service_path="tests/fixtures/mern/backend", build_context="tests/fixtures/mern/backend", application_port=5000, runtime="Node.js", framework="Express", environment_variable_requirements=[]))
    generated = DockerfileGenerator().generate(real_plan)
    client = FakeDockerClient()
    validator = DockerValidator(client)

    result = validator.validate(real_plan)

    expected_path = generated["services"][0]["dockerfile_path"]
    assert any(call["kind"] == "build" and call["dockerfile_path"] == expected_path for call in client.calls)
    assert result.services[0].build_status == "success"


def test_docker_validator_passes_declared_build_context_to_docker_build():
    client = FakeDockerClient()
    validator = DockerValidator(client)
    plan = _plan(_service(build_context="tests/fixtures/mern/backend", environment_variable_requirements=[]))

    validator.validate(plan)

    build_call = next(call for call in client.calls if call["kind"] == "build")
    assert build_call["build_context"] == "tests/fixtures/mern/backend"


def test_docker_validator_uses_container_command_from_containerization_plan():
    client = FakeDockerClient()
    validator = DockerValidator(client)
    plan = _plan(_service(start_command="node server.js", environment_variable_requirements=[]))

    validator.validate(plan)

    run_call = next(call for call in client.calls if call["kind"] == "run")
    assert run_call["command"] == ["node", "server.js"]


def test_docker_validator_maps_port_only_when_known():
    client = FakeDockerClient()
    validator = DockerValidator(client)
    plan = _plan(_service(application_port=5000, port=5000, environment_variable_requirements=[]))

    validator.validate(plan)

    run_call = next(call for call in client.calls if call["kind"] == "run")
    assert run_call["port"] == 5000

    missing_client = FakeDockerClient()
    missing_validator = DockerValidator(missing_client)
    plan_missing = _plan(_service(application_port=None, port=None, environment_variable_requirements=[]))
    missing_validator.validate(plan_missing)
    assert all(call["kind"] != "run" for call in missing_client.calls)


def test_docker_validator_passes_generated_dockerfile_content_unchanged_to_build():
    real_plan = _plan(_service(service_path="tests/fixtures/mern/backend", build_context="tests/fixtures/mern/backend", application_port=5000, runtime="Node.js", framework="Express", environment_variable_requirements=[]))
    generated = DockerfileGenerator().generate(real_plan)
    expected = generated["services"][0]["dockerfile_content"]
    client = FakeDockerClient()
    validator = DockerValidator(client)

    validator.validate(real_plan)

    build_call = next(call for call in client.calls if call["kind"] == "build")
    assert str(build_call["dockerfile_path"]).endswith("Dockerfile")
    assert expected.startswith("FROM node:slim")


def test_docker_validator_build_failure_prevents_runtime_execution():
    client = FakeDockerClient(build_result={"success": False, "stdout": "", "stderr": "build failed", "error": "build failed", "command": ["docker", "build"], "image_tag": "cloudforge-backend:validation"})
    validator = DockerValidator(client)
    plan = _plan(_service(environment_variable_requirements=[]))

    result = validator.validate(plan)

    assert result.services[0].build_status == "failed"
    assert result.services[0].runtime_status == "skipped"
    assert all(call["kind"] != "run" for call in client.calls)


def test_docker_validator_cleanup_runs_after_runtime_failure():
    client = FakeDockerClient(logs_output="runtime boom", run_result={"success": True, "stdout": "container-123\n", "stderr": "", "error": None, "command": ["docker", "run"], "image_tag": "cloudforge-backend:validation", "container_id": "container-123"}, stop_result={"success": True, "stdout": "stopped", "stderr": "", "container_id": "container-123"}, remove_result={"success": True, "stdout": "removed", "stderr": "", "container_id": "container-123"})
    validator = DockerValidator(client)
    plan = _plan(_service(environment_variable_requirements=[]))

    result = validator.validate(plan)

    assert result.services[0].runtime_status == "success"
    assert result.services[0].cleanup_status == "success"
    assert any(call["kind"] == "stop" for call in client.calls)
    assert any(call["kind"] == "remove" for call in client.calls)


def test_docker_validator_distinguishes_build_and_runtime_status():
    client = FakeDockerClient(build_result={"success": True, "stdout": "ok", "stderr": "", "error": None, "command": ["docker", "build"], "image_tag": "cloudforge-backend:validation"}, logs_output="started")
    validator = DockerValidator(client)
    plan = _plan(_service(environment_variable_requirements=[]))

    result = validator.validate(plan)

    assert result.services[0].build_status == "success"
    assert result.services[0].runtime_status == "success"
    assert result.services[0].validation_status == "ready"
    assert result.services[0].valid is True


def test_docker_validator_overall_status_uses_service_results():
    client = FakeDockerClient(available=False)
    validator = DockerValidator(client)
    plan = _plan(_service(environment_variable_requirements=[]))

    result = validator.validate(plan)

    assert result.validation_status == "skipped"
    assert result.valid is False
