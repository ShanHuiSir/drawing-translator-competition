"""Long-duration stability runner. Do not report 72h success before it finishes.

Each iteration reopens the supplied drawing and disables extraction cache.
The journal captures failures and RSS evidence, including the exact process ID.
Use the final journal on Windows for the task's specified 72-hour acceptance.
"""

import argparse
import json
import os
import time
from datetime import datetime
from pathlib import Path

from drawing_translator.pipeline import Pipeline


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("drawing", type=Path)
    parser.add_argument("--hours", type=float, default=72)
    parser.add_argument("--journal", type=Path, default=Path("outputs/soak.jsonl"))
    args = parser.parse_args()
    try:
        import psutil
    except ImportError:
        raise SystemExit("请先安装 psutil：python -m pip install psutil")
    args.journal.parent.mkdir(parents=True, exist_ok=True)
    pipeline = Pipeline(); process = psutil.Process(); start = time.monotonic(); iteration = 0
    while time.monotonic() - start < args.hours * 3600:
        iteration += 1
        try:
            result = pipeline.run(args.drawing, pages=[0], cache=False)
            entry = {"status": "ok", "elapsed": result["elapsed_seconds"], "regions": result["statistics"]["text_regions"]}
        except Exception as error:
            entry = {"status": "error", "error": str(error)}
        entry.update(time=datetime.now().astimezone().isoformat(), iteration=iteration, pid=os.getpid(), runtime_seconds=time.monotonic() - start, rss_bytes=process.memory_info().rss)
        with args.journal.open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        print(entry, flush=True)
    with args.journal.open("a", encoding="utf-8") as f:
        f.write(json.dumps({"status": "finished", "hours": args.hours, "iterations": iteration}) + "\n")


if __name__ == "__main__":
    main()
