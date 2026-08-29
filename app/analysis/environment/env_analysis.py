from __future__ import annotations

from pathlib import Path


class EnvironmentAnalyzer:
    def analyze(self, service_dir: Path, source_env_names: set[str], files: list[Path]) -> list[dict]:
        env_vars: list[dict] = []
        matched_names: set[str] = set()

        for file_path in files:
            if file_path.name not in {".env", ".env.example", ".env.sample", ".env.template"}:
                continue

            for line in file_path.read_text(encoding="utf-8", errors="ignore").splitlines():
                stripped = line.strip()
                if not stripped or stripped.startswith("#") or "=" not in stripped:
                    continue
                name, value = stripped.split("=", 1)
                cleaned_name = name.strip()
                if cleaned_name in source_env_names or file_path.parent == service_dir:
                    if cleaned_name in matched_names:
                        continue
                    matched_names.add(cleaned_name)
                    env_vars.append({
                        "name": cleaned_name,
                        "value": "<redacted>" if value.strip() else "",
                        "required": True,
                        "source": str(file_path),
                    })
        return env_vars
