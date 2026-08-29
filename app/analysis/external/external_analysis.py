from __future__ import annotations


class ExternalDependencyAnalyzer:
    def analyze(self, services: list[dict]) -> list[dict]:
        external: list[dict] = []
        for service in services:
            deps = {dep["name"].lower() for dep in service.get("dependencies", [])}
            if "mongoose" in deps:
                external.append({
                    "name": "MongoDB",
                    "type": "database",
                    "confidence": 0.9,
                    "evidence": ["mongoose dependency and MONGO_URI usage"],
                    "service": service["name"],
                })
            if "redis" in deps:
                external.append({
                    "name": "Redis",
                    "type": "cache",
                    "confidence": 0.8,
                    "evidence": ["redis dependency detected"],
                    "service": service["name"],
                })
            if "requests" in deps:
                external.append({
                    "name": "HTTP API",
                    "type": "external_http",
                    "confidence": 0.6,
                    "evidence": ["requests dependency detected"],
                    "service": service["name"],
                })
        return external
