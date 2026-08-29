from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from app.analysis.parsers.base import BaseManifestParser, ParsedManifest


def _normalize_package_name(name: str) -> str:
    return re.sub(r"\[.*?\]", "", name).strip().lower()


def _normalize_version(version: str | None) -> str:
    if version is None:
        return ""
    normalized = version.strip()
    return re.sub(r"^[\^~><=!]+", "", normalized)


class PackageJsonManifest(ParsedManifest):
    def __init__(self, data: dict[str, Any], file_path: Path) -> None:
        self._data = data
        self.file_path = file_path

    @property
    def manifest_type(self) -> str:
        return "package.json"

    @property
    def dependencies(self) -> list[dict[str, Any]]:
        all_deps: list[dict[str, Any]] = []
        for scope_name in ("dependencies", "devDependencies", "optionalDependencies"):
            deps = self._data.get(scope_name, {})
            for name, version in deps.items():
                all_deps.append({
                    "name": _normalize_package_name(name),
                    "version": _normalize_version(str(version)),
                    "source": str(self.file_path),
                    "scope": "dev" if scope_name == "devDependencies" else "runtime",
                })
        return all_deps


class PackageJsonParser(BaseManifestParser):
    supported_names = ("package.json",)

    def parse(self, file_path: Path) -> ParsedManifest:
        with file_path.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
        return PackageJsonManifest(data, file_path)
