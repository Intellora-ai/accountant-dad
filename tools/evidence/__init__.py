"""Citation verification: prove where every quoted line of law actually came from.

Public surface:

    Registry.load()      every document the manifest declares, plus its parser
    verify.run(root)     the five proofs, over every claim under `root`
    bootstrap.main()     fetch and checksum every declared source

Entry points:

    python3 -m tools.evidence.verify
    python3 -m tools.evidence.bootstrap [--check]
"""

from __future__ import annotations

from .model import Citation, CitationError, Failure, Layer, Span, evidence_id, normalise
from .registry import Document, Registry

__all__ = [
    "Citation",
    "CitationError",
    "Document",
    "Failure",
    "Layer",
    "Registry",
    "Span",
    "evidence_id",
    "normalise",
]
