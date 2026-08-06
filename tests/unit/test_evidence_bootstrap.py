"""Clone → bootstrap → verify must land in the same place on every machine.

The repository commits 17 MB of extracted text and ignores 42 MB of PDFs. That
split is deliberate — the text makes verification independent of which PDF
library is installed, and the PDFs are re-fetchable government bytes whose job
is to anchor that text to an official source by checksum.

The split only works if fetching is real and checked. These tests run against a
genuine HTTP server on loopback rather than a patched `urlopen`, because the
thing under test IS the download path: a mocked fetch would prove the mock
returns what the mock was told to return (§J.7 — fake only at the narrowest I/O
edge, and here the edge is the socket, not the function).

The case that matters most is a download whose bytes do not match the manifest.
A wrong-but-present document is worse than an absent one: absence is loud and
stops the run, while a silently wrong version verifies every quote against text
nobody chose. So the file is deleted, not kept and flagged.
"""

from __future__ import annotations

import hashlib
import http.server
import json
import pathlib
import threading
from collections.abc import Iterator

import pytest

from tools.evidence.bootstrap import fetch, report_missing
from tools.evidence.model import CitationError
from tools.evidence.registry import Registry, read_manifest

PAYLOAD = b"16. Eligibility and conditions for taking input tax credit.- (1) Every person."
TRUE_HASH = hashlib.sha256(PAYLOAD).hexdigest()
SHA256_HEX_LENGTH = 64


class _Server(http.server.BaseHTTPRequestHandler):
    """Serves `/correct` faithfully and `/tampered` with different bytes."""

    def do_GET(self) -> None:
        body = PAYLOAD if self.path == "/correct" else b"not the document you asked for"
        self.send_response(200)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args: object) -> None:
        """Silence. A passing test should not print a web log."""


@pytest.fixture
def origin() -> Iterator[str]:
    """A real HTTP origin on loopback, torn down with the test."""
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), _Server)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_address[1]}"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def build_manifest(tmp_path: pathlib.Path, url: str, sha256: str) -> pathlib.Path:
    library = tmp_path / "Evidence_Library"
    (library / "sources").mkdir(parents=True)
    manifest = library / "manifest.jsonl"
    manifest.write_text(
        json.dumps(
            {
                "file": "Tiny-Act.pdf",
                "body": "TEST",
                "kind": "act",
                "version": "as enacted",
                "url": url,
                "sha256": sha256,
            }
        )
        + "\n",
        encoding="utf-8",
    )
    return manifest


def test_a_document_that_matches_its_checksum_is_kept(tmp_path: pathlib.Path, origin: str) -> None:
    manifest = build_manifest(tmp_path, f"{origin}/correct", TRUE_HASH)
    document = read_manifest(manifest, manifest.parent / "sources")["Tiny-Act.pdf"]

    assert not document.present()
    fetch(document)

    assert document.present()
    assert document.path.read_bytes() == PAYLOAD
    assert document.actual_sha256() == TRUE_HASH


def test_a_download_whose_bytes_do_not_match_is_deleted_not_kept(
    tmp_path: pathlib.Path, origin: str
) -> None:
    """A present-and-wrong document is more dangerous than an absent one."""
    manifest = build_manifest(tmp_path, f"{origin}/tampered", TRUE_HASH)
    document = read_manifest(manifest, manifest.parent / "sources")["Tiny-Act.pdf"]

    with pytest.raises(CitationError, match="manifest declares"):
        fetch(document)

    assert not document.present(), "a checksum-failing download must not survive on disk"


def test_an_unreachable_source_fails_loudly(tmp_path: pathlib.Path) -> None:
    """Port 1 on loopback refuses instantly — a real connection failure, not a patch."""
    manifest = build_manifest(tmp_path, "http://127.0.0.1:1/nothing", TRUE_HASH)
    document = read_manifest(manifest, manifest.parent / "sources")["Tiny-Act.pdf"]

    with pytest.raises(CitationError, match="could not fetch"):
        fetch(document)

    assert not document.present()


def test_the_missing_report_carries_everything_needed_to_act(tmp_path: pathlib.Path) -> None:
    """A gate that fails without saying how to fix it trains people to ignore it."""
    manifest = build_manifest(tmp_path, "https://example.invalid/act.pdf", TRUE_HASH)
    registry = Registry.load(manifest, parsers={})

    missing = registry.missing()
    assert [d.file for d in missing] == ["Tiny-Act.pdf"]

    report = report_missing(missing)
    assert "https://example.invalid/act.pdf" in report
    assert TRUE_HASH in report
    assert "tools.evidence.bootstrap" in report


def test_a_present_document_is_not_reported_missing(tmp_path: pathlib.Path) -> None:
    manifest = build_manifest(tmp_path, "https://example.invalid/act.pdf", TRUE_HASH)
    (manifest.parent / "sources" / "Tiny-Act.pdf").write_bytes(PAYLOAD)

    assert Registry.load(manifest, parsers={}).missing() == []


def find_manifest() -> pathlib.Path:
    """The repository's real manifest, found by walking up rather than counting up.

    `parents[2]` was wrong and CI proved it. Under mutation, mutmut copies the
    tree into `mutants/` and runs pytest from there, so `parents[2]` resolves to
    `mutants/` — which has no `Accounting_Brain`. The test failed, the BASELINE
    suite failed with it, and mutmut therefore scored 1593 mutants as
    "not checked": a gate reporting nothing while looking like it ran.

    Walking up for the directory finds it from either tree and cannot silently
    resolve to the wrong depth if the layout changes.
    """
    for parent in pathlib.Path(__file__).resolve().parents:
        candidate = parent / "Accounting_Brain" / "Evidence_Library" / "manifest.jsonl"
        if candidate.is_file():
            return candidate
    raise AssertionError(
        "no Accounting_Brain/Evidence_Library/manifest.jsonl above "
        f"{pathlib.Path(__file__).resolve()} — the repository declares no documents"
    )


def test_the_repositorys_own_manifest_declares_every_field_a_proof_needs() -> None:
    """The real manifest, not a fixture. Every declared document must carry a
    source URL, a checksum and a parseable kind — the three things without which
    a citation against it could never be proven on another machine."""
    documents = read_manifest(find_manifest())

    assert documents, "the repository declares no documents"
    for document in documents.values():
        assert document.url.startswith(("http://", "https://")), document.file
        assert len(document.sha256) == SHA256_HEX_LENGTH, document.file
        assert document.kind, document.file
        assert document.version, f"{document.file} declares no version"
