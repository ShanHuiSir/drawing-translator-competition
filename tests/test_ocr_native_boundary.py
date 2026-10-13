"""Subprocess regression for the actual native resize crash, not a Python exception."""

import os
import subprocess
import sys
from pathlib import Path


def test_enhanced_real_small_drawing_does_not_native_crash(tmp_path):
    root = Path(__file__).resolve().parents[1]
    script = """
from drawing_translator.extraction import Drawing, Extractor
with Drawing('tests/fixtures/reference_1.png') as drawing:
    page = Extractor().extract(drawing, 0, 'accurate')
    assert any('GROOVE' in r.source for r in page.regions), 'Expected real drawing text'
    print('REGRESSION_OK', len(page.regions))
"""
    env = dict(os.environ, DRAWING_DATA_DIR=str(tmp_path))
    result = subprocess.run([sys.executable, "-X", "faulthandler", "-c", script], cwd=root,
                            env=env, capture_output=True, text=True, timeout=60)
    assert result.returncode == 0, f"Native OCR exited {result.returncode}: {result.stderr[-3000:]}"
    assert "REGRESSION_OK" in result.stdout
