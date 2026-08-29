from __future__ import annotations

from pathlib import Path


class DockerAnalyzer:
    def analyze(self, root: Path) -> dict:
        docker_files: list[Path] = []
        for name in ("Dockerfile", "docker-compose.yml", "docker-compose.yaml", "compose.yml", "compose.yaml"):
            candidate = root / name
            if candidate.exists():
                docker_files.append(candidate)

        if not docker_files:
            return {}

        result: dict = {"files": [str(path) for path in docker_files]}
        for file_path in docker_files:
            content = file_path.read_text(encoding="utf-8", errors="ignore")
            if file_path.name == "Dockerfile":
                result["dockerfile"] = {
                    "path": str(file_path),
                    "base_image": self._first_match(content, r"^FROM\s+(\S+)", "FROM"),
                    "working_directory": self._first_match(content, r"^WORKDIR\s+(\S+)", "WORKDIR"),
                    "start_command": self._first_match(content, r"^(?:CMD|ENTRYPOINT)\s+(.*)$", "CMD/ENTRYPOINT")
                }
            elif file_path.name.endswith(("docker-compose.yml", "docker-compose.yaml", "compose.yml", "compose.yaml")):
                result["compose"] = {
                    "path": str(file_path),
                    "services": self._extract_compose_services(content),
                }
        return result

    @staticmethod
    def _first_match(content: str, pattern: str, label: str) -> str | None:
        import re
        match = re.search(pattern, content, flags=re.MULTILINE)
        return match.group(1) if match else None

    @staticmethod
    def _extract_compose_services(content: str) -> list[str]:
        import re
        matches = re.findall(r"^\s{2,}(\w+):\s*$", content, flags=re.MULTILINE)
        return matches
