"""The Brain stub — it answers, and it knows nothing.

`MVP_IMPLEMENTATION_BLUEPRINT.md:136` — P3 is done when *"the Brain stub answers
structurally without faking knowledge."* Those are two requirements pulling
opposite ways, and the resolution is the whole design of this module.

IT ANSWERS. It satisfies `KnowledgeBrain` structurally, so every engine can call
it at P3 and the seam is proven before any knowledge exists behind it. An
engine written against this interface needs no change when P4 replaces it.

IT KNOWS NOTHING, AND SAYS SO IN THE ONLY HONEST WAY AVAILABLE.
    Every answer carries zero statements.

    `knowledge_contract.py` made an empty answer legal on purpose, quoting
    `SYSTEM_INVARIANTS.md` — *"Gaps stay gaps. An absent fact is marked absent
    until supplied. No defaults, no conventions, no most-common-value."* An
    empty answer is not a failure to respond. It is the accurate response from
    something that has been given no knowledge.

    The alternative — returning plausible accounting statements so the pipeline
    looks alive at P3 — is the single most dangerous thing this file could do.
    It would be indistinguishable at the seam from a real Brain, and every
    downstream number would be measuring invention. `CLAUDE.md` Law 24: never
    fabricate data. `BLUEPRINT:136` also forbids any accuracy claim at P3, and a
    stub that answered would make one impossible to avoid.

IT READS NOTHING, AND THAT IS ENFORCED BY THE SIGNATURE.
    The parameter is named `_question` and never touched. A stub that branched
    on the question would have behaviour to get wrong, and a test asserting
    "it returns nothing" would start passing for the wrong reason the moment
    someone taught it one special case.

    `KnowledgeBrain` declares the parameter positional-only precisely so an
    implementation that ignores it may say so in the name.
"""

from __future__ import annotations

from accountant_dad.knowledge_contract import KnowledgeAnswer, KnowledgeQuestion

#: What the stub knows. Named so the emptiness is a stated fact rather than an
#: oversight a reader has to infer from an empty tuple literal.
KNOWS_NOTHING = KnowledgeAnswer(statements=())


class StubBrain:
    """Satisfies `KnowledgeBrain`. Answers every question with nothing.

    Deliberately does NOT inherit from `KnowledgeBrain` — it is a `Protocol`,
    checked structurally by mypy, and `knowledge_contract.py` notes that
    `src/brain/` never imports it to subclass. Inheriting would couple the
    implementation to the contract's class identity instead of its shape.
    """

    def answer(self, _question: KnowledgeQuestion, /) -> KnowledgeAnswer:
        """Return nothing, for every question, always.

        No caching, no clock, no randomness, no I/O. Two calls with the same
        question return equal answers, and so do two calls with different ones —
        which is what makes this stub's behaviour fully stated by its name.
        """
        return KNOWS_NOTHING
