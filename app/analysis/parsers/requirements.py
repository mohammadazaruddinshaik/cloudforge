from __future__ import annotations

import re
from pathlib import Path

from app.analysis.parsers.base import BaseManifestParser, ParsedManifest


def _normalize_package_name(name: str) -> str:
    return re.sub(r"\[.*?\]", "", name).strip().lower()


def _normalize_version(version: str) -> str:
    return version.strip().split(";", 1)[0].strip()


class RequirementsManifest(ParsedManifest):
    def __init__(self, dependencies: list[dict[str, str]], file_path: Path) -> None:
        self._dependencies = dependencies
        self.file_path = file_path

    @property
    def manifest_type(self) -> str:
        return "requirements.txt"

    @property
    def dependencies(self) -> list[dict[str, str]]:
        return list(self._dependencies)


class RequirementsParser(BaseManifestParser):
    supported_names = ("requirements.txt",)

    def parse(self, file_path: Path) -> ParsedManifest:
        dependencies: list[dict[str, str]] = []
        for raw_line in file_path.read_text(encoding="utf-8").splitlines():
            clean = raw_line.strip()
            if not clean or clean.startswith("#") or clean.startswith("-"):
                continue
            if "==" in clean:
                name, version = clean.split("==", 1)
            elif ">=" in clean:
                name, version = clean.split(">=", 1)
            elif "~=" in clean:
                name, version = clean.split("~=", 1)
            elif ">" in clean:
                name, version = clean.split(">", 1)
            elif "<" in clean:
                name, version = clean.split("<", 1)
            else:
                name, version = clean, ""
            dependencies.append({
                "name": _normalize_package_name(name),
                "version": _normalize_version(version),
                "source": str(file_path),
                "scope": "runtime",
            })
        return RequirementsManifest(dependencies, file_path)
