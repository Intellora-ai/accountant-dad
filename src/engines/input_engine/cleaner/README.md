# cleaner

> Sub-engine of the **Input Engine**. Canonical definition: [`docs/SUB_ENGINE_RESPONSIBILITIES.md`](../../../../docs/SUB_ENGINE_RESPONSIBILITIES.md). Deep spec: [`docs/ENGINE_1_INPUT_ENGINE_RULES.md`](../../../../docs/ENGINE_1_INPUT_ENGINE_RULES.md#81-cleaner).
>
> **Phase 1 placeholder — no implementation.**

## Purpose

A document cannot be read reliably until it is physically readable. Improve raw document quality before extraction.

## Responsibility

Owns document preprocessing — the physical quality of the artifact: deskewing, rotation, denoising, cropping, contrast, and normalisation of file format and character encoding.

## Input

The raw artifact exactly as received: photo, camera capture, image upload, PDF, scan, handwritten note, or other digital file — including poor-quality human inputs.

## Output

- Cleaned document representation.
- Quality issues detected.
- Preservation status.

## Boundary

**Can:** reduce visual noise · improve readability · normalize document appearance · improve image quality.

**Cannot:** change numbers · remove important evidence · interpret text · correct accounting information · alter original meaning.

It alters presentation only. It cannot discard content it judges irrelevant, redundant or illegible.

## Failure Behaviour

**If processing may damage information: preserve the original input and mark uncertainty.**

- The original artifact is never discarded, so a damaging transformation is always recoverable.
- Preservation status records whether the cleaned representation or the original is the safer basis for reading.
- Detected quality issues are reported as evidence for [`confidence`](../confidence/), never repaired by guesswork.

## Future Notes

- The transformation record exists so a poor reading can later be traced to a cleaning step; keep it complete enough to reproduce the result.
- Multi-page and multi-document artifacts will need a splitting decision. Splitting is physical, so it belongs here — but only on physical evidence, never on content.
