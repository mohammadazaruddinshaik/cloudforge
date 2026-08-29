from __future__ import annotations

from app.analysis.detectors.base import BaseTechnologyDetector


class PythonDetector(BaseTechnologyDetector):
    name = "python"

    def detect(self, service_context: dict) -> dict:
        deps = {dep["name"] for dep in service_context.get("dependencies", [])}
        python_files = service_context.get("python_files", [])
        python_markers = {"fastapi", "django", "flask", "uvicorn", "gunicorn"}

        if not python_files and not deps.intersection(python_markers):
            return {}

        framework = "Unknown"
        confidence = 0.35
        evidence: list[str] = []

        if python_files:
            evidence.append("Python source files discovered")

        if "fastapi" in deps:
            framework = "FastAPI"
            confidence = 0.97
            evidence.append("fastapi dependency detected")
        elif "django" in deps:
            framework = "Django"
            confidence = 0.96
            evidence.append("django dependency detected")
        elif "flask" in deps:
            framework = "Flask"
            confidence = 0.95
            evidence.append("flask dependency detected")
        elif python_files or deps:
            framework = "Python"
            confidence = 0.7
            evidence.append("Python runtime detected without a specialized web framework")

        return {
            "language": {"value": "Python", "confidence": confidence, "evidence": evidence or ["Python dependency or source detected"]},
            "runtime": {"value": "Python", "confidence": confidence, "evidence": evidence or ["Python dependency or source detected"]},
            "framework": {"value": framework, "confidence": confidence, "evidence": evidence or ["Python dependency or source detected"]},
        }
