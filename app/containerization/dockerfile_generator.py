from __future__ import annotations

from pathlib import Path
from typing import Any

from app.containerization.models import ContainerizationPlan


class DockerfileGenerator:
    def generate(self, containerization_plan: dict | ContainerizationPlan) -> dict:
        if isinstance(containerization_plan, dict):
            container_plan = ContainerizationPlan.model_validate(containerization_plan)
        else:
            container_plan = containerization_plan

        if not container_plan.services:
            return {
                "repository": container_plan.repository,
                "services": [],
                "dockerfile_generation_readiness": "blocked",
                "generation_ready": False,
                "warnings": list(container_plan.warnings),
                "blockers": ["No containerization plans were available for Dockerfile generation."],
                "assumptions": list(container_plan.assumptions),
                "validation": {"valid": False, "warnings": [], "blockers": ["No services available."]},
            }

        service_results: list[dict[str, Any]] = []
        top_warnings = list(dict.fromkeys(container_plan.warnings))
        top_blockers: list[str] = []
        assumptions = list(dict.fromkeys(container_plan.assumptions))

        for service in container_plan.services:
            result = self._generate_for_service(service)
            service_results.append(result)
            top_warnings.extend(result.get("warnings", []))
            top_blockers.extend(result.get("blockers", []))
            assumptions.extend(result.get("assumptions", []))

        readiness = self._assess_generation_readiness(service_results)
        validation = self._validate_service_results(service_results)

        return {
            "repository": container_plan.repository,
            "services": service_results,
            "dockerfile_generation_readiness": readiness,
            "generation_ready": readiness == "ready",
            "warnings": list(dict.fromkeys(top_warnings)),
            "blockers": list(dict.fromkeys(top_blockers)),
            "assumptions": list(dict.fromkeys(assumptions)),
            "validation": validation,
        }

    def _generate_for_service(self, service: Any) -> dict[str, Any]:
        service_name = service.service_name
        service_path = service.service_path or service.name or "./"
        runtime = self._normalize_runtime(service.runtime)
        framework = service.framework
        working_directory = service.working_directory or "/app"
        dep_install = service.dependency_install_command
        build_command = service.build_command
        start_command = service.start_command
        port = service.application_port
        entry_point = service.entry_point
        env_requirements = service.environment_variable_requirements
        warnings: list[str] = list(service.warnings)
        blockers: list[str] = list(service.blockers)
        assumptions: list[str] = list(service.assumptions)

        base_image = self._choose_base_image(runtime)
        if not base_image:
            blockers.append(f"{service_name}: no safe base image could be determined from the containerization plan.")
            generation_readiness = "blocked"
        elif service.containerization_readiness == "blocked":
            generation_readiness = "blocked"
        elif service.application_port is None:
            generation_readiness = "requires_confirmation"
            warnings.append(f"{service_name}: application port is unknown; Dockerfile generation requires confirmation.")
        elif service.production_serving_strategy in {None, "unknown"} and framework in {"React", "Next.js"}:
            generation_readiness = "requires_confirmation"
            warnings.append(f"{service_name}: Production serving strategy is unknown; Dockerfile generation requires confirmation.")
        elif service.containerization_readiness == "requires_confirmation":
            generation_readiness = "requires_confirmation"
            warnings.append(f"{service_name}: containerization plan requires confirmation before generating a production-ready Dockerfile.")
        else:
            generation_readiness = "ready"

        if not dep_install:
            assumptions.append(f"{service_name}: dependency installation command was not explicit in the containerization plan.")
        if not start_command:
            blockers.append(f"{service_name}: start command is missing; Dockerfile generation is blocked.")
        if build_command and service.containerization_readiness == "ready":
            build_steps = [f"RUN {build_command}"]
        else:
            build_steps = []

        if dep_install:
            dependency_steps = [f"RUN {dep_install}"]
        else:
            dependency_steps = []

        commands = []
        commands.append(f"FROM {base_image}") if base_image else None
        commands.append(f"WORKDIR {working_directory}")
        if dep_install:
            commands.append("COPY package*.json ./") if service.runtime and "node" in service.runtime.lower() else None
            if service.runtime and "python" in service.runtime.lower() and service.service_path:
                requirements_file = self._requirements_file_for_service(service)
                if requirements_file:
                    commands.append(f"COPY {requirements_file} ./")
            commands.extend(dependency_steps)
        if service.service_path:
            commands.append(f"COPY . .")
        if build_steps:
            commands.extend(build_steps)
        if port is not None:
            commands.append(f"EXPOSE {port}")
        if start_command:
            cmd_tokens = self._command_tokens(start_command)
            commands.append(f"CMD {cmd_tokens}")
        else:
            commands.append("CMD []")

        dockerfile_content = "\n".join(commands) + "\n"

        # Sanitize secrets and hidden file copying.
        for env in env_requirements:
            if env.value is not None:
                blockers.append(f"{service_name}: secret values must not appear in Dockerfile content.")
        if ".env" in dockerfile_content.lower() or ".env" in str(service_path).lower():
            warnings.append(f"{service_name}: .env files are not copied into the generated Dockerfile.")

        dockerfile_content = self._strip_secret_values(dockerfile_content)

        return {
            "service_name": service_name,
            "service_path": service_path,
            "dockerfile_path": str(Path(service_path) / "Dockerfile") if service_path else None,
            "dockerfile_content": dockerfile_content,
            "base_image": base_image,
            "working_directory": working_directory,
            "dependency_install_steps": dependency_steps,
            "build_steps": build_steps,
            "copy_steps": ["COPY package*.json ./", "COPY . ."] if service.runtime and "node" in service.runtime.lower() else ["COPY . ."],
            "exposed_port": port,
            "environment_variable_declarations": [],
            "command": start_command,
            "entrypoint": entry_point,
            "assumptions": list(dict.fromkeys(assumptions)),
            "warnings": list(dict.fromkeys(warnings)),
            "blockers": list(dict.fromkeys(blockers)),
            "generation_readiness": generation_readiness,
            "generation_ready": generation_readiness == "ready",
        }

    def _normalize_runtime(self, runtime: Any) -> str | None:
        if runtime is None:
            return None
        if isinstance(runtime, str):
            normalized = runtime.strip()
            return normalized if normalized and normalized.lower() not in {"unknown", "n/a", "none"} else None
        return str(runtime)

    def _choose_base_image(self, runtime: str | None) -> str | None:
        if runtime is None:
            return None
        runtime_lower = runtime.lower()
        if "node" in runtime_lower:
            return "node:slim"
        if "python" in runtime_lower:
            return "python:slim"
        if "java" in runtime_lower:
            return "eclipse-temurin:11"
        if "go" in runtime_lower:
            return "golang:1"
        return None

    def _requirements_file_for_service(self, service: Any) -> str | None:
        service_path = service.service_path or "./"
        path = Path(service_path)
        for candidate in [path / "requirements.txt", path / "pyproject.toml"]:
            if candidate.exists():
                return candidate.name
        return None

    def _command_tokens(self, start_command: str) -> str:
        tokens = start_command.strip().split()
        if not tokens:
            return "[]"
        if len(tokens) == 1:
            return f"[\"{tokens[0]}\"]"
        return "[" + ", ".join(f"\"{token}\"" for token in tokens) + "]"

    def _strip_secret_values(self, dockerfile_content: str) -> str:
        lines = []
        for line in dockerfile_content.splitlines():
            lower = line.lower()
            if "mongodb://" in lower or "postgres://" in lower or "redis://" in lower or "password=" in lower or "secret=" in lower:
                continue
            lines.append(line)
        return "\n".join(lines) + "\n"

    def _assess_generation_readiness(self, generated_services: list[dict[str, Any]]) -> str:
        if not generated_services:
            return "blocked"
        if any(service["generation_readiness"] == "blocked" for service in generated_services):
            return "blocked"
        if any(service["generation_readiness"] == "requires_confirmation" for service in generated_services):
            return "requires_confirmation"
        return "ready"

    def _validate_service_results(self, generated_services: list[dict[str, Any]]) -> dict[str, Any]:
        warnings: list[str] = []
        blockers: list[str] = []
        for service in generated_services:
            warnings.extend(service.get("warnings", []))
            blockers.extend(service.get("blockers", []))
            if not service.get("dockerfile_content"):
                blockers.append(f"{service['service_name']}: generated Dockerfile content is empty.")
            if service.get("generation_readiness") == "ready":
                if "FROM " not in service.get("dockerfile_content", ""):
                    blockers.append(f"{service['service_name']}: Dockerfile is missing a base image.")
                if "WORKDIR " not in service.get("dockerfile_content", ""):
                    blockers.append(f"{service['service_name']}: Dockerfile is missing WORKDIR.")
                if "CMD " not in service.get("dockerfile_content", ""):
                    blockers.append(f"{service['service_name']}: Dockerfile is missing a start command.")
            if service.get("exposed_port") is None and service.get("generation_readiness") == "ready":
                blockers.append(f"{service['service_name']}: ready Dockerfile cannot have an unknown port.")
            if any(secret in str(service.get("dockerfile_content", "")).lower() for secret in ["mongodb://", "postgres://", "redis://", "password="]):
                blockers.append(f"{service['service_name']}: secret values must not appear in generated Dockerfiles.")
        return {"valid": not blockers, "warnings": list(dict.fromkeys(warnings)), "blockers": list(dict.fromkeys(blockers))}


__all__ = ["DockerfileGenerator"]
