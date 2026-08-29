from __future__ import annotations

from pathlib import Path

from app.analysis.discovery.manifest_discovery import ManifestDiscovery
from app.analysis.docker.docker_analysis import DockerAnalyzer
from app.analysis.external.external_analysis import ExternalDependencyAnalyzer
from app.analysis.relationships.service_relationships import RelationshipAnalyzer
from app.analysis.services.resolver import ServiceResolver


def analyze_repository(repository_path: str | Path) -> dict:
    root = Path(repository_path)
    if not root.exists():
        raise FileNotFoundError(f"Repository path does not exist: {repository_path}")

    discovered_files = ManifestDiscovery().discover(root)
    services, warnings = ServiceResolver().resolve(root)
    for service in services:
        for source_file in service.get("source_analysis", {}).get("source_files", []):
            discovered_files.append(Path(source_file))
    discovered_files = list(dict.fromkeys(str(path) for path in discovered_files))
    docker_configuration = DockerAnalyzer().analyze(root)
    external_dependencies = ExternalDependencyAnalyzer().analyze(services)
    relationships = RelationshipAnalyzer().analyze(services, root)

    repository_name = root.name if root.name else "repository"
    result = {
        "repository": {
            "name": repository_name,
            "path": str(root),
        },
        "services": services,
        "external_dependencies": external_dependencies,
        "relationships": relationships,
        "docker_configuration": docker_configuration,
        "analysis_warnings": warnings,
        "discovered_files": discovered_files,
    }

    if not services:
        result["analysis_warnings"].append("No deployable services could be inferred from the repository content.")

    return result
