r"""Offline Windows runtime smoke test; its successful output is required evidence.

Run with the bundle's python\python.exe, not an unrelated system Python.
This verifies imports, actual OCR, translation, both exports and source integrity.
It is intentionally separate from the unexecuted Windows 10/11 acceptance claim.
"""

import io
import json
import platform
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))


def main():
    import cv2
    import pymupdf as fitz
    from PIL import Image, ImageDraw, ImageFont
    from drawing_translator.pipeline import Pipeline, digest
    from drawing_translator.exporting import export_result
    assert cv2.__version__.startswith("4.11"), "Unexpected OpenCV runtime"
    results = []
    pipeline = Pipeline()
    with tempfile.TemporaryDirectory(prefix="drawing_smoke_") as temp:
        directory = Path(temp)
        for extension in [".png", ".jpg", ".bmp"]:
            source = directory / ("sample" + extension)
            image = Image.new("RGB", (1000, 600), "white")
            font = ImageFont.truetype(io.BytesIO(fitz.Font("helv").buffer), 40)
            ImageDraw.Draw(image).text((80, 100), "GROOVE DEPTH", font=font, fill="black")
            image.save(source)
            before = digest(source)
            result = pipeline.run(source, cache=False)
            assert any(r["translation"] == "槽深" for r in result["pages"][0]["regions"])
            for mode in ["beside", "cover"]:
                files, report = export_result(source, result, directory / mode, mode)
                assert all(p.exists() and p.stat().st_size > 0 for p in files)
                assert report["omitted_annotations"] == 0
            assert digest(source) == before
            results.append({"format": extension, "seconds": result["elapsed_seconds"], "status": "passed"})
        demo = ROOT / "src/drawing_translator/data/demo/sample.pdf"
        result = pipeline.run(demo, cache=False)
        assert result["statistics"]["text_regions"] > 10
        assert pipeline.translator._load_model(), "Offline translation model missing"
        for mode in ["beside", "cover"]:
            files, _ = export_result(demo, result, directory / "pdf" / mode, mode)
            with fitz.open(files[0]) as d:
                assert d.page_count == 1
        results.append({"format": ".pdf", "seconds": result["elapsed_seconds"], "status": "passed"})
    report = {"platform": platform.platform(), "python": sys.version, "opencv": cv2.__version__, "results": results, "status": "passed"}
    target = ROOT / "Windows自检结果.json"
    target.write_text(json.dumps(report, ensure_ascii=False, indent=2), "utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
