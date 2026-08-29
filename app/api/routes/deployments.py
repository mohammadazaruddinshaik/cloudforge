from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.analysis.repository import analyze_repository
from app.planning.planner import DeploymentPlanner

router = APIRouter(prefix="/deployments", tags=["deployments"])


class DeploymentPlanRequest(BaseModel):
    repository_path: str | None = None
    repository_analysis: dict | None = None


@router.post("/plan")
def plan_deployment_route(payload: DeploymentPlanRequest) -> dict:
    try:
        analysis = payload.repository_analysis
        if analysis is None:
            if payload.repository_path is None:
                raise ValueError("A repository path or repository analysis payload is required.")
            analysis = analyze_repository(payload.repository_path)
        plan = DeploymentPlanner().plan(analysis)
        return {"deployment_plan": plan}
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
