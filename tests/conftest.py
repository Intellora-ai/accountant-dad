"""Put the CI tooling on the import path.

Mirrors what `merge.yml` does with `PYTHONPATH: tools/ci`, so the tests exercise
the modules exactly as CI imports them rather than through a different path.
"""

import sys
from pathlib import Path

TOOLS_CI = Path(__file__).resolve().parent.parent / "tools" / "ci"
if str(TOOLS_CI) not in sys.path:
    sys.path.insert(0, str(TOOLS_CI))
