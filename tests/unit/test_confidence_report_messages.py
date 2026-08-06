"""Every sentence the `confidence` sub-engine emits, pinned word for word.

WHAT MEASURED THIS FILE INTO EXISTENCE. Mutation testing over
`accountant_dad.engines.input_engine.confidence_report` at commit `d7a8ed9`
(LOCAL ONLY — NOT AUTHORITATIVE) reached 53 mutants that no assertion in
`test_input_engine_confidence.py` or `test_input_engine_confidence_redteam.py`
could tell apart from the real thing: uncertainty-marker reasons deleted,
re-cased and emptied; a NOT_APPLICABLE basis blanked; the capture-fidelity
outcome in the reliability line replaced by "not supplied" on a document that
supplied one. Every existing assertion over those strings reads a FRAGMENT —
`"absent" in reason`, `"does not match" in marker.reason`,
`"no per-region extraction score" in marker.reason` — and a fragment clears
every edit that happens to fall outside it.

WHY THE WORDING IS NOT DECORATION HERE. `ENGINE_1_INPUT_ENGINE_RULES.md:626`:
*"Every uncertainty marker carries a reason. A bare score cannot become a good
question downstream."* The reason IS the marker's product. A marker whose
subject is right and whose reason has been emptied still counts, still appears
in the artifact, and still tells the accountant reading it nothing — which is
the concealed uncertainty `ENGINE_1_ARCHITECTURE.md` P-F3 forbids, arriving by
a route that leaves every count correct.

WHY A SEPARATE FILE. `test_input_engine_confidence.py` asserts what the module
DECIDES — which regions earn a marker, which fields earn a score, that no
number is invented. This file asserts what it SAYS. Keeping them apart means a
wording change fails here, next to the pinned text, rather than somewhere in
the middle of a behavioural test that was never about wording.

IF ONE OF THESE FAILS, THE MESSAGE CHANGED. Read the new one and decide whether
the change was intended. Do NOT relax the assertion to make it pass (Law 4).
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import numpy as np
import pytest

from accountant_dad.artifacts.evidence import (
    Corroborated,
    HumanBusinessContext,
    Provenance,
    SourceType,
    UncertaintyMarker,
)
from accountant_dad.confidence import MeasurementState, UnmeasuredType, measurement_state
from accountant_dad.engines.input_engine.cleaner import CleanedDocument, PreservationStatus
from accountant_dad.engines.input_engine.confidence_report import (
    CAPTURE_FIDELITY_FIELD_NAME,
    HumanCaptureEvidence,
    MissingField,
    ParsedField,
    RegionReading,
    capture_fidelity,
    record_confidence,
)

WHEN = datetime(2026, 8, 5, 9, 0, tzinfo=UTC)
HIGH = Decimal("0.9800")

NOTE = "Paid rent for June in cash."


# ── builders ─────────────────────────────────────────────────────────────────
# Explicit, matching the convention in `test_input_engine_confidence.py`: every
# builder takes the one value the test cares about and supplies the rest with
# an unremarkable default. The real frozen types are used throughout — a
# stand-in would prove the stand-in (§J.6).


def a_cleaned_document(
    *, preservation_status: PreservationStatus = PreservationStatus.CLEANED_IS_SAFER
) -> CleanedDocument:
    frame = np.zeros((2, 2), dtype=np.uint8)
    return CleanedDocument(
        original=frame,
        cleaned=frame,
        quality_observations=(),
        preservation_status=preservation_status,
    )


def a_human_business_context(*, original_user_text: str = NOTE) -> HumanBusinessContext:
    return HumanBusinessContext(
        original_user_text=original_user_text,
        provenance=Provenance(
            source_type=SourceType.HUMAN,
            source_id="typed by the operator",
            evidence_reference="the note field",
            timestamp=WHEN,
            confidence=HIGH,
            corroborated=Corroborated.NOT_ASSESSED,
        ),
    )


def marker_named(markers: tuple[UncertaintyMarker, ...], subject: str) -> UncertaintyMarker:
    """The one marker with this subject, or a failure that says what was there.

    Indexing by position would pass while the module emitted the markers in a
    different order and said different things about them.
    """
    matching = [marker for marker in markers if marker.subject == subject]
    assert len(matching) == 1, (
        f"expected exactly one marker about {subject!r}; got "
        f"{[marker.subject for marker in markers]}"
    )
    return matching[0]


# ── cleaner's own finding, relayed verbatim ──────────────────────────────────


def test_the_preservation_marker_is_pinned_word_for_word() -> None:
    """The marker says WHOSE finding it is and WHERE that finding was made.

    `_preservation_marker` re-decides nothing — it relays a verdict `cleaner`
    already reached from its own caller's `max_ink_loss_fraction`. The sentence
    naming `cleaner.py` and `PreservationStatus.ORIGINAL_IS_SAFER` is the only
    thing in the emitted artifact that says so, and without it a reader has a
    warning about "the document as cleaned" and no way to find out who issued
    it or on what basis.
    """
    report = record_confidence(
        cleaned=a_cleaned_document(preservation_status=PreservationStatus.ORIGINAL_IS_SAFER),
        reader_regions=(),
        parsed_fields=(),
        missing_fields=(),
    )
    marker = marker_named(report.uncertainty_markers, "the document as cleaned")
    assert marker.reason == (
        "cleaner found that processing this artifact could have lost "
        "information and reported the original as the safer basis for "
        "reading (engines/input_engine/cleaner.py, "
        "PreservationStatus.ORIGINAL_IS_SAFER); this module records "
        "that finding rather than re-deciding it."
    )


def test_the_other_preservation_status_produces_no_marker_at_all() -> None:
    """The disconfirming half. A relay that fired on both states would satisfy
    the assertion above and warn about every document ever cleaned, which is a
    warning that carries no information."""
    report = record_confidence(
        cleaned=a_cleaned_document(preservation_status=PreservationStatus.CLEANED_IS_SAFER),
        reader_regions=(),
        parsed_fields=(),
        missing_fields=(),
    )
    assert report.uncertainty_markers == ()


# ── the two region markers, which must never read alike ──────────────────────


def test_the_unread_region_marker_is_pinned_word_for_word() -> None:
    """ "nothing is guessed in its place" is the half that is not a symptom.

    That a region could not be read is bad news; that nothing was invented to
    fill it is the assurance the reader actually needs
    (`ENGINE_1_INPUT_ENGINE_RULES.md:337`, Law 24). An assertion reading only
    "could not read this region at all" clears a marker with that assurance
    deleted.
    """
    report = record_confidence(
        cleaned=a_cleaned_document(),
        reader_regions=(
            RegionReading(source_location="p1 footer", text=None, extraction_confidence=None),
        ),
        parsed_fields=(),
        missing_fields=(),
    )
    marker = marker_named(report.uncertainty_markers, "p1 footer")
    assert marker.reason == (
        "reader could not read this region at all; nothing is guessed in its place."
    )


def test_the_unscored_region_marker_is_pinned_word_for_word() -> None:
    """This is the marker EVERY region of a PDF text layer earns, and the MVP's
    primary input is a PDF text layer (`CLAUDE.md` §B.7).

    So this sentence is the one an accountant reads most often, and it has to
    carry three separate facts: no recogniser ran, WHY none ran, and that the
    text is real and travelling on regardless. Drop any of them and the marker
    reads as a failure to extract rather than as the ordinary state of a
    transcribed document.
    """
    report = record_confidence(
        cleaned=a_cleaned_document(),
        reader_regions=(
            RegionReading(
                source_location="p1 head", text="TAX INVOICE", extraction_confidence=None
            ),
        ),
        parsed_fields=(),
        missing_fields=(),
    )
    marker = marker_named(report.uncertainty_markers, "p1 head")
    assert marker.reason == (
        "reader read this region but produced no per-region extraction "
        "score for it: the backend transcribed the text rather than "
        "recognising it, so no recogniser ran to produce one "
        "(engines/input_engine/reader.py, 'THE CONFIDENCE OF A TEXT "
        "LAYER IS None'). The text is real and is carried through; the "
        "absence of a score is recorded rather than filled in."
    )


def test_the_two_region_markers_share_no_word_of_their_reasons() -> None:
    """An unscored region reported in the words of an unread one is a lie about
    a region whose text WAS recovered. Pinning each separately proves each is
    right; this proves they are not the same sentence."""
    report = record_confidence(
        cleaned=a_cleaned_document(),
        reader_regions=(
            RegionReading(source_location="p1 footer", text=None, extraction_confidence=None),
            RegionReading(
                source_location="p1 head", text="TAX INVOICE", extraction_confidence=None
            ),
        ),
        parsed_fields=(),
        missing_fields=(),
    )
    unread = marker_named(report.uncertainty_markers, "p1 footer")
    unscored = marker_named(report.uncertainty_markers, "p1 head")
    assert unread.reason != unscored.reason


# ── a field the document does not contain: its marker AND its basis ──────────


@pytest.mark.parametrize("state", ["absent", "zero", "unreadable"])
def test_a_missing_field_states_parsers_own_word_in_both_places(state: str) -> None:
    """`ENGINE_1_INPUT_ENGINE_RULES.md:569` — *"absent", "zero" and
    "unreadable"* must stay distinguishable, and no locked document says which
    measurement state each implies. So `parser`'s word is carried through
    VERBATIM rather than translated, in the marker and in the NOT_APPLICABLE
    basis alike, and both sentences are pinned: an assertion reading only
    `"absent" in basis` clears a basis that has been reduced to that one word.
    """
    report = record_confidence(
        cleaned=a_cleaned_document(),
        reader_regions=(),
        parsed_fields=(),
        missing_fields=(MissingField(field_name="PO Number", state=state),),
    )

    marker = marker_named(report.uncertainty_markers, "PO Number")
    assert marker.reason == (f"parser recorded this field as {state}: not read from the document.")

    (score,) = report.confidence_scores
    assert score.field_name == "PO Number"
    assert measurement_state(score.confidence) is MeasurementState.NOT_APPLICABLE
    assert isinstance(score.confidence, UnmeasuredType)
    assert score.confidence.basis == (
        f"parser recorded this field as {state}: it was not read "
        "from the document, so there is no reading here for a score to "
        "be about"
    )


# ── the capture-fidelity mismatch: the finding IS the sentence ───────────────


def test_the_capture_fidelity_mismatch_marker_is_pinned_word_for_word() -> None:
    """A mismatch emits NO number, so the sentence is the entire finding.

    It has to say what broke (a preservation guarantee, cited to the two
    clauses that impose it), why no partial score was invented
    (`ENGINE_1_CONFIDENCE_PARAMETERS.md` gap #12), and that inventing one is
    forbidden rather than merely unimplemented (`CLAUDE.md` Law 54). Strip any
    of that and the next reader's obvious move is to add a fabricated score.
    """
    stored = a_human_business_context(original_user_text="Paid rent for June")
    evidence = HumanCaptureEvidence(submitted_text="Paid rent for july", stored=stored)

    score, marker = capture_fidelity(evidence)

    assert measurement_state(score) is MeasurementState.FAILED
    assert marker is not None
    assert marker.subject == "the human business context"
    assert marker.reason == (
        "the text now stored does not match, character for character, "
        "the text submitted, even though cleaner and reader are both "
        "required to pass a provided source through untouched "
        "(ENGINE_1_INPUT_ENGINE_RULES.md:459, :508). No numeric capture "
        "fidelity score is emitted for a mismatch: no locked document "
        "states a rule for grading a partial loss "
        "(ENGINE_1_CONFIDENCE_PARAMETERS.md gap #12), and inventing one "
        "is exactly what CLAUDE.md Law 54 forbids. The mismatch itself "
        "is the finding."
    )


def test_the_same_marker_reaches_the_recorded_report_unaltered() -> None:
    """`capture_fidelity` returning the right sentence proves nothing about
    what `record_confidence` puts in the artifact. This is the wiring."""
    stored = a_human_business_context(original_user_text="Paid rent for June")
    evidence = HumanCaptureEvidence(submitted_text="Paid rent for july", stored=stored)
    _score, direct = capture_fidelity(evidence)
    assert direct is not None

    report = record_confidence(
        cleaned=a_cleaned_document(),
        reader_regions=(),
        parsed_fields=(),
        missing_fields=(),
        human_capture=evidence,
    )
    recorded = marker_named(report.uncertainty_markers, "the human business context")
    assert recorded.reason == direct.reason


def test_an_exact_match_emits_no_marker_and_no_sentence_about_one() -> None:
    """The disconfirming half: the mismatch sentence must not appear on a
    document where nothing mismatched."""
    stored = a_human_business_context(original_user_text=NOTE)
    score, marker = capture_fidelity(HumanCaptureEvidence(submitted_text=NOTE, stored=stored))
    assert marker is None
    assert measurement_state(score) is MeasurementState.MEASURED


# ── the reliability line reports the capture outcome it actually got ─────────
#
# `_capture_fidelity_state` has three answers and `_reliability_information`
# quotes whichever one applies. At commit `d7a8ed9` two separate mutants passed
# `None` in place of the human capture — one inside `record_confidence`, one
# inside `_reliability_information` — so a document that DID supply a note was
# reported as "not supplied", and every assertion in the suite still passed
# because none of them ran the reliability line with a note attached.


def a_report_line(*, submitted: str | None, stored_text: str) -> str:
    """The emitted reliability line for a document whose only variable is
    whether — and how faithfully — a human note was captured."""
    human_capture = (
        None
        if submitted is None
        else HumanCaptureEvidence(
            submitted_text=submitted,
            stored=a_human_business_context(original_user_text=stored_text),
        )
    )
    report = record_confidence(
        cleaned=a_cleaned_document(),
        reader_regions=(),
        parsed_fields=(),
        missing_fields=(),
        human_capture=human_capture,
    )
    return report.reliability_information


def expected_line(capture_state: str) -> str:
    """The whole line, with only the capture clause varying."""
    return (
        "0 field(s) carry a confidence score from parser; "
        "0 of 0 region(s) reader attempted could not be read at all; "
        "0 of them were read but carry no per-region extraction score; "
        "0 field(s) parser recorded as missing; "
        "cleaner's preservation status: the cleaned representation is the safer "
        "basis for reading; "
        f"human business context capture fidelity: {capture_state}."
    )


def test_no_note_supplied_is_reported_as_not_supplied() -> None:
    assert a_report_line(submitted=None, stored_text=NOTE) == expected_line("not supplied")


def test_a_faithfully_captured_note_is_reported_as_matching_character_for_character() -> None:
    """THE CASE NO TEST RAN. Every reliability-line assertion in the suite used
    a document with no human note, so the two branches that only exist when one
    IS supplied were never reached by an assertion."""
    assert a_report_line(submitted=NOTE, stored_text=NOTE) == expected_line(
        "matched the text as submitted, character for character"
    )


def test_a_mis_captured_note_is_reported_as_not_established() -> None:
    """And the third branch, which must not read like either of the other two:
    "could not be established" is a broken preservation guarantee, "not
    supplied" is an ordinary document with no note on it."""
    assert a_report_line(submitted="Paid rent for july", stored_text="Paid rent for June") == (
        expected_line("could not be established: the stored text differs from what was submitted")
    )


def test_the_three_capture_outcomes_are_three_distinct_sentences() -> None:
    """The disconfirming form: one shared sentence would satisfy any single
    assertion above that happened to be written against it."""
    outcomes = (
        a_report_line(submitted=None, stored_text=NOTE),
        a_report_line(submitted=NOTE, stored_text=NOTE),
        a_report_line(submitted="Paid rent for july", stored_text="Paid rent for June"),
    )
    # Against the number of cases, never a literal: a fourth outcome added here
    # widens the claim instead of leaving a case nobody counted.
    assert len(set(outcomes)) == len(outcomes), (
        f"two capture outcomes report identically: {sorted(outcomes)}"
    )


def test_the_recorded_score_and_the_reported_line_agree_about_the_same_document() -> None:
    """A line that said "matched" while the score said FAILED would be the
    artifact contradicting itself — the shape a `None` substituted for the
    human capture produces, and the reason both halves are asserted together.
    """
    stored = a_human_business_context(original_user_text="Paid rent for June")
    evidence = HumanCaptureEvidence(submitted_text="Paid rent for july", stored=stored)
    report = record_confidence(
        cleaned=a_cleaned_document(),
        reader_regions=(),
        parsed_fields=(),
        missing_fields=(),
        human_capture=evidence,
    )
    scores = {score.field_name: score.confidence for score in report.confidence_scores}
    assert measurement_state(scores[CAPTURE_FIDELITY_FIELD_NAME]) is MeasurementState.FAILED
    assert "could not be established" in report.reliability_information
    assert "matched the text as submitted" not in report.reliability_information


def test_a_scored_field_does_not_change_which_capture_sentence_is_reported() -> None:
    """The counts and the capture clause are independent, and the line is
    pinned whole so a count that drifted into the capture clause fails here."""
    report = record_confidence(
        cleaned=a_cleaned_document(),
        reader_regions=(
            RegionReading(source_location="p1 total", text="1180.00", extraction_confidence=HIGH),
        ),
        parsed_fields=(ParsedField(field_name="Total", extraction_confidence=HIGH),),
        missing_fields=(),
        human_capture=HumanCaptureEvidence(
            submitted_text=NOTE, stored=a_human_business_context(original_user_text=NOTE)
        ),
    )
    assert report.reliability_information == (
        "1 field(s) carry a confidence score from parser; "
        "0 of 1 region(s) reader attempted could not be read at all; "
        "0 of them were read but carry no per-region extraction score; "
        "0 field(s) parser recorded as missing; "
        "cleaner's preservation status: the cleaned representation is the safer "
        "basis for reading; "
        "human business context capture fidelity: matched the text as submitted, "
        "character for character."
    )
