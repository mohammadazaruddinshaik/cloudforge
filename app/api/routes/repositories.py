from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.analysis.repository import analyze_repository

router = APIRouter(prefix="/repositories", tags=["repositories"])


class RepositoryAnalysisRequest(BaseModel):
    repository_path: str


@router.post("/analyze")
def analyze_repository_route(payload: RepositoryAnalysisRequest) -> dict:
    try:
        return analyze_repository(payload.repository_path)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
