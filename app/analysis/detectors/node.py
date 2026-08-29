from __future__ import annotations

from app.analysis.detectors.base import BaseTechnologyDetector


class NodeDetector(BaseTechnologyDetector):
    name = "node"

    def detect(self, service_context: dict) -> dict:
        deps = {dep["name"] for dep in service_context.get("dependencies", [])}
        package_json = service_context.get("package_json")
        package_data = service_context.get("package_data") or {}
        node_markers = {"next", "react", "express", "@nestjs/core", "react-dom"}

        if not package_json and not package_data and not deps.intersection(node_markers):
            return {}

        framework = "Unknown"
        confidence = 0.3
        evidence: list[str] = []

        if package_json or package_data:
            evidence.append("package manifest found")

        if "next" in deps:
            framework = "Next.js"
            confidence = 0.95
            evidence.append("next dependency detected")
        elif "react" in deps:
            framework = "React"
            confidence = 0.92
            evidence.append("react dependency detected")
        elif "express" in deps:
            framework = "Express"
            confidence = 0.93
            evidence.append("express dependency detected")
        elif "@nestjs/core" in deps:
            framework = "NestJS"
            confidence = 0.94
            evidence.append("@nestjs/core dependency detected")

        language = "JavaScript"
        runtime = "Node.js"

        if framework != "Unknown":
            confidence = max(confidence, 0.9)

        return {
            "language": {"value": language, "confidence": confidence, "evidence": evidence},
            "runtime": {"value": runtime, "confidence": confidence, "evidence": evidence},
            "framework": {"value": framework, "confidence": confidence, "evidence": evidence},
        }
