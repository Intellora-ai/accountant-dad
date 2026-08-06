"""F-024 — a name is imported everywhere and defined nowhere.

THE DEFECT. `e921c3c` designed `Exclusion` and shipped everything around it:
the module docstring explains it at `conformance.py:100`, the `Uncovered` enum
that gives it its reasons is defined at `:148`, `Registry` accepts it at `:422`
and `test_conformance_registry.py:74` imports it. **The dataclass itself was
never written.** The suite could not collect:

    ImportError: cannot import name 'Exclusion' from 'accountant_dad.conformance'
    !!!! Interrupted: 1 error during collection !!!!
    1 error in 10.71s

WHY THAT IS WORSE THAN A RED TEST. A collection error is not one failure — it
is ZERO results. Every other number measured at that commit had to be taken
with the file excluded, and every gate downstream of `unit tests` had nothing
to judge. Law 1 is *keep the repo buildable always*, and the repository was not.

WHY NO GATE SAW IT COMING. Four separate things referred to `Exclusion` and not
one of them was an executable claim that it exists. A docstring cannot be
wrong. An enum member is not a reference. A type annotation under `from
__future__ import annotations` is a string that nothing resolves. Only the
import was load-bearing, and an import is checked by RUNNING it — which is the
thing that had stopped working.

THE TRANSFORM (Law 53). *"Does the suite collect?"* can only be answered by
collecting, and when the answer is no the report is one line naming one file.
*"Does every first-party imported name have a definition?"* is a question about
TEXT: parse every module, collect what each binds at module scope, and check
every `from accountant_dad… import X` against it. It answers in milliseconds,
names every offender at once instead of the first, and — the part collection
can never do — it also catches a name that is unresolved in a module no test
imports yet.
"""

from __future__ import annotations

import ast

import first_party
import pytest
import unresolved_symbols

# The real `conformance.py` at `e921c3c`, reduced to the four things that were
# present, with the one thing that was absent still absent. Written out rather
# than fetched from git so the reproduction keeps working in a checkout with no
# history (and so it states, in the file, what the shape of the bug was).
CONFORMANCE_AS_SHIPPED = '''\
"""...an omission is silent and the suite is green. `Exclusion` is the fix..."""

from __future__ import annotations

import enum
from dataclasses import dataclass


class Uncovered(enum.Enum):
    NOT_A_PROHIBITION = "not_a_prohibition"
    RESTATEMENT = "restatement"
    UNWITNESSABLE = "unwitnessable"


@dataclass(frozen=True)
class Prohibition:
    source: str
'''

REGISTRY_TEST_AS_SHIPPED = """\
from accountant_dad.conformance import Exclusion, Prohibition, Uncovered
"""


def _table(**modules: str) -> tuple[dict[str, frozenset[str]], frozenset[str]]:
    """A symbol table built from source text, the shape the real scan builds."""
    trees = {name: ast.parse(text) for name, text in modules.items()}
    defined = {name: first_party.defined_names(t) for name, t in trees.items()}
    return defined, frozenset(trees)


# ═══════════════════════════════════════════════════════════════════════════
# The regression. This is the import that produced `1 error in 10.71s`.
# ═══════════════════════════════════════════════════════════════════════════


def test_the_collection_failure_does_not_recur() -> None:
    """`Exclusion` is imported, and nothing in `conformance` defines it."""
    defined, known = _table(**{"accountant_dad.conformance": CONFORMANCE_AS_SHIPPED})

    findings = unresolved_symbols.unresolved(
        ast.parse(REGISTRY_TEST_AS_SHIPPED),
        "tests/unit/test_conformance_registry.py",
        "accountant_dad",
        defined,
        known,
    )

    assert [f.name for f in findings] == ["Exclusion"], (
        f"the scan must name Exclusion and nothing else; got {findings}"
    )
    assert findings[0].module == "accountant_dad.conformance"
    assert findings[0].line == 1
    assert "Exclusion" in str(findings[0])


def test_the_names_that_did_exist_are_not_reported() -> None:
    """FALSE-POSITIVE GUARD. `Prohibition` and `Uncovered` were both real.

    A scan that flagged them too would have been noise on the day it shipped,
    and noise is what gets a gate deleted.
    """
    defined, known = _table(**{"accountant_dad.conformance": CONFORMANCE_AS_SHIPPED})
    findings = unresolved_symbols.unresolved(
        ast.parse("from accountant_dad.conformance import Prohibition, Uncovered\n"),
        "x.py",
        "accountant_dad",
        defined,
        known,
    )
    assert findings == ()


# ═══════════════════════════════════════════════════════════════════════════
# The real tree.
# ═══════════════════════════════════════════════════════════════════════════


def test_every_first_party_import_in_this_repository_resolves() -> None:
    """THE DETECTOR, on `src/`, `tests/` and `tools/ci/`.

    Goes red naming file, line, module and symbol the moment a name is imported
    that nothing defines — including in a module no test imports, which is the
    case collection can never reach.
    """
    findings = unresolved_symbols.unresolved_first_party_imports()
    assert findings == (), "imported name(s) that nothing defines:\n  " + "\n  ".join(
        str(finding) for finding in findings
    )


def test_every_name_a_module_exports_is_a_name_it_defines() -> None:
    """`__all__` is a promise about attributes. An entry with no definition is
    an `AttributeError` for `from x import *` and a lie to every reader.
    """
    findings = unresolved_symbols.undefined_exports()
    assert findings == (), "__all__ entr(ies) with no definition:\n  " + "\n  ".join(
        str(finding) for finding in findings
    )


def test_the_scan_actually_reads_the_repository() -> None:
    """HOLLOW-GATE DEFENCE. A scan over nothing returns `()` and passes.

    Pins that the walk finds the real package, real tests, and a known-real
    symbol — so an empty result means "all resolved", never "nothing looked at".
    """
    defined, known = unresolved_symbols.repository_symbol_table()
    assert "accountant_dad.conformance" in known
    assert "Exclusion" in defined["accountant_dad.conformance"], (
        "Exclusion is expected to EXIST on this tree; F-024 was fixed after e921c3c"
    )
    assert (
        len(unresolved_symbols.scanned_files()) >= unresolved_symbols.FEWEST_FILES_THAT_CAN_BE_REAL
    )


# ═══════════════════════════════════════════════════════════════════════════
# The scan, attacked.
# ═══════════════════════════════════════════════════════════════════════════


def test_importing_from_a_module_that_does_not_exist_is_reported() -> None:
    """The other half of F-024: not a missing NAME but a missing MODULE."""
    defined, known = _table(**{"accountant_dad.real": "value = 1\n"})
    findings = unresolved_symbols.unresolved(
        ast.parse("from accountant_dad.imaginary import thing\n"),
        "x.py",
        "accountant_dad",
        defined,
        known,
    )
    assert len(findings) == 1
    assert findings[0].module == "accountant_dad.imaginary"
    assert "no such module" in findings[0].reason


def test_a_submodule_is_a_resolvable_name() -> None:
    """`from accountant_dad.engines import input_engine` imports a MODULE, and
    a module is not bound in its parent's source. Treating only module-scope
    assignments as definitions would flag every package import in the repo.
    """
    defined, known = _table(
        **{
            "accountant_dad.engines": "",
            "accountant_dad.engines.input_engine": "",
        }
    )
    findings = unresolved_symbols.unresolved(
        ast.parse("from accountant_dad.engines import input_engine\n"),
        "x.py",
        "accountant_dad",
        defined,
        known,
    )
    assert findings == ()


def test_a_re_exported_name_resolves() -> None:
    """A module that imports a name binds it, and `from that import name`
    is legal. Refusing it would flag every façade module in the package.
    """
    defined, known = _table(
        **{
            "accountant_dad.deep": "class Thing:\n    pass\n",
            "accountant_dad.facade": "from accountant_dad.deep import Thing\n",
        }
    )
    findings = unresolved_symbols.unresolved(
        ast.parse("from accountant_dad.facade import Thing\n"),
        "x.py",
        "accountant_dad",
        defined,
        known,
    )
    assert findings == ()


def test_a_name_bound_only_inside_a_function_does_not_count() -> None:
    """THE EXACT SHAPE OF F-024. A local binding is invisible to an importer.

    This is the false-NEGATIVE direction: counting it would let the next
    `Exclusion` through, because the name would appear "defined" to the scan
    and still raise ImportError at runtime.
    """
    defined, known = _table(
        **{"accountant_dad.m": "def build() -> None:\n    Exclusion = 1\n    del Exclusion\n"}
    )
    findings = unresolved_symbols.unresolved(
        ast.parse("from accountant_dad.m import Exclusion\n"),
        "x.py",
        "accountant_dad",
        defined,
        known,
    )
    assert [f.name for f in findings] == ["Exclusion"]


def test_a_name_bound_under_type_checking_does_count() -> None:
    """`if TYPE_CHECKING:` binds at module scope for type purposes and is a
    legitimate re-export. Flagging it would be a false alarm.
    """
    defined, known = _table(
        **{
            "accountant_dad.t": (
                "from typing import TYPE_CHECKING\n"
                "if TYPE_CHECKING:\n"
                "    from accountant_dad.other import Shape\n"
            ),
            "accountant_dad.other": "class Shape:\n    pass\n",
        }
    )
    findings = unresolved_symbols.unresolved(
        ast.parse("from accountant_dad.t import Shape\n"),
        "x.py",
        "accountant_dad",
        defined,
        known,
    )
    assert findings == ()


def test_a_third_party_import_is_never_examined() -> None:
    """`from pydantic import BaseModel` is not this repository's promise."""
    defined, known = _table(**{"accountant_dad.m": ""})
    findings = unresolved_symbols.unresolved(
        ast.parse("from pydantic import BaseModel\nimport numpy\n"),
        "x.py",
        "accountant_dad",
        defined,
        known,
    )
    assert findings == ()


def test_a_star_import_is_not_reported_as_a_missing_name() -> None:
    """`*` names nothing in particular, so there is nothing to fail to find."""
    defined, known = _table(**{"accountant_dad.m": "x = 1\n"})
    findings = unresolved_symbols.unresolved(
        ast.parse("from accountant_dad.m import *\n"),
        "x.py",
        "accountant_dad",
        defined,
        known,
    )
    assert findings == ()


def test_an_unparseable_module_fails_loudly_rather_than_reporting_no_symbols() -> None:
    """A module that cannot be parsed cannot be imported either — the same
    failure one step earlier. Swallowing the SyntaxError would report it as a
    module defining nothing, and then flag every name imported from it as
    missing: a true failure disguised as a hundred false ones.
    """
    with pytest.raises(SyntaxError):
        first_party.parse_text("def broken(:\n", "broken.py")


def test_an_undefined_export_is_reported_and_a_defined_one_is_not() -> None:
    """Both directions of the `__all__` check, so returning the whole list
    cannot pass by accident.
    """
    tree = ast.parse('__all__ = ["real", "ghost"]\n\ndef real() -> None:\n    pass\n')
    findings = unresolved_symbols.undefined_in_all(tree, "m.py", "accountant_dad.m")
    assert [f.name for f in findings] == ["ghost"]
