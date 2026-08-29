from __future__ import annotations

from pathlib import Path

from app.analysis.parsers.base import BaseManifestParser
from app.analysis.parsers.package_json import PackageJsonParser
from app.analysis.parsers.pyproject import PyProjectParser
from app.analysis.parsers.requirements import RequirementsParser
from app.core.registry import ParserRegistry


class ManifestParserRegistry(ParserRegistry):
    def __init__(self) -> None:
        super().__init__()
        self.register("package.json", PackageJsonParser())
        self.register("requirements.txt", RequirementsParser())
        self.register("pyproject.toml", PyProjectParser())

    def get_for_path(self, file_path: Path) -> BaseManifestParser:
        file_name = file_path.name
        for parser in self.all():
            if parser.can_parse(file_name):
                return parser
        raise ValueError(f"No parser registered for {file_name}")
