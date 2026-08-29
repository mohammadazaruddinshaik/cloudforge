from __future__ import annotations

from pathlib import Path

from app.core.configuration import DEFAULT_SETTINGS


class ManifestDiscovery:
    def __init__(self, settings=None) -> None:
        self.settings = settings or DEFAULT_SETTINGS

    def discover(self, root_path: str | Path) -> list[Path]:
        root = Path(root_path)
        discovered: list[Path] = []

        if not root.exists():
            return discovered

        def walk(current: Path) -> None:
            if current.is_dir() and current.name in self.settings.ignored_directories:
                return
            if current.is_dir():
                for child in sorted(current.iterdir()):
                    if child.is_dir() and child.name in self.settings.ignored_directories:
                        continue
                    if child.is_dir():
                        walk(child)
                    elif child.name in self.settings.manifest_filenames:
                        discovered.append(child)

        walk(root)
        return sorted(discovered)
