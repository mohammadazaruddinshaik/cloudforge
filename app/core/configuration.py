from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

IGNORED_DIRECTORIES = {
    ".git",
    "node_modules",
    "venv",
    ".venv",
    "__pycache__",
    "dist",
    "build",
    ".next",
    "target",
    "vendor",
    "coverage",
}

MANIFEST_FILENAMES = {
    "package.json",
    "requirements.txt",
    "pyproject.toml",
    "Pipfile",
    "poetry.lock",
    "go.mod",
    "Cargo.toml",
    "pom.xml",
    "build.gradle",
    "build.gradle.kts",
    "composer.json",
    "Gemfile",
    "Dockerfile",
    "docker-compose.yml",
    "docker-compose.yaml",
    "compose.yml",
    "compose.yaml",
    ".env.example",
    ".env.sample",
    ".env.template",
    "README.md",
}


@dataclass
class AnalysisSettings:
    ignored_directories: set[str] = field(default_factory=lambda: set(IGNORED_DIRECTORIES))
    manifest_filenames: set[str] = field(default_factory=lambda: set(MANIFEST_FILENAMES))

    def should_skip_directory(self, directory_name: str) -> bool:
        return directory_name in self.ignored_directories


DEFAULT_SETTINGS = AnalysisSettings()
