from __future__ import annotations

import json
from pathlib import Path

from app.analysis.detectors.registry import TechnologyDetectorRegistry
from app.analysis.environment.env_analysis import EnvironmentAnalyzer
from app.analysis.parsers.registry import ManifestParserRegistry
from app.analysis.source.code_analysis import SourceAnalyzer


class ServiceResolver:
    def __init__(self) -> None:
        self.parser_registry = ManifestParserRegistry()
        self.detector_registry = TechnologyDetectorRegistry()
        self.source_analyzer = SourceAnalyzer()
        self.environment_analyzer = EnvironmentAnalyzer()

    def resolve(self, root_path: str | Path) -> tuple[list[dict], list[str]]:
        root = Path(root_path)
        warnings: list[str] = []
        services: list[dict] = []

        manifest_files = sorted(p for p in root.rglob("*") if p.is_file() and p.name in {"package.json", "requirements.txt", "pyproject.toml"})
        if not manifest_files:
            return services, warnings

        grouped: dict[Path, list[Path]] = {}
        for manifest in manifest_files:
            if _looks_like_ignored(manifest.parent):
                continue
            grouped.setdefault(manifest.parent, []).append(manifest)

        for directory, manifests in sorted(grouped.items(), key=lambda item: str(item[0])):
            if _looks_like_ignored(directory):
                continue

            python_files = [
                path for path in directory.rglob("*")
                if path.is_file() and path.suffix in {".py", ".js", ".ts", ".jsx", ".tsx", ".go", ".rs", ".java", ".cs"}
            ]
            deps: list[dict] = []
            package_data = {}
            parsed_manifest_paths: list[Path] = []
            for manifest_path in manifests:
                try:
                    parser = self.parser_registry.get_for_path(manifest_path)
                    parsed = parser.parse(manifest_path)
                    deps.extend(parsed.dependencies)
                    parsed_manifest_paths.append(manifest_path)
                    if manifest_path.name == "package.json":
                        with manifest_path.open("r", encoding="utf-8") as handle:
                            package_data = json.load(handle)
                except (json.JSONDecodeError, ValueError, OSError, TypeError) as exc:
                    warnings.append(f"Malformed manifest ignored: {manifest_path} ({exc})")

            if not parsed_manifest_paths:
                continue

            source_info = self.source_analyzer.analyze(directory, python_files)
            source_env_names = {entry["name"] for entry in source_info["environment_variables"]}
            env_lookup_files = [
                *list(directory.rglob(".env*")),
                *list(root.rglob(".env*")),
            ]
            env_vars = self.environment_analyzer.analyze(directory, source_env_names, env_lookup_files)
            source_info["environment_variables"] = env_vars + source_info["environment_variables"]
            detector_context = {
                "dependencies": deps,
                "package_json": any(m.name == "package.json" for m in parsed_manifest_paths),
                "package_data": package_data,
                "python_files": [str(path) for path in python_files if path.suffix == ".py"],
            }
            technology = self.detector_registry.detect(detector_context)
            if technology:
                tech_profile = max(technology, key=lambda item: (
                    item.get("framework", {}).get("confidence", 0),
                    item.get("language", {}).get("confidence", 0),
                ))
            else:
                tech_profile = {
                    "language": {"value": "Unknown", "confidence": 0.2, "evidence": ["No technology evidence found"]},
                    "runtime": {"value": "Unknown", "confidence": 0.2, "evidence": ["No runtime evidence found"]},
                    "framework": {"value": "Unknown", "confidence": 0.2, "evidence": ["No framework evidence found"]},
                }

            service_name = directory.name if directory != root else root.name
            service = {
                "name": service_name,
                "path": str(directory),
                "technology": tech_profile,
                "manifests": [str(path) for path in parsed_manifest_paths],
                "dependencies": deps,
                "entry_points": source_info["entry_points"],
                "ports": source_info["ports"],
                "environment_variables": source_info["environment_variables"],
                "build": {},
                "source_analysis": source_info,
                "docker_configuration": {},
                "warnings": [],
            }
            services.append(service)

        if not services:
            warnings.append("No supported manifests were discovered.")

        return services, warnings


def _looks_like_ignored(path: Path) -> bool:
    return any(part in {"node_modules", "venv", ".venv", "__pycache__", "dist", "build", ".next", "target", "vendor", "coverage", ".git"} for part in path.parts)
