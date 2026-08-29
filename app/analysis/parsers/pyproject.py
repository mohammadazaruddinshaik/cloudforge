from __future__ import annotations

import re
import tomllib
from pathlib import Path
from typing import Any

from app.analysis.parsers.base import BaseManifestParser, ParsedManifest


def _normalize_package_name(name: str) -> str:
    return re.sub(r"\[.*?\]", "", name).strip().lower()


def _normalize_version(version: str) -> str:
    return version.strip().split(";", 1)[0].strip()


class PyProjectManifest(ParsedManifest):
    def __init__(self, data: dict[str, Any], file_path: Path) -> None:
        self._data = data
        self.file_path = file_path

    @property
    def manifest_type(self) -> str:
        return "pyproject.toml"

    @property
    def dependencies(self) -> list[dict[str, str]]:
        deps: list[dict[str, str]] = []
        project = self._data.get("project", {})
        for dep in project.get("dependencies", []):
            name, version = self._extract_dependency(dep)
            deps.append({
                "name": _normalize_package_name(name),
                "version": _normalize_version(version),
                "source": str(self.file_path),
                "scope": "runtime",
            })
        for dep_group in project.get("optional-dependencies", {}).values():
            for item in dep_group:
                name, version = self._extract_dependency(item)
                deps.append({
                    "name": _normalize_package_name(name),
                    "version": _normalize_version(version),
                    "source": str(self.file_path),
                    "scope": "dev",
                })
        return deps

    @staticmethod
    def _extract_dependency(value: str) -> tuple[str, str]:
        cleaned = value.strip()
        for operator in ("==", ">=", "~=", ">", "<", "!=", "="):
            if operator in cleaned:
                index = cleaned.find(operator)
                return cleaned[:index].strip(), cleaned[index + len(operator):].split(";", 1)[0].strip()
        return cleaned, ""


class PyProjectParser(BaseManifestParser):
    supported_names = ("pyproject.toml",)

    def parse(self, file_path: Path) -> ParsedManifest:
        with file_path.open("rb") as handle:
            data = tomllib.load(handle)
        return PyProjectManifest(data, file_path)
