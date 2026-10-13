"""Build on any host using official CPython + binary Windows wheels.

This is a download/assembly step, not a Windows runtime test. The final app has
no setup dependency and performs no downloads. Run a Windows smoke test separately.
"""

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
import urllib.request
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PYTHON_URL = "https://www.python.org/ftp/python/3.12.10/python-3.12.10-embed-amd64.zip"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--assemble-only", action="store_true")
    parser.add_argument("--pip-python", default=sys.executable)
    args = parser.parse_args()
    build = ROOT / "build/windows"
    downloads = build / "downloads"
    downloads.mkdir(parents=True, exist_ok=True)
    python_zip = downloads / "python-3.12.10-embed-amd64.zip"
    if not args.assemble_only:
        if not python_zip.exists():
            with urllib.request.urlopen(PYTHON_URL, timeout=120) as response:
                python_zip.write_bytes(response.read())
        subprocess.run([args.pip_python, "-m", "pip", "download", "--disable-pip-version-check", "--no-cache-dir",
                        "--platform", "win_amd64", "--python-version", "312", "--implementation", "cp",
                        "--abi", "cp312", "--only-binary=:all:", "--dest", str(downloads), "-r", str(ROOT / "requirements.txt")], check=True)
    bundle = ROOT / "dist/图译_Windows免安装版"
    if bundle.exists():
        shutil.rmtree(bundle)
    (bundle / "python/Lib/site-packages").mkdir(parents=True)
    with zipfile.ZipFile(python_zip) as z:
        z.extractall(bundle / "python")
    manifest = {"python": {"url": PYTHON_URL, "sha256": hashlib.sha256(python_zip.read_bytes()).hexdigest()}, "wheels": []}
    from packaging.utils import canonicalize_name, parse_wheel_filename
    pinned = {}
    for line in (ROOT / "requirements.txt").read_text().splitlines():
        if "==" in line:
            name, version = line.split("==", 1)
            pinned[canonicalize_name(name)] = version
    for wheel in sorted(downloads.glob("*.whl")):
        name, version, _, _ = parse_wheel_filename(wheel.name)
        if name in pinned and str(version) != pinned[name]:
            continue
        with zipfile.ZipFile(wheel) as z:
            z.extractall(bundle / "python/Lib/site-packages")
        manifest["wheels"].append({"file": wheel.name, "sha256": hashlib.sha256(wheel.read_bytes()).hexdigest()})
    # Isolated embedded Python ignores PYTHONPATH. All entries are bundle-relative.
    (bundle / "python/python312._pth").write_text("python312.zip\n.\nLib/site-packages\n../src\nimport site\n", "utf-8")
    shutil.copytree(ROOT / "src", bundle / "src", ignore=shutil.ignore_patterns("__pycache__", "*.egg-info"))
    shutil.copytree(ROOT / "models/translate-en_zh-1_9", bundle / "models/translate-en_zh-1_9", ignore=shutil.ignore_patterns("stanza"))
    shutil.copytree(ROOT / "models/ocr", bundle / "models/ocr")
    shutil.copy2(ROOT / "models/source.json", bundle / "models/source.json")
    for file in ["run_app.py", "启动图译.bat", "README.md", "THIRD_PARTY_NOTICES.md", "LICENSE"]:
        if (ROOT / file).exists():
            shutil.copy2(ROOT / file, bundle / file)
    shutil.copytree(ROOT / "scripts", bundle / "scripts", ignore=shutil.ignore_patterns("__pycache__"))
    for file in ["pyproject.toml", "requirements.txt"]:
        shutil.copy2(ROOT / file, bundle / file)
    if (ROOT / "build/图译.exe").exists():
        shutil.copy2(ROOT / "build/图译.exe", bundle / "图译.exe")
    (bundle / "构建清单.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), "utf-8")
    print(bundle)


if __name__ == "__main__":
    main()
