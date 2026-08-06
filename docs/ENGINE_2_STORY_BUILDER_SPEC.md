# Engine 2 — Story Builder: Implementation Specification

> **Precedence level 3 — Engine Specifications.** Subordinate to [`SYSTEM_INVARIANTS.md`](SYSTEM_INVARIANTS.md) and to [`ENGINE_2_UNDERSTANDING_ENGINE_RULES.md`](ENGINE_2_UNDERSTANDING_ENGINE_RULES.md). Where this document contradicts either, this document is wrong and is revised.
>
> **Status: DESIGN ONLY. No implementation exists and none is authorized.** `CLAUDE.md` §P Amendment 4 is an **unsigned DRAFT** — *"THIS AMENDMENT IS NOT APPROVED AND RELEASES NOTHING."* `ENGINE_2_AUTHORIZED` in `tests/unit/test_package.py` is `frozenset()`, verified, so every path named below is refused by the freeze guard today. This document exists so that when the amendment is signed, implementation starts the same hour.
>
> **Base commit: `6fe2d8e`** — the commit that carries the `§M Amendment — Understanding Confidence Aggregation` in [`ACCOUNTING_DEFINITIONS.md`](ACCOUNTING_DEFINITIONS.md), which is this document's normative input.

---

## 0. What this document is, and what it is not

**It is** the complete construction rule for `story_builder`, the one Engine 2 sub-engine that needs no language model. Precise enough that two engineers implementing it independently produce the same bytes from the same six Results.

**It is not** a licence to build. It adds no rule to a locked document, resolves no undefined term, and sets no threshold. Where a rule is missing, §10 names the gap and stops — **an undefined term in a specification is a false statement waiting to be discovered** (Law 54), and inventing one here would plant exactly that.

**Every claim below about existing code was verified by reading it or by running it.** Observations are marked `MEASURED @ 6fe2d8e · LOCAL ONLY — NOT AUTHORITATIVE` (Law 44, Law 56). No CI result is quoted, because none exists for code that does not exist.

---

## 1. Mission and finish line

### 1.1 Mission

> Assemble the six Understanding Results into one Business Understanding Object, adding no fact, resolving no conflict, removing no unknown and raising no confidence.

### 1.2 Why this sub-engine can be built without a model

`ENGINE_2` §8.7 grants Story Builder exactly four powers — *"Combine the six sub-engine outputs · Organize information · Create the Transaction Story component · Create the Business Understanding Object"* — and forbids nine things, every one of which is a form of judgement: *"Change source observations · Override sub-engine results · **Resolve conflicts** · **Choose the "correct" interpretation when evidence disagrees** · **Remove unknowns** · **Increase confidence** · Create accounting conclusions · Add a fact no sub-engine produced · Use accounting vocabulary."*

What remains after the nine subtractions is **transcription and arithmetic**. Both are deterministic. That is the whole reason this component is separable from the six that need a model.

### 1.3 The measurable finish line (Law 52)

Story Builder is **not** measured by accuracy, and no accuracy claim about it is possible or permitted — `ACCOUNTING_DEFINITIONS.md` §2 makes understanding correctness a property measured against a frozen human ceiling, and `CLAUDE.md` §P records **`Ground truth — 25 documents, 2 accountants, frozen ceiling · ❌ None exists`**.

Story Builder's own finish line is a **count, and the count is zero**:

```
count(falsifiers in §8 that fire on CI)  ==  0
```

Sixteen falsifiers are listed in §8.3. Each is an executable predicate over a real assembled artifact. **The gate is `0`, with the unit *violations*.** It is not a threshold that can be approached; a single fire is a failed build (Law 55).

The **engine-level** number — `understanding correctness ≥ 80% of the frozen ceiling` (`ACCOUNTING_DEFINITIONS.md` §2) — is quoted here only to be explicit that it belongs to Engine 2 as a whole, is blocked on the ceiling, and **is not claimed by this component**.

---

## 2. Inputs and outputs

Every type below already exists in [`src/accountant_dad/artifacts/understanding.py`](../src/accountant_dad/artifacts/understanding.py), [`src/accountant_dad/confidence.py`](../src/accountant_dad/confidence.py) and [`src/accountant_dad/identity.py`](../src/accountant_dad/identity.py). **Nothing new is invented; where a type is missing, §10 says so rather than declaring one.**

### 2.1 The signature

```python
def assemble(
    *,
    transaction: TransactionUnderstandingResult,
    party: PartyUnderstandingResult,
    item: ItemUnderstandingResult,
    payment: PaymentUnderstandingResult,
    timeline: TimelineUnderstandingResult,
    business_context: BusinessContextResult,
    evidence_reliability: Decimal | UnmeasuredType,
    artifact_id: ArtifactId,
    transaction_id: TransactionId,
) -> BusinessUnderstandingObject: ...
```

**Keyword-only, and six separately typed Results rather than one container.** Two reasons, both structural:

1. **A missing Result becomes a `TypeError` at the call**, not a `None` that gets defaulted around. `ENGINE_2` §7 fixes the count at *"exactly seven"* sub-engines and §5 requires all six Results in Supporting Understanding Data; `understanding.py` already states *"All six are required. A missing Result is a sub-engine that did not run."* Python's own arity check is the cheapest possible enforcement and needs no code (Law 11: fail loudly).
2. **Six distinct types make a mis-wired call a type error.** Passing the Party Result where the Item Result belongs is refused by the typechecker, not by review.

> **A missing Result produces no artifact.** INV-4: *"Engine failure is not an artifact. An engine that cannot complete produces nothing — never a partial artifact."* The Application Layer records the runtime failure and may restart from the last completed artifact. Story Builder does not absorb it, does not substitute an empty Result, and does not narrate around it.

### 2.2 Inputs, by type

| Parameter | Type — already exists | What the type already validates |
|---|---|---|
| `transaction` | `TransactionUnderstandingResult` | `identified_event: Facts` · `unknown_information` · inherited `confidence: Confidence` and `conflicts_detected` · **`_a_result_reports_something`** — refuses a Result carrying no fact, no unknown and no conflict |
| `party` | `PartyUnderstandingResult` | `identified_entities` · `relationships` · `unknown_parties` · no field that could hold a merge or a chosen canonical party (`ENGINE_2:431`) |
| `item` | `ItemUnderstandingResult` | `identified_goods_and_services` · **`descriptions: StatedFacts`** — every entry must carry the document's own words (`_each_fact_quotes_the_document`) · `unknown_item_details` |
| `payment` | `PaymentUnderstandingResult` | `payment_method` / `payment_status` optional open text · `payment_references: StatedFacts` · `amount_relationships` · `unknown_payment_details` |
| `timeline` | `TimelineUnderstandingResult` | `dates: StatedFacts` — **never a parsed `datetime`**, so `01/08/2026` keeps both readings (`ENGINE_2:557`) · `event_sequence` · `time_relationships` · `missing_dates` |
| `business_context` | `BusinessContextResult` | `context_clues` · `business_purpose_indicators` · `unknown_context` |
| `evidence_reliability` | `Decimal \| UnmeasuredType` | `Decimal` in `[0.0000, 1.0000]`, ≤ 4 places, finite, never `float`/`int`; or one of `NotMeasuredType` / `NotApplicableType` / `MeasurementFailedType`, each carrying a non-blank `basis` |
| `artifact_id` | `ArtifactId` | UUIDv4, opaque (INV-9) |
| `transaction_id` | `TransactionId` | UUIDv4, opaque; created once by the Application Layer (INV-3, INV-4) |

Inside every Result, the leaf types are:

- **`ObservedFact`** — `statement: AuthoredText` (non-blank, vocabulary-checked) · `stated_text: StatedText | None` (verbatim, **never** vocabulary-checked, **never** trimmed) · `evidence_references: tuple[NonEmptyText, ...]`, and `_a_fact_names_its_evidence` refuses an empty tuple. *"A fact with no evidence reference cannot appear in a Result. There is no mechanism for producing one, and that is deliberate: it is the structural reason this engine cannot hallucinate"* — `COMMUNICATION_RULES_UNDERSTANDING_INTERNAL.md` Rule 5.
- **`Unknown`** — `subject: AuthoredText` · `why_it_matters: AuthoredText`. Both required and both vocabulary-checked.
- **`Conflict`** — `subject: AuthoredText` · `competing_readings: Facts`, with `_a_conflict_has_something_to_conflict` requiring **at least `MINIMUM_COMPETING_READINGS` (= 2)** distinct statements. There is no field for a resolution and `extra="forbid"` prevents one being added.

**`artifact_id` and `transaction_id` are supplied, never minted.** `ArtifactId.new()` is the one non-deterministic call this module could make, and calling it would destroy the property §4.6 rests on — *same inputs, identical bytes*. INV-9 makes supplying them free of consequence: a v4 UUID encodes nothing, so no reasoning can depend on where it came from. This copies the precedent already set by `engines/understanding_engine/stub.py`.

### 2.3 Output

Exactly one `BusinessUnderstandingObject`, with the four components `DATA_FLOW.md` §2.2 draws plus the universal identity envelope:

```
BusinessUnderstandingObject
├── identity                        IdentityEnvelope(artifact_id, version=FIRST_VERSION,
│                                                    parent_versions=(), transaction_id)
├── transaction_story               TransactionStory(narrative=<§4>)
├── supporting_understanding_data   SupportingUnderstandingData(the six Results, unaltered)
├── identified_unknowns             <§4.5 — a superset of all_unknowns>
└── confidence_assessment           ConfidenceAssessment(evidence_confidence,
                                                         understanding_confidence=<§3>)
```

`missing_information` and `detected_conflicts` — the third and fourth components `ENGINE_2` §11 names — are **derived properties on the artifact, never stored**. That is deliberate and it is what makes dropping a conflict inexpressible rather than merely forbidden.

**Always version 1, always no parents.** A correction (version ≥ 2) requires knowing which artifact it corrects, which is an input Story Builder is not given and may not guess (INV-5).

### 2.4 What Story Builder does NOT receive

`ENGINE_2` §8.7 says Story Builder receives *"All six preceding sub-engine Results, plus the Confidence Report within the Document Evidence Object."*

**It does not receive the Document Evidence Object itself.** It receives one number derived from the Confidence Report: `evidence_reliability`. Handing Story Builder the whole Document Evidence Object would give it a route to read a field the six Results did not report — which is the definition of *"Add a fact no sub-engine produced."* The narrowest possible input is the structural guard.

> **Who derives `evidence_reliability` is UNDEFINED and is an owner decision — §10, U-1.** It is not decided here.

---

## 3. The aggregation

### 3.1 The rule, verbatim from its source

`ACCOUNTING_DEFINITIONS.md` `§M Amendment — Understanding Confidence Aggregation`, approved by the owner 2026-08-06, normative from that date:

```text
Understanding Confidence = min(
    transaction_confidence,
    party_confidence,
    item_confidence,
    payment_confidence,
    timeline_confidence,
    business_context_confidence,
    evidence_reliability
)
```

Seven inputs. `evidence_reliability` is **inside** the `min`, and the amendment says why: *"so the existing ceiling `Understanding Confidence ≤ Evidence Reliability` holds **by construction** rather than by a second check that could be forgotten."*

**This is an equality, not a ceiling.** The distinction is the whole point of the amendment — *"A ceiling bounds a value; it does not produce one."*

### 3.2 One named function, and only one

The amendment's migration strategy requires it: *"The aggregation lives behind a single named function. No caller computes a confidence itself, and no caller is allowed to."*

```python
def understanding_confidence(
    *,
    transaction: Decimal | UnmeasuredType,
    party: Decimal | UnmeasuredType,
    item: Decimal | UnmeasuredType,
    payment: Decimal | UnmeasuredType,
    timeline: Decimal | UnmeasuredType,
    business_context: Decimal | UnmeasuredType,
    evidence_reliability: Decimal | UnmeasuredType,
) -> Decimal | UnmeasuredType: ...
```

Keyword-only over seven named slots, not a sequence, so a caller cannot pass six and cannot silently reorder them. `assemble` calls it exactly once and stores the result; no other code path in the repository computes an understanding confidence, and a test asserts that (§9.7).

### 3.3 `UNMEASURED` propagation — the exact rule

The amendment:

> **A missing required sub-engine output is NOT zero confidence. It is UNMEASURED.**
>
> ```text
> 0.0000       a measurement was taken and the answer was "no support"
> UNMEASURED   no measurement was taken; nothing is known
> ```
>
> `UNMEASURED` **must propagate forward.** It is never coerced to 0.0, never defaulted, and never dropped so an aggregate can be computed. A `min()` over a set containing `UNMEASURED` is `UNMEASURED`, not the smallest number present — otherwise a missing dimension would silently read as a measured weak one.

Stated as an algorithm over the four states `confidence.MeasurementState` already defines:

```
states := { measurement_state(x) for x in the seven inputs }

if states == { MEASURED }:
    return the arithmetic minimum of the seven Decimals
if the non-MEASURED states present number exactly one distinct kind:
    return an instance of that kind, carrying a basis built per §3.5
otherwise:
    REFUSE — raise. See §10, U-2.
```

**The middle branch chooses nothing.** When one and only one kind of absence is present among the inputs, the aggregate carries that same kind; there is no alternative to select, so no decision is made. This is a derivation from what is already written, offered so it can be argued with rather than assumed.

**The last branch refuses rather than picks.** When two inputs carry *different* absences — say `timeline` is `NOT_MEASURED` and `payment` is `FAILED` — no document says which the aggregate becomes. `confidence.records_the_same_measurement` already rules that *"different states DISAGREE ... including every pair of DIFFERENT non-measured states"*, and `ENGINE_2:673` says *"Never silently choose one answer."* Refusing is the only behaviour consistent with both. **It is a refusal, not a rule** — the rule is UNSET and belongs to the owner (§10, U-2).

### 3.4 Why coercing `UNMEASURED` to `0.0` is forbidden

Four reasons, and the fourth is the dangerous one.

1. **It is a false statement.** `0.0000` asserts that an instrument ran and found no support. When nothing ran, that assertion is fabricated data — Law 24, and `confidence.py` already refuses it at the type level (*"`0.0000` asserts a measured worthlessness nobody measured"*).
2. **It destroys a distinction the repository spent an amendment building.** `confidence.py` Amendment 7 carries four states precisely so that "nothing scored this" and "this scored zero" cannot wear one shape.
3. **It reads downstream as a measured weak dimension** — the amendment's own words. Engine 4 triages on doubts and Engine 5 on safety; a dimension reported as *measured and weak* is triaged differently from one reported as *never measured*, and the difference is which question a human gets asked.
4. **A coerced zero produces a structurally VALID artifact containing a false claim.** `0.0000` satisfies every ordering check in `understanding.py` trivially — it is at or below every ceiling, always. So the coercion would not be caught by any existing guard; it would sail through conformance and reach Engine 3 looking correct. That is the exact shape of failure §5 of `COMMUNICATION_RULES_UNDERSTANDING_INTERNAL.md` warns about: *"None of these fail loudly. They all produce output that looks better than the honest version."*

### 3.5 The `basis` on a propagated absence

`UnmeasuredType.__init__` refuses a blank `basis` — *"An absence with no stated reason is a gap that reads as a decision nobody made."* So the aggregate must carry one, and it must be deterministic.

**Construction rule.** The basis is the frozen prefix followed by the names of every non-measured input, in the **fixed seven-slot order of §3.1** (transaction · party · item · payment · timeline · business_context · evidence_reliability), joined by `", "`. Never in set order, never sorted at runtime.

```
"no measurement exists for: timeline, evidence_reliability"
```

The input `basis` strings are **not** concatenated into it: they are already carried on the input values, which travel inside the Results and the Confidence Report, and copying them would create a second copy that could drift (Law 19).

### 3.6 The builtin `min` cannot be used — measured, not assumed

```
MEASURED @ 6fe2d8e · LOCAL ONLY — NOT AUTHORITATIVE

min([UNMEASURED, Decimal("0.4"), Decimal("0.9")])   -> TypeError
min([Decimal("0.4"), UNMEASURED, Decimal("0.9")])   -> TypeError
min([Decimal("0.4"), Decimal("0.9"), UNMEASURED])   -> TypeError
UNMEASURED > Decimal("0.5")                          -> TypeError
Decimal("0.5") > UNMEASURED                          -> TypeError
bool(UNMEASURED)                                     -> TypeError
```

`UnmeasuredType` refuses ordering and truth on purpose. The consequence is good and worth naming: **there is no way to write the aggregation with the builtin `min` and have it quietly do the wrong thing.** The failure mode the amendment fears — *"the smallest number present"* — is not reachable by accident in this codebase; it would take deliberately stripping the absences out of the sequence first. §9.4 tests exactly that attack.

### 3.7 The ceiling still holds, and is still checked separately

The equality implies both ceilings. They are nevertheless enforced independently by `understanding.py`, and that redundancy is kept:

- `ConfidenceAssessment._understanding_never_exceeds_evidence` — `understanding_confidence > evidence_confidence` is refused (`ENGINE_2:756`).
- `BusinessUnderstandingObject._nothing_the_results_raised_was_lost` — every Result above `evidence_confidence` is refused, and `understanding_confidence` above `min(six Results)` is refused (`ENGINE_2:638` with INV-2).

**A defence that only exists inside the producer is a defence that disappears the first time someone writes a second producer.** The artifact keeps its own.

### 3.8 The gap this opens — the schema cannot hold an absence

```
MEASURED @ 6fe2d8e · LOCAL ONLY — NOT AUTHORITATIVE

ConfidenceAssessment(evidence_confidence=UNMEASURED, understanding_confidence=Decimal("0.5"))
    -> ValidationError: "confidence must be a Decimal, got NotMeasuredType"
ConfidenceAssessment(evidence_confidence=Decimal("0.5"), understanding_confidence=UNMEASURED)
    -> ValidationError: "confidence must be a Decimal, got NotMeasuredType"
```

`ConfidenceAssessment.evidence_confidence`, `ConfidenceAssessment.understanding_confidence` and `UnderstandingResult.confidence` are all annotated `Confidence`, which is `Decimal`-only.

> **The amendment's `UNMEASURED` propagation is, today, unrepresentable in the artifact it must reach.**

This is the single largest implementation item and it touches a built schema, not new code. What it requires, exactly:

| Change | Where | Why |
|---|---|---|
| `UnderstandingResult.confidence: ConfidenceOrUnmeasured` | `artifacts/understanding.py` | A sub-engine that did not run reports an absence, not a zero |
| `ConfidenceAssessment.evidence_confidence: ConfidenceOrUnmeasured` | same | The Confidence Report can itself be unmeasured — `reader.read_pdf_text_layer` sets `extraction_confidence=None` on **every** region of a PDF text layer, and a PDF text layer is the MVP's primary input |
| `ConfidenceAssessment.understanding_confidence: ConfidenceOrUnmeasured` | same | It is the output of a `min` that can be an absence |
| Rewrite three ordering validators to branch on `measurement_state` before comparing | same | `>` and `min` against an absence raise `TypeError` (measured, §3.6). Raising is correct behaviour and wrong plumbing: the artifact must *refuse with a reason*, not crash on a comparison |

**Scope note.** `artifacts/understanding.py` is an artifact schema, permitted by Amendment 2 (*"artifact schemas"* is on the exhaustive permitted list). It is therefore not blocked by the unsigned Amendment 4. **It is nevertheless not changed by this document** — this document is design only, and widening a slot on a schema six engines depend on is a change that should land with its tests, not ahead of them.

### 3.9 The second gap — the schema enforces a ceiling where the amendment states an equality

```
MEASURED @ 6fe2d8e · LOCAL ONLY — NOT AUTHORITATIVE

six Results at 0.9000 except transaction at 0.4000; evidence_confidence 0.9000
  understanding_confidence = 0.4000  (equal to the min)   -> ACCEPTED
  understanding_confidence = 0.1000  (BELOW the min)      -> ACCEPTED
```

The artifact accepts any value at or below `min(six, evidence)`. The amendment says the value **is** that minimum. So today **nothing structurally guards the amendment's own rule** — a Story Builder that emitted an arbitrary low number would produce a valid artifact.

Two ways to close it, and they are not equivalent:

1. **Conformance predicate (specified here, §8.3 F-04).** Assert `understanding_confidence == understanding_confidence(...)` over every assembled artifact. Cheap, catches Story Builder.
2. **Schema equality validator (recommended, out of scope here).** Move the check into `BusinessUnderstandingObject`, so *any* producer is caught, not just this one. This requires the artifact to know `evidence_reliability`, which it already does as `evidence_confidence`, and the six Result confidences, which it already carries — so the check is computable inside the artifact with no new field.

**Recommendation: both.** (2) is the structural fix and (1) is what proves the producer, not just the schema.

### 3.10 What confidence does NOT do

`MEASUREMENT_FRAMEWORK.md` §10: *"Until it passes this test, confidence is an ordinal ranking, not a probability, and it may gate **NOTHING**."* Separation ≥ 0.30 has not been measured, because there is no labelled data to measure it on.

The amendment's five posting conditions and its two thresholds are **explicitly UNSET** — *"no number is chosen here (Law 10, Law 52). Until they are set, condition 1 and condition 2 cannot be satisfied, and therefore **nothing auto-posts**."*

> **Story Builder computes the number and gates nothing with it.** No branch anywhere in `story_builder` reads `understanding_confidence` and changes behaviour. A test asserts this by ablation (§9.7).

---

## 4. The narrative

### 4.1 The problem, transformed (Law 53)

The direct problem — *"write one coherent prose account of a business event from six structured Results"* — is a generation problem. Solving it needs a model, and a model would be free to add a sentence no Result supports. `ENGINE_2:640` forbids exactly that: *"Add a fact no sub-engine produced."*

**The transform: do not compose. Transcribe.**

> **Every character of the narrative is either (a) copied verbatim from a string a sub-engine authored, or (b) drawn from a frozen constant table that asserts nothing about the business.**

Everything the component needs follows from that one rule, for free:

| Property | Why it holds |
|---|---|
| **No fact is added** | Nothing is synthesised. Category (b) strings are structural — headings and connectives — and a test asserts each of them names no business quantity, party, date or event |
| **No accounting vocabulary appears** | Every category (a) string is `AuthoredText` and has already passed `_authored_text`. Every category (b) string is checked once by a test against `FORBIDDEN_VOCABULARY` |
| **No conflict is resolved** | The renderer has no branch that selects among competing readings; it emits all of them (§5) |
| **No unknown is removed** | The renderer iterates `identified_unknowns` exhaustively and a falsifier counts them (§8.3 F-07) |
| **Determinism** | Concatenation of ordered material in a fixed order, with no clock, no randomness, no set iteration and no identifier read |

### 4.2 Section order — fixed, and not negotiable

```
1. What happened                      <- transaction
2. Who took part                      <- party
3. What moved                         <- item
4. How money moved                    <- payment
5. When                               <- timeline
6. How this sits in the business      <- business_context
7. Disagreements                      <- every Conflict, from every Result
8. What is not known                  <- identified_unknowns, in artifact order
9. Assembly                           <- incoherence findings (§6)
```

Sections 1–6 are the `SupportingUnderstandingData.results` tuple order, which is itself the dependency order `ENGINE_2` §7 and `COMMUNICATION_RULES_UNDERSTANDING_INTERNAL.md` §2 both draw. **The order is load-bearing there and is reused rather than re-chosen** (Law 19).

**Every section is always emitted, including empty ones.** An absent section is indistinguishable from an omitted one, and `ENGINE_2:884` states the asymmetry the whole engine leans on — *"a story that is incomplete and honestly marked is a success. A complete, coherent story built on one quiet assumption is a failure."* A missing "How money moved" heading reads as *nothing to say*; the frozen empty-section line reads as *nothing was established*, which is the true statement.

### 4.3 The grammar, exactly

```
narrative      := section  ( "\n\n" section )*                 sections 1..9, no trailing newline
section        := heading  "\n"  body
heading        := a frozen string from HEADINGS
body           := result_body | conflicts_body | unknowns_body | assembly_body

result_body    := NOTHING_ESTABLISHED                          when the Result states no component fact
                | statement ( "\n" statement )*                otherwise

conflicts_body := NO_DISAGREEMENT                              when all_conflicts is empty
                | ORDER_CARRIES_NO_PREFERENCE "\n" conflict ( "\n" conflict )*

conflict       := subject "\n" reading ( "\n" reading )* "\n" UNRESOLVED
reading        := "- " statement

unknowns_body  := unknown ( "\n" unknown )*                    identified_unknowns is never empty when
                                                               any Result named a gap; when it IS empty,
                                                               NOTHING_UNKNOWN is emitted
unknown        := subject " — " why_it_matters

assembly_body  := COHERENT                                     when no §6 predicate fired
                | finding ( "\n" finding )*                    one frozen line per fired predicate
```

Where `statement` is `ObservedFact.statement`, `subject` is `Conflict.subject` or `Unknown.subject`, and `why_it_matters` is `Unknown.why_it_matters` — each copied **verbatim, byte for byte, with no trimming, no case change, no Unicode normalisation and no punctuation repair.** Those strings are a sub-engine's output and `COMMUNICATION_RULES_UNDERSTANDING_INTERNAL.md` Rule 3 makes them read-only to Story Builder: *"A Result is **read-only** to every sibling, permanently ... This holds for Story Builder too. Assembly is not permission to edit."*

### 4.4 The separator must contain a non-word character — measured

```
MEASURED @ 6fe2d8e · LOCAL ONLY — NOT AUTHORITATIVE

"".join(["the amount is ta", "x free"])     -> "the amount is tax free"    REFUSED (mints `tax`)
"\n".join(["the amount is ta", "x free"])   -> accepted
". ".join(["the amount is ta", "x free"])   -> accepted
```

`FORBIDDEN` is a `\b`-anchored regex, so a forbidden word can be **created** at a join point when the separator is empty. Two individually clean statements would then produce a narrative the artifact refuses — a defect that surfaces only on the specific pair of strings that triggers it.

> **Rule: every separator in §4.3 is `"\n"`, `"\n\n"`, `" — "` or `"- "`. Every one of them contains a character outside `\w`, so no join can mint a word.** A test asserts this over the separator constants themselves, so a future edit to a separator is caught by the constant test rather than by a rare input.

### 4.5 `stated_text` never enters the narrative

`ObservedFact.stated_text` is the document's own words, verbatim, and is deliberately **not** vocabulary-checked — filtering it would modify evidence. `TransactionStory.narrative` **is** `AuthoredText` and **is** vocabulary-checked. The two are incompatible:

```
MEASURED @ 6fe2d8e · LOCAL ONLY — NOT AUTHORITATIVE

ObservedFact(statement="The document names a party.",
             stated_text="Ledger Solutions Pvt Ltd", ...)              -> ACCEPTED
TransactionStory(narrative='The party is stated on the document as
                            "Ledger Solutions Pvt Ltd".')              -> REFUSED
      ValidationError: accounting vocabulary in authored text: ledger
```

A supplier genuinely named *Ledger Solutions Pvt Ltd* is an ordinary Indian company name, and quoting it into the narrative **refuses the entire artifact**.

> **Rule: the narrative copies `ObservedFact.statement` and never `ObservedFact.stated_text`.**

Nothing is lost. `ENGINE_2` §5 is explicit that both travel — *"Both travel, so a downstream engine may read the narrative or the underlying records"* — and the document's own words remain in `supporting_understanding_data`, where `StatedText` protects them from being trimmed or filtered. The narrative is prose for a human; the Results are the record.

**This is a real constraint on the six sub-engines, and it belongs in their specifications when they are written:** a `statement` is the engine's own summary of a fact and must stand on its own, because it is the only part of the fact the narrative can carry.

### 4.6 Determinism — the requirement and its proof

> **Same inputs, identical bytes. Not "equivalent output" — the same `bytes`.**

Everything the renderer walks is already ordered and already stable:

```
MEASURED @ 6fe2d8e · LOCAL ONLY — NOT AUTHORITATIVE

TransactionUnderstandingResult  ['confidence','conflicts_detected','identified_event','unknown_information']
PartyUnderstandingResult        ['confidence','conflicts_detected','identified_entities','relationships','unknown_parties']
ItemUnderstandingResult         ['confidence','conflicts_detected','identified_goods_and_services','descriptions','unknown_item_details']
PaymentUnderstandingResult      ['confidence','conflicts_detected','payment_method','payment_status','payment_references','amount_relationships','unknown_payment_details']
TimelineUnderstandingResult     ['confidence','conflicts_detected','dates','event_sequence','time_relationships','missing_dates']
BusinessContextResult           ['confidence','conflicts_detected','context_clues','business_purpose_indicators','unknown_context']

Result.facts order   : component facts in field-declaration order, THEN every
                       conflict's competing readings, in conflict order
                       observed: ['alpha','beta','fifty thousand','forty-five thousand']
evidence union       : first-appearance order, no sorting  ('e1','e2','e3','e4')
all_unknowns         : results-tuple order, then within-Result declaration order
                       50 rebuilds -> 1 distinct ordering

full derived-view digest, PYTHONHASHSEED=0          -> ac89046b4af7544b38cf059aed1e244342aedfca935a2dfb9423e634e2c0b996
full derived-view digest, PYTHONHASHSEED=987654321  -> ac89046b4af7544b38cf059aed1e244342aedfca935a2dfb9423e634e2c0b996
```

No set is iterated on any path that reaches output ordering. Nothing is sorted at runtime. No dictionary whose insertion order is not the declaration order is walked.

**Forbidden in the renderer, by rule and by test:** `set` / `frozenset` iteration · `sorted()` without an explicit total key · `datetime.now` · `random` · `uuid` · reading `artifact_id` or `transaction_id` · any environment variable · any file · any locale-sensitive call (`str.title`, `str.capitalize`, locale collation) · Unicode normalisation.

### 4.7 Separating component facts from conflict readings

A Result's `facts` property **includes** its conflicts' competing readings (measured, §4.6). Rendering `facts` directly into a Result section would print two contradictory readings as two flat statements — **presenting a conflict as agreement**, which is the one thing §10 of `ENGINE_2` exists to prevent.

The Result section must render **component facts only**. Two ways, and the first is better:

1. **Recommended.** Add a derived `component_facts` property to `UnderstandingResult` alongside `facts`, computed the same way `facts` already is. One source of truth (Law 19), no arithmetic in the caller. This is a schema change and is **out of scope for this document**; it is named because it is the right shape.
2. **Fallback, if (1) is not authorized.** Use the documented shape of `facts` directly:

   ```python
   readings = sum(len(c.competing_readings) for c in result.conflicts_detected)
   component_facts = result.facts[: len(result.facts) - readings]
   ```

   This is exact and deterministic, and it couples the renderer to the internal layout of `facts`. **It is therefore guarded by its own regression test** (§9.3 T-13), which builds a Result with facts in several components plus two conflicts and asserts the slice equals the component facts by value. If `facts` ever changes shape, that test goes red before anything else does.

**Do not filter by `id()` and do not filter by value.** Both break under aliasing — the same `ObservedFact` object legitimately appearing both as a component fact and as a competing reading would be wrongly dropped by the first, and a value-identical pair by the second.

### 4.8 The frozen constant table

Every category (b) string lives in one module-level table, and every entry is covered by the constant tests in §9.2.

| Name | Purpose |
|---|---|
| `HEADINGS` | the nine section headings of §4.2, as an ordered tuple |
| `NOTHING_ESTABLISHED` | body of a Result section that carries no component fact |
| `NO_DISAGREEMENT` | body of the Disagreements section when `all_conflicts` is empty |
| `ORDER_CARRIES_NO_PREFERENCE` | the sentence that removes ordering as a signal (§5.3) |
| `UNRESOLVED` | closes each conflict block |
| `NOTHING_UNKNOWN` | body of the unknowns section when `identified_unknowns` is empty |
| `COHERENT` | body of the Assembly section when no §6 predicate fired |
| `INCOHERENCE_LINES` | one frozen line per §6 predicate, for the Assembly section |
| `INCOHERENCE_UNKNOWNS` | the `subject` and `why_it_matters` of the `Unknown` §6.6 adds per predicate. **These are Story-Builder-authored strings that reach the narrative**, so they belong in this table or F-08 fires on them |
| `SEPARATORS` | `("\n", "\n\n", " — ", "- ")` — the §4.4 non-word-character guarantee |

### 4.9 The narrative is prose, never a format

Nothing downstream parses it. `ACCOUNTING_DEFINITIONS.md` §2 defines understanding correctness by *"a qualified accountant reading only the Transaction Story"* — the audience is a human. Engine 3 reads `supporting_understanding_data`, `identified_unknowns` and `confidence_assessment` for structure.

**Consequence, stated so nobody relies on the wrong thing:** a `Conflict.subject` that happens to equal a section heading is cosmetically confusing and structurally harmless. No parser exists to be confused. Do not add one, and do not escape or namespace headings to make one possible — that would make the narrative a wire format, and a wire format is a second representation of what `supporting_understanding_data` already carries (Law 14).

---

## 5. Conflict handling

### 5.1 The rule

`ENGINE_2` §10 Rule 1: *"**Never silently choose one answer.** A conflict is information. Resolving it by preference destroys the one signal that would have told a human something was wrong."*

§8.7 failure behaviour: *"Where the Results disagree, the narrative reports the disagreement rather than selecting a reading — a story containing an unresolved conflict is the correct output, not a failure."*

### 5.2 What the structure already guarantees

- `Conflict` has fields `subject` and `competing_readings` and **nothing else**; `extra="forbid"` means a resolution cannot be bolted on.
- `_a_conflict_has_something_to_conflict` requires ≥ 2 readings with distinct statements — *"one reading is a resolved conflict wearing the label."*
- `BusinessUnderstandingObject.detected_conflicts` is a **derived** view over `supporting_understanding_data.all_conflicts`. It cannot be set, so it cannot be shortened.

> **The only place a conflict could be lost is the narrative.** That is what §5.3 and falsifier F-06 exist for.

### 5.3 What the narrative says when Results disagree

For every `Conflict` in `supporting_understanding_data.all_conflicts`, in **results-tuple order then within-Result conflict order**:

```
<conflict.subject>
- <competing_readings[0].statement>
- <competing_readings[1].statement>
- ...
<UNRESOLVED>
```

preceded once, at the top of the section, by `ORDER_CARRIES_NO_PREFERENCE`.

Three rules make this a report rather than a resolution:

1. **Every reading is rendered.** No truncation, no "and 2 others", no cap. A cap is a resolution with a length limit.
2. **Every reading carries the identical marker `"- "`.** Numbering would rank them; a first/second distinction is a preference expressed by layout.
3. **`ORDER_CARRIES_NO_PREFERENCE` says out loud that the order is the sub-engine's tuple order and means nothing.** Without it, "first" reads as "preferred" to a human, and the human is the audience.

**`UNRESOLVED` closes the block** and states that the Understanding Engine did not settle it and cannot — `ENGINE_2` §10: *"It does not return a resolution, because resolving requires information the engine does not have."*

### 5.4 The banned-connective list

A test asserts that **no** string in the frozen constant table contains any of:

```
likely · probably · appears to be · more consistent · the correct · correct reading ·
we take · take the · prefer · preferred · instead · rather than · supersedes ·
overrides · resolved · resolves · settled · chosen · we conclude · most plausible ·
best fit · on balance
```

The list is a **necessary and knowingly not sufficient** check, in exactly the sense `understanding.py` already applies to `FORBIDDEN_VOCABULARY`: a paraphrase walks through it. What it does catch is the drift that actually happens — an engineer softening a blunt frozen line into a readable one, six months from now, and turning a report into a recommendation without noticing.

### 5.5 Zero conflicts

`NO_DISAGREEMENT` is emitted. The section is never omitted. *"No disagreement was recorded"* and *"the disagreement section is missing"* are different statements to a reader, and only one of them is true.

### 5.6 What Story Builder cannot see, and must not pretend to

Two Results naming different buyers is a contradiction **between** Results. Story Builder cannot detect it — detecting it requires understanding that two names refer to two entities, which is comprehension, and Story Builder has none.

The architecture already places that job elsewhere. `COMMUNICATION_RULES_UNDERSTANDING_INTERNAL.md` Rule 3: *"A sub-engine that believes a sibling's Result is wrong does not correct it. It records the disagreement in its own Result as a **conflict**."* The sub-engine that *can* see it is the one that reads the sibling's Result — `business_context`, which receives the preceding five, or any of party/item/payment/timeline, which receive the Transaction Result.

> **A cross-Result contradiction that no sub-engine recorded is invisible to Story Builder, permanently. This is a known blind spot, not a gap to be filled here.** Filling it would require Story Builder to compare the meaning of two statements, which is precisely *"Choose the 'correct' interpretation when evidence disagrees"* wearing a different hat.

---

## 6. Incoherence, defined measurably

### 6.1 The requirement and the trap

`ENGINE_2` §8.7: *"Where the six Results cannot be made into a coherent narrative at all, that incoherence is itself reported, with the Results preserved unchanged beneath it."*

**"Cannot be made into a coherent narrative" is an undefined term** and Law 54 forbids building on one. It is also not resolvable by asking harder: the direct reading — *does this read as one sensible account?* — is a comprehension question, and Amendment 4 forbids a model inside this component.

### 6.2 The transform

Under §4's transcription rule, a narrative is **always** constructible from any six valid Results. Concatenation does not fail. So "cannot form a coherent narrative" cannot mean *assembly failed* — assembly never fails.

> **It must mean: a property of the six Results, decidable by counting, that leaves the narrative unable to carry the event.**

That is the easier equivalent problem (Law 53). It is answerable with arithmetic.

### 6.3 The definition

Exactly two predicates are decidable without comprehension and without a threshold.

**I-1 · Nothing was established.**

```
sum(len(component_facts(r)) for r in the six Results) == 0
```

No Result states a single fact. Every one of them named only gaps or conflicts. The narrative then contains no statement about the business at all — sections 1–6 are six copies of `NOTHING_ESTABLISHED`. `ENGINE_2` §8.7's purpose clause says what must not be handed on: *"The Accounting Engine must receive one coherent account of events, not six fragments."* Six empty fragments is the limiting case.

**I-2 · No base event.**

```
len(component_facts(transaction)) == 0
  AND  sum(len(component_facts(r)) for r in the other five) > 0
```

`ENGINE_2` §7 makes the Transaction Result the anchor the other five enrich: *"Transaction Understanding establishes the base event; the other components enrich it. The same name on a document means a different thing on a purchase than on a sales return, and the same date means a different thing on an invoice than on a receipt."*

Five enrichments of an event that was never established are, precisely, *six fragments*. A reader of the story alone — the audience `ACCOUNTING_DEFINITIONS.md` §2 defines — cannot reach any treatment from *who, what, how, when and why* with no *what happened*.

Both predicates are **counts of facts**. Neither needs a threshold, a model, a calibration or a judgement. Both are computable in one pass.

### 6.4 Necessary, and knowingly not sufficient

> **These two predicates catch a real class of incoherence. They do not catch all of it, and no arithmetic over these Results can.**

What escapes, named so it is visible rather than assumed away:

- Six Results, each internally fine, that jointly describe two different transactions.
- A Transaction Result naming a sale while every other Result describes a purchase.
- Facts that are individually true and jointly impossible — a payment dated before the goods that were paid for.

Each of those needs comprehension. Each is, correctly, a **conflict** that a sub-engine with the sibling Result in hand should have recorded (§5.6). Where no sub-engine recorded it, it travels silently, and Story Builder is not the layer that catches it.

**Stating this is the point.** The same honesty is already written into `understanding.py` about the vocabulary check — *"NO ACCOUNTING VOCABULARY — a NECESSARY check, and knowingly not a SUFFICIENT one ... A string check cannot prove the absence of accounting reasoning."* A predicate presented as sufficient when it is only necessary is a false green.

### 6.5 A predicate that was designed and then falsified — recorded, not hidden

**Rejected: I-3, total evidential disjunction.** *"The six Results cite no evidence reference in common, so they did not describe one transaction."*

It was falsified against the normal case before it was written down. `party` citing `d1:vendor_block` and `timeline` citing `d1:invoice_date` are two references into one document, and they are disjoint. The predicate fires on **healthy input**, constantly.

Restating it over *documents* rather than references does not rescue it: the artifact deliberately carries no document-id list — *"Which ones is answered by the evidence references its facts cite, not by a list of document identifiers — a second list could disagree with the first"* — and grouping references by document would require parsing their format, **which no document defines** (§10, U-5).

Recorded here because a rejected predicate with its falsifier is worth more than a silent omission: it stops the next engineer from rediscovering and shipping it.

### 6.6 How incoherence is reported

**Two places, and one of them is structural.**

1. **In the narrative.** The Assembly section (§4.2, section 9) carries one frozen `INCOHERENCE_LINES` entry per fired predicate, and `COHERENT` when none fired.
2. **As an `Unknown` in `identified_unknowns`.** One per fired predicate, with a frozen `subject` and `why_it_matters`.

The second matters because `SPEC_GAPS` in `understanding.py` already records the hole: *"`TransactionStory` — `ENGINE_2:645` requires incoherence be reported and names no field; it is reported in the narrative only"* — and prose is not readable by Engine 4's triage. Adding an `Unknown` makes it structurally readable **without adding a field to a locked artifact**, which would be an architecture change requiring §M.

### 6.7 Why adding an `Unknown` is permitted where adding a fact is not

§8.7 forbids *"Add a fact no sub-engine produced."* An `Unknown` is not a fact — `ObservedFact` is the fact type, and `Unknown` is a named gap with a separate class, separate fields and no evidence references.

The permission is already structural, not remembered:

- `BusinessUnderstandingObject._nothing_the_results_raised_was_lost` checks that `identified_unknowns` is a **superset** of `all_unknowns`. It refuses drops; it permits additions. `tests/unit/test_understanding.py::test_story_builder_may_add_an_unknown_no_sub_engine_raised` proves it.
- `understanding.py` says why in as many words: *"A superset is allowed: `:645` also requires Story Builder report an incoherence no sub-engine could have raised."*
- Facts, by contrast, live only inside Results, which are frozen and copied unaltered. **Story Builder has no route to add one.**

> **Story Builder may add a gap. It may never add a fact. The schema enforces both halves.**

### 6.8 Incoherence is not a failure

An incoherent assembly still produces an artifact. `COMMUNICATION_RULES_UNDERSTANDING_ENGINE.md` item 9: *"The Understanding Engine does not halt the pipeline. Gaps, conflicts and low confidence cross the boundary **as named unknowns and preserved conflicts**, not as errors."*

The six Results are carried into `supporting_understanding_data` **unaltered** — which they are by construction, since the frozen models are copied by reference and cannot be edited.

---

## 7. Failure modes and edge cases

Every row is either enforced by an existing validator (**S** — structural, already true) or is a rule this specification adds (**R**).

| # | Case | Behaviour | Basis |
|---|---|---|---|
| E-01 | All six Results state zero facts | Artifact produced. I-1 fires. Assembly section names it; one `Unknown` added | **R** §6.3 |
| E-02 | Transaction Result states no fact, others do | Artifact produced. I-2 fires | **R** §6.3 |
| E-03 | A Result carries no fact, no unknown and no conflict | **Refused by `_a_result_reports_something`** before Story Builder is reached | **S** |
| E-04 | One Result missing | `TypeError` at the call. No artifact. INV-4 — engine failure is not an artifact | **R** §2.1 |
| E-05 | Seven Results / an extra Result | `TypeError` (unexpected keyword). `SupportingUnderstandingData` also forbids extras | **S** + **R** |
| E-06 | All seven confidences `UNMEASURED`, one kind | Aggregate is that kind, with the §3.5 basis. **Unrepresentable in the artifact today** — §3.8 | **R** §3.3 |
| E-07 | Confidences carry two *different* absences | **Refuse and raise.** The rule is UNSET (§10, U-2). Never pick | **R** §3.3 |
| E-08 | One confidence absent, six measured | Aggregate is the absence, **not** the minimum of the six | **R** §3.3 |
| E-09 | Someone strips absences before the `min` to make it compute | Caught by falsifier F-05 and adversarial test A-3 | **R** §9.4 |
| E-10 | A Result more confident than `evidence_reliability` | **Artifact refuses**, naming the Result and both numbers. Not absorbed, not clamped | **S** |
| E-11 | `evidence_reliability` below every Result confidence | The `min` is `evidence_reliability`; but E-10 fires first and the artifact refuses. **Story Builder raises rather than lowering a Result** | **S** |
| E-12 | Two Results raise structurally identical `Unknown`s | **Both carried, in `all_unknowns` order, no de-duplication.** §7.1 | **R** |
| E-13 | A conflict's competing readings number 1, or 0 | **Refused by `_a_conflict_has_something_to_conflict`** before Story Builder is reached | **S** |
| E-14 | An `Unknown` with a blank or missing `subject` | **Refused by `AuthoredText`** at Result construction | **S** |
| E-15 | A document genuinely names a party *"Ledger Solutions"* | Recorded in `ObservedFact.stated_text`, which is never checked. **Never quoted into the narrative** (§4.5) | **S** + **R** |
| E-16 | A sub-engine authors a `statement` containing banned vocabulary | **Refused by `AuthoredText`** at Result construction. Story Builder never sees it | **S** |
| E-17 | Joining two clean statements would mint a banned word | Impossible: every separator contains a non-word character (§4.4), asserted by a constant test | **R** |
| E-18 | A `Conflict.subject` equals a section heading | Cosmetic only. Nothing parses the narrative (§4.9). No escaping, no namespacing | **R** |
| E-19 | Statements contain RTL text, emoji, combining marks, control characters | Copied verbatim. **No Unicode normalisation, ever** — normalising modifies a string the sub-engine authored (Rule 3) | **R** §4.3 |
| E-20 | Zero conflicts anywhere | `NO_DISAGREEMENT` emitted. Section never omitted | **R** §5.5 |
| E-21 | `identified_unknowns` would be empty | `NOTHING_UNKNOWN` emitted. Possible only when all six Results carry facts or conflicts and no gaps | **R** §4.3 |
| E-22 | Narrative grows very large | **No bound is specified anywhere and none is invented here** — §10, U-7 | — |
| E-23 | Empty evidence batch, or a batch spanning two Transaction IDs | Out of scope. Handled at the engine boundary before Story Builder — see `EvidenceBatchRejectedError` in `engines/understanding_engine/stub.py` | — |
| E-24 | A caller passes `artifact_id` twice for two different assemblies | Not detectable here and not Story Builder's concern. INV-9: an identifier influences nothing | — |
| E-25 | Two Results name different buyers, no sub-engine recorded a conflict | **Invisible. Known blind spot** (§5.6). Not detected, not guessed, not narrated as agreement | **R** |

### 7.1 On E-12 — why identical unknowns are both carried

`Unknown` is a frozen pydantic model, so it is hashable and equal by value.

```
MEASURED @ 6fe2d8e · LOCAL ONLY — NOT AUTHORITATIVE
two structurally identical Unknowns:  equal=True  hashable=True
```

The artifact's validator builds `carried = set(self.identified_unknowns)` and tests membership, so carrying **one** copy where two Results raised the same `Unknown` would pass. De-duplication is therefore *permitted* by the schema.

**It is nevertheless forbidden here.** De-duplicating asserts that two gaps naming the same subject are the same gap. `Unknown` equality is structural, not semantic — two sub-engines can name the same subject for different reasons and their `why_it_matters` may differ by a word while meaning two things. Collapsing them is a judgement, and *"Remove unknowns"* is on the forbidden list.

> **Carry all of them, in `all_unknowns` order. Removing nothing is the only option that removes nothing.**

The counter-position, stated so it can be argued rather than discovered: a reader sees the same line twice, which is noise. That cost is one duplicated line. The cost of the other choice is a dropped gap. §K/§L of `CLAUDE.md` and the amendment's own trade-off section both say the same thing about asymmetric costs.

---

## 8. Invariants and falsifiers

### 8.1 The invariants

| # | Invariant | Source |
|---|---|---|
| SB-1 | The six Results reach `supporting_understanding_data` **unaltered** | `UNDERSTANDING_INTERNAL:148` |
| SB-2 | `identified_unknowns` is a **superset** of `all_unknowns` | `ENGINE_2:645` · schema validator |
| SB-3 | Every `Conflict` in `all_conflicts` appears in the narrative, with **every** competing reading | `ENGINE_2:673` |
| SB-4 | `understanding_confidence == understanding_confidence(seven inputs)` | §M amendment |
| SB-5 | An absent input propagates as an absence, never as `0.0000` and never as the smallest number present | §M amendment |
| SB-6 | Every character of the narrative is a copied authored string or a frozen constant | `ENGINE_2:640` |
| SB-7 | The narrative contains no accounting vocabulary | `ENGINE_2:641` · `AuthoredText` |
| SB-8 | Same inputs → identical narrative bytes | §4.6 |
| SB-9 | No branch anywhere reads `understanding_confidence` and changes behaviour | `MEASUREMENT_FRAMEWORK.md` §10 |
| SB-10 | `stated_text` never appears in the narrative | §4.5 |
| SB-11 | Story Builder adds no `ObservedFact` — anywhere, ever | `ENGINE_2:640` |
| SB-12 | Incoherence, when detected, is reported both in prose and as an `Unknown` | `ENGINE_2:645` |

### 8.2 Rollback

Story Builder is a pure function with no state, no I/O and no persistence. **Rollback is reverting the commit**, and there is nothing to undo beyond that. It ships behind the same freeze guard as the rest of Engine 2: until `ENGINE_2_AUTHORIZED` names its path, the module cannot exist; removing the path from that list is a one-line revert that re-freezes it.

### 8.3 The falsifiers

Sixteen. Each is the observation that would prove its invariant violated. **The finish line (§1.3) is that all sixteen count zero.**

| # | Invariant | The observation that proves it violated |
|---|---|---|
| F-01 | SB-1 | Any Result reachable from the artifact is not `==` to the Result passed in |
| F-02 | SB-2 | An `Unknown` in `all_unknowns` is absent from `identified_unknowns` |
| F-03 | SB-2 | `len(identified_unknowns) < len(all_unknowns)` when no `Unknown` repeats |
| F-04 | SB-4 | `confidence_assessment.understanding_confidence != understanding_confidence(...)` recomputed from the seven inputs |
| F-05 | SB-5 | Any input is non-`MEASURED` and the result is `MEASURED` |
| F-06 | SB-3 | `count(conflict subjects in narrative) != len(all_conflicts)`, or any `competing_readings[i].statement` is absent from the narrative |
| F-07 | SB-2 | `count(unknown subjects in narrative) != len(identified_unknowns)` |
| F-08 | SB-6 | A maximal substring of the narrative, after removing every frozen constant and every separator, is not equal to some authored string of some Result |
| F-09 | SB-7 | `TransactionStory(narrative=...)` raises `ValidationError` for any assembly built from valid Results |
| F-10 | SB-8 | Two assemblies from equal inputs produce narratives that differ in any byte |
| F-11 | SB-8 | The narrative differs between two runs under different `PYTHONHASHSEED` |
| F-12 | SB-9 | Changing only `understanding_confidence` changes any other byte of the artifact (ablation) |
| F-13 | SB-10 | Any `ObservedFact.stated_text` in any Result appears as a substring of the narrative, when that text does not also appear in some `statement` |
| F-14 | SB-11 | `sum(len(r.facts) for r in artifact...results)` differs from the same sum over the inputs |
| F-15 | SB-12 | A §6 predicate holds over the inputs and the Assembly section reads `COHERENT`, or no matching `Unknown` was added |
| F-16 | SB-5 | The aggregate is `Decimal("0.0000")` while any input is non-`MEASURED` |

**F-08 is the strongest and the hardest.** It is the executable form of *"adds no fact"*: strip every frozen constant and separator from the narrative, and every remaining fragment must be, verbatim, a string some Result authored. A single invented word fails it. It is written as a set-difference assertion, not a regex.

---

## 9. Test strategy

Test-first, per `CLAUDE.md` §J.1: each test is written, watched **fail for the right reason**, and only then made to pass. A test that passed on the first run is the wrong test.

Files: `tests/unit/test_story_builder.py` (T-series) and `tests/unit/test_story_builder_redteam.py` (A-series), following the naming already used for every Engine 1 module.

### 9.1 The aggregation — T-01 … T-09

| # | Assertion |
|---|---|
| T-01 | Seven measured inputs, distinct values → the result **equals the arithmetic minimum**, exactly, as a `Decimal` |
| T-02 | The minimum is supplied by **each of the seven slots in turn** — seven parametrised cases. Catches a slot dropped from the computation |
| T-03 | Six at `1.0000`, `evidence_reliability` at `0.3000` → result is `0.3000`. The ceiling holds **by construction**, not by a second check |
| T-04 | All seven equal → that value. No drift, no rescaling, no rounding |
| T-05 | Fewer than four decimal places are preserved verbatim: `Decimal("0.5")` in → `Decimal("0.5")` out, not `0.5000` |
| T-06 | One input `NOT_MEASURED`, six measured → `measurement_state(result) is NOT_MEASURED`. Parametrised over all seven positions |
| T-07 | Same, for `NOT_APPLICABLE` and for `FAILED` |
| T-08 | Two inputs with **different** absence kinds → **raises**, and the message names both kinds |
| T-09 | The propagated `basis` names every non-measured input, in the fixed §3.1 order, and is byte-identical across two calls |

### 9.2 The frozen constants — T-10 … T-12

| # | Assertion |
|---|---|
| T-10 | Every constant passes `_authored_text` — i.e. contains no term from `FORBIDDEN_VOCABULARY` or `FORBIDDEN_PLURALS`, checked against the **imported** tables, never a copy |
| T-11 | Every entry of `SEPARATORS` contains at least one character outside `\w`. The §4.4 mint-a-word guarantee |
| T-12 | No constant contains any term from the §5.4 banned-connective list, case-insensitively |

### 9.3 The narrative — T-13 … T-24

| # | Assertion |
|---|---|
| T-13 | **The `component_facts` slice guard** (§4.7). A Result with facts in three components plus two conflicts of two readings each: the slice equals the component facts, by value, in declaration order. Goes red if `facts` ever changes shape |
| T-14 | All nine section headings appear, in §4.2 order, exactly once each |
| T-15 | A Result with zero component facts renders `NOTHING_ESTABLISHED` under its own heading — and the other five sections are unaffected |
| T-16 | Every `statement` of every component fact appears verbatim in the narrative |
| T-17 | **F-08.** Strip every frozen constant and every separator; every remaining fragment is an authored string of some Result. Asserted as a set difference, and the failure message prints the orphan fragment |
| T-18 | **F-13.** A Result carrying `stated_text="Ledger Solutions Pvt Ltd"` assembles successfully, and that string is **absent** from the narrative |
| T-19 | **F-10.** Two `assemble` calls with equal inputs → `narrative_a == narrative_b`, and the full `model_dump_json()` is byte-identical apart from the supplied identifiers |
| T-20 | **F-11.** The narrative digest is equal under `PYTHONHASHSEED` `0` and `987654321`, run as two subprocesses |
| T-21 | No trailing whitespace on any line; no trailing newline on the narrative |
| T-22 | A statement containing RTL text, an emoji, a combining mark and a `\t` survives byte-identically. No normalisation |
| T-23 | The narrative is non-blank for the minimal legal input — six Results each naming exactly one gap — because the headings alone satisfy `AuthoredText` |
| T-24 | **F-14.** Total fact count across the artifact's six Results equals the total across the six inputs |

### 9.4 Conflicts — T-25 … T-30

| # | Assertion |
|---|---|
| T-25 | **F-06.** Conflicts in three different Results → all three subjects and all six readings appear; the count matches `len(all_conflicts)` |
| T-26 | A conflict with five competing readings → **all five** appear. No truncation, no cap |
| T-27 | Every reading carries the identical `"- "` marker. **No numbering, no ordinal, no "first"/"second"** |
| T-28 | `ORDER_CARRIES_NO_PREFERENCE` appears exactly once, before the first conflict |
| T-29 | `UNRESOLVED` appears once per conflict |
| T-30 | Zero conflicts → `NO_DISAGREEMENT`, and the Disagreements heading is still present |

### 9.5 Unknowns and incoherence — T-31 … T-38

| # | Assertion |
|---|---|
| T-31 | **F-02.** Every `Unknown` from every Result reaches `identified_unknowns` |
| T-32 | **F-07.** Every `Unknown.subject` and every `why_it_matters` appears in the narrative |
| T-33 | **E-12.** Two Results raising structurally identical `Unknown`s → **both** are carried; `len(identified_unknowns) == len(all_unknowns)` |
| T-34 | **I-1.** All six Results with zero facts → the Assembly section names I-1 and an `Unknown` for it is present |
| T-35 | **I-2.** Transaction Result with zero facts, other five with facts → I-2 named; `Unknown` present |
| T-36 | **I-2 negative.** Transaction Result with one fact, all others empty → **I-2 does not fire.** The predicate is not "most Results are empty" |
| T-37 | **F-15.** No predicate holds → Assembly section reads `COHERENT` and **no** incoherence `Unknown` was added |
| T-38 | An incoherent assembly still **produces an artifact**, and its six Results are `==` to the inputs (`ENGINE_2:645`, "the Results preserved unchanged beneath it") |

### 9.6 Boundary and structure — T-39 … T-44

| # | Assertion |
|---|---|
| T-39 | **E-04.** Omitting any one Result raises `TypeError` — parametrised over all six |
| T-40 | Passing the Party Result where the Item Result belongs is a typecheck failure (asserted by the repository's existing typecheck gate, and by a runtime `isinstance` check with a message) |
| T-41 | The artifact's `identity` carries `version == FIRST_VERSION` and `parent_versions == ()` |
| T-42 | `transaction_id` and `artifact_id` are the ones supplied, unchanged |
| T-43 | **E-10.** A Result more confident than `evidence_reliability` → the artifact refuses, and the message names the Result class and both numbers |
| T-44 | `story_builder` imports nothing outside `decimal`, `accountant_dad.artifacts.understanding`, `accountant_dad.confidence` and `accountant_dad.identity` — asserted by parsing this module's own import list, as `engines/understanding_engine/stub.py` already does. No engine import (AL-INV-5), no `accountant_dad.services` import (AL-INV-4), no clock, no randomness, no I/O |

### 9.7 Adversarial — A-01 … A-10

The §M amendment names three attack classes by name: *"attempts to manufacture confidence, to hide a weak dimension, and to coerce `UNMEASURED` to `0.0`."* All three are here, plus vocabulary smuggling.

| # | Attack | The assertion that defeats it |
|---|---|---|
| **A-01** | **Manufacture confidence.** Emit an `understanding_confidence` above the true minimum | The artifact refuses (`_nothing_the_results_raised_was_lost`), **and** F-04 fires. Both are asserted, so removing either guard is caught |
| **A-02** | **Manufacture confidence, subtly.** Emit `min(six)` and ignore `evidence_reliability` when evidence is the lowest | F-04 fires. T-03 covers the same shape from the positive side |
| **A-03** | **Hide a weak dimension.** Drop the weakest Result from the aggregation input | F-04 fires. T-02's seven parametrised cases mean no slot can be dropped unnoticed |
| **A-04** | **Hide a weak dimension by omission.** Compute over six inputs, silently defaulting the seventh to `1.0000` | F-04 fires; and T-01's distinct-value inputs mean a default cannot coincide with the answer |
| **A-05** | **Coerce `UNMEASURED` to `0.0`.** Replace an absence with `Decimal("0.0000")` before the `min` | **F-16 and F-05 both fire.** Asserted explicitly, because a coerced zero satisfies every *ordering* check in the artifact and would otherwise pass silently (§3.4, reason 4) |
| **A-06** | **Coerce by filtering.** Strip absences from the sequence, then call the builtin `min` over what remains | F-05 fires. This is the exact behaviour the amendment names — *"the smallest number present"* |
| **A-07** | **Smuggle accounting vocabulary** via a frozen constant softened in a later edit | T-10 fires, reading `FORBIDDEN_VOCABULARY` from the live import so the tables cannot drift apart |
| **A-08** | **Smuggle accounting vocabulary** by quoting `stated_text` into the narrative | T-18 and F-13 fire. The artifact itself also refuses (measured, §4.5) |
| **A-09** | **Resolve a conflict by presentation.** Render only the first competing reading, or number them, or add "most likely" | T-26, T-27 and T-12 fire |
| **A-10** | **Drop an unknown that reads badly.** Filter `identified_unknowns` before constructing the artifact | The artifact refuses, naming the dropped subject; F-02 and T-32 fire |

### 9.8 Ablation — the executable form of "confidence gates nothing"

`MEASUREMENT_FRAMEWORK.md` §11 gives the pattern: *"Any rule of the form 'X must not influence Y' converts the same way"* — change X, re-run, assert byte-identical output.

**A-11.** Assemble twice from identical Results, varying only `evidence_reliability` between two measured values that both satisfy every ceiling. Assert the **narrative is byte-identical** and every field except `confidence_assessment` is unchanged. That is F-12, and it is what proves SB-9 rather than asserting it.

**A-12.** The same ablation over `artifact_id` and `transaction_id` (INV-9). `tests/unit/test_id_ablation.py` already exists as the pattern to copy.

### 9.9 Mutation

Story Builder is a pure function over frozen inputs, which is close to the best possible case for mutation testing. **Every falsifier in §8.3 must kill at least one mutant**, and the module must clear whatever coverage and mutation floors CI enforces at the time it lands (Law 55 — the floor is the floor; no number is quoted here because none has been measured for code that does not exist).

The mutants worth naming in advance, because they are the ones that would otherwise survive:

- `min` → `max` in the aggregation (killed by T-01, T-03)
- a `<` → `<=` in the incoherence predicates (killed by T-36)
- a dropped `evidence_reliability` argument (killed by T-03, A-02)
- a section skipped when its body is empty (killed by T-15, T-30)
- a separator changed to `""` (killed by T-11 and, on the right input, by F-09)

---

## 10. Undefined terms — owner decisions, unresolved

**None of the following is resolved in this document.** Each is a term or number that is load-bearing for Story Builder and that no locked document defines. Law 54: *"Never invent the definition yourself. Ask."*

| # | Term | Where it is load-bearing | Why it cannot be resolved here |
|---|---|---|---|
| **U-1** | **`evidence_reliability`** — how the Confidence Report's many scores, across many documents, become the **one** number the §M `min` consumes | The seventh input to the amendment's own rule. Without it the rule cannot be computed at all | `ENGINE_2:157` gives Engine 2 *all* Document Evidence Objects sharing one Transaction ID, and each holds many field scores. Mean, min, weighted, per-field — no document names one. `engines/understanding_engine/stub.py` already refuses to choose: *"'the' evidence confidence would need an aggregation rule that no document defines."* **This is the highest-priority decision and it blocks the amendment's rule from being computed on real input** |
| **U-2** | **Which absence state the aggregate carries when inputs carry *different* absences** — `NOT_MEASURED` vs `NOT_APPLICABLE` vs `FAILED` | §3.3's third branch | The amendment writes one `UNMEASURED`; `confidence.py` Amendment 7 has three, and `records_the_same_measurement` rules that two different absences **disagree**. Nothing says which wins. §3.3 **refuses** rather than picking; a refusal is not a rule |
| **U-3** | **"calibrated confidence threshold"** | The amendment's own definition of **Weak Interpretation** — *"falls below its calibrated confidence threshold"* | `MEASUREMENT_FRAMEWORK.md` §10 holds that confidence *"may gate NOTHING"* until separation ≥ 0.30 passes, and `ACCOUNTING_DEFINITIONS.md` §6 Amendment 8 struck a term for naming such a threshold: *"No such threshold exists and none may be invented."* **Weak Interpretation is therefore not measurable today.** Story Builder does not consume it, so this is latent rather than blocking — see §11, C-4 |
| **U-4** | **The approved posting threshold** and **the approved reliability threshold** | Conditions 1 and 2 of the amendment's five-condition posting policy | The amendment itself marks both **UNSET** and states the consequence — *"nothing auto-posts. That is the correct failure direction and is deliberate."* Not Story Builder's to set; recorded because the number it emits feeds them |
| **U-5** | **The format of an evidence reference** | Any predicate that would group references by document | `evidence_references` is `tuple[NonEmptyText, ...]` — opaque, deliberately. The artifact carries no document-id list on purpose. This is why incoherence predicate I-3 was rejected (§6.5) |
| **U-6** | **"coherent narrative"**, beyond the two counting predicates | `ENGINE_2:645` | §6.3 gives the **necessary** condition set. The **sufficient** condition needs comprehension, which this component does not have and Amendment 4 forbids it acquiring. Named as a permanent limit of this layer, not as work outstanding |
| **U-7** | **Any bound on narrative length** | E-22 | No document states one. A truncation rule would be a resolution with a length limit, so none is invented |

---

## 11. Contradictions between locked documents

Found while writing this. Each is reported, not resolved — `CLAUDE.md` §M: *"If code and a frozen doc disagree, the doc wins and the code is wrong. Report it. Never resolve silently in code."*

### C-1 · The amendment is an equality; the schema enforces a ceiling

**Doc vs code.** `ACCOUNTING_DEFINITIONS.md` §M: `Understanding Confidence = min(...)`. `understanding.py` enforces `≤`.

**Measured @ `6fe2d8e` · LOCAL ONLY — NOT AUTHORITATIVE:** with the six Results' minimum at `0.4000`, an `understanding_confidence` of `0.1000` is **accepted**.

The code is permissive rather than wrong, but the amendment's own rule is **structurally unguarded**. Fix in §3.9. Not applied here.

### C-2 · The artifact cannot represent the amendment's `UNMEASURED`

**Doc vs code.** The amendment makes `UNMEASURED` propagation normative. All three confidence slots are `Decimal`-only.

**Measured @ `6fe2d8e` · LOCAL ONLY — NOT AUTHORITATIVE:** `ConfidenceAssessment` refuses `UNMEASURED` in either slot with `ValidationError`.

**The normative rule is unimplementable against the artifact as built.** Fix in §3.8. Not applied here.

### C-3 · The amendment names a required artefact that does not exist

**Doc vs doc.** The amendment's Implementation table requires:

| Artefact | Change |
|---|---|
| `DATA_FLOW.md` | Understanding Confidence's derivation named on the Engine 2 → Engine 3 arrow |

**Verified @ `6fe2d8e`:** `DATA_FLOW.md` §2 row 2 and §2.2 describe the Confidence Assessment's four components and **do not name the derivation**. The amendment is normative from 2026-08-06 and one of its own required artefacts is outstanding. `DATA_FLOW.md` is a precedence-level-2 locked document; editing it is a §M change and is not done here.

### C-4 · "Weak Interpretation" is defined by a threshold the repository forbids

**Doc vs doc.** The amendment defines a weak interpretation as one that *"falls below its calibrated confidence threshold."* `ACCOUNTING_DEFINITIONS.md` §6 Amendment 8 struck a term for exactly such a threshold: *"No such threshold exists and none may be invented (Law 52, Law 54)."* `MEASUREMENT_FRAMEWORK.md` §10 adds that confidence *"may gate NOTHING"* until separation passes.

**Weak Interpretation is not measurable today.** Story Builder does not consume it, so nothing here is blocked. Reported because a term defined against a forbidden quantity is a false statement waiting to be discovered.

### C-5 · One `UNMEASURED` in the amendment, three absence states in the code

**Doc vs code.** The amendment writes `UNMEASURED` singular and simultaneously cites the four states of `confidence.py` (F-019). `records_the_same_measurement` treats two *different* non-measured states as a **disagreement**. The amendment does not say which state an aggregate over mixed absences carries. See U-2.

### C-6 · `ENGINE_2:645` requires incoherence be reported and names no field

**Doc gap, already recorded.** `understanding.py`'s own `SPEC_GAPS` names it: *"`TransactionStory` — `ENGINE_2:645` requires incoherence be reported and names no field; it is reported in the narrative only."* **Verified still true @ `6fe2d8e`.** §6.6 mitigates it by also emitting an `Unknown`, which is structurally readable; it does not close it, because closing it means adding a field to a locked artifact.

---

## 12. What this component deliberately does NOT include

The most valuable section, per `CLAUDE.md` §G9 — it is what stops scope creep being arguable.

- **No language model, no API call, no network, no key, no spend.** Amendment 4 (draft): *"the six reasoning sub-engines — Transaction, Party, Item, Payment, Timeline, Business Context — remain FROZEN, as do all LLM/AI calls anywhere in the engine."*
- **No conflict resolution, ever** — including "helpfully" ordering readings by plausibility.
- **No unknown removal, no unknown de-duplication, no unknown summarisation.**
- **No confidence increase, and no confidence produced by any route but §3.2's single function.**
- **No accounting vocabulary, no accounting reasoning, no ledger, no tax, no period, no voucher.**
- **No fact added.** Not a summary sentence, not a total, not a count of line items, not an inferred date.
- **No parsing of the Document Evidence Object.** Story Builder receives Results and one number (§2.4).
- **No gating.** It emits a number and branches on nothing (`MEASUREMENT_FRAMEWORK.md` §10).
- **No cross-Result contradiction detection** (§5.6) — a permanent limit of a component with no comprehension.
- **No accuracy claim.** The ceiling does not exist; by Law 52 and Law 54 none is provable, therefore none is made.
- **No posting policy.** The amendment's five conditions belong to Engine 5 and the Application Layer.
- **No alternative aggregation model**, not even behind a flag. The amendment: *"Alternative aggregation models are not implemented, not partially implemented, and not left behind a flag."*

---

## 13. Implementation order — one sitting, once Amendment 4 is signed

Each step is independently checkable and independently revertible. No step begins before the one above it is green.

| # | Step | Done when |
|---|---|---|
| 0 | **Owner answers U-1** (`evidence_reliability` derivation) | A rule exists. **Steps 1–8 do not depend on it** — the parameter is supplied — but nothing runs on real input until it does |
| 1 | Add `engines/understanding_engine/story_builder` to `ENGINE_2_AUTHORIZED` in `tests/unit/test_package.py` | The freeze guard admits exactly that path and nothing else. Gate count rises, never falls |
| 2 | Write T-01 … T-09 (aggregation). **Watch them fail.** | Nine red tests, each failing because the function does not exist |
| 3 | Implement `understanding_confidence` (§3.2, §3.3, §3.5) | T-01 … T-09 green |
| 4 | Widen the three confidence slots and rewrite the three ordering validators (§3.8) | E-06 becomes representable; the whole existing `tests/unit/test_understanding.py` suite stays green, **unweakened** (Law 4) |
| 5 | Write T-10 … T-12 (constants). **Watch them fail.** Then write the frozen table | Green |
| 6 | Write T-13 … T-24 and T-25 … T-30 (narrative, conflicts). **Watch them fail.** Then implement `narrate` | Green, including T-19 and T-20 byte-determinism |
| 7 | Write T-31 … T-38 (unknowns, incoherence). **Watch them fail.** Then implement the §6 predicates | Green |
| 8 | Write T-39 … T-44, then implement `assemble` | Green |
| 9 | Write A-01 … A-12. **Every one must fail against a deliberately broken build first** (§I.9) | All twelve green on correct code, all twelve red on the matching sabotage |
| 10 | Add the sixteen §8.3 falsifiers as conformance predicates | `count(fires) == 0` — the §1.3 finish line |
| 11 | Run the DONE GATE (`CLAUDE.md` §N) in full, **before** the commit | Stated in the output, every line ticked or marked N/A |
| 12 | Push. **GitHub CI is the only authority** (Law 44) | Every mandatory gate at or above its floor (Law 55). Every number quoted with its commit (Law 56) |

**Steps 2, 5, 6, 7, 8 and 9 all begin with a red test.** A test that passes the first time it is run tests nothing (`CLAUDE.md` §J.1).

---

## Related documents

- [`ENGINE_2_UNDERSTANDING_ENGINE_RULES.md`](ENGINE_2_UNDERSTANDING_ENGINE_RULES.md) — §7 the seven sub-engines and their order · §8.7 Story Builder · §9 assembly authority · §11 the confidence model.
- [`COMMUNICATION_RULES_UNDERSTANDING_INTERNAL.md`](COMMUNICATION_RULES_UNDERSTANDING_INTERNAL.md) — the six rules between sub-engines; Rule 6 is Story Builder's.
- [`COMMUNICATION_RULES_UNDERSTANDING_ENGINE.md`](COMMUNICATION_RULES_UNDERSTANDING_ENGINE.md) — the outbound boundary, all nine items.
- [`ACCOUNTING_DEFINITIONS.md`](ACCOUNTING_DEFINITIONS.md) — §2 Understanding, and the **§M Amendment — Understanding Confidence Aggregation** that is this document's normative input.
- [`MEASUREMENT_FRAMEWORK.md`](MEASUREMENT_FRAMEWORK.md) — §10, why confidence gates nothing yet; §11, the ablation pattern.
- [`SYSTEM_INVARIANTS.md`](SYSTEM_INVARIANTS.md) — INV-2 · INV-3 · INV-4 · INV-5 · INV-9 · INV-10.
- [`DATA_FLOW.md`](DATA_FLOW.md) — §2 row 2 and §2.2, the Business Understanding Object.
- [`src/accountant_dad/artifacts/understanding.py`](../src/accountant_dad/artifacts/understanding.py) — every input and output type named above.
- [`src/accountant_dad/confidence.py`](../src/accountant_dad/confidence.py) — `Confidence`, the four measurement states, `ConfidenceOrUnmeasured`, `measurement_state`.
- [`src/accountant_dad/engines/understanding_engine/stub.py`](../src/accountant_dad/engines/understanding_engine/stub.py) — the P3 seam, and the precedent for supplied identifiers and a refused batch.
