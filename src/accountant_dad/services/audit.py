"""The append-only history of what happened to a transaction, and when.

`APPLICATION_LAYER_API.md:126` — this exists so that *"why is this transaction
here"* is answered **without inference**. Inference is what the alternative is:
read the artifacts, guess the order, and produce a story that is plausible
rather than true. A plausible story about a financial posting is worse than no
story, because it gets believed.

WHAT IT MAY CARRY, AND WHAT IT MAY NOT.
    `:131` lists the record field for field — *"from · to · timestamp · trigger
    · engine involved · retry attempt · releasing identity where applicable."*
    `:138` draws the other edge of the same line — *"Returns workflow history
    only. It never returns artifact content, decision reasoning or confidence —
    those belong to the artifacts and the engines that own them."*

    So `Transition` has six fields and no seventh, and `frozen=True,
    slots=True` makes that structural rather than remembered: an instance
    cannot be handed a `confidence` afterwards, because there is no slot to put
    one in.

    One item on `:131`'s list is deliberately absent. **`releasing identity`
    has no field here.** The only thing that produces one is
    `release_waiting_for_approval()` (`:84`, `:94`), and `:7` records that
    operation as depending on an amendment `ARCHITECTURE_AMENDMENTS.md:37`
    marks **PROPOSED, not approved**. `WaitingForApproval` is not in the locked
    state machine, so *"where applicable"* currently applies nowhere. Adding the
    field now would build the shape of an unapproved amendment into a record
    type other modules already depend on. Reported, not resolved here (§M).

APPEND-ONLY, ENFORCED BY WHAT DOES NOT EXIST.
    `:135` — *"history is never truncated, compacted or summarised."* So
    `AuditTrail` has exactly two methods, and the only write in it has the shape
    *everything already there* + *one more*. No delete, no update, no
    compaction, no retention policy. A test reads this class's own method names,
    so adding one fails the build rather than depending on a reviewer noticing.

    Each transaction's entries are stored as a TUPLE, not a list. A list would
    make "append-only" a property of the methods that happen to be written here;
    a tuple makes it a property of the value — a recorded history cannot be
    shortened in place at all, by this module or by anything that reaches past
    it.

THE CLOCK IS THE CALLER'S, ALWAYS.
    `at` is supplied and never read from a clock. Two reasons, both structural.
    A module that calls a clock returns a different value on every run, so the
    test proving *"the order is exactly this"* could not exist. And the moment
    that belongs in the record is the moment the transition COMPLETED, which
    only the caller that completed it knows — a clock read here would timestamp
    the bookkeeping instead of the event.

    A naive datetime is refused loudly rather than assumed to be UTC. Assuming
    is how a five-and-a-half-hour Indian offset becomes an ordering nobody can
    reproduce.

RETRY IS AN ATTRIBUTE, NEVER A STATE.
    `APPLICATION_LAYER_INVARIANTS.md:172` — *"Retry is a transition attribute,
    never a state."* `attempt` is that attribute and it counts from 1; attempt 0
    describes a transition nobody made. `state.py` has nowhere to park a
    transaction while it retries, and this module does not quietly invent one by
    letting `attempt` carry a state's meaning.

AL-INV-3 — A RECORDED TRANSITION IS ONE THAT ACTUALLY COMPLETED.
    `:134` names the invariant this history preserves;
    `APPLICATION_LAYER_INVARIANTS.md:44` states it — *"Transitions are
    atomic."* Recording happens after a transition commits, so an entry naming
    an edge the locked machine does not draw describes something that could not
    have completed. `Transition` refuses to be constructed in that case, and
    delegates the predicate to `state.is_allowed()` rather than keeping a second
    copy of the whitelist (Law 19 — one source of truth).

    That is a well-formedness check on the record, not workflow enforcement.
    This module has no opinion about what should happen next: `state.py` owns
    which edges exist, and the state store owns which one a transaction is on.

WHAT `history()` DOES WITH AN UNKNOWN TRANSACTION — A REPORTED DIVERGENCE.
    `:132` gives `get_transaction_history()` the precondition *"Transaction
    exists"* and `:135` rejects an unknown Transaction ID. This method returns
    an **empty tuple** instead, deliberately. `get_transaction_history()` is the
    Application Layer's public API, and *does this transaction exist* is a
    question the STATE STORE answers — `APPLICATION_LAYER_INVARIANTS.md:32`,
    *"The state store permits exactly one row per Transaction ID."* This class
    holds history, not existence. Making it reject an unknown ID would either
    create a second existence authority (INV-10 — one concept, one owner) or
    force it to import the store, which is the dependency it is specified not to
    have.

    The rejection belongs to the caller that owns existence, and is NOT
    implemented here. Recorded rather than resolved (Law 40).

IN-MEMORY IS THE WHOLE OF P3. No database, no file, no dependency. Durability is
a P4 question, and answering it early picks a storage engine nobody asked for.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from accountant_dad.identity import TransactionId
from accountant_dad.services.state import INITIAL_STATE, TransactionState, is_allowed


class UnrecordableTransitionError(Exception):
    """A record describing something that did not happen. Never downgraded.

    `APPLICATION_LAYER_API.md:18` — *"Every failure is loud. Nothing returns a
    default on error."* There is deliberately no `Transition.is_valid()` and no
    lenient constructor: a malformed entry that merely warns is an entry that
    reaches the history anyway, and `:135` says the history is never edited
    afterwards. Construction is the only moment this can still be caught.
    """


@dataclass(frozen=True, slots=True)
class Transition:
    """One movement between two states, that completed.

    Frozen for the reason every artifact in this repo is frozen — INV-5,
    history is never modified. Slotted for a second reason: an attribute this
    class does not declare cannot be attached to an instance later, so nobody
    can smuggle `transition.confidence = 0.4` onto a record that
    `APPLICATION_LAYER_API.md:138` says carries no confidence.
    """

    #: `None` for the creation entry and nothing else —
    #: `APPLICATION_LAYER_API.md:32`, `start_transaction()`'s postcondition,
    #: *"state is `Input` · audit records creation"*. A transaction has no
    #: previous state before it exists, and writing `Input → Input` instead
    #: would record movement that did not happen (AL-INV-2).
    from_state: TransactionState | None
    to_state: TransactionState
    #: Timezone-aware, PASSED IN. See "THE CLOCK IS THE CALLER'S" above.
    at: datetime
    #: What caused this movement. `:131` lists the trigger as part of what
    #: history returns; an entry recording the movement but not its cause
    #: leaves the reader inferring, which is what `:126` exists to prevent.
    trigger: str
    #: The engine that was running, where one was; `None` where none was — the
    #: creation entry, and anything a human drove. A NAME, never a handle: the
    #: record names the engine, and AL-INV-4 keeps the traffic one-way — no
    #: engine ever reads this back.
    engine: str | None
    #: The retry attempt, counting from 1. An attribute, never a state
    #: (`APPLICATION_LAYER_INVARIANTS.md:172`).
    attempt: int

    def __post_init__(self) -> None:
        """Refuse to exist, rather than be recorded and then be wrong.

        The checks live here and not in `AuditTrail.record()` because a
        `Transition` that cannot be constructed cannot reach ANY recorder —
        including one written later by somebody who never read this file.
        """
        if self.at.tzinfo is None or self.at.tzinfo.utcoffset(self.at) is None:
            raise UnrecordableTransitionError(
                f"`at` must be timezone-aware; got the naive datetime {self.at!r}. "
                "A naive timestamp means 'some clock, somewhere' — two transitions "
                "stamped in two zones sort into an order neither happened in, and "
                "APPLICATION_LAYER_API.md:126 says this history answers 'why is this "
                "transaction here' WITHOUT inference."
            )
        if not self.trigger.strip():
            raise UnrecordableTransitionError(
                f"`trigger` must name what caused this transition; got {self.trigger!r}. "
                "APPLICATION_LAYER_API.md:131 lists the trigger as part of what history "
                "returns, and an entry with no cause is the inference :126 forbids."
            )
        if self.engine is not None and not self.engine.strip():
            raise UnrecordableTransitionError(
                "`engine` is None when no engine was involved. A blank string is not "
                "'no engine' — it is a missing answer wearing the shape of one."
            )
        if self.attempt < 1:
            raise UnrecordableTransitionError(
                f"`attempt` counts from 1; got {self.attempt}. "
                "APPLICATION_LAYER_INVARIANTS.md:172 — retry is a transition ATTRIBUTE, "
                "never a state — so a first attempt is attempt 1, and attempt 0 would "
                "describe a transition nobody made."
            )
        if self.from_state is None and self.to_state is not INITIAL_STATE:
            raise UnrecordableTransitionError(
                f"a creation entry ends in {INITIAL_STATE.value}, not {self.to_state.value}. "
                "APPLICATION_LAYER_API.md:32 — start_transaction() leaves the transaction "
                "in `Input` and audit records the creation; `from_state=None` anywhere "
                "else claims a transaction had no previous state when it did."
            )
        # `to_state` is never None, so this is true only when both name the same
        # state. AL-INV-2 — a transaction is in exactly one state at any moment,
        # so re-entering the one it already occupies is movement that did not
        # happen. `state.py` rejects the same pair for the same reason.
        if self.from_state is self.to_state:
            raise UnrecordableTransitionError(
                f"{self.to_state.value} to itself is not a transition (AL-INV-2). "
                "A record of it is a record of movement that did not happen."
            )
        # AL-INV-3, via the ONE whitelist. `is_allowed` is called rather than
        # copied: a second copy of the transition table here would drift from
        # `state.py`'s, and the drifted one would be believed because it is the
        # one written into the permanent history.
        if self.from_state is not None and not is_allowed(self.from_state, self.to_state):
            raise UnrecordableTransitionError(
                f"{self.from_state.value} → {self.to_state.value} is not in the locked "
                "state machine (DATA_FLOW.md §14), so it cannot have completed, so it "
                "cannot be history. APPLICATION_LAYER_API.md:134 — every recorded "
                "transition is one that actually completed (AL-INV-3)."
            )


class AuditTrail:
    """Every transition, per transaction, in the order recorded.

    Two methods. The third one you might reach for — prune, compact, correct,
    reindex — is the one `APPLICATION_LAYER_API.md:135` forbids by name.

    `__slots__` is here for the same reason it is on `Transition`: it stops an
    instance from growing a `_deleted` or `_tombstones` attribute at runtime,
    which is how append-only quietly becomes append-mostly.
    """

    __slots__ = ("_by_transaction",)

    def __init__(self) -> None:
        # Values are TUPLES. A list here would leave every recorded history
        # mutable in place by anything holding a reference to it, and this
        # module's whole claim is that a recorded history cannot change.
        self._by_transaction: dict[TransactionId, tuple[Transition, ...]] = {}

    def record(self, transaction_id: TransactionId, transition: Transition) -> None:
        """Append one completed transition to this transaction's history.

        Called AFTER the transition commits, never before (AL-INV-3,
        `APPLICATION_LAYER_INVARIANTS.md:44` — *"Transitions are atomic."*).
        Recording an intention rather than a fact is how a history stops being
        evidence.

        Deduplicates nothing. Two identical transitions are two transitions; a
        retry of the same edge is exactly what `attempt` exists to distinguish,
        and collapsing them would be the summarising `:135` forbids.
        """
        previous = self._by_transaction.get(transaction_id, ())
        # The only write in this class. Its shape — everything already there,
        # plus one — is why there is no expression anywhere here that can
        # produce a shorter history.
        self._by_transaction[transaction_id] = (*previous, transition)

    def history(self, transaction_id: TransactionId) -> tuple[Transition, ...]:
        """In the order recorded. Empty tuple for a transaction with no history.

        Order is insertion order, NOT `at` order. The recorded sequence is what
        happened; a re-sort by timestamp would let a caller's clock skew rewrite
        the order of events it did not control. `at` is data in the record, not
        the index of it.

        An unknown Transaction ID returns empty rather than raising, which
        differs from `get_transaction_history()`'s `:132`/`:135` contract. The
        reason is in the module docstring: existence is the state store's
        question, not this class's, and answering it here would make two owners
        of one concept.
        """
        return self._by_transaction.get(transaction_id, ())
