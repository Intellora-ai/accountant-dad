"""The Business Understanding Object — Engine 2's one output artifact.

`DATA_FLOW.md` §2 row 2 and §2.2 · `ENGINE_2_UNDERSTANDING_ENGINE_RULES.md:216-234`.

Engine 2 answers *"what happened in the business?"* and is forbidden from
answering *"how should it be recorded?"*. Four rules carry that separation, and
each one below is structural rather than remembered.

UNCERTAINTY ENTERING THIS ENGINE LEAVES IT.
    `ENGINE_2:280` — *"It may be described more precisely. It is never
    removed."* `ENGINE_2:638` forbids Story Builder from removing an unknown or
    raising confidence.

    Problem transformed (Law 53). Detecting that a narrative quietly dropped a
    doubt needs the comprehension the checker does not have. So the check
    became arithmetic instead: **`missing_information` and `detected_conflicts`
    are derived, not stored.** They are computed from the six Results, so
    dropping one from the summary is not a thing that can be expressed. And
    `identified_unknowns` is required to contain every unknown the six Results
    raised — a superset, so Story Builder may still report the incoherence
    `ENGINE_2:645` requires, but may not lose what it was handed.

CONFIDENCE NEVER EXCEEDS THE EVIDENCE.
    `ENGINE_2:756` — *"Understanding confidence cannot exceed evidence
    reliability."* Checked for the assembled assessment and for each of the six
    Results.

    A stricter reading, stated so it can be argued with: `understanding` is also
    held at or below the **lowest** of the six Result confidences.
    `ENGINE_2:638` says Story Builder cannot increase confidence and INV-2 says
    confidence changes only when evidence changes — Story Builder introduces no
    evidence, so its output cannot be more certain than its least certain
    input. `min` rather than `max` is the strict reading of a line no document
    quantifies; it is recorded here because a strictness chosen silently is a
    decision nobody made.

EVERY FACT NAMES ITS EVIDENCE.
    `COMMUNICATION_RULES_UNDERSTANDING_INTERNAL.md:130` — *"A fact with no
    evidence reference cannot appear in a Result. There is no mechanism for
    producing one, and that is deliberate: it is the structural reason this
    engine cannot hallucinate."* So `ObservedFact` requires at least one, and
    each Result's evidence component is the derived union of its facts' —
    one source of truth, and a Result cannot declare evidence its facts do not
    cite, nor omit evidence they do.

NO ACCOUNTING VOCABULARY — a NECESSARY check, and knowingly not a SUFFICIENT one.
    `ENGINE_2:641` and `:882`. `:852` gives the worked failure: ✗ *"Fixed asset
    purchase"* · ✓ *"Item description: Laptop."*

    A string check cannot prove the absence of accounting reasoning — a
    paraphrase walks straight through it. What it can do is separate the two
    kinds of text the artifact carries, which is the actual boundary `:852`
    draws: `AuthoredText` is the engine's own words and is vocabulary-checked;
    `StatedText` is quoted verbatim off a document and is never checked and
    never trimmed, because filtering it would modify evidence (`ENGINE_2:190`).
    A party genuinely named *"Ledger Solutions"* is recorded as stated text; an
    interpretation calling something a ledger is refused.

    Every banned term traces to the line that bans it (`FORBIDDEN_VOCABULARY`).
    Three terms the specification uses elsewhere are deliberately NOT banned:
    `debit` and `credit` name event kinds at `:380` and a payment method at
    `:502`, and `expense` is an event kind at `:380`. `tally` is not banned
    either — *"the amounts do not tally"* is the sentence an honest conflict
    narrative writes, and the prohibition on posting is structural (this
    artifact has no destination field) rather than lexical.

FOUR THINGS NO DOCUMENT SETTLES. See `SPEC_GAPS`. None is resolved here.
"""

from __future__ import annotations

import re
from decimal import Decimal
from typing import Annotated

from pydantic import AfterValidator, BaseModel, ConfigDict, PlainValidator, model_validator

from accountant_dad.confidence import Confidence, ConfidenceOrUnmeasured, weakest_link
from accountant_dad.identity import ArtifactId, IdentityEnvelope, TransactionId

_FROZEN = ConfigDict(frozen=True, extra="forbid")

#: Terms this engine may never author, each with the line that forbids it. Every
#: entry is a term the specification itself uses; nothing here is invented, and
#: a test reads the cited lines off disk to prove it. The check is necessary and
#: not sufficient — see the module docstring.
FORBIDDEN_VOCABULARY: dict[str, str] = {
    "accounting": "ENGINE_2:388,429,470,551,591,641 — treatment, group, heads, period, rules",
    "journal": "ENGINE_2:268 — Create journal entries",
    "ledger": "ENGINE_2:269,429 — Choose ledgers · select, create or match a ledger account",
    "voucher": "ENGINE_2:389 — Map the event to a voucher type",
    "asset": "ENGINE_2:469,852 — Decide asset, expense or inventory · 'Fixed asset purchase'",
    "inventory": "ENGINE_2:469 — Decide asset, expense or inventory",
    "tax": "ENGINE_2:271,471 — Apply tax rules · Determine tax rates",
    "chart of accounts": "ENGINE_2:592 — Read or apply the company's accounting configuration",
}

#: Plural forms of the above. Morphology, not additional claims — the words are
#: listed rather than stemmed because a rule that caught `ledger` and let
#: `ledgers` through would be evaded by a keystroke, and `\btax\w*` would reject
#: `taxi`. These carry no separate citation because they make no separate claim.
FORBIDDEN_PLURALS: tuple[str, ...] = (
    "journals",
    "ledgers",
    "vouchers",
    "assets",
    "inventories",
    "taxes",
)

#: A disagreement needs two sides. `ENGINE_2:673` — *"Never silently choose one
#: answer."* One reading is a resolved conflict wearing the label.
MINIMUM_COMPETING_READINGS = 2

_FORBIDDEN = re.compile(
    r"\b(?:"
    + "|".join(re.escape(term) for term in (*FORBIDDEN_VOCABULARY, *FORBIDDEN_PLURALS))
    + r")\b",
    re.IGNORECASE,
)

#: What no document settles, named so the gap is visible in code rather than
#: only in a commit message (Law 54). None is resolved here.
SPEC_GAPS: tuple[str, ...] = (
    # ENGINE_2:380 lists nine event kinds, :420 four party roles, :502 five
    # payment methods and :503 three payment statuses — none declared closed,
    # and :517 requires a fourth status, `unstated`, that :503 omits. All four
    # vocabularies are therefore open validated text, not enums.
    "TransactionUnderstandingResult.identified_event — ENGINE_2:380, open",
    "PartyUnderstandingResult.identified_entities role — ENGINE_2:420, open",
    "PaymentUnderstandingResult.payment_method — ENGINE_2:502, open",
    "PaymentUnderstandingResult.payment_status — ENGINE_2:503 omits the "
    "`unstated` value that :517 requires; the two lists disagree",
    # ENGINE_2:342-348 names `conflicts detected` for the Transaction Result
    # only, while :476 and :557 require the Item and Timeline Results to record
    # conflicts and give them nowhere to put one. Resolved additively — every
    # Result carries `conflicts_detected` — because nothing else satisfies both.
    "UnderstandingResult.conflicts_detected — ENGINE_2:342 names it for one "
    "Result, :476 and :557 require it for two more",
    # ENGINE_2:645 requires an incoherent assembly be "itself reported" and
    # names no field for it. It is left to the narrative rather than given an
    # invented flag, so nothing downstream can read it structurally.
    "TransactionStory — ENGINE_2:645 requires incoherence be reported and "
    "names no field; it is reported in the narrative only",
)


def _meaningful_text(value: object) -> str:
    """A real string with something in it."""
    if not isinstance(value, str):
        raise ValueError(f"must be a string, got {type(value).__name__}")
    if not value.strip():
        raise ValueError("must not be empty or blank")
    return value


NonEmptyText = Annotated[str, PlainValidator(_meaningful_text)]


def _authored_text(value: object) -> str:
    """The engine's own words. Vocabulary-checked."""
    text = _meaningful_text(value)
    found = sorted({match.group(0).lower() for match in _FORBIDDEN.finditer(text)})
    if found:
        raise ValueError(
            f"accounting vocabulary in authored text: {', '.join(found)}. "
            "The Understanding Engine sends facts, never accounting conclusions "
            "(ENGINE_2:852). A word quoted off a document belongs in stated_text, "
            "which is never checked and never trimmed."
        )
    return text


AuthoredText = Annotated[str, PlainValidator(_authored_text)]


def _stated_text(value: object) -> str:
    """Quoted off a document, verbatim.

    Never trimmed, never normalised, never vocabulary-checked. `ENGINE_2:190`
    makes the Document Evidence Object read-only to this engine permanently, and
    editing a quotation of it is modifying evidence by another route.
    """
    if not isinstance(value, str):
        raise ValueError(f"must be a string, got {type(value).__name__}")
    if not value.strip():
        raise ValueError("must not be empty or blank")
    return value


StatedText = Annotated[str, PlainValidator(_stated_text)]


class ObservedFact(BaseModel):  # type: ignore[explicit-any]  # pydantic BaseModel's own signature carries Any; the gate stays on
    """One thing this engine says happened, and the evidence that says so.

    There is no field here that could hold an accounting conclusion, and
    `extra` is forbidden so one cannot be bolted on.
    """

    model_config = _FROZEN

    statement: AuthoredText
    #: What the document actually says, when the fact quotes one. Verbatim.
    stated_text: StatedText | None = None
    evidence_references: tuple[NonEmptyText, ...]

    @model_validator(mode="after")
    def _a_fact_names_its_evidence(self) -> ObservedFact:
        if not self.evidence_references:
            # UNDERSTANDING_INTERNAL:130. Refused rather than defaulted: a fact
            # that cannot be traced is indistinguishable from an invented one.
            raise ValueError(
                "a fact must cite at least one evidence reference; a fact with "
                "no evidence reference cannot appear in a Result "
                "(COMMUNICATION_RULES_UNDERSTANDING_INTERNAL.md:130)"
            )
        return self


def _each_fact_quotes_the_document(facts: tuple[ObservedFact, ...]) -> tuple[ObservedFact, ...]:
    """For the components the specification records *as stated*."""
    for index, fact in enumerate(facts):
        if fact.stated_text is None:
            raise ValueError(
                f"fact {index} must carry the document's own words in stated_text; "
                "this component records what the document states, not a paraphrase "
                "of it (ENGINE_2:462, :504)"
            )
    return facts


Facts = tuple[ObservedFact, ...]
StatedFacts = Annotated[tuple[ObservedFact, ...], AfterValidator(_each_fact_quotes_the_document)]


class Unknown(BaseModel):  # type: ignore[explicit-any]  # pydantic BaseModel's own signature carries Any; the gate stays on
    """A named gap and what its absence prevents.

    `ENGINE_2:794` — the engine may *"explain why understanding is
    incomplete."* A gap with no stated consequence cannot become a good
    question in the Clarification Engine, which is the only reason it travels.
    """

    model_config = _FROZEN

    subject: AuthoredText
    why_it_matters: AuthoredText


class Conflict(BaseModel):  # type: ignore[explicit-any]  # pydantic BaseModel's own signature carries Any; the gate stays on
    """Two or more readings the evidence supports, carried forward unresolved.

    `ENGINE_2:673` — *"Never silently choose one answer."* There is no field
    here for a resolution, a preferred reading or a winner, and `extra` is
    forbidden so one cannot be added. A test reads this model's own field names
    and fails if any word among them could name a resolution.
    """

    model_config = _FROZEN

    subject: AuthoredText
    competing_readings: Facts

    @model_validator(mode="after")
    def _a_conflict_has_something_to_conflict(self) -> Conflict:
        if len(self.competing_readings) < MINIMUM_COMPETING_READINGS:
            raise ValueError(
                f"a conflict needs at least two competing readings, got "
                f"{len(self.competing_readings)}; one reading is a resolved "
                "conflict wearing the label (ENGINE_2:673)"
            )
        statements = [reading.statement for reading in self.competing_readings]
        if len(set(statements)) < len(statements):
            raise ValueError(
                "two competing readings state the same thing; identical readings "
                "do not disagree, so nothing here is a conflict"
            )
        return self


class UnderstandingResult(BaseModel):  # type: ignore[explicit-any]  # pydantic BaseModel's own signature carries Any; the gate stays on
    """What every one of the six Results carries.

    `ENGINE_2:350` — *"Every Result carries confidence, unknowns and evidence
    references. No Result may omit them."* The `§7` table omits the evidence
    component for the Payment and Timeline Results and omits `conflicts
    detected` for five of the six; both are supplied here, because `:350`,
    `:476` and `:557` require them and nothing subtracts them. See `SPEC_GAPS`.

    The facts, unknowns and evidence views below are computed off the model's
    own fields rather than a hand-written list, so adding a component to a
    subclass cannot leave them stale.
    """

    model_config = _FROZEN

    confidence: Confidence
    conflicts_detected: tuple[Conflict, ...] = ()

    def _entries_of[T: BaseModel](self, kind: type[T]) -> tuple[T, ...]:
        collected: list[T] = []
        for name in type(self).model_fields:
            value: object = getattr(self, name)
            if isinstance(value, tuple):
                collected.extend(entry for entry in value if isinstance(entry, kind))
        return tuple(collected)

    @property
    def facts(self) -> tuple[ObservedFact, ...]:
        """Every fact this Result states, in every component."""
        facts = list(self._entries_of(ObservedFact))
        for conflict in self.conflicts_detected:
            facts.extend(conflict.competing_readings)
        return tuple(facts)

    @property
    def unknowns(self) -> tuple[Unknown, ...]:
        """Every gap this Result names, in every component."""
        return self._entries_of(Unknown)

    @property
    def evidence_references(self) -> tuple[str, ...]:
        """The union of what this Result's facts cite. Derived, never stored.

        One source of truth (Law 19): a Result cannot declare evidence its
        facts do not cite, and cannot omit evidence they do.
        """
        seen: list[str] = []
        for fact in self.facts:
            for reference in fact.evidence_references:
                if reference not in seen:
                    seen.append(reference)
        return tuple(seen)

    @model_validator(mode="after")
    def _a_result_reports_something(self) -> UnderstandingResult:
        if not (self.facts or self.unknowns or self.conflicts_detected):
            # A Result with nothing in it has not observed that there was
            # nothing to observe — it has failed to run and said so quietly.
            # An honest empty Result records the gap (ENGINE_2:435, :517).
            raise ValueError(
                "a Result must state at least one fact, name at least one unknown, "
                "or record at least one conflict; a Result carrying none of the "
                "three reports nothing and cannot be distinguished from one that "
                "never ran"
            )
        return self


class TransactionUnderstandingResult(UnderstandingResult):  # type: ignore[explicit-any]  # inherited from pydantic BaseModel; the gate stays on
    """`ENGINE_2:342` · §8.1. The base event, and nothing about how to record it."""

    identified_event: Facts = ()
    unknown_information: tuple[Unknown, ...] = ()

    @property
    def supporting_evidence_references(self) -> tuple[str, ...]:
        """`§7`'s name for the derived evidence union."""
        return self.evidence_references


class PartyUnderstandingResult(UnderstandingResult):  # type: ignore[explicit-any]  # inherited from pydantic BaseModel; the gate stays on
    """`ENGINE_2:343` · §8.2. Who, and in what role.

    `:431` forbids merging two parties believed to be the same entity — the
    resemblance is a fact, recorded in `relationships`, never acted on. There
    is no field for a merge and no field for a chosen canonical party.
    """

    identified_entities: Facts = ()
    relationships: Facts = ()
    unknown_parties: tuple[Unknown, ...] = ()

    @property
    def supporting_evidence(self) -> tuple[str, ...]:
        return self.evidence_references


class ItemUnderstandingResult(UnderstandingResult):  # type: ignore[explicit-any]  # inherited from pydantic BaseModel; the gate stays on
    """`ENGINE_2:344` · §8.3. What moved, as stated.

    `:472` forbids recomputing a stated line value or supplying an omitted one,
    so `descriptions` is `StatedFacts`: each entry must carry the document's own
    words. A description this engine composed is a paraphrase, and a paraphrase
    of a line value is arithmetic wearing quotation marks.
    """

    identified_goods_and_services: Facts = ()
    descriptions: StatedFacts = ()
    unknown_item_details: tuple[Unknown, ...] = ()


class PaymentUnderstandingResult(UnderstandingResult):  # type: ignore[explicit-any]  # inherited from pydantic BaseModel; the gate stays on
    """`ENGINE_2:345` · §8.4. How money moved, or was promised to.

    `payment_method` and `payment_status` are open text: `:502` and `:503` list
    values without declaring the lists closed, and `:517` requires a status
    (`unstated`) that `:503` omits. `:514` forbids inferring payment from
    silence, so both are optional — absent means the Result did not observe
    one, which is what `:517` calls unstated, and the gap belongs in
    `unknown_payment_details`.
    """

    payment_method: NonEmptyText | None = None
    payment_status: NonEmptyText | None = None
    payment_references: StatedFacts = ()
    amount_relationships: Facts = ()
    unknown_payment_details: tuple[Unknown, ...] = ()


class TimelineUnderstandingResult(UnderstandingResult):  # type: ignore[explicit-any]  # inherited from pydantic BaseModel; the gate stays on
    """`ENGINE_2:346` · §8.5. When.

    Dates are facts carrying the document's own words, never parsed datetimes.
    `:557` — *"Where a date format is genuinely ambiguous, the ambiguity travels
    rather than being silently normalised."* Parsing `01/08/2026` into a
    `datetime` IS that normalisation: it picks a reading and destroys the
    evidence that two existed.
    """

    dates: StatedFacts = ()
    event_sequence: Facts = ()
    time_relationships: Facts = ()
    missing_dates: tuple[Unknown, ...] = ()


class BusinessContextResult(UnderstandingResult):  # type: ignore[explicit-any]  # inherited from pydantic BaseModel; the gate stays on
    """`ENGINE_2:347` · §8.6. Why — as indicators, never as a determination.

    `:594` — *"It produces indicators, never a determination of why someone
    acted."* An indicator is a fact about what was observed, so it carries
    evidence like any other; the prohibition it is under is that nothing
    downstream may read it as a conclusion, which is a rule about the reader.
    """

    context_clues: Facts = ()
    business_purpose_indicators: Facts = ()
    unknown_context: tuple[Unknown, ...] = ()

    @property
    def supporting_evidence(self) -> tuple[str, ...]:
        return self.evidence_references


class SupportingUnderstandingData(BaseModel):  # type: ignore[explicit-any]  # pydantic BaseModel's own signature carries Any; the gate stays on
    """The six Results, unaltered. `UNDERSTANDING_INTERNAL:148`.

    All six are required. A missing Result is a sub-engine that did not run,
    and `:645` requires that be reported rather than absorbed.
    """

    model_config = _FROZEN

    transaction: TransactionUnderstandingResult
    party: PartyUnderstandingResult
    item: ItemUnderstandingResult
    payment: PaymentUnderstandingResult
    timeline: TimelineUnderstandingResult
    business_context: BusinessContextResult

    @property
    def results(self) -> tuple[UnderstandingResult, ...]:
        return (
            self.transaction,
            self.party,
            self.item,
            self.payment,
            self.timeline,
            self.business_context,
        )

    @property
    def all_unknowns(self) -> tuple[Unknown, ...]:
        return tuple(unknown for result in self.results for unknown in result.unknowns)

    @property
    def all_conflicts(self) -> tuple[Conflict, ...]:
        return tuple(conflict for result in self.results for conflict in result.conflicts_detected)


class TransactionStory(BaseModel):  # type: ignore[explicit-any]  # pydantic BaseModel's own signature carries Any; the gate stays on
    """The assembled narrative. A component, never the artifact's name.

    `ENGINE_2:260` — *"`Transaction Story` names its narrative component and is
    never used as the name of the artifact itself."*
    """

    model_config = _FROZEN

    narrative: AuthoredText


class ConfidenceAssessment(BaseModel):  # type: ignore[explicit-any]  # pydantic BaseModel's own signature carries Any; the gate stays on
    """Two scores. The other two components of `§11` are derived on the artifact.

    `§11` names four things: evidence confidence, understanding confidence,
    missing information and detected conflicts. The first two are authored and
    stored here. The other two are views over the six Results, exposed on the
    Business Understanding Object — derived precisely so that assembling the
    artifact cannot drop a conflict or a gap (`ENGINE_2:638`).
    """

    model_config = _FROZEN

    #: WIDENED FROM `Confidence` ON 2026-08-06, because the amendment that
    #: governs this field could not be represented in it.
    #:
    #: `ACCOUNTING_DEFINITIONS.md`'s §M *Understanding Confidence Aggregation*
    #: requires that `UNMEASURED` propagate through the aggregation: *"a `min`
    #: over a set containing UNMEASURED is UNMEASURED, not the smallest number
    #: present."* Both slots were `Decimal`-only, so the artifact REFUSED the
    #: value the normative rule produces, and the rule was unimplementable
    #: against the schema meant to carry it.
    #:
    #: It bites hardest where it is least visible: `confidence.py` records that
    #: a PDF text layer produces no score and *"is also the MVP's primary
    #: input"* — so the honest value was exactly the one that could not be
    #: stored. §M: where code and a frozen document disagree, the document wins
    #: and the code is wrong.
    evidence_confidence: ConfidenceOrUnmeasured
    understanding_confidence: ConfidenceOrUnmeasured

    @model_validator(mode="after")
    def _understanding_never_exceeds_evidence(self) -> ConfidenceAssessment:
        """The ceiling, over four measurement states rather than one.

        `>` between a `Decimal` and an absence raises `TypeError` — loud, but
        the wrong complaint, and it would fire on the commonest real input
        rather than on a defect. The comparison is therefore made only where
        BOTH sides are measured, which is the only case in which "exceeds"
        means anything at all.

        An absence on either side is NOT silently permissive: nothing is
        asserted about an ordering that was never measurable, and the amendment
        already forbids the aggregation from inventing one.
        """
        understanding = self.understanding_confidence
        evidence = self.evidence_confidence
        both_measured = isinstance(understanding, Decimal) and isinstance(evidence, Decimal)
        if both_measured and understanding > evidence:
            # ENGINE_2:756, :773 — "A confident interpretation of an unreliable
            # reading is not understanding; it is invention with a score
            # attached."
            raise ValueError(
                f"understanding confidence {understanding} exceeds "
                f"evidence reliability {evidence}. Understanding "
                "confidence cannot exceed evidence reliability (ENGINE_2:756)."
            )
        return self


class BusinessUnderstandingObject(BaseModel):  # type: ignore[explicit-any]  # pydantic BaseModel's own signature carries Any; the gate stays on
    """Engine 2 → Engine 3. `DATA_FLOW.md` §2 row 2.

    Four components, exactly as `§2.2` draws them, plus the identity envelope
    `DATA_FLOW.md:32` makes universal and does not repeat inside an artifact.

    Many Document Evidence Objects contribute to one of these (INV-3,
    `ENGINE_2:157`). Which ones is answered by the evidence references its facts
    cite, not by a list of document identifiers — a second list could disagree
    with the first, and then no reader could tell which traced the artifact.
    """

    model_config = _FROZEN

    identity: IdentityEnvelope
    transaction_story: TransactionStory
    supporting_understanding_data: SupportingUnderstandingData
    identified_unknowns: tuple[Unknown, ...]
    confidence_assessment: ConfidenceAssessment

    @property
    def understanding_id(self) -> ArtifactId:
        """The Understanding ID IS the Artifact ID (`DATA_FLOW.md:32`)."""
        return self.identity.artifact_id

    @property
    def transaction_id(self) -> TransactionId:
        return self.identity.transaction_id

    @property
    def missing_information(self) -> tuple[Unknown, ...]:
        """`§11`'s third component. The same gaps, under the name `§11` uses."""
        return self.identified_unknowns

    @property
    def detected_conflicts(self) -> tuple[Conflict, ...]:
        """`§11`'s fourth component. Derived, so a conflict cannot be dropped."""
        return self.supporting_understanding_data.all_conflicts

    @model_validator(mode="after")
    def _nothing_the_results_raised_was_lost(self) -> BusinessUnderstandingObject:
        raised = self.supporting_understanding_data.all_unknowns
        carried = set(self.identified_unknowns)
        dropped = [unknown for unknown in raised if unknown not in carried]
        if dropped:
            # ENGINE_2:638, :645 — Story Builder cannot remove unknowns, and
            # "Unknowns are carried into Identified Unknowns intact." A
            # superset is allowed: :645 also requires Story Builder report an
            # incoherence no sub-engine could have raised.
            subjects = ", ".join(repr(unknown.subject) for unknown in dropped)
            raise ValueError(
                f"{len(dropped)} unknown(s) raised by the Results are missing from "
                f"identified_unknowns: {subjects}. Unknowns are carried into "
                "Identified Unknowns intact (ENGINE_2:645); uncertainty entering "
                "this engine leaves it (ENGINE_2:280)."
            )

        # BOTH SIDES MEASURED, OR NO ORDERING IS ASSERTED. `>` between a
        # `Decimal` and an absence raises `TypeError`, which would fire on the
        # commonest real input rather than on a defect — `confidence.py` records
        # that a PDF text layer produces no score and is the MVP's primary
        # input. Skipping the comparison asserts nothing about an ordering that
        # was never measurable; it does not permit one.
        evidence = self.confidence_assessment.evidence_confidence
        for result in self.supporting_understanding_data.results:
            if (
                isinstance(result.confidence, Decimal)
                and isinstance(evidence, Decimal)
                and result.confidence > evidence
            ):
                raise ValueError(
                    f"{type(result).__name__} carries confidence {result.confidence}, "
                    f"above evidence reliability {evidence}. Understanding confidence "
                    "cannot exceed evidence reliability (ENGINE_2:756)."
                )

        understanding = self.confidence_assessment.understanding_confidence
        lowest = weakest_link(
            tuple(result.confidence for result in self.supporting_understanding_data.results)
        )
        if (
            isinstance(understanding, Decimal)
            and isinstance(lowest, Decimal)
            and understanding > lowest
        ):
            # ENGINE_2:638 with INV-2. Story Builder introduces no evidence, so
            # it cannot be more certain than its least certain input. See the
            # module docstring for why this is `min` and not `max`.
            raise ValueError(
                f"understanding confidence "
                f"{self.confidence_assessment.understanding_confidence} exceeds the "
                f"lowest Result confidence {lowest}. Story Builder cannot increase "
                "confidence (ENGINE_2:638), and confidence changes only when "
                "evidence changes (INV-2)."
            )
        return self
