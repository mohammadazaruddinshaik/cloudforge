from __future__ import annotations

from app.planning.planner import DeploymentPlanner


class DeploymentPlanValidator:
    def validate(self, plan: dict | object) -> dict:
        if hasattr(plan, "model_dump"):
            payload = plan.model_dump()
        else:
            payload = plan

        planner = DeploymentPlanner()
        return planner._validate(payload) if isinstance(payload, dict) else planner._validate(plan)


__all__ = ["DeploymentPlanValidator"]
