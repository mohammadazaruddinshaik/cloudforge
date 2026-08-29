from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any


class ParsedManifest(ABC):
    @property
    @abstractmethod
    def manifest_type(self) -> str:
        raise NotImplementedError

    @property
    @abstractmethod
    def dependencies(self) -> list[dict[str, Any]]:
        raise NotImplementedError


class BaseManifestParser(ABC):
    supported_names: tuple[str, ...] = ()

    @abstractmethod
    def parse(self, file_path: Path) -> ParsedManifest:
        raise NotImplementedError

    def can_parse(self, file_name: str) -> bool:
        return file_name in self.supported_names
