from __future__ import annotations

from app.analysis.detectors.node import NodeDetector
from app.analysis.detectors.python import PythonDetector
from app.core.registry import DetectorRegistry


class TechnologyDetectorRegistry(DetectorRegistry):
    def __init__(self) -> None:
        super().__init__()
        self.register("node", NodeDetector())
        self.register("python", PythonDetector())

    def detect(self, service_context: dict) -> dict:
        detections = []
        for detector in self.all():
            result = detector.detect(service_context)
            if result:
                detections.append(result)
        return detections
