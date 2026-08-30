from __future__ import annotations

from app.containerization.models import ContainerizationPlan


class ContainerizationPlanValidator:
    def validate(self, plan: dict | ContainerizationPlan) -> dict:
        if isinstance(plan, dict):
            plan = ContainerizationPlan.model_validate(plan)

        warnings: list[str] = []
        blockers: list[str] = []

        for service in plan.services:
            if service.runtime is None:
                blockers.append(f"{service.service_name}: runtime is missing.")
            if not service.start_command:
                blockers.append(f"{service.service_name}: start command is missing.")
            if service.application_port is None and service.containerization_readiness == "ready":
                blockers.append(f"{service.service_name}: ready state cannot have an unknown application port.")
            if any(env.value is not None for env in service.environment_variable_requirements):
                blockers.append(f"{service.service_name}: secret values must not appear in the containerization plan.")
            warnings.extend(service.warnings)
            blockers.extend(service.blockers)

        if any(env.value is not None for service in plan.services for env in service.environment_variable_requirements):
            blockers.append("Secret values must not appear in the containerization plan.")

        valid = not blockers
        return {
            "valid": valid,
            "warnings": list(dict.fromkeys(warnings + plan.warnings)),
            "blockers": list(dict.fromkeys(blockers + plan.blockers)),
        }


__all__ = ["ContainerizationPlanValidator"]
