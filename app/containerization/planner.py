from __future__ import annotations

from pathlib import Path
from typing import Any

from app.containerization.models import ContainerizationPlan, ContainerizationServicePlan, EnvironmentVariableRequirement


class ContainerizationPlanner:
    def plan(self, deployment_plan: dict) -> dict:
        repository = deployment_plan.get("repository", {})
        services = deployment_plan.get("services", [])

        if not services:
            plan = ContainerizationPlan(
                repository=repository,
                warnings=list(deployment_plan.get("warnings", [])) or ["No deployment services were available for containerization planning."],
                blockers=["No deployable services were discovered for containerization planning."],
                assumptions=["No deployable services were discovered by Phase 2; containerization planning is not possible."],
                containerization_readiness="blocked",
                containerization_ready=False,
            )
            return plan.model_dump()

        service_plans: list[ContainerizationServicePlan] = []
        top_warnings: list[str] = list(dict.fromkeys(deployment_plan.get("warnings", [])))
        top_blockers: list[str] = []
        assumptions: list[str] = []

        validation = deployment_plan.get("validation", {})
        if isinstance(validation, dict):
            top_blockers.extend(validation.get("blockers", []))
            top_warnings.extend(validation.get("warnings", []))

        for service in services:
            runtime = self._normalize_unknown(service.get("runtime"))
            framework = self._normalize_unknown(service.get("framework"))
            dependency_install_command = service.get("dependency_install_command")
            build_command = service.get("build_command")
            start_command = service.get("start_command")
            production_serving_strategy = service.get("production_serving_strategy") or "unknown"
            entry_point = service.get("entry_point")
            port = service.get("port")
            deployment_type = service.get("deployment_type", "container")
            service_path = service.get("service_path") or service.get("path")
            service_name = service.get("name") or service.get("service_name") or "unknown-service"

            env_requirements = [
                EnvironmentVariableRequirement(
                    name=entry.get("name", "unknown"),
                    service=service_name,
                    required=bool(entry.get("required", True)),
                    secret=bool(entry.get("secret", self._looks_secret(entry.get("name", "")))),
                    source=entry.get("source"),
                    source_type=entry.get("source_type"),
                    value=None,
                )
                for entry in service.get("required_environment_variables", [])
            ]

            warnings: list[str] = list(service.get("warnings", []))
            blockers: list[str] = []
            service_assumptions: list[str] = []

            for warning in warnings:
                if "secret" in warning.lower() and "value" in warning.lower():
                    continue
            if runtime is None:
                blockers.append(f"{service_name}: runtime is missing.")
                service_assumptions.append(f"{service_name}: runtime could not be inferred from the existing Phase 1/2 evidence.")
            if not start_command:
                blockers.append(f"{service_name}: start command is missing.")
            if port is None:
                warnings.append(f"{service_name}: application port is unknown; containerization will require confirmation.")
            if framework in {"React", "Next.js"} and production_serving_strategy in {None, "unknown"}:
                warnings.append(f"{service_name}: production serving strategy is uncertain and has not been confirmed by repository evidence.")
            if not dependency_install_command and runtime is not None:
                service_assumptions.append(f"{service_name}: dependency installation command was not explicitly identified in deployment evidence.")

            relevant_source_files: list[str] = []
            if entry_point:
                if service_path:
                    candidate = Path(service_path) / entry_point
                    if candidate.exists():
                        relevant_source_files.append(str(candidate))
                relevant_source_files.append(str(entry_point))
            if service_path:
                relevant_source_files.insert(0, str(service_path))

            plan_service = ContainerizationServicePlan(
                service_name=service_name,
                name=service_name,
                service_path=service_path,
                runtime=runtime,
                framework=framework,
                base_runtime_requirement=self._base_runtime_requirement(runtime),
                working_directory=service.get("container_requirements", {}).get("working_directory") or "/app",
                dependency_install_command=dependency_install_command,
                build_command=build_command,
                start_command=start_command,
                production_serving_strategy=production_serving_strategy,
                entry_point=entry_point,
                application_port=port,
                port=port,
                environment_variable_requirements=env_requirements,
                deployment_type=deployment_type,
                container_command=start_command,
                container_arguments=[],
                build_context=self._build_context(repository, service_path),
                relevant_source_files=list(dict.fromkeys(relevant_source_files)),
                assumptions=service_assumptions,
                warnings=list(dict.fromkeys(warnings)),
                blockers=list(dict.fromkeys(blockers)),
            )

            plan_service.containerization_readiness = self._assess_containerization_readiness(plan_service)
            plan_service.containerization_ready = plan_service.containerization_readiness == "ready"
            assumptions.extend(plan_service.assumptions)
            service_plans.append(plan_service)

        summary_warnings = list(dict.fromkeys(top_warnings + [warning for service in service_plans for warning in service.warnings]))
        summary_blockers = list(dict.fromkeys(top_blockers + [blocker for service in service_plans for blocker in service.blockers]))
        readiness = self._assess_plan_readiness(service_plans)
        plan = ContainerizationPlan(
            repository=repository,
            services=service_plans,
            assumptions=list(dict.fromkeys(assumptions)),
            warnings=summary_warnings,
            blockers=summary_blockers,
            containerization_readiness=readiness,
            containerization_ready=(readiness == "ready"),
        )
        return plan.model_dump()

    def _normalize_unknown(self, value: Any) -> str | None:
        if value is None:
            return None
        if isinstance(value, str):
            normalized = value.strip()
            if not normalized:
                return None
            if normalized.lower() in {"unknown", "n/a", "none"}:
                return None
            return normalized
        return str(value)

    def _looks_secret(self, name: str) -> bool:
        if not name:
            return False
        upper_name = name.upper()
        markers = {"SECRET", "TOKEN", "KEY", "PASSWORD", "PASS", "URI", "URL", "DB", "MONGO", "REDIS"}
        return any(marker in upper_name for marker in markers)

    def _base_runtime_requirement(self, runtime: str | None) -> str | None:
        if runtime is None:
            return None
        normalized = runtime.lower()
        if "node" in normalized:
            return "node"
        if "python" in normalized:
            return "python"
        if "java" in normalized:
            return "java"
        if "go" in normalized:
            return "go"
        if "dotnet" in normalized or ".net" in normalized or "c#" in normalized:
            return "dotnet"
        return runtime.lower()

    def _build_context(self, repository: dict, service_path: str | None) -> str | None:
        if service_path:
            return service_path
        return repository.get("path")

    def _assess_containerization_readiness(self, service: ContainerizationServicePlan) -> str:
        if service.runtime is None:
            return "blocked"
        if not service.start_command:
            return "blocked"
        if service.application_port is None:
            return "requires_confirmation"
        if service.framework in {"React", "Next.js"} and service.production_serving_strategy in {None, "unknown"}:
            return "requires_confirmation"
        return "ready"

    def _assess_plan_readiness(self, services: list[ContainerizationServicePlan]) -> str:
        if not services:
            return "blocked"
        if any(service.containerization_readiness == "blocked" for service in services):
            return "blocked"
        if any(service.containerization_readiness == "requires_confirmation" for service in services):
            return "requires_confirmation"
        return "ready"


__all__ = ["ContainerizationPlanner"]
