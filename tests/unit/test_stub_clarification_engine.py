"""The Engine 4 P3 stub emits a valid artifact and fabricates nothing. Prove BOTH.

Validity alone is trivially provable and almost worthless here: a stub that
composed a plausible accounting question would pass every structural check and
be **indistinguishable at the seam from real judgement**, which is the failure
`MVP_IMPLEMENTATION_BLUEPRINT.md:136` forbids by permitting no accuracy claim at
P3, and `CLAUDE.md` Law 24 forbids outright.

So the tests below are built to BREAK the module, not to watch it pass. The
three that carry the weight:

  content-blindness   Two Accounting Decisions sharing an identity and agreeing
                      on nothing else must produce EQUAL Requests. A stub that
                      echoed `unresolved_doubts` into `missing_information`
                      would look exactly like working detection; this is what
                      makes "no detection happened" an assertion rather than a
                      comment.

  the sentinel        A string that appears nowhere but inside the decision's
                      prose must appear nowhere in the serialised Request. It
                      traps the partial echo that content-blindness alone would
                      miss if two decisions happened to echo equally.

  the import graph    `AL-INV-5` — engines never call each other; checked by
                      *"no engine module imports another engine."* `AL-INV-4` —
                      no engine reads workflow state; checked by *"no engine
                      module imports the state store."* Parsed off the source,
                      so the check does not depend on import order or on a
                      reviewer noticing.

MUTATION-PROVEN, NOT ASSUMED (§J.5). Ten deliberate breaks were applied to
`stub.py` and each was caught by the test named beside it. A green suite proves
nothing until the suite has been shown able to go red:

    echo `unresolved_doubts` into `missing_information`   content-blindness (4)
    compose a plausible accounting question               the stated constant (3)
    status `Created` -> `Open`                            the status test
    priority `High` -> `Low`                              the priority test
    confidence 0.0000 -> 0.5000                           the confidence test
    mint the artifact id instead of using the injected    determinism (4)
    mint a fresh Transaction ID                           transaction-id (4)
    hardcode `related_artifact_version` to 1              the version tests (4)
    name the decision's UUID in `affected_decision`       INV-9 prose (3)
    `from accountant_dad.services import state`           the import graph

Every fixed value the stub emits is asserted against the specification line that
fixes it, never against "whatever it returned": `ENGINE_4:499` (why a Request
exists at all), `:529` (unknown priority), `:593` (what confidence measures),
`:214` (why the status is not `Open`). A test that only pinned today's output
would ratify a wrong value as readily as a right one.

Schema-level guarantees — `extra="forbid"`, frozenness, the state machine — are
already proven in `test_clarification.py` and are deliberately not repeated here
(Law 14). These tests are about the STUB.
"""

from __future__ import annotations

import ast
import re
import uuid
from decimal import Decimal

import pytest
from authored_source import authored_source

from accountant_dad.artifacts.clarification import (
    ClarificationPriority,
    ClarificationRequest,
    ClarificationStatus,
)
from accountant_dad.artifacts.decision import (
    AccountingAssumption,
    AccountingDecision,
    DecisionStatus,
    JournalLine,
    RiskIndicator,
    UnresolvedDoubt,
)
from accountant_dad.engines.clarification_engine import stub
from accountant_dad.identity import (
    FIRST_VERSION,
    ArtifactId,
    IdentityEnvelope,
    ParentVersion,
    TransactionId,
)

# ─────────────────────────────────────────────────────────────────────────────
# Builders. Fixed identifiers, so a failure is reproducible rather than a
# different UUID every run (Law 43 — every failure reproducible).
# ─────────────────────────────────────────────────────────────────────────────

DECISION_ID = ArtifactId(uuid.UUID(int=1))
TRANSACTION_ID = TransactionId(uuid.UUID(int=2))
REQUEST_ARTIFACT_ID = ArtifactId(uuid.UUID(int=3))
CLARIFICATION_ID = ArtifactId(uuid.UUID(int=4))


def _identity(
    version: int = FIRST_VERSION, transaction_id: TransactionId = TRANSACTION_ID
) -> IdentityEnvelope:
    parents = (
        ()
        if version == FIRST_VERSION
        else (ParentVersion(artifact_id=DECISION_ID, version=version - 1),)
    )
    return IdentityEnvelope(
        artifact_id=DECISION_ID,
        version=version,
        parent_versions=parents,
        transaction_id=transaction_id,
    )


def a_complete_decision(
    version: int = FIRST_VERSION, transaction_id: TransactionId = TRANSACTION_ID
) -> AccountingDecision:
    """A decision that decided everything: balanced journal, high confidence, no doubt."""
    return AccountingDecision(
        identity=_identity(version, transaction_id),
        decision_status=DecisionStatus.COMPLETE,
        accounting_treatment="Capitalise the laptop as a fixed asset",
        ledger_classification="Computers",
        debit_entries=(JournalLine(ledger="Computers", amount=Decimal("50000.00")),),
        credit_entries=(JournalLine(ledger="Bank", amount=Decimal("50000.00")),),
        journal_structure="Single debit, single credit",
        tax_treatment="Input GST credit claimed at 18%",
        accounting_assumptions=(),
        risk_indicators=(),
        decision_confidence=Decimal("0.9900"),
        supporting_reasoning="The invoice names a laptop and a bank transfer settled it",
        unresolved_doubts=(),
    )


def a_doubt_ridden_decision(
    version: int = FIRST_VERSION, sentinel: str = "unrepeatable"
) -> AccountingDecision:
    """The opposite decision in every content field, sharing only the identity.

    Empty journal, floor confidence, assumptions, risks and doubts — everything a
    stub would be tempted to read. `sentinel` is threaded through every prose
    field so a partial echo is detectable.
    """
    return AccountingDecision(
        identity=_identity(version),
        decision_status=DecisionStatus.INCOMPLETE_INFORMATION_REQUIRED,
        accounting_treatment=f"Undetermined {sentinel}",
        ledger_classification=f"Suspense {sentinel}",
        debit_entries=(),
        credit_entries=(),
        journal_structure=f"None yet {sentinel}",
        tax_treatment=f"Unknown GST rate {sentinel}",
        accounting_assumptions=(
            AccountingAssumption(assumed=f"Vendor is registered {sentinel}", why=f"No {sentinel}"),
        ),
        risk_indicators=(
            RiskIndicator(indicator=f"Missing GSTIN {sentinel}", reason=f"Illegible {sentinel}"),
        ),
        decision_confidence=Decimal("0.0000"),
        supporting_reasoning=f"Could not proceed {sentinel}",
        unresolved_doubts=(
            UnresolvedDoubt(
                missing_fact=f"The vendor GSTIN {sentinel}",
                required_clarification=f"Supply the GSTIN {sentinel}",
            ),
        ),
    )


def emit(decision: AccountingDecision) -> ClarificationRequest:
    return stub.emit_clarification_request(
        decision,
        artifact_id=REQUEST_ARTIFACT_ID,
        clarification_id=CLARIFICATION_ID,
    )


# ─────────────────────────────────────────────────────────────────────────────
# It emits — a structurally valid artifact, revalidated independently.
# ─────────────────────────────────────────────────────────────────────────────


def test_the_emitted_object_survives_a_second_independent_validation() -> None:
    """Constructing a pydantic model runs its validators, so a Request that exists
    is already valid. Re-validating the dumped payload proves the same thing the
    hard way: nothing was smuggled past construction via `model_construct`, and
    the artifact round-trips."""
    request = emit(a_complete_decision())
    revalidated = ClarificationRequest.model_validate(request.model_dump())
    assert revalidated == request


def test_every_one_of_the_twelve_components_is_populated() -> None:
    """`ENGINE_4:172-186` lists twelve. A stub that left one to a default would
    be emitting an artifact the specification does not describe."""
    request = emit(a_complete_decision())
    assert set(ClarificationRequest.model_fields) == {
        "identity",
        "clarification_id",
        "related_decision_id",
        "related_artifact_version",
        "missing_information",
        "detected_conflicts",
        "required_clarification",
        "reason_clarification_is_required",
        "affected_decision",
        "priority",
        "supporting_evidence_references",
        "clarification_confidence",
        "status",
    }
    assert set(request.model_dump(exclude_unset=True)) == set(ClarificationRequest.model_fields)


# ─────────────────────────────────────────────────────────────────────────────
# It fabricates nothing — the three load-bearing tests.
# ─────────────────────────────────────────────────────────────────────────────


def test_two_decisions_agreeing_only_on_identity_produce_equal_requests() -> None:
    """THE falsification test. If the stub read one content field, this goes red.

    Verified by mutation: adding `unresolved_doubts` to `missing_information`
    inside the stub turns this test red, and removing it turns it green again.
    """
    decided_everything = a_complete_decision()
    decided_nothing = a_doubt_ridden_decision()

    assert decided_everything != decided_nothing, "the two inputs must actually differ"
    assert emit(decided_everything) == emit(decided_nothing)


def test_no_text_from_the_decision_reaches_the_request() -> None:
    """The partial echo the equality test alone could miss.

    Two decisions echoing the *same* content would still compare equal. A
    sentinel present only inside the decision's prose closes that: it may appear
    nowhere in the serialised Request.
    """
    sentinel = "zqx-sentinel-never-emitted"
    request = emit(a_doubt_ridden_decision(sentinel=sentinel))
    assert sentinel not in str(request.model_dump())


def test_the_module_imports_no_other_engine_no_application_layer_and_no_brain() -> None:
    """`AL-INV-5` — *"no engine module imports another engine."* `AL-INV-4` —
    *"no engine module imports the state store."*

    Read off the source with `ast` rather than off `sys.modules`: an import-graph
    check that depends on what some other test happened to import already is a
    check that passes or fails by test order.
    """
    source = authored_source(stub)
    imported: set[str] = set()
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None and node.level == 0:
            imported.add(node.module)

    forbidden = sorted(
        name
        for name in imported
        if name.startswith(("accountant_dad.services", "accountant_dad.brain"))
        or (
            name.startswith("accountant_dad.engines")
            and not name.startswith("accountant_dad.engines.clarification_engine")
        )
    )
    assert forbidden == [], (
        f"AL-INV-4 / AL-INV-5 violated: {forbidden}. Every artifact passes through "
        "the Application Layer; an engine holds no other engine's address, reads no "
        "workflow state, and the Brain is advisory and reached through a contract."
    )
    # Relative imports would dodge the string check above entirely.
    assert not any(
        isinstance(node, ast.ImportFrom) and node.level > 0 for node in ast.walk(ast.parse(source))
    ), "a relative import can reach a sibling engine without naming it"


# ─────────────────────────────────────────────────────────────────────────────
# Each fixed value, against the line that fixes it.
# ─────────────────────────────────────────────────────────────────────────────


def test_the_status_is_created_and_not_one_that_asserts_something_happened() -> None:
    """`Created` is *"record created, not yet presented"*. `Open` claims delivery
    to an external actor (`ENGINE_4:262`), which `ENGINE_4:214` puts outside this
    engine — *"Engine 4 never asks users directly."* The other four assert an
    outcome or a lifecycle judgement the stub did not make."""
    request = emit(a_complete_decision())
    assert request.status is ClarificationStatus.CREATED
    assert request.status not in {
        ClarificationStatus.OPEN,
        ClarificationStatus.ANSWERED,
        ClarificationStatus.RESOLVED,
        ClarificationStatus.SUPERSEDED,
        ClarificationStatus.CANCELLED,
    }


def test_the_priority_is_the_value_the_specification_assigns_to_an_unknown_one() -> None:
    """`ENGINE_4:529` — *"Unknown priority defaults to High until sufficient
    information exists."* Asserted against the rule, not against today's output:
    the stub ran no `answer_understanding` and has no severity opinion."""
    assert stub.UNKNOWN_PRIORITY is ClarificationPriority.HIGH
    assert emit(a_complete_decision()).priority is ClarificationPriority.HIGH


def test_confidence_is_zero_and_therefore_exceeds_no_upstream_confidence() -> None:
    """`ENGINE_4:593` — confidence answers *"has every decision-blocking
    uncertainty been found?"* Nothing was sought, so the answer is zero.

    `ENGINE_4:612` — *"Clarification Confidence may never exceed upstream
    confidence."* `clarification.py` records that the schema CANNOT enforce this
    (no field carries upstream confidence), so the stub satisfies it by sitting
    at the floor, and this asserts that against the strictest upstream there is.
    """
    request = emit(a_complete_decision())
    assert request.clarification_confidence == Decimal("0.0000")
    assert isinstance(request.clarification_confidence, Decimal)

    floor = a_doubt_ridden_decision().decision_confidence
    assert floor == Decimal("0.0000")
    assert request.clarification_confidence <= floor


def test_nothing_is_reported_as_missing_and_nothing_as_conflicting() -> None:
    """`ENGINE_4:190-191` — *"what was unclear?"*, *"why did it matter?"* Nothing
    was found unclear because nothing was examined. Naming a missing fact here
    would be `ENGINE_4:231` — inventing one."""
    request = emit(a_doubt_ridden_decision())
    assert request.missing_information == ()
    assert request.detected_conflicts == ()


def test_exactly_one_evidence_reference_and_it_names_the_input() -> None:
    """`min_length=1` comes from `COMM_CLARIFICATION_INTERNAL:83-87`. With no
    finding made there is nothing for a reference to support, so the single entry
    names the input artifact — the only thing available that is not invented."""
    request = emit(a_complete_decision())
    assert request.supporting_evidence_references == (stub.THE_ONLY_HONEST_REFERENCE,)
    assert len(request.supporting_evidence_references) == 1


@pytest.mark.parametrize(
    ("field", "stated"),
    [
        ("required_clarification", stub.NO_QUESTION_WAS_COMPOSED),
        ("reason_clarification_is_required", stub.NECESSITY_WAS_NOT_DETERMINED),
        ("affected_decision", stub.AFFECTED_DECISION_WAS_NOT_ANALYSED),
    ],
)
def test_each_prose_field_is_the_stated_constant_not_a_composed_string(
    field: str, stated: str
) -> None:
    """Identity, not equality. `is` proves the field is the module constant a
    reader can go and check, so a future f-string that happened to render the
    same text would still fail. The three fields are exactly the ones a real
    `question_generator` would compose (`ENGINE_4:533-557`)."""
    value = getattr(emit(a_complete_decision()), field)
    assert value is stated


@pytest.mark.parametrize(
    ("field", "stated"),
    [
        ("required_clarification", "NO QUESTION WAS COMPOSED"),
        ("reason_clarification_is_required", "NECESSITY WAS NOT DETERMINED"),
        ("affected_decision", "was not analysed"),
    ],
)
def test_each_prose_field_says_in_words_that_no_judgement_was_made(field: str, stated: str) -> None:
    """The constants are load-bearing PROSE, read by whoever receives this
    Request. A constant renamed honestly but reworded into something that reads
    like a real question would pass the identity test above and fail here."""
    assert stated in getattr(emit(a_complete_decision()), field)


# ─────────────────────────────────────────────────────────────────────────────
# Identity — carried, never invented; and never leaked into prose.
# ─────────────────────────────────────────────────────────────────────────────


def test_the_transaction_id_follows_the_decision_and_is_neither_minted_nor_fixed() -> None:
    """INV-3/INV-4 — the Application Layer creates the Transaction ID and engines
    consume it. One business event, one Transaction ID, whole lifecycle.

    Two decisions carrying different Transaction IDs must yield Requests carrying
    each one. Asserting a single expected value would pass just as happily
    against a stub that hardcoded a constant or minted a fresh UUID.
    """
    other = TransactionId(uuid.UUID(int=99))
    assert other != TRANSACTION_ID

    assert emit(a_complete_decision()).identity.transaction_id == TRANSACTION_ID
    assert emit(a_complete_decision(transaction_id=other)).identity.transaction_id == other


def test_the_two_artifact_identifiers_are_the_injected_ones_and_stay_distinct() -> None:
    """`clarification.py` records that no document says whether the Clarification
    ID and the Artifact ID are one value or two, so nothing may bind them. A stub
    that reused one value would assert a relationship the documents never make."""
    request = emit(a_complete_decision())
    assert request.identity.artifact_id == REQUEST_ARTIFACT_ID
    assert request.clarification_id == CLARIFICATION_ID
    assert request.identity.artifact_id != request.clarification_id
    # And neither is the decision's — a new artifact gets its own identity.
    assert request.identity.artifact_id != DECISION_ID


def test_the_request_is_raised_against_the_exact_decision_and_version() -> None:
    """`ENGINE_4:196-198` — recording the version is what makes a stale request
    detectable when the decision is rebuilt."""
    a_later_version = 4
    request = emit(a_complete_decision(version=a_later_version))
    assert request.related_decision_id == DECISION_ID
    assert request.related_artifact_version == a_later_version


@pytest.mark.parametrize("version", [1, 2, 7, 1000])
def test_the_recorded_version_tracks_the_decision_across_the_range(version: int) -> None:
    """A hardcoded 1 would pass the version-4 test's sibling and be wrong
    everywhere else. Boundary included: `FIRST_VERSION` is the origin."""
    assert emit(a_complete_decision(version=version)).related_artifact_version == version


def test_the_request_is_a_first_version_carrying_no_parent() -> None:
    """It is a new artifact, not a correction, and `identity.py` forbids version 1
    from recording a parent. The upstream link lives in `related_decision_id` and
    `related_artifact_version` instead — where `ENGINE_4:196-198` puts it."""
    request = emit(a_complete_decision(version=9))
    assert request.identity.version == FIRST_VERSION
    assert request.identity.parent_versions == ()


_UUID_SHAPED = re.compile(
    r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}"
    r"|\b[0-9a-fA-F]{32}\b"
)


@pytest.mark.parametrize(
    "field",
    ["required_clarification", "reason_clarification_is_required", "affected_decision"],
)
def test_no_prose_field_carries_an_identifier(field: str) -> None:
    """INV-9, `ENGINE_4:200-202` — identifiers identify; they never influence
    reasoning. `affected_decision` is the tempting one: the honest way to name
    which decision is affected is the typed field, never the UUID in a sentence.
    """
    text = getattr(emit(a_complete_decision()), field)
    assert _UUID_SHAPED.search(text) is None, f"{field} names an identifier in prose"


def test_the_single_evidence_reference_carries_no_identifier() -> None:
    (reference,) = emit(a_complete_decision()).supporting_evidence_references
    assert _UUID_SHAPED.search(reference) is None


# ─────────────────────────────────────────────────────────────────────────────
# Purity — no clock, no randomness, no hidden state, no upstream mutation.
# ─────────────────────────────────────────────────────────────────────────────


def test_repeated_calls_are_equal_so_there_is_no_clock_and_no_randomness() -> None:
    """Full equality, with nothing excused. This is only assertable because both
    identifiers are injected; a stub that minted them would force the comparison
    to skip exactly the fields a clock or a counter would hide in."""
    decision = a_complete_decision()
    assert emit(decision) == emit(decision) == emit(a_complete_decision())


def test_the_stub_does_not_touch_the_accounting_decision_it_was_given() -> None:
    """`ENGINE_4:228` — never modify accounting decisions. The artifact is frozen,
    so this cannot fail today; it is the regression trap for the day someone
    reaches for `model_copy(update=...)` to "enrich" the input."""
    decision = a_doubt_ridden_decision()
    before = decision.model_dump()
    emit(decision)
    assert decision.model_dump() == before


def test_a_decision_that_already_carries_doubts_does_not_shortcut_the_stub() -> None:
    """The most plausible wrong implementation is *"if the decision names doubts,
    report them; otherwise report nothing."* It would be defensible-looking and it
    would be detection the stub did not perform (`ENGINE_4:231`, `:554`). Both
    branches must produce the identical, judgement-free Request."""
    with_doubts = emit(a_doubt_ridden_decision())
    without_doubts = emit(a_complete_decision())
    assert with_doubts == without_doubts
    assert with_doubts.missing_information == ()
    assert with_doubts.required_clarification is stub.NO_QUESTION_WAS_COMPOSED
