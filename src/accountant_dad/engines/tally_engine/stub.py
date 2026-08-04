"""The Execution Engine stub — it produces a record, and it contacts nobody.

`ENGINE_6_EXECUTION_ENGINE_RULES.md:19` — the architectural name is Execution
Engine, the folder is `tally_engine`, and the folder never changes.

THE PROBLEM A STUB HAS HERE IS NOT THE PROBLEM THE OTHER FIVE STUBS HAVE.
    Engine 6 is *"the final transport layer"* (`ENGINE_6:23`) and *"execution is
    irreversible"* (`ENGINE_6:41`). Every other engine can stub itself by
    declining to REASON. This one would have to decline to ACT, and the artifact
    it owns is the system's only evidence that an entry reached someone's books.

    So the dangerous stub is not the one that returns nothing. It is the one that
    returns something plausible — `posting_status="posted"`,
    `destination_system="Tally"`, one invented voucher number — because that
    record is indistinguishable from a real posting, and every reader downstream,
    human or code, would conclude an entry exists in a real ledger.
    `ENGINE_6:458`: *"Never assume success. Never invent external IDs."*

WHAT THIS MODULE DOES INSTEAD.
    It assembles exactly one Execution Result whose every open-vocabulary field
    states that nothing was attempted, and it returns it. It opens no connection,
    emits no XML, writes no file, starts no process and reads no clock.
    `CLAUDE.md` §P freezes Tally posting; §K.6 — *"Nothing posts to a real ledger
    on a canary"*; `MVP_IMPLEMENTATION_BLUEPRINT.md:136` permits no accuracy
    claim at this phase, and a fabricated success would be one.

    Six fields on the Execution Result are opaque validated strings whose value
    sets no document enumerates (`artifacts/execution.py`, `UNENUMERATED_FIELDS`,
    and `ENGINE_6:321` leaves the destination set explicitly OPEN). That freedom
    is spent on telling the truth rather than on imitating a destination's
    vocabulary — none of the values below is spelled the way any real
    destination spells anything, so neither a reader nor a string comparison can
    mistake this record for a posting.

    `external_transaction_ids` is empty. It is the one field that would be PROOF
    that something reached a ledger, so putting anything in it would be inventing
    the proof.

    `execution_confidence` is 0.0000. `ENGINE_6:177` scopes it to *"transport
    success only"*; no transport occurred, so no evidence of transport success
    exists, and confidence changes only when evidence changes (`CLAUDE.md` §O).

THE NON-EXECUTION IS REPORTED AS A FAILURE, ON PURPOSE.
    `ENGINE_6:245-253` — when execution cannot proceed, the engine reports what
    failed, why, where, the current status and the recommended next action, and
    *"never hides failure."* `ENGINE_6:491` — *"Every failure remains permanently
    visible. Execution never silently disappears."*

    A `classified_error` of `None` beside a truthful outcome string would leave
    the one field a consumer checks for trouble saying there is none, so the
    Classified Error is always present. The Execution Result has no field for a
    *recommended next action*: `retry_permissible=False` is the nearest thing,
    and the gap is named here rather than smuggled into `cause`.

IT NAMES A STAGE; IT ROUTES NOTHING (AL-INV-11).
    *"Engine 6 never returns work to an earlier stage. It names the responsible
    stage; the Application Layer routes."* `ENGINE_6:470` — *"It names; it does
    not route."* The responsible stage is this engine, written into a field. This
    module imports no other engine (AL-INV-5) and not the Application Layer
    (AL-INV-4); a test parses this file and asserts the whole import list against
    an allowlist, so an edit that reaches for either turns red.

EVERY VALUE THAT COULD VARY IS PASSED IN.
    No clock, no `uuid4`, no environment, no randomness. Identical arguments
    produce an equal artifact — which is the only thing that makes the seam
    testable, and the reason `execution_timestamp` is an argument: a stub that
    read the system clock could not produce the same record twice.

    `accounting_decision_id` and `decision_version` are read OFF the Validation
    Decision (`related_decision_id`, `related_artifact_version`) rather than
    accepted as separate arguments. A caller holding both artifacts could
    otherwise hand over a Validation Decision approving version 1 beside an
    Accounting Decision at version 2, and the Execution Result would name a
    version nobody validated. Taking the pair from the artifact that binds them
    makes that mismatch unrepresentable instead of merely checked (Law 53 — the
    easier equivalent problem).

A NON-APPROVING VALIDATION DECISION RAISES; IT PRODUCES NO RECORD.
    `ENGINE_6:144-151` — `Rejected` and `Clarification Required` are *never
    received*, and *"Engine 6 may never bypass Engine 5."* An Execution Result
    naming a rejected decision is that bypass written down, even with nothing
    posted. `APPROVING_STATUSES` is imported rather than re-spelled (Law 15);
    `Approved With Warning` is inside it because the Application Layer releases
    such a decision after human attention (`ENGINE_6:147`), and Engine 6 may
    never learn that a gate existed (AL-INV-4) — so a status check here cannot
    and must not try to tell a released one from an unreleased one.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from accountant_dad.artifacts.execution import (
    AuditReference,
    ClassifiedError,
    ExecutionAttemptId,
    ExecutionId,
    ExecutionResult,
)
from accountant_dad.artifacts.validation import APPROVING_STATUSES, ValidationDecision
from accountant_dad.identity import IdentityEnvelope

#: The five open-vocabulary fields of the Execution Result, answered honestly.
#: Each opens with a negation because the first token is what a human skimming a
#: log sees, and `ENGINE_6:65` names Tally, Zoho Books, Busy, SAP and QuickBooks
#: — no word from any of them appears in any value below, and a test asserts it.
NO_DESTINATION = "NONE: no destination was contacted"
NOTHING_TRANSMITTED = "NOT ATTEMPTED: nothing was transmitted"
NOTHING_QUEUED = "NOT QUEUED: no work was queued"
NOBODY_NOTIFIED = "NOT SENT: nobody was notified"
NOT_EXECUTED = "NOT EXECUTED: the Execution Engine is a P3 stub"

#: `ENGINE_6:476` reserves `unclassifiable` for a failure that CANNOT be
#: classified. This one can be: the engine is not built yet. Saying so is more
#: informative than borrowing the word for the unknown.
NOT_IMPLEMENTED = "NOT IMPLEMENTED: the Execution Engine is a P3 stub"

#: A statement of consequence, not a member of an invented severity scale — no
#: document enumerates severities. Nothing reached a ledger, which is the worst
#: an execution can do to the books.
BLOCKING = "BLOCKING: nothing reached any destination"

#: AL-INV-11 — the responsible stage is NAMED, and named only. Nothing in this
#: module calls anything, so there is no route for it to travel.
RESPONSIBLE_STAGE = "Execution Engine"

#: The *why* of `ENGINE_6:248`. `cause` normally carries a destination's own
#: response body; there was no response, so it carries the reason there was
#: none. Nothing in the text could be misread as something a destination said.
#:
#: An earlier draft cited the freeze by its own words — *"freezes Tally
#: posting"* — and a test caught it: that put the string `Tally` inside an
#: emitted field, and the rule this module is built around is that no value it
#: emits carries a real destination's name. The citation is kept, the name is
#: not. `grep -i tally` over anything this stub emits now returns nothing.
NOTHING_HAPPENED = (
    "No destination was contacted and no voucher was transmitted. "
    "This is the Execution Engine stub: CLAUDE.md section P freezes posting to "
    "every accounting destination until its scheduled phase, and "
    "MVP_IMPLEMENTATION_BLUEPRINT.md:100 schedules only an engine stub at P3. "
    "This record exists to state that nothing happened. It is not evidence of "
    "a posting."
)

#: Empty, and named so that the emptiness reads as a decision rather than as an
#: oversight a reader has to infer from a bare `()`. `ENGINE_6:458` — never
#: invent external IDs.
NO_EXTERNAL_TRANSACTION_IDS: tuple[str, ...] = ()

#: `ENGINE_6:177` — Execution Confidence is transport success ONLY.
NO_TRANSPORT_CONFIDENCE = Decimal("0.0000")

#: Nothing was attempted, so nothing was re-attempted.
NO_RETRIES = 0


def report_nothing_posted(
    *,
    identity: IdentityEnvelope,
    execution_id: ExecutionId,
    execution_attempt_id: ExecutionAttemptId,
    validation: ValidationDecision,
    execution_timestamp: datetime,
) -> ExecutionResult:
    """Assemble the Execution Result for an execution that never happened.

    Pure assembly, which is precisely what `ENGINE_6:115` gives the parent
    engine — *"the parent assembles. It never overrides, rewrites or suppresses
    any sub-engine output."* Here there are no sub-engines to override, because
    none of the six ran and none of them exists yet.

    Raises `ValueError` if `validation` is not approving. It never returns a
    record for a decision Validation did not release, and it never returns a
    record claiming a posting — those are the only two ways this function could
    do harm, and neither is reachable.
    """
    if validation.validation_status not in APPROVING_STATUSES:
        # Loud, not silent (Law 11). A rejected decision arriving here is an
        # Application Layer defect; producing an Execution Result for it would
        # record a bypass of Engine 5 in the permanent history.
        raise ValueError(
            f"validation status {validation.validation_status.value!r} is not "
            "approving, so no Execution Result exists for it. ENGINE_6:151 — "
            "Engine 6 may never bypass Engine 5."
        )

    return ExecutionResult(
        identity=identity,
        execution_id=execution_id,
        execution_attempt_id=execution_attempt_id,
        accounting_decision_id=validation.related_decision_id,
        decision_version=validation.related_artifact_version,
        validation_decision_id=validation.validation_id,
        destination_system=NO_DESTINATION,
        # Hardcoded, and not an argument. A stub that accepted a correction
        # target could be made to claim it repaired a posting that never
        # happened — `ENGINE_6:79`, Engine 6 must never invent corrections.
        corrects_execution_result=None,
        posting_status=NOTHING_TRANSMITTED,
        external_transaction_ids=NO_EXTERNAL_TRANSACTION_IDS,
        retry_count=NO_RETRIES,
        queue_status=NOTHING_QUEUED,
        notification_status=NOBODY_NOTIFIED,
        classified_error=ClassifiedError(
            category=NOT_IMPLEMENTED,
            cause=NOTHING_HAPPENED,
            severity=BLOCKING,
            # AL-INV-12 — only runtime failures are retried. A stub is not a
            # runtime failure, and retrying would return this identical record
            # forever while looking like progress.
            retry_permissible=False,
            responsible_stage=RESPONSIBLE_STAGE,
        ),
        audit_reference=AuditReference(execution_id=execution_id),
        execution_outcome=NOT_EXECUTED,
        execution_confidence=NO_TRANSPORT_CONFIDENCE,
        execution_timestamp=execution_timestamp,
    )
