from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class RegistryError(ValueError):
    pass


class Registry(ABC):
    def __init__(self) -> None:
        self._items: dict[str, Any] = {}

    def register(self, name: str, item: Any) -> None:
        self._items[name] = item

    def get(self, name: str) -> Any:
        if name not in self._items:
            raise RegistryError(f"No item registered for '{name}'")
        return self._items[name]

    def all(self) -> list[Any]:
        return list(self._items.values())

    def names(self) -> list[str]:
        return list(self._items.keys())


class ParserRegistry(Registry):
    pass


class DetectorRegistry(Registry):
    pass
