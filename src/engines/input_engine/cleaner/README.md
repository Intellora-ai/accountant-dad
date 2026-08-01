# cleaner

> Sub-engine of the **Input Engine**. Canonical definition: [`docs/SUB_ENGINE_RESPONSIBILITIES.md`](../../../../docs/SUB_ENGINE_RESPONSIBILITIES.md).
>
> **Phase 1 placeholder — no implementation.**

## Purpose

A document cannot be read reliably until it is physically readable.

## Responsibility

Owns the physical quality of the artifact — deskewing, rotation, denoising, cropping, contrast, and normalisation of file format and character encoding.

## Input

The raw artifact exactly as received: scan, photograph, PDF, or digital file.

## Output

A normalised artifact, ready to be read, plus a record of every transformation applied.

## Boundary

Cannot interpret the meaning of anything on the artifact. Cannot discard content it judges irrelevant, redundant or illegible. Cannot alter values — only presentation.

## Future Notes

- The transformation record exists so a poor reading can later be traced to a cleaning step; keep it complete enough to reproduce the result.
- Multi-page and multi-document artifacts will need a splitting decision. Splitting is physical, so it belongs here — but only on physical evidence, never on content.
