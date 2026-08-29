from __future__ import annotations

import re
from pathlib import Path


class SourceAnalyzer:
    def analyze(self, service_path: Path, files: list[Path]) -> dict:
        entry_points: list[dict] = []
        ports: list[dict] = []
        env_vars: list[dict] = []
        source_files = [path for path in files if path.is_file() and path.suffix in {".py", ".js", ".ts", ".jsx", ".tsx", ".go", ".rs", ".java", ".cs"}]

        for file_path in source_files:
            content = file_path.read_text(encoding="utf-8", errors="ignore")
            if self._looks_like_entry_point(file_path.name, content):
                entry_points.append({
                    "path": str(file_path),
                    "confidence": 0.8,
                    "evidence": [f"Framework bootstrap pattern detected in '{file_path.name}'"],
                })

            for match in re.finditer(r"process\.env\.([A-Z0-9_]+)", content):
                env_vars.append({
                    "name": match.group(1),
                    "required": True,
                    "source": str(file_path),
                })

            for match in re.finditer(r"os\.getenv\(\s*[\"']([A-Za-z_][A-Za-z0-9_]*)[\"']\s*(?:,\s*[^)]*)?\)|os\.environ\.get\(\s*[\"']([A-Za-z_][A-Za-z0-9_]*)[\"']\s*(?:,\s*[^)]*)?\)|os\.environ\[[\"']([A-Za-z_][A-Za-z0-9_]*)[\"']\]|environ\[[\"']([A-Za-z_][A-Za-z0-9_]*)[\"']\]", content):
                env_name = next((group for group in match.groups() if group), None)
                if env_name:
                    env_vars.append({
                        "name": env_name,
                        "required": True,
                        "source": str(file_path),
                    })

            for match in re.finditer(r"PORT\s*\|\|\s*(\d+)|PORT\s*\?\?\s*(\d+)|port\s*=\s*process\.env\.PORT\s*\|\|\s*(\d+)|uvicorn\.run\([^\n]*port\s*=\s*(\d+)", content):
                port = next((group for group in match.groups() if group), None)
                if port:
                    ports.append({
                        "port": int(port),
                        "source": str(file_path),
                        "confidence": 0.9,
                        "evidence": ["explicit port assignment detected in source"],
                    })

            for match in re.finditer(r"listen\s*\(\s*process\.env\.PORT\s*\|\|\s*(\d+)", content):
                port = match.group(1)
                ports.append({
                    "port": int(port),
                    "source": str(file_path),
                    "confidence": 0.95,
                    "evidence": ["Express-style listen call detected"],
                })

        return {
            "entry_points": entry_points,
            "ports": ports,
            "environment_variables": env_vars,
            "source_files": [str(path) for path in source_files],
        }

    @staticmethod
    def _looks_like_entry_point(file_name: str, content: str) -> bool:
        lower = file_name.lower()
        if lower in {"server.js", "server.ts", "main.py", "main.go", "main.rs", "application.java", "program.cs", "main.js", "main.ts", "main.jsx", "main.tsx", "index.js", "index.ts", "index.jsx", "index.tsx"}:
            return True
        if "app = FastAPI" in content or "uvicorn.run" in content or "express()" in content or "createRoot(" in content or "ReactDOM.render(" in content or "hydrateRoot(" in content:
            return True
        return False
