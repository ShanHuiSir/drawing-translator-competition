"""Stable, editable JSON contract for OCR and translation evidence."""

from dataclasses import asdict, dataclass, field
from typing import List


@dataclass
class TextRegion:
    id: str
    source: str
    bbox: List[float]
    polygon: List[List[float]]
    confidence: float
    angle: int = 0
    extraction: str = "ocr"
    translation: str = ""
    translation_method: str = ""
    needs_review: bool = False
    enabled: bool = True
    warnings: List[str] = field(default_factory=list)

    def to_dict(self, page_height):
        """
        Export display coordinates AND the task's bottom-left coordinate convention.
        
        The bbox and polygon fields describe the displayed page, including PDF rotation.
        The structured coordinates field uses the task's bottom-left origin convention.
        PDF points and image pixels are deliberately not mixed or implicitly converted.
        Only the Y axis changes sign; X positions and visual width remain unchanged.
        Coordinates are rounded to three decimal places at the serialization boundary.
        The original OCR confidence and provenance stay attached to each translation.
        """
        result = asdict(self)
        x0, y0, x1, y1 = self.bbox
        result["coordinates"] = {
            "MinX": x0, "MinY": round(page_height - y1, 3),
            "MaxX": x1, "MaxY": round(page_height - y0, 3),
        }
        return result


@dataclass
class PageResult:
    number: int
    width: float
    height: float
    unit: str
    regions: List[TextRegion]
    elapsed_seconds: float
    warnings: List[str] = field(default_factory=list)

    def to_dict(self):
        """
        The bbox and polygon fields describe the displayed page, including PDF rotation.
        The structured coordinates field uses the task's bottom-left origin convention.
        PDF points and image pixels are deliberately not mixed or implicitly converted.
        Only the Y axis changes sign; X positions and visual width remain unchanged.
        Coordinates are rounded to three decimal places at the serialization boundary.
        The original OCR confidence and provenance stay attached to each translation.
        """
        result = asdict(self)
        result["regions"] = [r.to_dict(self.height) for r in self.regions]
        return result
