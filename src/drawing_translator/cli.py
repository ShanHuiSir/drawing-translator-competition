"""Batch interface for judge scripts, repeatable measurements and offline export."""

import argparse
import json
from pathlib import Path

from .extraction import SUPPORTED
from .exporting import export_result, write_metadata
from .pipeline import Pipeline


def main():
    """
    Use the same pipeline as the workbench, without browser automation.
    A directory input selects supported drawing files and ignores other extensions.
    Documents are handled sequentially to bound memory and CPU contention.
    The both mode exports two red-annotation alternatives plus coordinate metadata.
    The no-cache flag is required for cold-run acceptance measurements.
    One failed file is recorded while later files still get a processing attempt.
    The final nonzero exit code signals any recorded document failure.
    The JSON summary gives measured timings, review counts and exact source names.
    """
    parser = argparse.ArgumentParser(description="机械图纸 OCR 与离线翻译")
    parser.add_argument("input", type=Path)
    parser.add_argument("--output", type=Path, default=Path("outputs/batch"))
    parser.add_argument("--quality", choices=("fast", "accurate"), default="fast")
    parser.add_argument("--mode", choices=("beside", "cover", "both", "json"), default="both")
    parser.add_argument("--pages", help="1,2,5；不指定则处理全部页")
    parser.add_argument("--no-cache", action="store_true", help="验收计时必须关闭缓存")
    args = parser.parse_args()
    pages = [int(x) - 1 for x in args.pages.split(",")] if args.pages else None
    files = sorted(p for p in args.input.iterdir() if p.suffix.lower() in SUPPORTED) if args.input.is_dir() else [args.input]
    args.output.mkdir(parents=True, exist_ok=True)
    pipeline = Pipeline()
    summary = []
    for source in files:
        print(f"\n处理：{source.name}", flush=True)
        try:
            result = pipeline.run(source, args.quality, pages, lambda done, total, msg: print(f"[{done}/{total}] {msg}", flush=True), cache=not args.no_cache)
            directory = args.output / source.stem
            directory.mkdir(parents=True, exist_ok=True)
            write_metadata(result, directory / "识别与翻译.json")
            for mode in (["beside", "cover"] if args.mode == "both" else [args.mode]):
                if mode != "json":
                    _, report = export_result(source, result, directory, mode)
                    print(f"{mode}: 未放置标注 {report['omitted_annotations']}", flush=True)
            summary.append({"file": source.name, "status": "done", "elapsed": result["elapsed_seconds"], **result["statistics"]})
        except Exception as error:
            print(f"失败：{error}", flush=True)
            summary.append({"file": source.name, "status": "error", "error": str(error)})
    (args.output / "批量处理报告.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), "utf-8")
    if any(x["status"] == "error" for x in summary):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
