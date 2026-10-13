"""Compare actual OCR + translation output with editable human gold evidence.

OCR recall, translation accuracy among detected terms, and joint pass rate have
different denominators. Missing OCR is never silently removed from the joint score.
Full owner-supplied acceptance sets should contain every annotated expected region.
"""

import argparse
import json
import platform
from pathlib import Path

from drawing_translator.glossary import normalize
from drawing_translator.pipeline import Pipeline
from drawing_translator.extraction import overlap

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--gold", type=Path, default=ROOT / "tests/golden_terms.json")
    parser.add_argument("--images", type=Path, default=ROOT / "tests/fixtures")
    parser.add_argument("--quality", choices=("fast", "accurate"), default="accurate")
    parser.add_argument("--output", type=Path, default=ROOT / "outputs/参考答案验证.json")
    args = parser.parse_args()
    gold = json.loads(args.gold.read_text("utf-8"))
    pipeline = Pipeline()
    processed, cases = {}, []
    for name in dict.fromkeys(c["image"] for c in gold["cases"]):
        print("识别参考原图", name, flush=True)
        processed[name] = pipeline.run(args.images / name, args.quality, cache=False)
    for case in gold["cases"]:
        regions = [r for p in processed[case["image"]]["pages"] for r in p["regions"]]
        candidates = [r for r in regions if normalize(case["source"]) in normalize(r["source"])]
        # Optional expected pixel boxes let a full acceptance set check localization.
        if case.get("bbox"):
            candidates = [r for r in candidates if overlap(r["bbox"], case["bbox"]) >= .5]
        correct = any(any(normalize(a) in normalize(r["translation"]) for a in case["accepted"]) for r in candidates)
        cases.append({**case, "detected": bool(candidates), "translation_correct": correct, "actual": [{"source": r["source"], "translation": r["translation"], "bbox": r["bbox"]} for r in candidates]})
    detected = sum(c["detected"] for c in cases)
    correct = sum(c["translation_correct"] for c in cases)
    report = {"scope": gold["description"], "machine": platform.platform(), "quality": args.quality,
              "expected": len(cases), "detected": detected, "correct": correct,
              "ocr_recall": detected / len(cases), "translation_accuracy_given_detection": correct / max(1, detected),
              "joint_pass_rate": correct / len(cases),
              "times": {n: r["elapsed_seconds"] for n, r in processed.items()}, "cases": cases}
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), "utf-8")
    print({k: v for k, v in report.items() if k != "cases"})


if __name__ == "__main__":
    main()
