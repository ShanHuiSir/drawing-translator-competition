"""Add red translations without re-rasterizing the source PDF or resizing images.

The non-cover layout uses an integral ink mask and existing text rectangles.
If no vacant area exists, the annotation is omitted with an explicit warning;
its translation and original location remain in the JSON/CSV deliverable.
"""

import csv
import io
import json
import math
from pathlib import Path

import numpy as np
import pymupdf as fitz
from PIL import ImageDraw, ImageFont

from .extraction import Drawing, overlap

FONT = fitz.Font("china-s")
FONT_BYTES = FONT.buffer


def wrap(text, size, width):
    """
    Wrap by actual glyph advance so mixed Chinese/dimensions never stretch.
    
    Use the embedded font's glyph advances, including Latin digits and CJK glyphs.
    Explicit newlines start new annotation lines and are not rendered as glyphs.
    A line is broken before adding a character that would exceed available width.
    The routine does not distort or horizontally scale the Chinese translation.
    Empty text produces a harmless empty line for the placement caller.
    Font size is chosen independently from the preserved source image resolution.
    """
    lines, line = [], ""
    for char in text:
        if char == "\n" or (line and FONT.text_length(line + char, fontsize=size) > width):
            lines.append(line)
            line = "" if char == "\n" else char
        else:
            line += char
    if line:
        lines.append(line)
    return lines or [""]


def intersect(a, b):
    """
    Test positive-area rectangle intersection, ignoring edge-only contact.
    Existing English boxes and already placed translations are treated as obstacles.
    This is a geometric check in the common displayed-page coordinate system.
    Ink-mask checks supplement boxes because leader lines and dimensions are not OCR text.
    The algorithm does not attempt semantic grouping of neighboring callouts.
    Geometry is kept deterministic so JSON placements can reproduce an export.
    """
    return min(a[2], b[2]) > max(a[0], b[0]) and min(a[3], b[3]) > max(a[1], b[1])


class Layout:
    def __init__(self, image, width, height, regions):
        gray = np.asarray(image.convert("L"))
        mask = (gray < 230).astype(np.uint32)
        self.ink = np.pad(mask.cumsum(0, dtype=np.int64).cumsum(1, dtype=np.int64), ((1, 0), (1, 0)))
        self.width, self.height = width, height
        self.sx, self.sy = image.width / width, image.height / height
        self.occupied = [r["bbox"] for r in regions]

    def vacant(self, box):
        """
        Reject candidates beyond the displayed page's visible rectangle.
        Reject overlap with any detected source text or previously placed annotation.
        Map candidate edges conservatively into the downsampled preview ink mask.
        An integral image provides the candidate's dark-pixel count in constant time.
        Only zero counted ink is accepted; empty white paper is the placement target.
        Tiny features below the preview resolution can still require human visual review.
        This method approves annotation layout, not the translated engineering meaning.
        """
        if box[0] < 1 or box[1] < 1 or box[2] > self.width - 1 or box[3] > self.height - 1:
            return False
        if any(intersect(box, r) for r in self.occupied):
            return False
        x0, y0 = math.floor(box[0] * self.sx), math.floor(box[1] * self.sy)
        x1, y1 = math.ceil(box[2] * self.sx), math.ceil(box[3] * self.sy)
        count = self.ink[y1, x1] - self.ink[y0, x1] - self.ink[y1, x0] + self.ink[y0, x0]
        # Strict zero-ink rule avoids painting onto dimensions or leader lines.
        return count == 0

    def place(self, region, mode):
        """
        Estimate a readable font size from the source's actual lettering orientation.
        Cover mode first fits the translation inside the original English text rectangle.
        If that would require an unreadable font, cover the original but seek a blank area.
        Non-cover mode tries nearby offsets, then a wider distance-ordered grid search.
        Each successful location is reserved before processing the next annotation.
        The original source bbox remains unchanged, regardless of annotation displacement.
        If no location is available, return an explicit omitted-annotation warning.
        Callers must propagate that warning into the export report and UI notification.
        """
        source = region["bbox"]
        x0, y0, x1, y1 = source
        letter_height = min(y1 - y0, x1 - x0) if (y1 - y0) > (x1 - x0) * 2 else y1 - y0
        size = max(5 if self.width < 2000 else 12, min(8 if self.width < 2000 else 24, letter_height * .8))
        text = region["translation"]
        if mode == "cover":
            # Cover only the English bounding box. Fit text inside the same rectangle.
            for candidate_size in np.arange(size, 4, -.5):
                lines = wrap(text, float(candidate_size), max(x1 - x0 - 2, 1))
                if len(lines) * candidate_size * 1.4 <= y1 - y0 - 1:
                    return source, lines, float(candidate_size), None
            box, lines, size, warning = self.place(region, "beside")
            return box, lines, size, warning or "原文框较小，遮挡原文并将译文移至空白区"
        max_width = max(30, min(self.width * .24, max(x1 - x0, size * 10)))
        lines = wrap(text, size, max_width)
        w = max(FONT.text_length(line, fontsize=size) for line in lines) + 4
        h = len(lines) * size * 1.4 + 3
        gap = max(3, size * .4)
        candidates = []
        # Try nearby above/below positions first, then gradually search wider.
        for distance in (gap, gap + h, gap + h * 2, gap + h * 4, self.height * .12):
            candidates.extend([
                [x0, y0 - h - distance, x0 + w, y0 - distance],
                [x0, y1 + distance, x0 + w, y1 + distance + h],
                [x1 + distance, y0, x1 + distance + w, y0 + h],
                [x0 - w - distance, y0, x0 - distance, y0 + h],
            ])
        for box in candidates:
            if self.vacant(box):
                self.occupied.append(box)
                return box, lines, size, None
        # Search the remaining page's blank areas in order of distance from source.
        # Placement coordinates are exported, so reviewers can trace relocated notes.
        grid = []
        for y in np.arange(3, self.height - h - 3, max(h + 4, self.height / 50)):
            for x in np.arange(3, self.width - w - 3, max(w / 2, self.width / 30)):
                grid.append([float(x), float(y), float(x + w), float(y + h)])
        grid.sort(key=lambda b: (b[0] - x0) ** 2 + (b[1] - y0) ** 2)
        for box in grid:
            if self.vacant(box):
                self.occupied.append(box)
                return box, lines, size, "译文移至可用空白区，标注位置详见导出 JSON"
        # A dense drawing is not made readable by forcing overlapping red text.
        return None, [], size, "附近无空白区域；译文保存在坐标 JSON 中，可手动缩短或调整"


def annotate_pdf_page(page, page_data, mode):
    """
    Keep the original objects, dimensions and color spaces; add one overlay layer.
    
    Remove page rotation by transforming objects, keeping the displayed geometry.
    Render a reduced-resolution ink map only for layout decisions.
    Embed a real CJK font once per document so measurement and rendering agree.
    Paint a white overlay only in cover mode, without deleting the source PDF content.
    Draw translations with a fixed red color in the topmost PDF content layer.
    Source image streams, vector paths and page dimensions are not rasterized.
    Return per-region annotation positions and layout warnings for the JSON evidence.
    """
    if page.rotation:
        page.remove_rotation()
    pix = page.get_pixmap(matrix=fitz.Matrix(min(1400 / max(page.rect.width, page.rect.height), 2),
                                            min(1400 / max(page.rect.width, page.rect.height), 2)), alpha=False)
    from PIL import Image
    image = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
    layout = Layout(image, page_data["width"], page_data["height"], page_data["regions"])
    # Embed one real CJK font per document. Built-in PDF CJK names use fixed Latin
    # advances, which disagree with font.text_length and can clip mixed notes.
    page.insert_font(fontname="DTChinese", fontbuffer=FONT_BYTES)
    placements = []
    for r in page_data["regions"]:
        if not r["enabled"] or not r["translation"] or r["translation_method"] == "identifier":
            continue
        box, lines, size, warning = layout.place(r, mode)
        entry = {"id": r["id"], "bbox": box, "font_size": size, "warning": warning}
        placements.append(entry)
        if box is None:
            continue
        if mode == "cover":
            # A white overlay is reversible: original PDF text remains underneath.
            page.draw_rect(fitz.Rect(r["bbox"]), color=None, fill=(1, 1, 1), overlay=True)
        for i, line in enumerate(lines):
            page.insert_text((box[0] + 1, box[1] + 1 + size * 1.05 + i * size * 1.4), line,
                             fontsize=size, fontname="DTChinese", color=(.88, .09, .12), overlay=True)
    return placements


def annotate_image(image, page_data, mode):
    """
    Annotate a copy at the original oriented pixel dimensions.
    RGB, RGBA and CMYK originals keep their respective direct color models.
    Grayscale cannot display red, so it becomes RGB with unchanged gray pixel values.
    The exported metadata explicitly reports that unavoidable color-model change.
    CMYK red and white are expressed as four-component ink values.
    The embedded font is passed directly to Pillow, avoiding machine-specific CJK fonts.
    Layout is measured on a temporary preview but painted on full-resolution pixels.
    """
    original_mode = image.mode
    # Red annotations require RGB for grayscale sources; preserve all original gray
    # pixel values exactly as equal R/G/B channels, with no JPEG recompression.
    if image.mode not in ("RGB", "RGBA", "CMYK"):
        image = image.convert("RGB")
    else:
        image = image.copy()
    preview = image.convert("RGB")
    preview.thumbnail((1600, 1600))
    layout = Layout(preview, image.width, image.height, page_data["regions"])
    painter = ImageDraw.Draw(image)
    red = (0, 255, 255, 0) if image.mode == "CMYK" else ((225, 23, 31, 255) if image.mode == "RGBA" else (225, 23, 31))
    white = (0, 0, 0, 0) if image.mode == "CMYK" else ((255, 255, 255, 255) if image.mode == "RGBA" else (255, 255, 255))
    placements = []
    for r in page_data["regions"]:
        if not r["enabled"] or not r["translation"] or r["translation_method"] == "identifier":
            continue
        box, lines, size, warning = layout.place(r, mode)
        placements.append({"id": r["id"], "bbox": box, "font_size": size, "warning": warning})
        if box is None:
            continue
        font = ImageFont.truetype(io.BytesIO(FONT_BYTES), max(3, round(size)))
        if mode == "cover":
            painter.rectangle(r["bbox"], fill=white)
        for i, line in enumerate(lines):
            painter.text((box[0] + 1, box[1] + 1 + i * size * 1.4), line, font=font, fill=red)
    return image, placements, original_mode


def write_metadata(result, target):
    """
    Write the complete OCR/translation/placement object as UTF-8 JSON.
    Write a parallel tabular CSV for inspection in Windows Excel.
    CSV uses a UTF-8 BOM so Chinese text does not depend on the machine code page.
    Untrusted text starting with spreadsheet formula prefixes is quoted as literal text.
    Coordinates are the task's bottom-left values, accompanied by their explicit unit.
    Source confidence, translation method, review state and enabled state are retained.
    This CSV is an inspection view; JSON remains the complete geometry contract.
    """
    target.write_text(json.dumps(result, ensure_ascii=False, indent=2), "utf-8")
    # UTF-8 BOM lets Windows Excel open Chinese correctly; formula injection is
    # escaped for arbitrary imported OCR/user text.
    def safe(value):
        value = str(value)
        return "'" + value if value.startswith(("=", "+", "-", "@")) else value
    with target.with_suffix(".csv").open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["page", "id", "english", "chinese", "MinX", "MinY", "MaxX", "MaxY", "unit", "confidence", "method", "needs_review", "enabled"])
        for p in result["pages"]:
            for r in p["regions"]:
                c = r["coordinates"]
                writer.writerow([p["number"], r["id"], safe(r["source"]), safe(r["translation"]), c["MinX"], c["MinY"], c["MaxX"], c["MaxY"], p["unit"], r["confidence"], r["translation_method"], r["needs_review"], r["enabled"]])


def export_result(source, result, directory, mode="beside"):
    """
    Return explicit files + placement evidence; never overwrite the input drawing.
    
    Validate the requested overlay mode before creating output files.
    Derive filenames from the source stem, but always write into a separate directory.
    All original PDF pages remain in a selected-page export; only processed pages gain text.
    Retain PDF xref objects directly to avoid quadratic CAD object deduplication.
    JPEG input is exported losslessly as PNG rather than recompressed as JPEG.
    CMYK raster output uses lossless TIFF because PNG does not represent CMYK.
    Persist every relocated or omitted annotation in the same metadata bundle.
    The return value includes files and a structured report, not an unqualified success.
    """
    if mode not in ("beside", "cover"):
        raise ValueError("标注模式不正确")
    source, directory = Path(source), Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    stem = source.stem + ("_不遮挡" if mode == "beside" else "_遮挡")
    report = {"mode": mode, "pages": [], "warnings": []}
    if source.suffix.lower() == ".pdf":
        output = directory / (stem + ".pdf")
        with fitz.open(source) as doc:
            for p in result["pages"]:
                placements = annotate_pdf_page(doc[p["number"] - 1], p, mode)
                report["pages"].append({"number": p["number"], "placements": placements})
            # Some CAD PDFs have 275,000 xref objects. Deduplicating them can be
            # quadratic; retain objects directly and preserve their original encoding.
            # In particular, do not recompress the source's scanned image streams.
            doc.save(output, garbage=0, deflate=False)
    else:
        with Drawing(source) as drawing:
            image, placements, old_mode = annotate_image(drawing.image, result["pages"][0], mode)
            suffix = ".tiff" if image.mode == "CMYK" else ".bmp" if source.suffix.lower() == ".bmp" else ".png"
            output = directory / (stem + suffix)
            save_options = {"compression": "tiff_lzw"} if suffix == ".tiff" else {}
            if drawing.image.info.get("icc_profile"):
                save_options["icc_profile"] = drawing.image.info["icc_profile"]
            if drawing.image.info.get("dpi"):
                save_options["dpi"] = drawing.image.info["dpi"]
            image.save(output, **save_options)
            report["pages"].append({"number": 1, "placements": placements})
            if old_mode not in ("RGB", "RGBA", "CMYK"):
                report["warnings"].append("灰度/索引图转为 RGB 以显示红色；原像素值和尺寸保持，导出采用无损格式")
    report["omitted_annotations"] = sum(x["bbox"] is None for p in report["pages"] for x in p["placements"])
    payload = dict(result, export=report)
    meta = directory / (stem + ".json")
    write_metadata(payload, meta)
    return [output, meta, meta.with_suffix(".csv")], report
