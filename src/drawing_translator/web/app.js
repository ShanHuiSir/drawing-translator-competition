"use strict";
const $ = id => document.getElementById(id);
const token = document.querySelector('meta[name="local-token"]').content;
const state = {jobs: [], active: null, result: null, page: 0, mode: "beside", filter: "all", selected: null, zoom: 100, revision: 0};
let toastTimer, polling = false, selecting = 0;

async function api(path, options = {}) {
  const response = await fetch(path, {...options, headers: {"X-Local-Token": token, ...(options.headers || {})}});
  if (!response.ok) {
    const text = await response.text();
    let detail = text;
    try { detail = JSON.parse(text).detail || text; } catch (_) {}
    throw new Error(typeof detail === "string" ? detail : "请求失败，请检查输入");
  }
  return response.json();
}
function notify(message, error = false) {
  $("toast").textContent = message; $("toast").classList.toggle("error", error); $("toast").hidden = false;
  clearTimeout(toastTimer); toastTimer = setTimeout(() => {$("toast").hidden = true;}, error ? 9000 : 6000);
}
function button(text, className, handler) {
  const node = document.createElement("button"); node.type = "button"; node.textContent = text; node.className = className;
  if (handler) node.addEventListener("click", handler); return node;
}
function renderJobs() {
  $("job-count").textContent = state.jobs.length;
  $("jobs").replaceChildren(...state.jobs.map(job => {
    const node = button("", "job-item" + (job.id === state.active ? " active" : ""), () => selectJob(job.id));
    const name = document.createElement("span"); name.className = "job-name"; name.textContent = job.filename;
    const meta = document.createElement("span"); meta.className = "job-meta";
    const statuses = {done: "已完成", queued: "等待处理", running: "正在识别", error: "处理失败", cancelled: "已取消"};
    meta.textContent = statuses[job.status] + (job.status === "running" ? ` · ${job.completed}/${job.total} 页` : job.statistics ? ` · ${job.statistics.text_regions} 个文本` : "");
    node.append(name, meta); return node;
  }));
}
async function uploadFiles(files) {
  const accepted = Array.from(files).filter(file => /\.(pdf|jpe?g|png|bmp)$/i.test(file.name));
  if (!accepted.length) return notify("请选择 PDF、JPG、PNG 或 BMP 文件", true);
  for (const file of accepted) {
    try {
      const form = new FormData(); form.append("file", file); form.append("quality", $("quality").value); form.append("pages", $("pages").value);
      $("status-text").textContent = `正在导入 ${file.name}…`;
      const job = await api("/api/jobs", {method: "POST", body: form});
      state.jobs.unshift(job); renderJobs(); await selectJob(job.id);
    } catch (error) {notify(`${file.name}：${error.message}`, true); $("status-text").textContent = "导入失败，请检查文件或页码";}
  }
  $("file-input").value = "";
}
async function selectJob(id) {
  const sequence = ++selecting;
  state.active = id; state.result = null; state.selected = null; state.revision = 0; state.page = 0;
  $("editor").hidden = true; $("highlight").hidden = true; $("empty-state").hidden = true; $("workbench").hidden = false;
  const job = state.jobs.find(j => j.id === id);
  if (!job) return;
  $("document-name").textContent = job.filename; $("export-button").disabled = true;
  $("region-count").textContent = "0"; $("translated-count").textContent = "0"; $("review-count").textContent = "0";
  $("elapsed").textContent = "处理中"; $("regions").replaceChildren(); $("page-select").replaceChildren();
  $("original-image").src = `/api/jobs/${id}/preview/1?mode=original`;
  $("translated-image").removeAttribute("src"); $("processing-state").hidden = false;
  renderJobs(); renderProgress(job);
  if (job.status === "done") {
    try {
      const data = await api(`/api/jobs/${id}/result`);
      if (sequence !== selecting) return;
      state.result = data; applyResult();
    } catch (error) {notify(error.message, true);}
  }
}
function renderProgress(job) {
  $("processing-message").textContent = job.message;
  $("progress").max = Math.max(1, job.total); $("progress").value = job.completed;
  $("cancel-button").hidden = !["running", "queued"].includes(job.status);
  $("status-text").textContent = `${job.filename} · ${job.message}`;
  if (["error", "cancelled"].includes(job.status)) {
    $("processing-state").querySelector("h3").textContent = job.status === "error" ? "文件未能处理" : "已停止处理";
    $("processing-state").querySelector(".spinner").hidden = true;
  } else {
    $("processing-state").querySelector("h3").textContent = "正在本地处理";
    $("processing-state").querySelector(".spinner").hidden = false;
  }
}
function applyResult() {
  const result = state.result;
  $("processing-state").hidden = true; $("export-button").disabled = false; $("cancel-button").hidden = true;
  $("page-select").replaceChildren(...result.pages.map((p, i) => {
    const option = document.createElement("option"); option.value = i; option.textContent = `第 ${p.number} 页`; return option;
  }));
  $("page-select").value = state.page;
  $("region-count").textContent = result.statistics.text_regions;
  $("translated-count").textContent = result.statistics.translated;
  $("review-count").textContent = result.statistics.needs_review;
  $("elapsed").textContent = `${result.pages.length} 页 · ${result.elapsed_seconds.toFixed(2)} 秒${result.pages.some(p => p.cache_hit) ? " · 含缓存" : ""}`;
  $("status-text").textContent = `${result.statistics.glossary_matches} 条术语匹配 · 通用机器译文和低置信度结果请复核`;
  renderPage();
}
function renderPage() {
  if (!state.result) return;
  const page = state.result.pages[state.page];
  $("prev-page").disabled = state.page === 0; $("next-page").disabled = state.page === state.result.pages.length - 1;
  $("page-select").value = state.page; $("editor").hidden = true; $("highlight").hidden = true; state.selected = null;
  $("original-image").src = `/api/jobs/${state.active}/preview/${page.number}?mode=original`;
  updatePreview(); renderRegions();
  $("coordinate-hint").textContent = `坐标单位 ${page.unit} · 左下角原点`;
}
function updatePreview() {
  if (!state.result) return;
  $("translated-image").src = `/api/jobs/${state.active}/preview/${state.result.pages[state.page].number}?mode=${state.mode}&v=${++state.revision}`;
}
function renderRegions() {
  if (!state.result) return;
  const page = state.result.pages[state.page]; const query = $("search").value.toLowerCase();
  const filtered = page.regions.filter(r => (state.filter !== "review" || r.needs_review) && (state.filter !== "glossary" || r.translation_method === "glossary") && `${r.source} ${r.translation}`.toLowerCase().includes(query));
  $("page-region-count").textContent = `${filtered.length} / ${page.regions.length} 条`;
  $("regions").replaceChildren(...filtered.map(r => {
    const node = button("", "region-item" + (state.selected === r.id ? " selected" : ""), () => editRegion(r.id));
    const english = document.createElement("span"); english.className = "english"; english.textContent = r.source;
    const chinese = document.createElement("span"); chinese.className = "chinese"; chinese.textContent = r.translation || "尚无译文";
    const meta = document.createElement("span"); meta.className = "region-meta";
    const status = document.createElement("span"); status.className = "region-status " + (r.needs_review ? "review" : "matched");
    status.textContent = r.translation_method === "identifier" ? "编号 / 尺寸保留" : r.needs_review ? "待复核" : r.translation_method === "manual" ? "已复核" : "术语匹配";
    const confidence = document.createElement("span"); confidence.textContent = `${(r.confidence * 100).toFixed(0)}% · ${r.id}`;
    meta.append(status, confidence); node.append(english, chinese, meta); return node;
  }));
  if (!filtered.length) {const p = document.createElement("p"); p.className = "panel-empty"; p.textContent = page.regions.length ? "没有符合条件的文本。" : "本页未识别到英文，可重新使用增强模式。"; $("regions").append(p);}
}
function editRegion(id) {
  const page = state.result.pages[state.page]; const r = page.regions.find(x => x.id === id);
  state.selected = id; $("editor").hidden = false; $("edit-id").textContent = `编辑 ${id}`;
  $("source-text").value = r.source; $("translation-text").value = r.translation; $("enabled").checked = r.enabled; $("save-term").checked = false;
  const c = r.coordinates;
  $("edit-coordinates").textContent = `MinX ${c.MinX.toFixed(2)} · MinY ${c.MinY.toFixed(2)}\nMaxX ${c.MaxX.toFixed(2)} · MaxY ${c.MaxY.toFixed(2)} ${page.unit}`;
  $("edit-warning").textContent = r.warnings.join("；") || (r.needs_review ? "本地机器译文，请结合图纸上下文核对。" : "");
  const box = r.bbox; const hl = $("highlight"); hl.hidden = false;
  Object.assign(hl.style, {left: `${box[0] / page.width * 100}%`, top: `${box[1] / page.height * 100}%`, width: `${(box[2] - box[0]) / page.width * 100}%`, height: `${(box[3] - box[1]) / page.height * 100}%`});
  hl.scrollIntoView({block: "center", inline: "center", behavior: "auto"});
  $("coordinate-hint").textContent = `${id} · ${page.unit}`; renderRegions();
}
async function saveEdit(event) {
  event.preventDefault(); if (!state.selected) return;
  $("save-button").disabled = true;
  try {
    const r = await api(`/api/jobs/${state.active}/regions/${state.selected}`, {method: "PATCH", headers: {"Content-Type": "application/json"}, body: JSON.stringify({source: $("source-text").value, translation: $("translation-text").value, enabled: $("enabled").checked, add_to_glossary: $("save-term").checked})});
    const page = state.result.pages[state.page]; const index = page.regions.findIndex(x => x.id === r.id); page.regions[index] = r;
    const regions = state.result.pages.flatMap(p => p.regions);
    state.result.statistics.needs_review = regions.filter(r => r.needs_review).length;
    state.result.statistics.translated = regions.filter(r => r.enabled && r.translation).length;
    $("review-count").textContent = state.result.statistics.needs_review;
    $("translated-count").textContent = state.result.statistics.translated;
    $("edit-warning").textContent = "已保存并标为已复核"; renderRegions(); updatePreview(); notify("译文已保存" + ($("save-term").checked ? "，已加入个人术语库" : ""));
  } catch (error) {notify(error.message, true);} finally {$("save-button").disabled = false;}
}
function zoom(value) {
  state.zoom = Math.max(50, Math.min(350, value)); $("zoom-label").textContent = `${state.zoom}%`;
  document.querySelectorAll(".paper").forEach(node => {node.style.width = `${state.zoom}%`; node.style.minWidth = `${state.zoom}%`;});
}
async function poll() {
  if (polling) return; polling = true;
  try {
    for (const job of state.jobs.filter(j => ["queued", "running"].includes(j.status))) {
      const fresh = await api(`/api/jobs/${job.id}`); Object.assign(job, fresh);
      if (job.id === state.active) {
        renderProgress(job);
        if (job.status === "done" && !state.result) {
          const active = state.active; const result = await api(`/api/jobs/${active}/result`);
          if (active === state.active) {state.result = result; state.page = 0; applyResult();}
        }
        if (job.status === "error") notify(job.message, true);
      }
    }
    renderJobs();
  } catch (_) {$("status-text").textContent = "连接中断，请检查应用是否仍在运行";} finally {polling = false;}
}
$("upload-button").onclick = $("empty-upload").onclick = () => $("file-input").click();
$("file-input").onchange = e => uploadFiles(e.target.files);
$("quit-button").onclick = async () => {
  try {await api("/api/shutdown", {method: "POST"}); notify("工作台已关闭，可关闭此浏览器页面。"); $("status-text").textContent = "工作台已退出"; clearInterval(pollTimer);} catch (error) {notify(error.message, true);}
};
const drop = $("drop-zone");
drop.addEventListener("keydown", e => {if (["Enter", " "].includes(e.key)) {e.preventDefault(); $("file-input").click();}});
document.body.addEventListener("dragover", e => {e.preventDefault(); drop.classList.add("dragging");});
document.body.addEventListener("dragleave", () => drop.classList.remove("dragging"));
document.body.addEventListener("drop", e => {e.preventDefault(); drop.classList.remove("dragging"); uploadFiles(e.dataTransfer.files);});
$("demo-button").onclick = async () => {
  $("demo-button").disabled = true;
  try {const job = await api("/api/demo", {method: "POST"}); state.jobs.unshift(job); await selectJob(job.id);} catch (error) {notify(error.message, true);} finally {$("demo-button").disabled = false;}
};
$("page-select").onchange = e => {state.page = +e.target.value; renderPage();};
$("prev-page").onclick = () => {if (state.page > 0) {state.page--; renderPage();}};
$("next-page").onclick = () => {if (state.page < state.result.pages.length - 1) {state.page++; renderPage();}};
document.querySelectorAll("[data-mode]").forEach(node => {node.onclick = () => {state.mode = node.dataset.mode; document.querySelectorAll("[data-mode]").forEach(n => n.classList.toggle("active", n === node)); updatePreview();};});
document.querySelectorAll("[data-filter]").forEach(node => {node.onclick = () => {state.filter = node.dataset.filter; document.querySelectorAll("[data-filter]").forEach(n => n.classList.toggle("active", n === node)); renderRegions();};});
$("search").oninput = renderRegions;
$("editor").onsubmit = saveEdit;
$("close-editor").onclick = () => {$("editor").hidden = true; $("highlight").hidden = true; state.selected = null; renderRegions();};
document.addEventListener("keydown", e => {if ((e.ctrlKey || e.metaKey) && e.key === "Enter" && !$("editor").hidden) saveEdit(e);});
$("zoom-out").onclick = () => zoom(state.zoom - 25); $("zoom-in").onclick = () => zoom(state.zoom + 25); $("zoom-fit").onclick = () => zoom(100);
$("cancel-button").onclick = async () => {try {await api(`/api/jobs/${state.active}/cancel`, {method: "POST"}); notify("已请求取消，当前 OCR 步骤结束后停止");} catch (error) {notify(error.message, true);}};
$("export-button").onclick = async () => {
  $("export-button").disabled = true; $("status-text").textContent = "正在生成原尺寸图纸、坐标 JSON 和 CSV…";
  try {
    const data = await api(`/api/jobs/${state.active}/export?mode=${state.mode}`, {method: "POST"});
    const link = document.createElement("a"); link.href = data.url; link.download = "图译_翻译结果.zip"; document.body.append(link); link.click(); link.remove();
    notify(data.report.omitted_annotations ? `已导出。有 ${data.report.omitted_annotations} 条译文因空间不足保留在 JSON / CSV 中，请检查导出报告。` : "已导出图纸、坐标 JSON 和 CSV。");
    $("status-text").textContent = `导出完成 · ${state.mode === "beside" ? "不遮挡模式" : "遮挡模式"} · ${data.report.omitted_annotations} 条未放置标注`;
  } catch (error) {notify(error.message, true);} finally {$("export-button").disabled = false;}
};
$("original-image").onerror = () => {$("status-text").textContent = "原图预览未能加载，请检查任务记录";};
$("translated-image").onerror = () => {if (state.result) {$("status-text").textContent = "译文预览未能生成，请检查结果或重新导出";}};
(async () => {
  try {
    const health = await api("/api/health"); $("model-status").textContent = health.model_installed ? "OCR + 英中翻译模型已就绪" : "仅术语库模式 · 通用模型未安装";
    state.jobs = await api("/api/jobs"); renderJobs();
    if (state.jobs.length) await selectJob(state.jobs[0].id);
  } catch (error) {notify(error.message, true);}
})();
const pollTimer = setInterval(poll, 1500);
