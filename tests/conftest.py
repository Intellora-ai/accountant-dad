"""Put the CI tooling and the repo root on the import path.

Mirrors what `merge.yml` does with `PYTHONPATH: tools/ci`, so the tests exercise
the modules exactly as CI imports them rather than through a different path.

The repo root is added for `tools.evidence`, the citation verifier. It goes here
rather than in `pyproject.toml`'s `pythonpath`, which is pinned by
`test_mutation_measures_the_real_tree.py` — that pin is load-bearing, because
under mutation pytest resolves `type="paths"` options against the INI FILE's
directory, and those two entries are what make the INSTRUMENTED copies the thing
being scored. Adding a third entry there broke the guard; the guard was right.

This mechanism cannot reintroduce that bug: `[tool.mutmut] paths_to_mutate` is
`["src"]`, so nothing under `tools/` is ever mutated and no scoring decision
depends on which copy of it is imported.
"""

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
TOOLS_CI = REPO_ROOT / "tools" / "ci"
for entry in (TOOLS_CI, REPO_ROOT):
    if str(entry) not in sys.path:
        sys.path.insert(0, str(entry))
