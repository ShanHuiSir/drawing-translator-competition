"""Functional acceptance tests; these are not the owner's 50-drawing benchmark."""

import io
import json
import socket
from pathlib import Path

import numpy as np
import pymupdf as fitz
import pytest
from PIL import Image, ImageDraw, ImageFont

from drawing_translator.extraction import Drawing, Extractor
from drawing_translator.exporting import export_result, intersect
from drawing_translator.models import TextRegion
from drawing_translator.pipeline import Pipeline, digest
from drawing_translator.translation import Translator, NUMBER


@pytest.fixture(scope="session")
def pipeline():
    return Pipeline()


def native_pdf(path, rotation=0):
    with fitz.open() as d:
        p = d.new_page(width=600, height=400)
        p.insert_text((72, 100), "GROOVE DEPTH", fontsize=18)
        p.insert_text((72, 200), "MATERIAL", fontsize=18)
        p.draw_rect(fitz.Rect(300, 100, 450, 250))
        p.set_rotation(rotation)
        d.save(path)


def raster(path, rotation=0, mode="RGB"):
    image = Image.new("RGB", (1100, 700), "white")
    font = ImageFont.truetype(io.BytesIO(fitz.Font("helv").buffer), 40)
    draw = ImageDraw.Draw(image)
    draw.text((100, 100), "GROOVE DEPTH", fill="black", font=font)
    draw.text((100, 220), "MATERIAL", fill="black", font=font)
    draw.text((100, 340), "TAPER RELIEF", fill="black", font=font)
    draw.rectangle((600, 140, 950, 520), outline="black", width=3)
    image = image.rotate(rotation, expand=True)
    if mode != "RGB":
        image = image.convert(mode)
    image.save(path)


@pytest.mark.parametrize("rotation", [0, 90, 180, 270])
def test_native_pdf_coordinates_and_exports(tmp_path, pipeline, rotation):
    source = tmp_path / "drawing.pdf"
    native_pdf(source, rotation)
    original_hash = digest(source)
    result = pipeline.run(source, cache=False)
    assert result["statistics"]["glossary_matches"] == 2
    p = result["pages"][0]
    assert p["unit"] == "pt"
    for r in p["regions"]:
        x0, y0, x1, y1 = r["bbox"]
        assert 0 <= x0 < x1 <= p["width"]
        assert 0 <= y0 < y1 <= p["height"]
        assert r["coordinates"]["MinY"] == pytest.approx(p["height"] - y1, abs=.001)
    for mode in ("cover", "beside"):
        files, report = export_result(source, result, tmp_path / mode, mode)
        assert report["omitted_annotations"] == 0
        with fitz.open(files[0]) as out:
            assert tuple(out[0].rect) == (0, 0, p["width"], p["height"])
            assert "槽深" in "".join(out[0].get_text().split())
            pix = out[0].get_pixmap()
            array = np.frombuffer(pix.samples, np.uint8).reshape(pix.height, pix.width, pix.n)
            assert np.any((array[:, :, 0] > 150) & (array[:, :, 1] < 100))
        saved = json.loads(files[1].read_text())
        assert saved["source_sha256"] == original_hash
        assert files[2].read_bytes().startswith(b"\xef\xbb\xbf")
    assert digest(source) == original_hash


@pytest.mark.parametrize("extension", [".png", ".jpg", ".bmp"])
def test_real_ocr_formats_and_lossless_export(tmp_path, pipeline, extension):
    source = tmp_path / ("raster" + extension)
    raster(source)
    result = pipeline.run(source, cache=False)
    translated = [r["translation"] for r in result["pages"][0]["regions"]]
    assert "槽深" in translated and "材料" in translated and "锥度避让" in translated
    files, report = export_result(source, result, tmp_path / "out", "beside")
    with Image.open(source) as original, Image.open(files[0]) as output:
        assert original.size == output.size
        old, new = np.array(original.convert("RGB")), np.array(output.convert("RGB"))
        # Non-cover annotations must not change any pixel in the detected English box.
        for r in result["pages"][0]["regions"]:
            x0, y0, x1, y1 = map(int, r["bbox"])
            assert np.array_equal(old[y0:y1, x0:x1], new[y0:y1, x0:x1])
        assert not np.array_equal(old, new)
        assert report["omitted_annotations"] == 0


@pytest.mark.parametrize("rotation", [90, 180, 270])
def test_rotated_raster_ocr_restores_coordinates(tmp_path, pipeline, rotation):
    source = tmp_path / "rotated.png"
    raster(source, rotation)
    result = pipeline.run(source, "accurate", cache=False)
    p = result["pages"][0]
    matches = [r for r in p["regions"] if r["translation"] == "槽深"]
    assert len(matches) == 1
    for r in p["regions"]:
        assert 0 <= r["bbox"][0] < r["bbox"][2] <= p["width"]
        assert 0 <= r["bbox"][1] < r["bbox"][3] <= p["height"]
    # A mapped box really covers black source pixels, not a rotated empty location.
    with Image.open(source) as image:
        assert np.array(image.convert("L").crop(matches[0]["bbox"])).min() < 100


def test_mixed_text_layer_does_not_hide_scan(tmp_path, pipeline):
    image = tmp_path / "image.png"; raster(image)
    source = tmp_path / "mixed.pdf"
    with fitz.open() as d:
        p = d.new_page(width=600, height=400)
        p.insert_image(fitz.Rect(0, 0, 600, 382), filename=image)
        p.insert_text((450, 395), "SCALE", fontsize=10)
        d.save(source)
    result = pipeline.run(source, cache=False)
    regions = result["pages"][0]["regions"]
    assert any(r["translation"] == "槽深" for r in regions)
    assert any(r["translation"] == "比例" and r["extraction"] == "pdf-text" for r in regions)


def test_all_pages_and_selected_pages(tmp_path, pipeline):
    source = tmp_path / "multipage.pdf"
    with fitz.open() as d:
        for _ in range(3):
            d.new_page().insert_text((100, 100), "MATERIAL", fontsize=18)
        d.save(source)
    result = pipeline.run(source, cache=False)
    assert [p["number"] for p in result["pages"]] == [1, 2, 3]
    result = pipeline.run(source, pages=[2], cache=False)
    assert [p["number"] for p in result["pages"]] == [3]
    with pytest.raises(ValueError, match="页码"):
        pipeline.run(source, pages=[3], cache=False)


@pytest.mark.parametrize("name", ["broken.pdf", "broken.png", "broken.bmp", "drawing.exe"])
def test_corrupt_and_unsupported_files_are_friendly(tmp_path, name):
    source = tmp_path / name; source.write_bytes(b"not a drawing")
    with pytest.raises(ValueError):
        with Drawing(source):
            pass


def test_offline_pipeline_never_opens_external_socket(tmp_path, pipeline, monkeypatch):
    source = tmp_path / "offline.pdf"; native_pdf(source)
    # Failure is immediate if application/model code attempts outbound communication.
    def blocked(*args, **kwargs):
        raise AssertionError("Outbound connection attempted")
    monkeypatch.setattr(socket.socket, "connect", blocked)
    result = pipeline.run(source, cache=False)
    assert result["offline"] is True
    source_image = tmp_path / "offline.png"; raster(source_image)
    result = pipeline.run(source_image, cache=False)
    assert result["statistics"]["glossary_matches"] >= 3


def test_dimensions_and_identifiers_are_preserved():
    translator = Translator()
    texts = ["LAND (1 PLC)", "SEE SHEET #2", "11-5711744-40150", "R.010", "ADD .250 TO OVERALL LENGTH OF PUNCH", "GROOVE DEPTH"]
    regions = [TextRegion(str(i), text, [0, 0, 100, 20], [], 1) for i, text in enumerate(texts)]
    translator.translate_regions(regions)
    for r in regions:
        assert NUMBER.findall(r.source) == NUMBER.findall(r.translation)
    assert regions[2].translation == regions[2].source and not regions[2].enabled
    assert regions[3].translation == "R.010"
    assert "直壁段" in regions[0].translation
    assert regions[-1].translation == "槽深"


def test_local_api_session_guard_and_invalid_upload(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient
    from drawing_translator import service
    monkeypatch.setattr(service, "DATA_ROOT", tmp_path)
    headers = {"X-Local-Token": service.TOKEN}
    with TestClient(service.app) as client:
        assert client.get("/api/health").json()["offline"] is True
        assert client.post("/api/jobs", files={"file": ("x.png", b"invalid")}).status_code == 403
        assert client.post("/api/jobs", headers=headers, files={"file": ("x.png", b"invalid")}).status_code == 422
        assert client.get("/", headers={"host": "evil.example"}).status_code == 403
        assert client.post("/api/demo", headers={**headers, "origin": "https://evil.example"}).status_code == 403
        assert client.get("/api/jobs/../../etc/passwd").status_code == 404


def test_manual_edit_persists_and_export_recovers_after_restart(tmp_path, monkeypatch, pipeline):
    from fastapi.testclient import TestClient
    from drawing_translator import service
    monkeypatch.setattr(service, "DATA_ROOT", tmp_path)
    jid = "a123456789abcdef"; directory = tmp_path / "jobs" / jid
    (directory / "source").mkdir(parents=True)
    source = directory / "source/drawing.pdf"; native_pdf(source)
    result = pipeline.run(source, cache=False)
    (directory / "result.json").write_text(json.dumps(result))
    service.jobs.pop(jid, None)
    with TestClient(service.app) as client:
        rid = result["pages"][0]["regions"][0]["id"]
        response = client.patch(f"/api/jobs/{jid}/regions/{rid}", headers={"X-Local-Token": service.TOKEN}, json={"source": "GROOVE DEPTH", "translation": "槽深（复核）", "enabled": True})
        assert response.status_code == 200 and not response.json()["needs_review"]
        service.jobs.pop(jid, None)
        assert client.get(f"/api/jobs/{jid}/result").json()["pages"][0]["regions"][0]["translation"] == "槽深（复核）"
        response = client.post(f"/api/jobs/{jid}/export", headers={"X-Local-Token": service.TOKEN})
        assert response.status_code == 200
        assert client.get(response.json()["url"]).status_code == 200


def test_grayscale_export_keeps_pixels_and_reports_color_conversion(tmp_path, pipeline):
    source = tmp_path / "gray.png"; raster(source, mode="L")
    result = pipeline.run(source, cache=False)
    files, report = export_result(source, result, tmp_path / "out", "beside")
    with Image.open(files[0]) as output:
        assert output.mode == "RGB" and output.size == (1100, 700)
    assert report["warnings"]


def test_cancellation_does_not_kill_pipeline(tmp_path, pipeline):
    source = tmp_path / "cancel.pdf"; native_pdf(source)
    with pytest.raises(InterruptedError):
        pipeline.run(source, cancelled=lambda: True)
    assert pipeline.run(source, cache=False)["statistics"]["translated"] == 2
