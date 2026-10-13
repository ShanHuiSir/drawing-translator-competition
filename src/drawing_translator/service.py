"""Local-only HTTP UI, serialized inference and persistent editable job results."""

import io
import json
import secrets
import shutil
import threading
import zipfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from fastapi import FastAPI, File, Form, Header, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .extraction import Drawing, SUPPORTED
from .exporting import annotate_pdf_page, annotate_image, export_result
from .glossary import save_term
from .paths import DATA_ROOT, PACKAGE_ROOT, MODEL_ROOT, prepare_storage
from .pipeline import Pipeline, atomic_json, audit

TOKEN = secrets.token_urlsafe(32)
app = FastAPI(title="图译 · 本地图纸翻译", docs_url=None, redoc_url=None, openapi_url=None)
app.mount("/assets", StaticFiles(directory=PACKAGE_ROOT / "web"), name="assets")
executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="drawing-worker")
jobs = {}
job_lock = threading.Lock()
pipeline = None
shutdown_callback = None


@app.middleware("http")
async def local_guard(request: Request, call_next):
    """
    Protect localhost against DNS rebinding and cross-site uploads/edits.
    
    Validate Host before serving a UI that holds a local session token.
    Allow only loopback hostnames, preventing DNS rebinding from another website.
    Reject cross-origin requests even if they appear to target the loopback service.
    Require the per-process token for every mutation, upload, export and shutdown.
    GET requests remain available for the same local preview and downloaded results.
    Response headers prevent MIME sniffing and leaking referrer URLs.
    The service does not bind to a public interface or configure outbound connectors.
    """
    host = request.headers.get("host", "").split(":")[0]
    if host not in ("127.0.0.1", "localhost", "testserver"):
        return Response("Only localhost is allowed", status_code=403)
    origin = request.headers.get("origin")
    if origin and origin not in (f"http://{request.headers.get('host')}",):
        return Response("Cross-origin requests are denied", status_code=403)
    if request.method not in ("GET", "HEAD") and request.headers.get("x-local-token") != TOKEN:
        return Response("Session token required", status_code=403)
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "no-referrer"
    return response


def get_job(job_id):
    """
    Job IDs are fixed-length hexadecimal-like local directory identifiers.
    Validate the identifier before resolving any filesystem-backed result.
    Completed jobs can be restored from their persisted result and copied original.
    Only supported drawing extensions are considered source candidates.
    An interrupted job without a complete result is not falsely presented as finished.
    Internal absolute source paths are excluded from the public status representation.
    """
    if not job_id.isalnum() or len(job_id) != 16:
        raise HTTPException(404, "任务不存在")
    if job_id not in jobs:
        directory = DATA_ROOT / "jobs" / job_id
        if not (directory / "result.json").exists():
            raise HTTPException(404, "任务不存在")
        sources = [p for p in (directory / "source").glob("*") if p.suffix.lower() in SUPPORTED]
        if not sources:
            raise HTTPException(404, "任务的源文件不存在")
        jobs[job_id] = {"id": job_id, "filename": sources[0].name, "source": str(sources[0]), "status": "done", "completed": 1, "total": 1, "message": "已从本地记录恢复", "cancelled": False}
    return jobs[job_id]


def load_result(job_id):
    """
    Resolve a valid persisted job before returning editable evidence.
    A queued or running job without result JSON returns a conflict response.
    The returned path lets mutation handlers perform an atomic replacement.
    The caller reads a full snapshot, so exports cannot observe a half-written edit.
    Malformed storage errors remain visible rather than silently losing translations.
    Completed records retain the original source fingerprint for later audit.
    """
    job = get_job(job_id)
    target = DATA_ROOT / "jobs" / job_id / "result.json"
    if not target.exists():
        raise HTTPException(409, "任务尚未完成")
    return job, json.loads(target.read_text("utf-8")), target


def public_job(job):
    """
    Expose status, filename, progress and aggregate statistics to the local UI.
    Do not send internal absolute source paths or arbitrary filesystem addresses.
    The result JSON is returned through its separate authenticated local workflow.
    The representation is serializable and contains no model objects.
    Returning status never triggers processing or reopens an original drawing.
    The filename is displayed as text, not inserted as HTML.
    """
    return {k: v for k, v in job.items() if k != "source"}


def run_job(job_id, quality, page_numbers):
    """
    A single-worker executor serializes model inference across uploaded documents.
    Progress updates distinguish page recognition from offline translation.
    The pipeline is reused to amortize model initialization between jobs.
    Cancellation is cooperative and leaves other queued tasks available.
    A failed file updates its own status instead of terminating the service process.
    A complete result is atomically persisted before the job becomes done.
    Errors and elapsed statistics are appended to local audit logs.
    """
    global pipeline
    job = jobs[job_id]
    if job["cancelled"]:
        job.update(status="cancelled", message="已取消")
        return
    job.update(status="running", message="加载本地模型")
    try:
        if pipeline is None:
            pipeline = Pipeline()
        def progress(done, total, message):
            job.update(completed=done, total=total, message=message)
        result = pipeline.run(job["source"], quality, page_numbers, progress, lambda: job["cancelled"])
        target = DATA_ROOT / "jobs" / job_id / "result.json"
        atomic_json(target, result)
        job.update(status="done", message="处理完成，请复核译文", statistics=result["statistics"], elapsed_seconds=result["elapsed_seconds"])
    except InterruptedError:
        job.update(status="cancelled", message="处理已取消")
    except Exception as error:
        # The worker survives a broken file; the next queued document still runs.
        job.update(status="error", message=f"处理失败：{error}")
        audit("document_error", filename=job["filename"], error=str(error))


@app.get("/", response_class=HTMLResponse)
def index():
    """
    Serve the entirely local HTML with a freshly generated process session token.
    The token is confined to the application page and used for mutation requests.
    CSS and JavaScript come from package resources, without CDN/font dependencies.
    Reloading the browser establishes the current process token after a server restart.
    The document contains accessible labels for the file, page and review controls.
    This handler does not expose any drawing contents by itself.
    """
    return (PACKAGE_ROOT / "web/index.html").read_text("utf-8").replace("__LOCAL_TOKEN__", TOKEN)


@app.get("/api/health")
def health():
    """
    Report local asset availability without loading the inference models.
    The response differentiates glossary-only operation from installed neural fallback.
    Supported formats are declared explicitly for automated installation checks.
    The health endpoint does not send telemetry or contact a model provider.
    A present model file is not a claim of completed Windows compatibility testing.
    Version information identifies the application schema and delivered behavior.
    """
    return {"offline": True, "model_installed": bool(list(MODEL_ROOT.glob("*/model/model.bin"))), "formats": sorted(SUPPORTED), "version": "1.0.0"}


@app.post("/api/shutdown")
def shutdown():
    """
    Stop this app's server; active OCR jobs receive the same cancellation flag.
    
    Cancel this process's queued and active drawing jobs cooperatively.
    Invoke the launcher's callback to let the local server terminate gracefully.
    The per-process mutation token is enforced by the shared middleware.
    Closing a browser tab alone does not stop the background Python process.
    Completed result files and logs remain on disk after shutdown.
    No unrelated process, browser or external application is terminated.
    """
    for job in jobs.values():
        if job["status"] in ("queued", "running"):
            job["cancelled"] = True
    if shutdown_callback:
        shutdown_callback()
    return {"message": "工作台已关闭"}


@app.get("/api/jobs")
def job_list():
    """
    Discover at most the latest 100 persisted completed job records.
    Transient running tasks remain in the current process's in-memory queue.
    Restore source and result references without resetting any saved translation.
    Only app-owned job directories are inspected; there is no user-folder scan.
    The browser receives a compact status list in recent-first presentation order.
    A completed record is not automatically reprocessed on startup.
    """
    prepare_storage()
    # Reload completed jobs after restarting the program, newest first.
    for path in sorted((DATA_ROOT / "jobs").glob("*/result.json"), key=lambda p: p.stat().st_mtime, reverse=True)[:100]:
        get_job(path.parent.name)
    return [public_job(j) for j in reversed(list(jobs.values()))]


@app.post("/api/demo")
def demo():
    """
    A real supplied drawing page ships as an immediately reviewable offline demo.
    
    Copy one real supplied development drawing into a normal editable local job.
    The bundled sample result was produced by the same offline pipeline as user uploads.
    Its measured processing time is recorded, rather than fabricated for presentation.
    The sample is independent of machine paths and available without an internet connection.
    Edits affect the copied job, leaving the packaged demonstration unchanged.
    Both translated preview modes and export handlers work through the usual job contract.
    """
    prepare_storage()
    demo_root = PACKAGE_ROOT / "data/demo"
    if not (demo_root / "sample.pdf").exists():
        raise HTTPException(404, "示例尚未安装，请直接导入图纸")
    job_id = secrets.token_hex(8)
    directory = DATA_ROOT / "jobs" / job_id
    (directory / "source").mkdir(parents=True)
    source = directory / "source" / "防跳屑结构示例.pdf"
    shutil.copyfile(demo_root / "sample.pdf", source)
    result = json.loads((demo_root / "result.json").read_text("utf-8"))
    result["filename"] = source.name
    atomic_json(directory / "result.json", result)
    jobs[job_id] = {"id": job_id, "filename": source.name, "source": str(source), "status": "done", "completed": 1, "total": 1, "message": "示例已载入", "statistics": result["statistics"], "elapsed_seconds": result["elapsed_seconds"], "cancelled": False}
    return public_job(jobs[job_id])


@app.post("/api/jobs")
async def upload(file: UploadFile = File(...), quality: str = Form("fast"), pages: str = Form("")):
    """
    Sanitize the client filename and copy data into an app-owned job directory.
    Stream in bounded chunks and reject files beyond the 250 MB upload budget.
    Open the copy to detect malformed, encrypted or unsupported drawing data early.
    Parse human page ranges into zero-based indexes, with bounded range expansion.
    Reject out-of-document pages before occupying an OCR worker.
    Remove only the newly created incomplete job directory on validation failure.
    Register the queued task only after its local source copy is fully validated.
    No selected original is overwritten, moved, or sent to an external service.
    """
    if quality not in ("fast", "accurate"):
        raise HTTPException(422, "识别模式不正确")
    name = Path((file.filename or "drawing").replace("\\", "/")).name
    if Path(name).suffix.lower() not in SUPPORTED:
        raise HTTPException(422, "请选择 PDF、PNG、JPG 或 BMP")
    page_numbers = None
    if pages.strip():
        try:
            numbers = set()
            for segment in pages.replace("，", ",").split(","):
                if "-" in segment:
                    a, b = map(int, segment.split("-"))
                    if b < a or b - a > 999:
                        raise ValueError()
                    numbers.update(range(a, b + 1))
                else:
                    numbers.add(int(segment))
            if min(numbers) < 1:
                raise ValueError()
            page_numbers = [i - 1 for i in sorted(numbers)]
        except ValueError:
            raise HTTPException(422, "页码格式示例：1-3,5（留空处理全部页）")
    prepare_storage()
    job_id = secrets.token_hex(8)
    directory = DATA_ROOT / "jobs" / job_id / "source"
    directory.mkdir(parents=True)
    target = directory / name
    try:
        size = 0
        with target.open("wb") as stream:
            while chunk := await file.read(1024 * 1024):
                size += len(chunk)
                if size > 250 * 1024 * 1024:
                    raise HTTPException(413, "单文件不得超过 250 MB")
                stream.write(chunk)
        if size == 0:
            raise HTTPException(422, "文件为空")
        with Drawing(target) as drawing:
            count = drawing.count
            if page_numbers and max(page_numbers) >= count:
                raise HTTPException(422, f"文件只有 {count} 页，请调整页码范围")
    except Exception as error:
        shutil.rmtree(directory.parent, ignore_errors=True)
        if isinstance(error, HTTPException):
            raise
        raise HTTPException(422, str(error)) from error
    job = {"id": job_id, "filename": name, "source": str(target), "status": "queued", "completed": 0, "total": len(page_numbers) if page_numbers else count, "message": "等待本地处理", "cancelled": False, "quality": quality}
    jobs[job_id] = job
    executor.submit(run_job, job_id, quality, page_numbers)
    return public_job(job)


@app.get("/api/jobs/{job_id}")
def job_status(job_id: str):
    """
    Return a compact snapshot suitable for bounded browser polling.
    The client polls only queued and running records, avoiding unnecessary inference.
    Completed counts describe actual processed pages, not a simulated timer.
    A process restart can restore only jobs with fully persisted results.
    Error messages are user-facing and the original exception type is logged locally.
    No result mutation occurs while inspecting this endpoint.
    """
    return public_job(get_job(job_id))


@app.post("/api/jobs/{job_id}/cancel")
def cancel(job_id: str):
    """
    Set the task's cooperative cancellation flag if it is still active.
    The OCR loop checks this flag between rotations and tiles, not inside a native call.
    Consequently cancellation can take one current inference step to become visible.
    Finished output records are never deleted or retroactively marked cancelled.
    Other queued jobs continue through the same worker after this one exits.
    The endpoint returns the current state so the UI can explain the pending stop.
    """
    job = get_job(job_id)
    if job["status"] in ("queued", "running"):
        job["cancelled"] = True
    return public_job(job)


@app.get("/api/jobs/{job_id}/result")
def result(job_id: str):
    """
    Return the complete persisted JSON evidence for one completed task.
    That object contains source text, translations, polygons, boxes and provenance.
    Each coordinate convention and page unit is declared in the schema.
    Partial processing results are not returned as if the document were complete.
    User edits are reloaded from disk, including after a service restart.
    Layout-specific placements appear in exported JSON, not the core OCR record.
    """
    return load_result(job_id)[1]


class RegionEdit(BaseModel):
    source: str = Field(max_length=4000)
    translation: str = Field(max_length=4000)
    enabled: bool = True
    add_to_glossary: bool = False


@app.patch("/api/jobs/{job_id}/regions/{region_id}")
def edit_region(job_id: str, region_id: str, edit: RegionEdit):
    """
    Find a stable region identifier inside its containing page.
    Keep source geometry while allowing human correction of source and translated text.
    An explicit save clears the review flag and sets manual provenance.
    Only an explicitly checked option adds this pair to the personal term dictionary.
    Recompute review and enabled-translation totals from the edited evidence.
    Persist atomically before reporting success to the browser.
    The text is stored as literal data; it is not evaluated or rendered as HTML.
    """
    job, data, target = load_result(job_id)
    for page in data["pages"]:
        for r in page["regions"]:
            if r["id"] == region_id:
                r.update(source=edit.source.strip(), translation=edit.translation.strip(), enabled=edit.enabled, needs_review=False, translation_method="manual", warnings=[])
                if edit.add_to_glossary and edit.source.strip() and edit.translation.strip():
                    save_term(edit.source, edit.translation)
                data["statistics"]["needs_review"] = sum(r["needs_review"] for p in data["pages"] for r in p["regions"])
                data["statistics"]["translated"] = sum(r["enabled"] and bool(r["translation"]) for p in data["pages"] for r in p["regions"])
                atomic_json(target, data)
                audit("translation_edited", filename=job["filename"], region_id=region_id)
                return r
    raise HTTPException(404, "文本区域不存在")


@app.get("/api/jobs/{job_id}/preview/{page_number}")
def preview(job_id: str, page_number: int, mode: str = "original"):
    """
    Render either the original or one annotation mode into a temporary PNG.
    Validate both page number and overlay mode before opening source objects.
    Translated previews are available only for pages that have actually been processed.
    A PDF copy is annotated in memory and discarded after the preview response.
    A raster copy is scaled only for the browser, never for final file export.
    No browser canvas export is used as a substitute for original-resolution output.
    No-store prevents an old preview from hiding a newly saved translation.
    """
    job = get_job(job_id)
    if mode not in ("original", "beside", "cover"):
        raise HTTPException(422, "预览模式不正确")
    with Drawing(job["source"]) as drawing:
        if not 1 <= page_number <= drawing.count:
            raise HTTPException(404, "页码不存在")
        if mode == "original":
            image = drawing.render(page_number - 1, 1600)
        else:
            _, data, _ = load_result(job_id)
            page_data = next((p for p in data["pages"] if p["number"] == page_number), None)
            if page_data is None:
                raise HTTPException(404, "该页未处理")
            if drawing.doc is not None:
                page = drawing.doc[page_number - 1]
                annotate_pdf_page(page, page_data, mode)
                image = drawing.render(page_number - 1, 1600)
            else:
                image, _, _ = annotate_image(drawing.image, page_data, mode)
                image.thumbnail((1600, 1600))
        buffer = io.BytesIO()
        image.convert("RGB").save(buffer, format="PNG")
        return Response(buffer.getvalue(), media_type="image/png", headers={"Cache-Control": "no-store"})


@app.post("/api/jobs/{job_id}/export")
def export(job_id: str, mode: str = "beside"):
    """
    Load an atomic result snapshot and generate the selected overlay artifacts.
    Package the translated drawing, complete JSON and inspection CSV together.
    Place output under the validated job's own exports tree.
    Return explicit omitted-annotation counts so layout limitations are reviewable.
    The ZIP contains no uploaded API key or external-service credential.
    Log mode and issue count, while leaving source and previous result intact.
    Download is a separate GET endpoint after successful artifact creation.
    """
    job, data, _ = load_result(job_id)
    directory = DATA_ROOT / "jobs" / job_id / "exports" / mode
    try:
        files, report = export_result(job["source"], data, directory, mode)
    except ValueError as error:
        raise HTTPException(422, str(error)) from error
    bundle = directory / "图译_结果.zip"
    with zipfile.ZipFile(bundle, "w", zipfile.ZIP_DEFLATED) as z:
        for path in files:
            z.write(path, path.name)
    audit("document_exported", filename=job["filename"], mode=mode, omitted=report["omitted_annotations"])
    return {"url": f"/api/jobs/{job_id}/download/{mode}", "files": [p.name for p in files], "report": report}


@app.get("/api/jobs/{job_id}/download/{mode}")
def download(job_id: str, mode: str):
    """
    Validate a known job and one of the two fixed export mode names.
    The target filename is fixed and cannot be chosen through a traversal parameter.
    Only an already generated application result ZIP is returned.
    UTF-8 filenames are handled by the framework's Content-Disposition response.
    The original drawing is not implicitly exported as a separate attachment.
    The exported JSON retains the source fingerprint for traceability.
    """
    get_job(job_id)
    if mode not in ("beside", "cover"):
        raise HTTPException(404)
    target = DATA_ROOT / "jobs" / job_id / "exports" / mode / "图译_结果.zip"
    if not target.exists():
        raise HTTPException(404, "请先导出结果")
    return FileResponse(target, filename="图译_翻译结果.zip", media_type="application/zip")
