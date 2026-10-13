"""Double-click / portable entry point. Startup failures are readable in startup.log."""

import os
import sys
from pathlib import Path

root = Path(__file__).resolve().parent
sys.path.insert(0, str(root / "src"))
os.chdir(root)
# pythonw has no terminal streams; preserve diagnostics on Windows, never hide errors.
if sys.stdout is None or sys.stderr is None:
    stream = (root / "startup.log").open("a", encoding="utf-8", buffering=1)
    sys.stdout = stream
    sys.stderr = stream

if __name__ == "__main__":
    from drawing_translator.launcher import main
    main()
