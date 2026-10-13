"""Restore versioned model weights and competition samples for a Git clone.

Network access is confined to this explicit setup command. The application itself
does not download models or transmit drawing content. A fixed archive digest makes
the release source bundle the same resource snapshot used in the delivery tests.
"""

import argparse
import hashlib
import shutil
import tempfile
import urllib.parse
import urllib.request
import zipfile
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parents[1]
URL = "https://github.com/ShanHuiSir/drawing-translator-competition/releases/download/v1.0.0/"
ASSET = "图译_源码及模型.zip"
SHA256 = "2b633d59c2418edd6404bae587d7a1c807314b7094a5755ac28790fb61c8e63a"


def restore(archive):
    """Verify the complete container before writing any resource from it."""
    digest = hashlib.sha256()
    with archive.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    if digest.hexdigest() != SHA256:
        raise ValueError("源码及模型包 SHA-256 不符；请使用 v1.0.0 原始发行包")
    count = 0
    with zipfile.ZipFile(archive) as bundle:
        for item in bundle.infolist():
            parts = PurePosixPath(item.filename).parts
            if item.is_dir() or len(parts) < 3:
                continue
            if parts[0] != "图译源码" or parts[1] not in ("models", "inputs"):
                continue
            if any(p in ("..", ".") or "\\" in p for p in parts):
                raise ValueError("发行包包含非法资源路径")
            destination = ROOT.joinpath(*parts[1:])
            if not destination.resolve().is_relative_to(ROOT.resolve()):
                raise ValueError("资源路径超出项目目录")
            destination.parent.mkdir(parents=True, exist_ok=True)
            with bundle.open(item) as source, destination.open("wb") as target:
                shutil.copyfileobj(source, target)
            count += 1
    if not count:
        raise ValueError("发行包中没有可恢复的模型或输入样例")
    print(f"校验通过，已恢复 {count} 个资源文件到 {ROOT}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", type=Path, help="使用已下载的源码及模型 ZIP，不联网")
    args = parser.parse_args()
    if args.archive:
        restore(args.archive)
        return
    with tempfile.TemporaryDirectory(prefix="drawing-assets-") as temporary:
        archive = Path(temporary) / "source-models.zip"
        request = urllib.request.Request(URL + urllib.parse.quote(ASSET),
                                         headers={"User-Agent": "drawing-translator-setup/1.0"})
        print("正在下载 v1.0.0 模型和样例；应用运行阶段不需要网络……", flush=True)
        with urllib.request.urlopen(request, timeout=120) as source, archive.open("wb") as target:
            shutil.copyfileobj(source, target)
        restore(archive)


if __name__ == "__main__":
    main()
