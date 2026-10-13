"""Assemble reviewable delivery artifacts and verify the finished ZIP containers.

Only explicitly listed project directories are included in source delivery.
Local caches, editor records, virtual environments and developer download caches
are deliberately excluded. Model weights and original sample inputs are included.
"""

import hashlib
import json
import shutil
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT.parent / "图译交付材料"


def add_tree(archive, directory, prefix):
    for path in sorted(directory.rglob("*")):
        if not path.is_file() or "__pycache__" in path.parts or any(p.endswith(".egg-info") for p in path.parts):
            continue
        if "stanza" in path.parts or path.suffix in (".argosmodel", ".pyc", ".DS_Store"):
            continue
        archive.write(path, str(Path(prefix) / path.relative_to(directory)))


def main():
    OUT.mkdir(exist_ok=True)
    for name in ["使用手册.md", "技术方案.md", "参赛演示稿.md"]:
        shutil.copy2(ROOT / "docs" / name, OUT / name)
    evidence = OUT / "测试证据"
    evidence.mkdir(exist_ok=True)
    for name in ["pytest-final.log", "参考答案验证.json", "单页独立计时.json", "源码注释统计.json", "导出保真验证.json", "短时稳定性.jsonl"]:
        shutil.copy2(ROOT / "outputs" / name, evidence / name)
    shutil.copy2(ROOT / "outputs/最终样例结果/批量处理报告.json", evidence / "批量处理报告.json")
    shutil.copy2(ROOT / "dist/图译_Windows免安装版/构建清单.json", evidence / "Windows构建清单.json")
    (OUT / "先读我.txt").write_text(
        "图译 / 英文零件图纸术语自动翻译\n\n"
        "1. 完整解压 图译_Windows免安装版.zip，然后双击 图译.exe。\n"
        "2. 源码与模型、测试、原始输入样例见 图译_源码及模型.zip。\n"
        "3. 六份 139 页图纸的两种译文模式见 图译_139页样例结果.zip。\n"
        "4. 功能、计时与验收边界见 图译_交付说明与实测报告.pdf。\n\n"
        "已实测：23 项功能测试、参考答案 20 个重点术语点、六份 PDF 首页无缓存计时。\n"
        "未完成的正式验收：Windows 10/11 真机、甲方 50 份完整金标、指定硬件所有图纸性能、72 小时连续稳定性。\n"
        "不要把重点术语通过率当作全文专业准确率。运行时不上传图纸，不使用外部 API。\n", "utf-8")
    artifacts = []
    portable = OUT / "图译_Windows免安装版.zip"
    with zipfile.ZipFile(portable, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as z:
        add_tree(z, ROOT / "dist/图译_Windows免安装版", "图译_Windows免安装版")
    artifacts.append(portable)
    source = OUT / "图译_源码及模型.zip"
    with zipfile.ZipFile(source, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as z:
        for directory in ["src", "models", "scripts", "docs", "tests", "inputs"]:
            add_tree(z, ROOT / directory, "图译源码/" + directory)
        for name in ["pyproject.toml", "requirements.txt", "README.md", "LICENSE", "THIRD_PARTY_NOTICES.md", "run_app.py", "启动图译.bat", "启动图译.command"]:
            z.write(ROOT / name, "图译源码/" + name)
    artifacts.append(source)
    sample = OUT / "图译_139页样例结果.zip"
    with zipfile.ZipFile(sample, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as z:
        add_tree(z, ROOT / "outputs/最终样例结果", "139页样例结果")
    artifacts.append(sample)
    for path in artifacts:
        with zipfile.ZipFile(path) as z:
            assert z.testzip() is None, path
        print(path.name, path.stat().st_size, flush=True)
    manifest = []
    for path in sorted(OUT.rglob("*")):
        if path.is_file() and path.name not in ("交付清单.json", "图译_比赛交付总包.zip"):
            manifest.append({"file": str(path.relative_to(OUT)), "bytes": path.stat().st_size,
                             "sha256": hashlib.sha256(path.read_bytes()).hexdigest()})
    (OUT / "交付清单.json").write_text(json.dumps({"date": "2026-10-13", "items": manifest}, ensure_ascii=False, indent=2), "utf-8")
    combined = OUT / "图译_比赛交付总包.zip"
    with zipfile.ZipFile(combined, "w", zipfile.ZIP_STORED) as z:
        for path in sorted(OUT.rglob("*")):
            if path.is_file() and path != combined:
                z.write(path, "图译交付材料/" + str(path.relative_to(OUT)))
    with zipfile.ZipFile(combined) as z:
        assert z.testzip() is None
    print(combined, combined.stat().st_size, flush=True)


if __name__ == "__main__":
    main()
