from __future__ import annotations

from abc import ABC, abstractmethod


class TechnologyEvidence:
    def __init__(self, value: str, confidence: float, evidence: list[str]) -> None:
        self.value = value
        self.confidence = confidence
        self.evidence = evidence


class BaseTechnologyDetector(ABC):
    name: str = "base"

    @abstractmethod
    def detect(self, service_context: dict) -> dict:
        raise NotImplementedError
