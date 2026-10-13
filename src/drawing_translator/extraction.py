"""PDF text objects first; otherwise local DBNet detection + CRNN recognition.

All geometry is returned in the displayed page's top-left coordinate system.
The affine inverse of each right-angle OCR pass maps polygons back to the page.
"""

import math
import re
import threading
import time
from pathlib import Path

import numpy as np
import pymupdf as fitz
from PIL import Image, ImageOps

from .models import PageResult, TextRegion
from .paths import MODEL_ROOT

SUPPORTED = {".pdf", ".png", ".jpg", ".jpeg", ".bmp"}
MAX_PIXELS = 100_000_000
# Fail clearly on pathological image sizes rather than exhausting machine memory.
Image.MAX_IMAGE_PIXELS = MAX_PIXELS


def inverse_rotation(points, turns, width, height):
    """
    Undo np.rot90: use continuous pixel-edge coordinates, not pixel indexes.
    
    Input polygons use coordinates relative to the rotated raster's outer edges.
    The width and height arguments refer to the unrotated display raster.
    Counterclockwise quarter-turns exchange axes and reverse one edge distance.
    Coordinates are clipped only to the original raster bounds after inversion.
    The page scale is applied separately, once, after rotation restoration.
    This prevents rotated scans from acquiring plausible but misplaced boxes.
    """
    restored = []
    for x, y in points:
        if turns == 1:
            x, y = width - y, x
        elif turns == 2:
            x, y = width - x, height - y
        elif turns == 3:
            x, y = y, height - x
        restored.append([max(0, min(width, x)), max(0, min(height, y))])
    return restored


def overlap(a, b):
    """
    Intersection/min(area) removes duplicate orientation and tile detections.
    
    Use intersection divided by the smaller area for duplicate-region suppression.
    A short OCR crop inside the same larger line can still be recognized as a duplicate.
    The epsilon guards zero-area degenerate detector output.
    Bounding-box overlap is an approximation for arbitrary rotated quadrilaterals.
    It is used for candidate deduplication, not as a certificate of OCR correctness.
    The original polygon is retained alongside the axis-aligned box for audit.
    """
    w = max(0, min(a[2], b[2]) - max(a[0], b[0]))
    h = max(0, min(a[3], b[3]) - max(a[1], b[1]))
    area = min((a[2] - a[0]) * (a[3] - a[1]), (b[2] - b[0]) * (b[3] - b[1]))
    return w * h / max(area, .001)


def load_image(path):
    """
    Decode with Pillow so actual format errors do not reach the OCR engine.
    Apply EXIF orientation exactly once to establish the displayed-image coordinate frame.
    A copied image outlives the input file handle without holding an open descriptor.
    An explicit pixel budget protects a local machine from decompression exhaustion.
    Indexed images become equivalent RGB/RGBA pixels where downstream drawing requires it.
    ICC profiles and resolution metadata are retained for the lossless exporter.
    """
    with Image.open(path) as source:
        if source.width * source.height > MAX_PIXELS:
            raise ValueError("图像超过 1 亿像素，请先裁分图纸")
        # EXIF orientation is applied once and becomes the documented display basis.
        image = ImageOps.exif_transpose(source).copy()
        if image.mode == "P":
            image = image.convert("RGBA" if "transparency" in source.info else "RGB")
        return image


class Drawing:
    def __init__(self, path):
        self.path = Path(path)
        self.doc = None
        self.image = None
        if self.path.suffix.lower() not in SUPPORTED:
            raise ValueError("支持 PDF、PNG、JPG 和 BMP 文件")
        try:
            if self.path.suffix.lower() == ".pdf":
                self.doc = fitz.open(self.path)
                if self.doc.is_encrypted:
                    raise ValueError("PDF 已加密，请使用解密后的副本")
                if not len(self.doc) or len(self.doc) > 1000:
                    raise ValueError("PDF 页数为空或超过 1000 页上限")
            else:
                self.image = load_image(self.path)
        except Exception as error:
            self.close()
            raise ValueError(f"无法读取图纸：文件损坏、已加密或格式不正确（{type(error).__name__}）") from error

    @property
    def count(self):
        return len(self.doc) if self.doc is not None else 1

    def geometry(self, index):
        """
        Return displayed width, height and a declared physical coordinate unit.
        A PDF page's display rectangle includes its existing rotation and crop.
        A raster's geometry is its oriented pixel grid, never a default PDF page size.
        Only an image document has exactly one indexable display page.
        The caller should validate the index against count before requesting geometry.
        The tuple is the common contract for OCR, preview, JSON and annotations.
        """
        if self.doc is not None:
            rect = self.doc[index].rect
            return rect.width, rect.height, "pt"
        return self.image.width, self.image.height, "px"

    def render(self, index, max_edge=2600, upscale=False):
        """
        Render a temporary OCR/preview image with a bounded maximum edge length.
        The scale maintains aspect ratio and is never applied to exported original pixels.
        PDF rendering accounts for existing page rotation automatically.
        The source PDF's native text and image objects remain available independently.
        Alpha is flattened only in this temporary recognition view.
        Each OCR point is later scaled back using the actual rendered dimensions.
        """
        width, height, _ = self.geometry(index)
        scale = min(max_edge / max(width, height), 4.0) if self.doc is not None else min(max_edge / max(width, height), 3.0 if upscale else 1.0)
        if self.doc is not None:
            pix = self.doc[index].get_pixmap(matrix=fitz.Matrix(scale, scale), alpha=False)
            return Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
        image = self.image.convert("RGB")
        return image.resize((max(1, round(width * scale)), max(1, round(height * scale))), resample=Image.Resampling.LANCZOS)

    def native_text(self, index):
        """
        Read PDF spans as lines rather than splitting dimensional notes into words.
        Native text coordinates are transformed with the page's rotation matrix.
        Only lines containing Latin letters are candidates for the English task.
        The extraction provenance differentiates exact PDF text from inferred OCR text.
        A sparse native layer is never treated as proof that a scanned page is complete.
        Native objects receive confidence 1.0 for extraction, not for translation accuracy.
        """
        if self.doc is None:
            return []
        page = self.doc[index]
        lines = []
        for block in page.get_text("dict")["blocks"]:
            for line in block.get("lines", []):
                text = "".join(s["text"] for s in line["spans"]).strip()
                if not re.search(r"[A-Za-z]", text):
                    continue
                rect = fitz.Rect(line["bbox"]) * page.rotation_matrix
                bbox = list(rect)
                polygon = [[rect.x0, rect.y0], [rect.x1, rect.y0], [rect.x1, rect.y1], [rect.x0, rect.y1]]
                direction = line.get("dir", (1, 0))
                angle = round((math.degrees(math.atan2(direction[1], direction[0])) + page.rotation) % 360)
                lines.append(TextRegion("", text, bbox, polygon, 1.0, angle, "pdf-text"))
        return lines

    def close(self):
        """
        Release both possible source types on normal completion and on errors.
        This avoids holding a PDF descriptor or decoded image across a long job queue.
        The object may have been only partially initialized by a corrupt input.
        Closing does not delete the uploaded local copy or any user original.
        The context-manager methods delegate here for deterministic resource cleanup.
        Temporary render buffers remain owned by the calling extraction/export step.
        """
        if self.doc is not None:
            self.doc.close()
        if self.image is not None:
            self.image.close()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()


class Extractor:
    def __init__(self):
        self.ocr = None
        self.lock = threading.Lock()

    def warmup(self):
        """
        Initialize inference sessions lazily so pure native PDFs do not require OCR.
        A lock prevents concurrent preview/job calls from racing to load models twice.
        ONNX telemetry is disabled before the application creates inference sessions.
        The English detector and recognizer are shipped as local resource files.
        The package's bundled multilingual models are a fallback if those assets are absent.
        CPU thread counts are bounded to keep a 16 GB machine responsive.
        No remote inference provider, package downloader or credential is initialized.
        """
        with self.lock:
            if self.ocr is None:
                import onnxruntime
                from rapidocr_onnxruntime import RapidOCR
                # Disable ONNX telemetry before opening any inference sessions.
                onnxruntime.disable_telemetry_events()
                english = MODEL_ROOT / "ocr"
                model_options = {}
                if (english / "en_PP-OCRv3_rec_infer.onnx").exists():
                    model_options["rec_model_path"] = str(english / "en_PP-OCRv3_rec_infer.onnx")
                    model_options["det_model_path"] = str(english / "en_PP-OCRv3_det_infer.onnx")
                self.ocr = RapidOCR(
                    intra_op_num_threads=4, inter_op_num_threads=1,
                    max_side_len=3300, det_limit_side_len=1800, det_limit_type="max",
                    text_score=.50, rec_batch_num=16,
                    **model_options,
                )

    def extract(self, drawing, index, quality="fast", cancelled=lambda: False):
        """
        Run a native-text pass and inspect whether raster content needs OCR too.
        Fast mode recognizes the displayed orientation at a bounded working resolution.
        Enhanced mode rotates the raster four ways and uses overlapping high-resolution tiles.
        The tile offset is undone before the right-angle affine inverse is applied.
        The detector's coordinates are then mapped into the original display-page units.
        Duplicate detections compete by confidence while native text retains precedence.
        White-paper contrast enhancement affects recognition pixels only.
        Low-confidence source text is flagged rather than silently corrected.
        Page and region identifiers are deterministic for an unchanged extraction order.
        The measured page duration excludes later drawing export and browser preview.
        """
        start = time.perf_counter()
        width, height, unit = drawing.geometry(index)
        native = drawing.native_text(index)
        # Native text is cheap and exact, but a sparse text layer can coexist with
        # scanned annotations. Such mixed pages still get OCR to avoid silent loss.
        image = drawing.render(index, 2200 if quality == "fast" else 3200, upscale=quality == "accurate")
        regions = native[:]
        if drawing.doc is not None:
            page = drawing.doc[index]
            has_large_image = any(fitz.Rect(info["bbox"]).get_area() > page.rect.get_area() * .15 for info in page.get_image_info())
        else:
            has_large_image = True
        if not native or has_large_image:
            self.warmup()
            array = np.asarray(image)
            # Faint engineering lettering gets darker on white paper. The source
            # pixels are untouched; this is an OCR-only contrast normalization.
            if float(array.mean()) > 235:
                array = np.clip(255 - (255 - array.astype(np.float32)) * 2.5, 0, 255).astype(np.uint8)
            frames = [(image, array, turn, False) for turn in ([0] if quality == "fast" else [0, 1, 2, 3])]
            if quality == "accurate":
                # High-resolution tile edges can split a long heading. A complete
                # lower-resolution pass preserves those lines before tile refinement.
                baseline = drawing.render(index, 2200)
                base_array = np.asarray(baseline)
                if float(base_array.mean()) > 235:
                    base_array = np.clip(255 - (255 - base_array.astype(np.float32)) * 2.5, 0, 255).astype(np.uint8)
                frames.insert(0, (baseline, base_array, 0, True))
            for frame_image, frame_array, turn, baseline_pass in frames:
                if cancelled():
                    raise InterruptedError("处理已取消")
                rotated = np.ascontiguousarray(np.rot90(frame_array, turn))
                # Large enhanced pages use overlapping tiles to preserve tiny text
                # without allocating an unbounded detector tensor.
                tile_size = 1700 if quality == "accurate" and not baseline_pass else max(rotated.shape[:2])
                stride = tile_size - 180
                ys = list(range(0, max(1, rotated.shape[0] - 180), stride))
                xs = list(range(0, max(1, rotated.shape[1] - 180), stride))
                for y in ys:
                    for x in xs:
                        if cancelled():
                            raise InterruptedError("处理已取消")
                        tile = np.ascontiguousarray(rotated[y:y + tile_size, x:x + tile_size])
                        with self.lock:
                            output, _ = self.ocr(tile, box_thresh=.35 if quality == "accurate" and not baseline_pass else .5,
                                                 text_score=.4 if quality == "accurate" and not baseline_pass else .5)
                        for points, text, confidence in output or []:
                            if not re.search(r"[A-Za-z]", text):
                                continue
                            poly = inverse_rotation([[p[0] + x, p[1] + y] for p in points], turn, frame_image.width, frame_image.height)
                            poly = [[round(a * width / frame_image.width, 3), round(b * height / frame_image.height, 3)] for a, b in poly]
                            bbox = [min(p[0] for p in poly), min(p[1] for p in poly), max(p[0] for p in poly), max(p[1] for p in poly)]
                            r = TextRegion("", text.strip(), bbox, poly, round(float(confidence), 4), (turn * 90) % 360)
                            collisions = [old for old in regions if overlap(old.bbox, bbox) > .65]
                            if not collisions:
                                regions.append(r)
                            elif all(old.extraction != "pdf-text" and self._prefer(r, old) for old in collisions):
                                regions = [old for old in regions if old not in collisions]
                                regions.append(r)
        regions.sort(key=lambda r: (round(r.bbox[1] / 8), r.bbox[0]))
        for i, r in enumerate(regions):
            r.id = f"p{index + 1}-t{i + 1}"
            if r.confidence < .85:
                r.warnings.append("OCR 置信度低于 0.85，请核对英文原文")
        warnings = []
        if quality == "fast":
            warnings.append("快速模式仅处理当前朝向；旋转文字与细小字体请使用四方向增强模式")
        if not regions:
            warnings.append("未发现英文文本；请检查页面、分辨率或改用增强模式")
        return PageResult(index + 1, width, height, unit, regions, round(time.perf_counter() - start, 3), warnings)

    @staticmethod
    def _prefer(incoming, existing):
        """Keep a confident complete line over a tile fragment even if its score is lower.

        OCR confidence alone ranks a short fragment above a complete long heading.
        Line completeness matters when combining a full-page pass with overlapping tiles.
        Native text precedence is enforced by the caller before this comparison.
        This heuristic does not normalize or rewrite the stored recognized characters.
        """
        old_length = len(re.sub(r"\s", "", existing.source))
        new_length = len(re.sub(r"\s", "", incoming.source))
        if existing.confidence >= .85 and old_length > new_length * 1.4:
            return False
        if incoming.confidence >= .85 and new_length > old_length * 1.4:
            return True
        return incoming.confidence > existing.confidence
