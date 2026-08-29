from __future__ import annotations

from pathlib import Path


class RelationshipAnalyzer:
    def analyze(self, services: list[dict], root: Path) -> list[dict]:
        relationships: list[dict] = []

        for service in services:
            deps = {dep["name"].lower() for dep in service.get("dependencies", [])}
            if "mongoose" in deps:
                relationships.append({
                    "source": service["name"],
                    "target": "mongodb",
                    "relationship": "database_dependency",
                    "confidence": 0.9,
                    "evidence": ["mongoose dependency detected and MONGO_URI usage is present in service source"],
                })

        return relationships
