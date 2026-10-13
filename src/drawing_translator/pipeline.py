"""One pipeline shared by the UI, batch CLI and reproducible acceptance runner."""

import hashlib
import json
import platform
import time
from datetime import datetime, timezone
from pathlib import Path

from . import __version__
from .extraction import Drawing, Extractor
from .exporting import write_metadata
from .paths import DATA_ROOT, prepare_storage
from .translation import Translator


def digest(path):
    """
    Stream the source file through SHA-256 using bounded chunks.
    The fingerprint records exactly which original produced each output.
    It also scopes OCR cache entries without storing arbitrary user paths in cache keys.
    Changing even a single source byte invalidates that source's cached extraction.
    This is an integrity identifier, not an anonymization or encryption mechanism.
    The function reads the source and never changes its metadata or contents.
    """
    hasher = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def atomic_json(path, value):
    """
    Serialize a complete UTF-8 evidence object to a sibling temporary file.
    Replacing the destination is atomic on the supported local filesystems.
    A browser reading during a save does not receive a truncated JSON document.
    Callers remain responsible for validating the schema and preparing the directory.
    The previous version persists if serialization fails before the rename.
    No raw API credential is part of the application's result schema.
    """
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2), "utf-8")
    temporary.replace(path)


def audit(event, **fields):
    """
    Append-only daily JSONL logs. No automatic deletion, thus retained >=180 days.
    
    Use timezone-aware ISO timestamps so exported evidence has an explicit offset.
    The daily log records filename, event, elapsed time and issue statistics.
    No deletion scheduler is installed; retention exceeds the required 180 days.
    The application does not promise retention if a person removes the workspace.
    OCR text and drawing image bytes are not copied into routine operation logs.
    The local export report remains the detailed source for individual warnings.
    """
    prepare_storage()
    now = datetime.now().astimezone()
    target = DATA_ROOT / "logs" / (now.strftime("%Y-%m-%d") + ".jsonl")
    with target.open("a", encoding="utf-8") as f:
        f.write(json.dumps({"time": now.isoformat(), "event": event, **fields}, ensure_ascii=False) + "\n")


class Pipeline:
    def __init__(self):
        self.extractor = Extractor()
        self.translator = Translator()

    def run(self, path, quality="fast", pages=None, progress=lambda *_: None, cancelled=lambda: False, cache=True):
        """
        A document is processed page by page, bounding temporary raster memory.
        
        Validate requested zero-based page indexes before starting expensive inference.
        Every page gets an independently measured extraction-plus-translation duration.
        Temporary rendered images are discarded before opening the next page.
        The optional extraction cache does not certify a cold-run performance result.
        Only OCR geometry is cached; changed glossary terms are always reapplied.
        Cancellation is checked between pages and inside enhanced OCR tile passes.
        Native PDF text remains preferred unless a substantial raster indicates mixed content.
        Statistics count accepted regions rather than asserting detection completeness.
        Neural translations remain reviewable even when the source OCR confidence is high.
        The original file hash, units and axis conventions are included in all results.
        """
        prepare_storage()
        path = Path(path)
        start = time.perf_counter()
        fingerprint = digest(path)
        indices = pages
        result = {
            "schema_version": "1.0", "app_version": __version__, "filename": path.name,
            "source_sha256": fingerprint, "created_at": datetime.now().astimezone().isoformat(),
            "offline": True, "quality": quality,
            "coordinate_system": {"bbox": "display-page top-left; x right, y down", "coordinates": "display-page bottom-left; x right, y up", "pdf_unit": "pt (1/72 inch)", "image_unit": "px; EXIF orientation applied"},
            "pages": [], "warnings": [],
        }
        self.translator.reload()
        with Drawing(path) as drawing:
            result["total_pages"] = drawing.count
            indices = list(range(drawing.count)) if indices is None else sorted(set(indices))
            if not indices or any(i < 0 or i >= drawing.count for i in indices):
                raise ValueError(f"页码须在 1 到 {drawing.count} 之间")
            for step, index in enumerate(indices):
                if cancelled():
                    raise InterruptedError("处理已取消")
                progress(step, len(indices), f"识别第 {index + 1} 页")
                # Cache only extraction, not translations: glossary edits always take effect.
                cache_path = DATA_ROOT / "cache" / f"{fingerprint}-{index}-{quality}-{__version__}.json"
                page_start = time.perf_counter()
                if cache and cache_path.exists():
                    from .models import PageResult, TextRegion
                    old = json.loads(cache_path.read_text("utf-8"))
                    old["regions"] = [TextRegion(**{k: v for k, v in r.items() if k != "coordinates"}) for r in old["regions"]]
                    page = PageResult(**old)
                    cache_hit = True
                else:
                    page = self.extractor.extract(drawing, index, quality, cancelled)
                    if cache:
                        atomic_json(cache_path, page.to_dict())
                    cache_hit = False
                progress(step, len(indices), f"本地翻译第 {index + 1} 页 · {len(page.regions)} 个文本区域")
                self.translator.translate_regions(page.regions)
                data = page.to_dict()
                data["elapsed_seconds"] = round(time.perf_counter() - page_start, 3)
                data["cache_hit"] = cache_hit
                result["pages"].append(data)
                progress(step + 1, len(indices), f"第 {index + 1} 页完成")
        result["elapsed_seconds"] = round(time.perf_counter() - start, 3)
        regions = [r for p in result["pages"] for r in p["regions"]]
        result["statistics"] = {
            "pages": len(result["pages"]), "text_regions": len(regions),
            "translated": sum(r["enabled"] and bool(r["translation"]) for r in regions),
            "needs_review": sum(r["needs_review"] for r in regions),
            "glossary_matches": sum(r["translation_method"] == "glossary" for r in regions),
            "identifiers_preserved": sum(r["translation_method"] == "identifier" for r in regions),
        }
        audit("document_processed", filename=path.name, elapsed=result["elapsed_seconds"], statistics=result["statistics"], quality=quality)
        return result
