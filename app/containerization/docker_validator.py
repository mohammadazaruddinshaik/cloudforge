from __future__ import annotations

import re
from typing import Any

from app.containerization.docker_client import DockerClient
from app.containerization.dockerfile_generator import DockerfileGenerator
from app.containerization.models import ContainerizationPlan, DockerServiceValidationResult, DockerValidationResult


class DockerValidator:
    def __init__(self, docker_client: DockerClient | None = None) -> None:
        self.docker_client = docker_client or DockerClient()

    def validate(self, containerization_plan: dict | ContainerizationPlan) -> DockerValidationResult:
        if isinstance(containerization_plan, dict):
            plan = ContainerizationPlan.model_validate(containerization_plan)
        else:
            plan = containerization_plan

        generated = DockerfileGenerator().generate(plan)

        service_results: list[DockerServiceValidationResult] = []
        overall_errors: list[str] = []
        overall_warnings: list[str] = []

        for service in plan.services:
            service_result = self._validate_service(service, generated)
            service_results.append(service_result)
            overall_errors.extend(service_result.errors)
            overall_warnings.extend(service_result.warnings)

        validation_status = self._overall_status(service_results)
        valid = all(result.valid for result in service_results) if service_results else False

        return DockerValidationResult(
            services=service_results,
            validation_status=validation_status,
            valid=valid,
            errors=list(dict.fromkeys(overall_errors)),
            warnings=list(dict.fromkeys(overall_warnings)),
        )

    def _validate_service(self, service: Any, generated: dict[str, Any]) -> DockerServiceValidationResult:
        service_name = service.service_name
        generated_service = self._find_generated_service(generated, service_name)

        if service.containerization_readiness == "blocked":
            return DockerServiceValidationResult(
                service_name=service_name,
                validation_status="blocked",
                build_status="blocked",
                runtime_status="skipped",
                valid=False,
                errors=list(service.blockers) or [f"{service_name}: containerization is blocked."],
                warnings=list(service.warnings),
                assumptions=list(service.assumptions),
                reason="blocked",
            )

        if service.containerization_readiness == "requires_confirmation":
            return DockerServiceValidationResult(
                service_name=service_name,
                validation_status="skipped",
                build_status="skipped",
                runtime_status="skipped",
                valid=False,
                errors=[],
                warnings=[
                    *service.warnings,
                    f"{service_name}: requires_confirmation; Docker build/runtime validation was skipped.",
                ],
                assumptions=list(service.assumptions),
                reason="requires_confirmation",
            )

        if not self.docker_client.is_available():
            return DockerServiceValidationResult(
                service_name=service_name,
                validation_status="skipped",
                build_status="docker_unavailable",
                runtime_status="skipped",
                valid=False,
                errors=["Docker daemon is unavailable."],
                warnings=["Docker validation was skipped because the Docker daemon is unavailable."],
                assumptions=list(service.assumptions),
                reason="docker_unavailable",
            )

        if generated_service is None:
            return DockerServiceValidationResult(
                service_name=service_name,
                validation_status="failed",
                build_status="failed",
                runtime_status="skipped",
                valid=False,
                errors=[f"{service_name}: generated Dockerfile output was not found."],
                warnings=list(service.warnings),
                assumptions=list(service.assumptions),
                reason="missing_generated_dockerfile",
            )

        dockerfile_path = self._dockerfile_path_for_service(service, generated_service)
        if not dockerfile_path:
            return DockerServiceValidationResult(
                service_name=service_name,
                validation_status="failed",
                build_status="failed",
                runtime_status="skipped",
                valid=False,
                errors=[f"{service_name}: could not determine Dockerfile output path."],
                warnings=list(service.warnings),
                assumptions=list(service.assumptions),
                reason="missing_dockerfile_path",
            )

        image_tag = self._image_tag(service_name)
        build_result_raw = self.docker_client.build_image(dockerfile_path, image_tag, build_context=service.build_context)
        build_result = self._normalize_result(build_result_raw)
        build_logs = self._combine_output(build_result["stdout"], build_result["stderr"])

        if not build_result["success"]:
            return DockerServiceValidationResult(
                service_name=service_name,
                validation_status="failed",
                build_status="failed",
                runtime_status="skipped",
                valid=False,
                image_tag=image_tag,
                build_logs=build_logs,
                errors=[build_result["error"] or f"{service_name}: Docker image build failed."],
                warnings=list(service.warnings),
                assumptions=list(service.assumptions),
                reason="build_failed",
            )

        runtime_result = self._validate_runtime(service, image_tag)
        runtime_logs = runtime_result["runtime_logs"]
        validation_status = self._service_validation_status(runtime_result["runtime_status"], bool(build_result["success"]))

        return DockerServiceValidationResult(
            service_name=service_name,
            validation_status=validation_status,
            build_status="success",
            runtime_status=runtime_result["runtime_status"],
            valid=(runtime_result["runtime_status"] == "success"),
            image_tag=image_tag,
            container_id=runtime_result["container_id"],
            build_logs=build_logs,
            runtime_logs=runtime_logs,
            errors=runtime_result["errors"],
            warnings=runtime_result["warnings"],
            cleanup_status=runtime_result["cleanup_status"],
            assumptions=list(service.assumptions),
            reason=runtime_result["reason"],
        )

    def _validate_runtime(self, service: Any, image_tag: str) -> dict[str, Any]:
        port = service.application_port
        env: dict[str, str] = {}
        required_vars = [env_req.name for env_req in getattr(service, "environment_variable_requirements", []) if env_req.required and env_req.secret and env_req.value is None]
        if required_vars:
            return {
                "runtime_status": "skipped",
                "container_id": None,
                "runtime_logs": "",
                "errors": [],
                "warnings": [f"{service.service_name}: required secret environment variables are unavailable; runtime validation was skipped."],
                "cleanup_status": "skipped",
                "reason": "required secret environment variables are unavailable",
            }

        if port is None:
            return {
                "runtime_status": "skipped",
                "container_id": None,
                "runtime_logs": "",
                "errors": [],
                "warnings": [f"{service.service_name}: application port is unknown; runtime validation was skipped."],
                "cleanup_status": "skipped",
                "reason": "port is unknown",
            }

        command = self._service_command(service)
        run_result_raw = self.docker_client.run_container(image_tag=image_tag, command=command, port=port, env=env, detach=True)
        run_result = self._normalize_result(run_result_raw)
        container_id = run_result["container_id"]
        if not run_result["success"] or not container_id:
            return {
                "runtime_status": "failed",
                "container_id": container_id,
                "runtime_logs": self._redact_secrets(self._combine_output(run_result["stdout"], run_result["stderr"])),
                "errors": [run_result["error"] or f"{service.service_name}: container startup failed."],
                "warnings": list(service.warnings),
                "cleanup_status": "skipped",
                "reason": "runtime_start_failed",
            }

        logs_result_raw = self.docker_client.logs(container_id)
        logs_result = self._normalize_result(logs_result_raw)
        runtime_logs = self._redact_secrets(self._combine_output(logs_result["stdout"], logs_result["stderr"]))

        cleanup_status = "skipped"
        stop_result_raw = self.docker_client.stop_container(container_id)
        remove_result_raw = self.docker_client.remove_container(container_id, force=True)
        stop_result = self._normalize_result(stop_result_raw)
        remove_result = self._normalize_result(remove_result_raw)
        if stop_result["success"] and remove_result["success"]:
            cleanup_status = "success"
        elif stop_result["success"] or remove_result["success"]:
            cleanup_status = "success"
        else:
            cleanup_status = "failed"

        runtime_status = "success" if logs_result["success"] else "failed"
        errors: list[str] = []
        if not logs_result["success"]:
            errors.append(f"{service.service_name}: unable to collect runtime logs.")
        if not stop_result["success"] and stop_result["error"]:
            errors.append(stop_result["error"])
        if not remove_result["success"] and remove_result["error"]:
            errors.append(remove_result["error"])

        return {
            "runtime_status": runtime_status,
            "container_id": container_id,
            "runtime_logs": runtime_logs,
            "errors": errors,
            "warnings": list(service.warnings),
            "cleanup_status": cleanup_status,
            "reason": "runtime_validation_completed",
        }

    def _service_command(self, service: Any) -> list[str]:
        command = getattr(service, "container_command", None) or getattr(service, "start_command", None)
        if not command:
            return []
        return self.docker_client.command_tokens(command)

    def _dockerfile_path_for_service(self, service: Any, generated_service: dict[str, Any]) -> str | None:
        dockerfile_path = generated_service.get("dockerfile_path") or (service.service_path + "/Dockerfile" if getattr(service, "service_path", None) else None)
        return dockerfile_path

    def _find_generated_service(self, generated: dict[str, Any], service_name: str) -> dict[str, Any] | None:
        for service_result in generated.get("services", []):
            if service_result.get("service_name") == service_name:
                return service_result
        return None

    @staticmethod
    def _image_tag(service_name: str) -> str:
        return f"cloudforge-{service_name.lower().replace('/', '-').replace('_', '-')}:validation"

    @staticmethod
    def _normalize_result(result: Any) -> dict[str, Any]:
        if isinstance(result, dict):
            return {
                "success": bool(result.get("success", False)),
                "stdout": str(result.get("stdout", "")),
                "stderr": str(result.get("stderr", "")),
                "error": result.get("error"),
                "exit_code": result.get("exit_code"),
                "command": result.get("command", []),
                "image_tag": result.get("image_tag"),
                "container_id": result.get("container_id"),
            }
        return {
            "success": bool(getattr(result, "success", False)),
            "stdout": str(getattr(result, "stdout", "")),
            "stderr": str(getattr(result, "stderr", "")),
            "error": getattr(result, "error", None),
            "exit_code": getattr(result, "exit_code", None),
            "command": list(getattr(result, "command", []) or []),
            "image_tag": getattr(result, "image_tag", None),
            "container_id": getattr(result, "container_id", None),
        }

    @staticmethod
    def _combine_output(stdout: str, stderr: str) -> str:
        chunks = [part for part in [stdout, stderr] if part]
        return "\n".join(chunks)

    @staticmethod
    def _redact_secrets(text: str) -> str:
        if not text:
            return text
        redacted = text
        patterns = [
            (r"(?i)(MONGO_URI=)[^\n\r]+", r"\1[REDACTED]"),
            (r"(?i)(mongodb://)[^\s]+", r"\1[REDACTED]"),
            (r"(?i)(password=)[^\s]+", r"\1[REDACTED]"),
            (r"(?i)(secret=)[^\s]+", r"\1[REDACTED]"),
            (r"(?i)(token=)[^\s]+", r"\1[REDACTED]"),
        ]
        for pattern, replacement in patterns:
            redacted = re.sub(pattern, replacement, redacted)
        return redacted

    @staticmethod
    def _service_validation_status(runtime_status: str, build_success: bool) -> str:
        if runtime_status == "failed":
            return "failed"
        if runtime_status == "skipped":
            return "skipped"
        if build_success and runtime_status == "success":
            return "ready"
        return "failed"

    @staticmethod
    def _overall_status(service_results: list[DockerServiceValidationResult]) -> str:
        if not service_results:
            return "blocked"
        if any(result.validation_status == "failed" for result in service_results):
            return "failed"
        if any(result.validation_status == "requires_confirmation" for result in service_results):
            return "requires_confirmation"
        if all(result.validation_status == "skipped" for result in service_results):
            return "skipped"
        if all(result.validation_status == "ready" for result in service_results):
            return "ready"
        return "requires_confirmation"


__all__ = ["DockerValidator", "DockerClient"]
