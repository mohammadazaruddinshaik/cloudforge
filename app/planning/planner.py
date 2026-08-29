from __future__ import annotations

import json
from pathlib import Path
import tomllib

from app.planning.models import (
    ContainerRequirements,
    DeploymentPlan,
    EnvironmentVariableRequirement,
    ExternalDependencyPlan,
    NetworkingPlan,
    ServiceDeploymentPlan,
    ServiceRelationship,
)


class DeploymentPlanner:
    def plan(self, analysis: dict) -> dict:
        services = analysis.get("services", [])
        external_dependencies = analysis.get("external_dependencies", [])
        relationships = analysis.get("relationships", [])

        if not services:
            plan = DeploymentPlan(
                repository=analysis.get("repository", {}),
                services=[],
                external_dependencies=[self._normalize_external(dep) for dep in external_dependencies],
                networking=NetworkingPlan(),
                environment={"variables": []},
                container_requirements={},
                assumptions=["No deployable services were discovered by Phase 1."],
                warnings=list(analysis.get("analysis_warnings", [])) or ["No deployable services could be determined from the repository evidence."],
                validation={"valid": False, "warnings": [], "blockers": ["No deployable services were discovered."]},
                deployment_readiness="blocked",
                deployment_ready=False,
            )
            return plan.model_dump()

        service_plans: list[ServiceDeploymentPlan] = []
        warnings: list[str] = list(analysis.get("analysis_warnings", []))
        assumptions: list[str] = []

        for service in services:
            service_warning_list: list[str] = []
            runtime = self._infer_runtime(service)
            framework = self._infer_framework(service)
            port = self._infer_port(service)
            dependency_install_command = self._infer_dependency_install_command(service)
            build_command = self._infer_build_command(service)
            start_command = self._infer_start_command(service)
            production_serving_strategy = self._infer_production_serving_strategy(service, start_command, framework)
            entry_point = self._infer_entry_point(service)
            required_envs = self._infer_environment_variables(service)
            dependencies = [dep.get("name") for dep in service.get("dependencies", []) if dep.get("name")]
            service_relationships = self._derive_service_relationships(service, relationships)
            exposure = self._infer_exposure(service, service_relationships)

            if port is None:
                service_warning_list.append("No reliable application port was detected for this service.")
                warnings.append(f"{service['name']}: no reliable port was detected.")
            if start_command is None:
                service_warning_list.append("No reliable start command could be determined from project evidence.")
                warnings.append(f"{service['name']}: no reliable start command was detected.")
            if framework in {"React", "Next.js"} and production_serving_strategy in {None, "unknown"}:
                service_warning_list.append("The frontend production serving strategy is uncertain; an ECS runtime server has not been identified from repository evidence.")
                warnings.append(f"{service['name']}: frontend production serving strategy is uncertain.")

            container_requirements = ContainerRequirements(
                runtime=runtime,
                working_directory="/app",
                port=port,
                entry_point=entry_point,
                build_command=build_command,
                start_command=start_command,
            )

            if runtime in {None, "Unknown"}:
                assumptions.append(f"{service['name']}: runtime could not be inferred reliably; container configuration will require confirmation.")
            if port in {None, "unknown"}:
                assumptions.append(f"{service['name']}: container port could not be inferred reliably; it will need explicit confirmation before deployment.")

            service_plan = ServiceDeploymentPlan(
                name=service.get("name", "unknown-service"),
                service_path=service.get("path", "/"),
                deployment_type="container",
                runtime=runtime,
                framework=framework,
                dependency_install_command=dependency_install_command,
                build_command=build_command,
                build_strategy=self._infer_build_strategy(service),
                start_command=start_command,
                production_serving_strategy=production_serving_strategy,
                entry_point=entry_point,
                port=port,
                required_environment_variables=required_envs,
                dependencies=dependencies,
                service_relationships=service_relationships,
                container_requirements=container_requirements,
                exposure=exposure,
                warnings=service_warning_list,
            )
            service_plan.deployment_readiness = self._assess_service_readiness(service_plan)
            service_plan.deployment_ready = service_plan.deployment_readiness == "ready"
            service_plans.append(service_plan)

        networking = NetworkingPlan(
            service_ports=[{"service": plan.name, "port": plan.port, "exposure": plan.exposure} for plan in service_plans],
            service_to_service_communication=[
                {
                    "source": relation.source,
                    "target": relation.target,
                    "relationship": relation.relationship,
                    "deployment_implication": relation.deployment_implication,
                }
                for service_plan in service_plans
                for relation in service_plan.service_relationships
            ],
            external_access=[dep.name for dep in self._normalize_external_dependencies(external_dependencies) if dep.type in {"database", "cache", "external_http"}],
            dependency_connectivity=["Service dependencies are represented as connectivity requirements rather than automatic ECS provisioning."],
            notes=["No actual AWS networking resources were created; this is a planning-only description."],
        )

        environment_config = {
            "variables": [
                {
                    "name": variable.name,
                    "service": variable.service,
                    "required": variable.required,
                    "secret": variable.secret,
                    "source": variable.source,
                    "source_type": variable.source_type,
                }
                for service_plan in service_plans
                for variable in service_plan.required_environment_variables
            ]
        }

        container_requirements = {
            "services": [
                {
                    "name": service_plan.name,
                    "runtime": service_plan.runtime,
                    "working_directory": service_plan.container_requirements.working_directory,
                    "port": service_plan.port,
                    "entry_point": service_plan.entry_point,
                    "build_command": service_plan.build_command,
                    "start_command": service_plan.start_command,
                }
                for service_plan in service_plans
            ]
        }

        readiness_state = self._assess_plan_readiness(service_plans)
        plan = DeploymentPlan(
            repository=analysis.get("repository", {}),
            services=service_plans,
            external_dependencies=[self._normalize_external(dep) for dep in external_dependencies],
            networking=networking,
            environment=environment_config,
            container_requirements=container_requirements,
            aws_target={"provider": "AWS", "registry": "ECR", "compute": "ECS"},
            assumptions=assumptions,
            warnings=list(dict.fromkeys(warnings)),
            validation={},
            deployment_readiness=readiness_state,
            deployment_ready=(readiness_state == "ready"),
        )
        validation = self._validate(plan)
        plan.validation = validation
        if plan.validation["valid"] and plan.deployment_readiness == "ready":
            plan.deployment_ready = True
        elif plan.validation["valid"] and plan.deployment_readiness != "ready":
            plan.deployment_ready = False
        return plan.model_dump()

    def _infer_runtime(self, service: dict) -> str | None:
        technology = service.get("technology", {})
        runtime = technology.get("runtime", {}).get("value")
        return runtime or "Unknown"

    def _infer_framework(self, service: dict) -> str | None:
        technology = service.get("technology", {})
        framework = technology.get("framework", {}).get("value")
        return framework or "Unknown"

    def _infer_port(self, service: dict):
        ports = service.get("ports", [])
        if not ports:
            return None
        port_entries = sorted(ports, key=lambda item: item.get("confidence", 0), reverse=True)
        candidate = port_entries[0].get("port")
        return int(candidate) if candidate is not None else None

    def _infer_entry_point(self, service: dict) -> str | None:
        entry_points = service.get("entry_points", [])
        if not entry_points:
            return None
        entry = sorted(entry_points, key=lambda item: item.get("confidence", 0), reverse=True)[0]
        path = entry.get("path")
        if path:
            return str(Path(path).name)
        return None

    def _infer_dependency_install_command(self, service: dict) -> str | None:
        for manifest in service.get("manifests", []):
            manifest_path = Path(manifest)
            if manifest_path.name == "package.json":
                return "npm install"
            if manifest_path.name == "requirements.txt":
                return "pip install -r requirements.txt"
            if manifest_path.name == "pyproject.toml":
                try:
                    with manifest_path.open("rb") as handle:
                        pyproject = tomllib.load(handle)
                except (OSError, tomllib.TOMLDecodeError):
                    continue
                if pyproject.get("tool", {}).get("poetry"):
                    return "poetry install"
                return "pip install ."
        return None

    def _infer_build_command(self, service: dict) -> str | None:
        for manifest in service.get("manifests", []):
            manifest_path = Path(manifest)
            if manifest_path.name == "package.json":
                try:
                    with manifest_path.open("r", encoding="utf-8") as handle:
                        package_data = json.load(handle)
                except (OSError, json.JSONDecodeError, TypeError):
                    continue
                scripts = package_data.get("scripts", {})
                if "build" in scripts:
                    return scripts["build"]
                return None
            if manifest_path.name == "pyproject.toml":
                return None
        return None

    def _infer_build_strategy(self, service: dict) -> str | None:
        build_command = self._infer_build_command(service)
        if build_command:
            return build_command
        return "unknown"

    def _infer_start_command(self, service: dict) -> str | None:
        for manifest in service.get("manifests", []):
            manifest_path = Path(manifest)
            if manifest_path.name == "package.json":
                try:
                    with manifest_path.open("r", encoding="utf-8") as handle:
                        package_data = json.load(handle)
                except (OSError, json.JSONDecodeError, TypeError):
                    continue
                scripts = package_data.get("scripts", {})
                if "start" in scripts:
                    return scripts["start"]
                return None

        for entry in service.get("entry_points", []):
            path = entry.get("path")
            if not path:
                continue
            file_path = Path(path)
            try:
                content = file_path.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            if "uvicorn.run" in content:
                if "app.main:app" in content:
                    return "uvicorn app.main:app --host 0.0.0.0 --port 8000"
                return "uvicorn app:app --host 0.0.0.0 --port 8000"
            if file_path.name.lower() == "server.js":
                return "node server.js"
            if file_path.name.lower() == "main.py":
                return "python main.py"
            if file_path.name.lower() == "app.py":
                return "python app.py"
        return None

    def _infer_production_serving_strategy(self, service: dict, start_command: str | None, framework: str | None) -> str | None:
        if not start_command:
            return "unknown"
        lowered = start_command.lower()
        if framework in {"React", "Next.js"}:
            if "vite" in lowered:
                return "vite"
            if "next" in lowered:
                return "next.js"
            if "serve" in lowered:
                return "static-server"
            return "unknown"
        if "uvicorn" in lowered:
            return "uvicorn"
        if "node" in lowered:
            return "node-process"
        if "python" in lowered:
            return "python-process"
        return "unknown"

    def _infer_environment_variables(self, service: dict) -> list[EnvironmentVariableRequirement]:
        vars_: list[EnvironmentVariableRequirement] = []
        seen: set[str] = set()
        for variable in service.get("environment_variables", []):
            name = variable.get("name")
            if not name or name in seen:
                continue
            seen.add(name)
            service_name = service.get("name", "unknown-service")
            env_var = EnvironmentVariableRequirement(
                name=name,
                service=service_name,
                required=bool(variable.get("required", True)),
                secret=self._looks_secret(name),
                source=variable.get("source"),
                source_type="source" if variable.get("source") else None,
                value=None,
            )
            vars_.append(env_var)
        return vars_

    def _looks_secret(self, name: str) -> bool:
        secret_markers = {"SECRET", "TOKEN", "KEY", "PASSWORD", "PASS", "URI", "URL", "DB", "MONGO", "REDIS"}
        upper_name = name.upper()
        return any(marker in upper_name for marker in secret_markers)

    def _derive_service_relationships(self, service: dict, relationships: list[dict]) -> list[ServiceRelationship]:
        service_name = service.get("name")
        derived = []
        for relationship in relationships:
            if relationship.get("source") != service_name and relationship.get("target") != service_name:
                continue
            target = relationship.get("target")
            if relationship.get("source") == service_name:
                target_value = target
            else:
                target_value = relationship.get("source")
            derived.append(
                ServiceRelationship(
                    source=service_name,
                    target=target_value,
                    relationship=relationship.get("relationship", "unknown"),
                    deployment_implication=self._relationship_implication(relationship),
                    confidence=relationship.get("confidence"),
                    evidence=relationship.get("evidence", []),
                )
            )
        return derived

    def _relationship_implication(self, relationship: dict) -> str:
        rel_type = relationship.get("relationship", "unknown")
        if rel_type == "database_dependency":
            return "The service requires connectivity to the referenced database dependency at runtime."
        if rel_type == "http_dependency":
            return "The service requires reachable upstream HTTP dependency connectivity."
        return "The service depends on a referenced dependency that must be reachable during deployment or runtime."

    def _infer_exposure(self, service: dict, relationships: list[ServiceRelationship]) -> str:
        service_name = service.get("name", "")
        lower_name = service_name.lower()
        port = self._infer_port(service)
        start_command = self._infer_start_command(service)
        framework = self._infer_framework(service)
        production_serving_strategy = self._infer_production_serving_strategy(service, start_command, framework)

        is_frontend_like = (
            lower_name.startswith("frontend")
            or "frontend" in lower_name
            or framework in {"React", "Next.js"}
        )

        if is_frontend_like:
            if port is None or start_command is None:
                return "requires_confirmation"
            if production_serving_strategy in {"vite", "next.js", "static-server", "node-process", "python-process", "uvicorn"}:
                return "public"
            return "requires_confirmation"
        if any(rel.target.lower() == "mongodb" for rel in relationships):
            return "internal"
        if any(rel.target.lower() == "backend" or rel.target.lower() == "api" for rel in relationships):
            return "internal"
        if not relationships:
            return "unknown"
        return "unknown"

    def _normalize_external(self, dependency: dict) -> ExternalDependencyPlan:
        return ExternalDependencyPlan(
            name=dependency.get("name", "Unknown dependency"),
            type=dependency.get("type", "unknown"),
            service=dependency.get("service"),
            confidence=dependency.get("confidence"),
            evidence=dependency.get("evidence", []),
        )

    def _normalize_external_dependencies(self, dependencies: list[dict]) -> list[ExternalDependencyPlan]:
        return [self._normalize_external(dep) for dep in dependencies]

    def _assess_service_readiness(self, service_plan: ServiceDeploymentPlan) -> str:
        if not service_plan.runtime or service_plan.runtime == "Unknown":
            return "blocked"
        if not service_plan.start_command:
            return "blocked"
        if service_plan.port is None:
            if service_plan.framework in {"React", "Next.js"}:
                return "requires_confirmation"
            return "requires_confirmation"
        if service_plan.framework in {"React", "Next.js"} and service_plan.production_serving_strategy in {None, "unknown"}:
            return "requires_confirmation"
        return "ready"

    def _assess_plan_readiness(self, service_plans: list[ServiceDeploymentPlan]) -> str:
        if not service_plans:
            return "blocked"
        if any(plan.deployment_readiness == "blocked" for plan in service_plans):
            return "blocked"
        if any(plan.deployment_readiness == "requires_confirmation" for plan in service_plans):
            return "requires_confirmation"
        return "ready"

    def _validate_service(self, service_plan: ServiceDeploymentPlan) -> tuple[bool, list[str], list[str]]:
        warnings: list[str] = []
        blockers: list[str] = []

        if not service_plan.runtime:
            blockers.append(f"{service_plan.name}: runtime is missing.")
        if service_plan.deployment_type != "container":
            blockers.append(f"{service_plan.name}: unsupported deployment type '{service_plan.deployment_type}'.")
        if service_plan.port is None:
            warnings.append(f"{service_plan.name}: no explicit application port was discovered; deployment will require confirmation.")
        if not service_plan.start_command:
            blockers.append(f"{service_plan.name}: no startup strategy could be confirmed.")
        if service_plan.framework in {"React", "Next.js"} and service_plan.production_serving_strategy in {None, "unknown"}:
            warnings.append(f"{service_plan.name}: frontend production serving strategy is uncertain.")
        if any(env.value is not None for env in service_plan.required_environment_variables):
            blockers.append(f"{service_plan.name}: environment variables must not include secret values in the deployment plan.")
        if service_plan.deployment_ready and service_plan.deployment_readiness != "ready":
            blockers.append(f"{service_plan.name}: deployment is marked ready even though deployment information is still unresolved.")
        return (not blockers, warnings, blockers)

    def _is_deployment_ready(self, service_plans: list[ServiceDeploymentPlan]) -> bool:
        return all(plan.deployment_readiness == "ready" for plan in service_plans)

    def _validate(self, plan: DeploymentPlan | dict) -> dict:
        if isinstance(plan, dict):
            plan = DeploymentPlan.model_validate(plan)

        warnings: list[str] = []
        blockers: list[str] = []
        existing_service_names = {service.name for service in plan.services}
        existing_dependency_names = {dep.name for dep in plan.external_dependencies}
        for service in plan.services:
            _, svc_warnings, svc_blockers = self._validate_service(service)
            warnings.extend(svc_warnings)
            blockers.extend(svc_blockers)
        for relationship in [rel for service in plan.services for rel in service.service_relationships]:
            normalized_target = relationship.target.lower()
            if relationship.source not in existing_service_names:
                blockers.append(f"Invalid relationship: source '{relationship.source}' does not exist.")
            if relationship.target.lower() not in {name.lower() for name in existing_service_names} and relationship.target.lower() not in {name.lower() for name in existing_dependency_names}:
                blockers.append(f"Invalid relationship: target '{relationship.target}' does not exist as a service or external dependency.")
        if plan.deployment_ready and plan.deployment_readiness != "ready":
            blockers.append("Deployment readiness is inconsistent: the plan is marked ready even though it is not in the ready state.")
        if plan.aws_target.provider != "AWS":
            blockers.append("AWS target provider must be AWS.")
        if plan.aws_target.compute != "ECS":
            blockers.append("AWS compute target must be ECS.")
        if plan.aws_target.registry != "ECR":
            blockers.append("Container registry target must be ECR.")
        if any(env.value is not None for service in plan.services for env in service.required_environment_variables):
            blockers.append("Secret values must not appear in the deployment plan.")
        if any(service.warnings for service in plan.services):
            for service in plan.services:
                if service.warnings:
                    warnings.extend(service.warnings)
        valid = not blockers
        return {"valid": valid, "warnings": list(dict.fromkeys(warnings)), "blockers": list(dict.fromkeys(blockers))}


__all__ = ["DeploymentPlanner"]
