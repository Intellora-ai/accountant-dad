"""`KNOWN_FAILURES.md` F-015 — Table Transformer is built once, not once per table.

WHAT THIS GUARDS, AND WHY A TIMER WOULD NOT GUARD IT. The defect was a cost, so
the obvious instrument is a stopwatch. A stopwatch is the wrong one: it is
noisy, it is machine-dependent, and it goes green on a slow runner that is
still rebuilding the model. The COUNT is exact, is the same on every machine,
and is what the defect actually was — `_bands_for` runs once per table and used
to construct the model inside itself, so a three-table invoice built it three
times.

    measured @ commit 00c6b8d, weights already in the HuggingFace cache, three
    repeats in ONE process with only the cache behaviour varied:

        3 tables, model built per table    14.476 s   median
        3 tables, model built once          7.015 s   median
        saved per EXTRA table                3.730 s

THE TRAP THIS FILE IS WRITTEN AROUND, AND IT IS NOT THE CONSTRUCTION COUNT.
A cache that also memoised the RESULT would satisfy "built once" and be
catastrophically wrong: every table after the first would report the FIRST
table's bands, which is invention (`ENGINE_1_INPUT_ENGINE_RULES.md:339` — *"an
invented value is indistinguishable downstream from an observed one"*). So the
count assertions below each carry their opposite: the model is built ONCE and
is INFERRED WITH ONCE PER TABLE, on that table's own crop. Either assertion
alone is a false green.

WHY THE LIBRARIES ARE SUBSTITUTED, AND WHERE. `requirements-ci.txt` carries
neither `transformers`, `torch` nor `pypdfium2` — `test_package.py:512` records
that deliberately — so a test that loaded the real weights could not run in CI
at all, which is the only place evidence counts (Law 44). `sys.modules` is the
narrowest edge available (§J.7): it is the exact seam `parser.require_module`
reaches through, everything in `_bands_for` above and below the model stays
real, and `reader.py`'s PaddleOCR fixtures already substitute at precisely this
edge for precisely this reason.

THE SUBSTITUTES ARE TYPED AGAINST THE PARSER'S OWN PROTOCOLS, NOT AGAINST
CONVENIENCE. `_FakeProcessor` is declared to satisfy `parser._ImageProcessor`,
`_FakeDetector` to satisfy `parser._ObjectDetector`, and the tensors to satisfy
`parser._Numbers`. That is deliberate and it is the difference between a fake
and a fiction: the day one of those protocols changes shape, this file stops
type-checking instead of quietly testing an API the production code no longer
uses. It also removes every `type: ignore` a looser fake would have needed.

The crop is a REAL `PIL.Image`, not a stand-in, because `_bands_for` does real
arithmetic on `.width`, `.height` and `.crop(...)`, and a fake returning
convenient numbers would be testing the fake.
"""

from __future__ import annotations

import contextlib
import sys
import types
from dataclasses import dataclass
from typing import TYPE_CHECKING, ClassVar

import pytest
from PIL import Image

from accountant_dad.engines.input_engine import parser

if TYPE_CHECKING:
    from collections.abc import Callable, Iterator, Mapping
    from contextlib import AbstractContextManager
    from pathlib import Path

# ── the numbers this test supplies, and they are the TEST'S ───────────────
#
# `TableStructureSettings` has no defaults on purpose (Law 52): the repository
# states none of these three, so `parse` refuses to invent them. A test may
# choose them because a test is not a production caller — nothing here claims
# these are the right operating point, only that they are legal.

RENDER_DPI = 144.0
SCORE_THRESHOLD = 0.5
CROP_PADDING_POINTS = 8.0

#: The rendered page the substituted pdfium hands back, in pixels.
PAGE_PIXELS = (1200, 1700)

#: The single detection the substituted processor reports per inference.
DETECTED_LABEL = 1
DETECTED_SCORE = 0.9125
DETECTED_BOX = (12.0, 24.0, 300.0, 60.0)
LABEL_NAME = "table row"

#: One build, then one cache clear, then one more build.
BUILDS_AFTER_ONE_CLEAR = 2


@dataclass(frozen=True, slots=True)
class Calls:
    """Everything the substituted libraries were asked to do, in order."""

    processors_built: list[str]
    detectors_built: list[str]
    #: `(width, height)` of the crop submitted for each inference. The SIZE is
    #: what identifies which table an inference was for.
    inferences: list[tuple[int, int]]
    #: How many inferences had already run each time `eval()` was called, which
    #: is what makes "asserted before any inference" checkable rather than
    #: merely stated.
    eval_calls: list[int]
    #: Each object the detector returned, so post-processing can be checked to
    #: have received THAT one. A processor handed a stale output still produces
    #: bands — the previous table's — and nothing raises.
    outputs: list[object]
    #: `"enter"` / `"exit"` for the no-gradient context, so inference can be
    #: proved to happen inside it.
    no_grad: list[str]


# ── the substitutes, each typed against the protocol it stands in for ─────


class _Tensor:
    """One tensor, faithful to the three things `_bands_for` does with one.

    Satisfies `parser._Numbers`. A plain `float` would not: it converts to
    `float` and to `int` but does not iterate, and `boxes` is iterated twice —
    once for the rows, once for each row's four edges.
    """

    def __init__(self, value: float = 0.0, parts: tuple[_Tensor, ...] = ()) -> None:
        self._value = value
        self._parts = parts

    def __iter__(self) -> Iterator[_Tensor]:
        return iter(self._parts)

    def __float__(self) -> float:
        return self._value

    def __int__(self) -> int:
        return int(self._value)


def _column(*values: float) -> _Tensor:
    return _Tensor(parts=tuple(_Tensor(value) for value in values))


def _rows(*boxes: tuple[float, float, float, float]) -> _Tensor:
    return _Tensor(parts=tuple(_column(*box) for box in boxes))


class _Detected:
    """One post-processed batch. Satisfies `parser._Detection`."""

    def __init__(self, columns: dict[str, _Tensor]) -> None:
        self._columns = columns

    def __getitem__(self, key: str) -> parser._Numbers:
        return self._columns[key]


class _FakeConfig:
    """Satisfies `parser._DetectorConfig`."""

    id2label: ClassVar[dict[int, str]] = {DETECTED_LABEL: LABEL_NAME}


class _FakeProcessor:
    """Satisfies `parser._ImageProcessor`."""

    def __init__(self, calls: Calls) -> None:
        self._calls = calls

    def __call__(self, *, images: object, return_tensors: str) -> Mapping[str, object]:
        assert return_tensors == "pt", (
            f"`_bands_for` asked for {return_tensors!r} tensors. The band arithmetic "
            "below it reads torch tensors; another framework's arrays would be a "
            "silent change of dependency."
        )
        assert isinstance(images, Image.Image), (
            f"the processor was handed {type(images).__name__}, not a PIL image. The "
            "crop is real pixels and the geometry below depends on it being so."
        )
        self._calls.inferences.append((images.width, images.height))
        return {"pixel_values": object()}

    def post_process_object_detection(
        self,
        outputs: object,
        *,
        threshold: float,
        target_sizes: list[tuple[int, int]],
    ) -> list[parser._Detection]:
        assert threshold == SCORE_THRESHOLD, (
            f"the caller's threshold {SCORE_THRESHOLD} did not reach the detector; "
            f"got {threshold}. A settings value that stops travelling is invisible."
        )
        assert len(target_sizes) == 1, (
            f"one crop was submitted, so one target size is expected; got {target_sizes!r}"
        )
        assert self._calls.outputs and outputs is self._calls.outputs[-1], (
            "post-processing was handed something other than the output this inference produced."
        )
        return [
            _Detected(
                {
                    "scores": _column(DETECTED_SCORE),
                    "labels": _column(DETECTED_LABEL),
                    "boxes": _rows(DETECTED_BOX),
                }
            )
        ]


class _FakeDetector:
    """Satisfies `parser._ObjectDetector`."""

    def __init__(self, calls: Calls) -> None:
        self._calls = calls

    @property
    def config(self) -> parser._DetectorConfig:
        return _FakeConfig()

    def eval(self) -> object:
        self._calls.eval_calls.append(len(self._calls.inferences))
        return self

    def __call__(self, **inputs: object) -> object:
        assert "pixel_values" in inputs, (
            f"the processor's output did not reach the detector; got {sorted(inputs)}"
        )
        assert self._calls.no_grad and self._calls.no_grad[-1] == "enter", (
            "inference ran outside `torch.no_grad()`. Gradient tracking left on is "
            "not a crash — it is silently different memory and a silently different "
            "graph, on every page of every document."
        )
        produced = object()
        self._calls.outputs.append(produced)
        return produced


class _ProcessorFactory:
    """Satisfies `parser._FromPretrained[parser._ImageProcessor]`."""

    def __init__(self, calls: Calls) -> None:
        self._calls = calls

    def from_pretrained(self, checkpoint: str) -> parser._ImageProcessor:
        self._calls.processors_built.append(checkpoint)
        return _FakeProcessor(self._calls)


class _DetectorFactory:
    """Satisfies `parser._FromPretrained[parser._ObjectDetector]`."""

    def __init__(self, calls: Calls) -> None:
        self._calls = calls

    def from_pretrained(self, checkpoint: str) -> parser._ObjectDetector:
        self._calls.detectors_built.append(checkpoint)
        return _FakeDetector(self._calls)


class _Render:
    def to_pil(self) -> Image.Image:
        return Image.new("RGB", PAGE_PIXELS, color=(255, 255, 255))


class _Page:
    def render(self, scale: float) -> _Render:
        assert scale > 0, f"a non-positive render scale cannot produce pixels; got {scale}"
        return _Render()


class _PdfDocument:
    def __init__(self, source: Path) -> None:
        assert source.is_file(), (
            f"the substituted pdfium was handed {source}, which does not exist. The "
            "path `_bands_for` opens must be the artifact it was given, not a name."
        )

    def __getitem__(self, index: int) -> _Page:
        assert index >= 0, f"the page index must be zero-based and non-negative, got {index}"
        return _Page()

    def close(self) -> None:
        return None


class _FakeTransformers(types.ModuleType):
    """A real module object carrying the two names `_table_structure_model` reads."""

    AutoImageProcessor: parser._FromPretrained[parser._ImageProcessor]
    TableTransformerForObjectDetection: parser._FromPretrained[parser._ObjectDetector]


class _FakeTorch(types.ModuleType):
    no_grad: Callable[[], AbstractContextManager[None]]


class _FakePdfium(types.ModuleType):
    PdfDocument: Callable[[Path], _PdfDocument]


def _install(calls: Calls, monkeypatch: pytest.MonkeyPatch) -> None:
    """Put all three substitutes behind the names `require_module` imports."""

    @contextlib.contextmanager
    def no_grad() -> Iterator[None]:
        calls.no_grad.append("enter")
        try:
            yield
        finally:
            calls.no_grad.append("exit")

    transformers = _FakeTransformers("transformers")
    transformers.AutoImageProcessor = _ProcessorFactory(calls)
    transformers.TableTransformerForObjectDetection = _DetectorFactory(calls)

    torch = _FakeTorch("torch")
    torch.no_grad = no_grad

    pdfium = _FakePdfium("pypdfium2")
    pdfium.PdfDocument = _PdfDocument

    monkeypatch.setitem(sys.modules, "transformers", transformers)
    monkeypatch.setitem(sys.modules, "torch", torch)
    monkeypatch.setitem(sys.modules, "pypdfium2", pdfium)


def _forget_everything_cached() -> None:
    """Empty BOTH caches. Forgetting either one is a silent leak.

    `require_module` is `@functools.cache`d, so a real `transformers` resolved
    earlier in this process would answer instead of the substitute.
    `_table_structure_model` is `@functools.cache`d, so a model built by ANY
    earlier test would answer and the construction count would read zero — a
    false green of exactly the shape §J.6 says to close by construction rather
    than by remembering.
    """
    parser.require_module.cache_clear()
    parser._table_structure_model.cache_clear()


@pytest.fixture
def calls(monkeypatch: pytest.MonkeyPatch) -> Iterator[Calls]:
    """Substitute the three libraries, and empty both caches in and out."""
    recorded = Calls(
        processors_built=[],
        detectors_built=[],
        inferences=[],
        eval_calls=[],
        outputs=[],
        no_grad=[],
    )
    _install(recorded, monkeypatch)
    _forget_everything_cached()

    yield recorded

    # Cleared on the way out too, so nothing installed here can reach a later
    # test in the same process.
    _forget_everything_cached()


@pytest.fixture
def settings() -> parser.TableStructureSettings:
    return parser.TableStructureSettings(
        render_dots_per_inch=RENDER_DPI,
        structure_score_threshold=SCORE_THRESHOLD,
        crop_padding_points=CROP_PADDING_POINTS,
    )


@pytest.fixture
def artifact(tmp_path: Path) -> Path:
    """A file that exists. Its BYTES are never read — pdfium is substituted."""
    source = tmp_path / "invoice.pdf"
    source.write_bytes(b"%PDF-1.7\n")
    return source


def a_table(ordinal: int) -> parser.Table:
    """One located table, at a position no other ordinal shares.

    The width grows with the ordinal so each table produces a DIFFERENT crop
    size, which is what lets a test tell "inferred once per table" apart from
    "inferred once and copied".
    """
    return parser.Table(
        detector=parser.DOCLING,
        box=parser.BoundingBox(
            page=1,
            left=40.0,
            top=60.0 + ordinal * 30.0,
            right=200.0 + ordinal * 40.0,
            bottom=260.0 + ordinal * 30.0,
        ),
        row_count=3,
        column_count=4,
        cells=(),
    )


# ── the defect itself ─────────────────────────────────────────────────────


@pytest.mark.parametrize("table_count", [1, 2, 3, 5])
def test_the_model_is_built_once_however_many_tables_a_document_has(
    table_count: int,
    calls: Calls,
    settings: parser.TableStructureSettings,
    artifact: Path,
) -> None:
    """F-015. Before the fix this was one construction per table, of each class.

    Measured against the pre-fix code before the fix was restored: this went
    red at `table_count` 2, 3 and 5 with exactly `table_count` constructions,
    and green at 1 — which is correct, because one table never discriminated.
    """
    for ordinal in range(table_count):
        parser._bands_for(artifact, a_table(ordinal), settings)

    assert calls.processors_built == [parser.TABLE_STRUCTURE_MODEL], (
        f"{table_count} tables built the image processor {len(calls.processors_built)} "
        "times. It is a per-process object that was living inside a per-table "
        "function (KNOWN_FAILURES.md F-015)."
    )
    assert calls.detectors_built == [parser.TABLE_STRUCTURE_MODEL], (
        f"{table_count} tables built the detector {len(calls.detectors_built)} times. "
        "Same defect, same cause, and this is the one carrying the model weights."
    )


@pytest.mark.parametrize("table_count", [1, 2, 3, 5])
def test_every_table_is_still_inferred_separately_on_its_own_crop(
    table_count: int,
    calls: Calls,
    settings: parser.TableStructureSettings,
    artifact: Path,
) -> None:
    """The other half, and the half that makes the count test worth anything.

    A cache that memoised the RESULT would pass the construction count above
    and report table 1's bands for every table after it. This makes that
    impossible: one inference per table, each on a crop of that table's own
    size.
    """
    for ordinal in range(table_count):
        parser._bands_for(artifact, a_table(ordinal), settings)

    assert len(calls.inferences) == table_count, (
        f"{table_count} tables produced {len(calls.inferences)} inferences. Caching "
        "the MODEL is the fix; caching the RESULT would be invention."
    )
    assert len(set(calls.inferences)) == table_count, (
        f"the {table_count} crops submitted were {calls.inferences}, which do not all "
        "differ. Every table here has a different width, so a repeated crop size "
        "means a table was measured with another table's pixels."
    )


def test_inference_mode_is_asserted_before_any_inference_and_never_again(
    calls: Calls, settings: parser.TableStructureSettings, artifact: Path
) -> None:
    """`eval()` moved into the builder, so it must still happen, and happen FIRST.

    The recorded value is how many inferences had already run when `eval()` was
    called. Zero is the only acceptable answer: a model inferred with while
    still in training mode reports different numbers, and nothing downstream
    could tell.
    """
    for ordinal in range(3):
        parser._bands_for(artifact, a_table(ordinal), settings)

    assert calls.eval_calls == [0], (
        f"`eval()` was called at inference counts {calls.eval_calls}. Expected exactly "
        "one call, before any inference had run."
    )


def test_the_processor_and_the_detector_are_the_same_checkpoint(
    calls: Calls, settings: parser.TableStructureSettings, artifact: Path
) -> None:
    """A preprocessor from one checkpoint feeding a model from another is silent.

    It produces bands. They are wrong, and nothing raises. The two names are
    asserted equal to each other AND to the module constant, so neither can
    drift alone.
    """
    parser._bands_for(artifact, a_table(0), settings)

    assert calls.processors_built == calls.detectors_built == [parser.TABLE_STRUCTURE_MODEL]


# ── behaviour is unchanged, which is the whole condition of the fix ───────


def test_the_same_table_through_the_cache_produces_identical_bands(
    calls: Calls, settings: parser.TableStructureSettings, artifact: Path
) -> None:
    """Second call, cached model, byte-identical output.

    `Band` is a frozen dataclass of `str` and `float`, so equality here is
    value equality all the way down. `repr` is compared as well, because two
    floats that read the same to a human do not always repr the same.
    """
    table = a_table(2)
    first = parser._bands_for(artifact, table, settings)
    second = parser._bands_for(artifact, table, settings)

    assert first == second
    assert repr(first) == repr(second)
    assert len(calls.detectors_built) == 1, "the second call must not have rebuilt anything"


def test_the_band_a_cached_model_produces_is_the_detectors_own_numbers(
    calls: Calls, settings: parser.TableStructureSettings, artifact: Path
) -> None:
    """The output is still assembled from what the detector reported, unrounded.

    Caching moved WHERE the model comes from. It must not have moved what this
    module does with the model's answer, and the score is the value most easily
    lost — it is a plain `float` carried verbatim precisely because `parser` has
    no authority to produce a confidence (`ENGINE_1_INPUT_ENGINE_RULES.md:109`).
    """
    (band,) = parser._bands_for(artifact, a_table(0), settings)

    assert band.label == LABEL_NAME
    assert band.score == DETECTED_SCORE
    assert band.box.page == 1
    assert calls.inferences, "no inference ran, so this band came from nowhere"


def test_inference_happens_inside_the_no_gradient_context_and_leaves_it(
    calls: Calls, settings: parser.TableStructureSettings, artifact: Path
) -> None:
    """The context is entered per table and exited per table, cached model or not.

    `_FakeDetector.__call__` refuses to run outside it, so the ENTER half is
    proved by every test in this file. This one proves the EXIT half: a context
    that is entered and never left is a leak that only shows up under load.
    """
    for ordinal in range(3):
        parser._bands_for(artifact, a_table(ordinal), settings)

    assert calls.no_grad == ["enter", "exit"] * 3


# ── what the cache must NOT remember ──────────────────────────────────────


def test_a_missing_transformers_is_raised_on_every_call_not_only_the_first(
    monkeypatch: pytest.MonkeyPatch, settings: parser.TableStructureSettings, artifact: Path
) -> None:
    """`functools.cache` stores return values, never exceptions — proven, not assumed.

    If it stored failures, an absent dependency would raise once and then be
    silently forgotten, and the second table in a document would take a
    different path from the first. The absence is CREATED rather than relied on
    — the principle `reader.py`'s `paddleocr_is_absent` fixture extracts from
    F-002 and F-009 — so this means the same thing on a machine where
    `transformers` is installed.
    """
    recorded = Calls(
        processors_built=[],
        detectors_built=[],
        inferences=[],
        eval_calls=[],
        outputs=[],
        no_grad=[],
    )
    _install(recorded, monkeypatch)
    monkeypatch.setitem(sys.modules, "transformers", None)
    _forget_everything_cached()
    try:
        for attempt in range(3):
            with pytest.raises(parser.ParserDependencyMissingError) as raised:
                parser._bands_for(artifact, a_table(attempt), settings)
            assert raised.value.module_name == "transformers"
        assert recorded.detectors_built == [], "nothing should have been built at all"
    finally:
        _forget_everything_cached()


def test_the_cache_is_emptied_by_name_so_a_test_can_never_leak_a_model(
    calls: Calls, settings: parser.TableStructureSettings, artifact: Path
) -> None:
    """`cache_clear` is part of the contract here, not an implementation detail.

    Every fixture in this file depends on it. If `_table_structure_model` ever
    stops being a `functools.cache`d function, the fixtures stop isolating and
    every count above starts reading whatever an earlier test left behind —
    which fails silently, in the green direction.
    """
    parser._bands_for(artifact, a_table(0), settings)
    assert len(calls.detectors_built) == 1

    parser._table_structure_model.cache_clear()
    parser._bands_for(artifact, a_table(1), settings)
    assert len(calls.detectors_built) == BUILDS_AFTER_ONE_CLEAR, (
        "clearing the cache did not force a rebuild, so the fixtures above and "
        "below this one are not isolating anything they claim to."
    )
