from __future__ import annotations

import json
from pathlib import Path

import pytest

from nvidia_startup_intel.nvidia_knowledge_ingestion import ingest_nvidia_knowledge_corpus
from nvidia_startup_intel.sql_repository import sqlite_repository


def test_ingestion_loads_official_corpus_and_persists_documents_and_chunks() -> None:
    repository = sqlite_repository()

    result = ingest_nvidia_knowledge_corpus(
        repository,
        _fixture_path(),
        run_id="run-ingest-001",
    )

    stored = repository.load_nvidia_knowledge_corpus("official-nvidia-fixture.v1")
    stored_document = stored.documents[0]
    stored_chunk = stored.chunks[0]
    document_row = repository.connection.execute(
        """
        SELECT schema_version, corpus_version, document_id, source_url, source_type, metadata_json, payload_json
        FROM nvidia_knowledge_documents
        WHERE corpus_version = ? AND document_id = ?
        """,
        (stored_document.corpus_version, stored_document.document_id),
    ).fetchone()
    chunk_row = repository.connection.execute(
        """
        SELECT schema_version, corpus_version, chunk_id, document_id, topic, metadata_json, payload_json
        FROM nvidia_knowledge_chunks
        WHERE corpus_version = ? AND chunk_id = ?
        """,
        (stored_chunk.corpus_version, stored_chunk.chunk_id),
    ).fetchone()

    assert result.schema_version == "nvidia_knowledge_ingestion.v1"
    assert result.run_id == "run-ingest-001"
    assert result.corpus_version == "official-nvidia-fixture.v1"
    assert result.document_count == len(stored.documents)
    assert result.chunk_count == len(stored.chunks)
    assert stored.schema_version == "nvidia_knowledge.v1"
    assert stored_document.source_url.startswith("https://")
    assert stored_document.source_type.startswith("official_nvidia_")
    assert stored_chunk.topic
    assert document_row[0:5] == (
        stored_document.schema_version,
        stored_document.corpus_version,
        stored_document.document_id,
        stored_document.source_url,
        stored_document.source_type,
    )
    assert chunk_row[0:5] == (
        stored_chunk.schema_version,
        stored_chunk.corpus_version,
        stored_chunk.chunk_id,
        stored_chunk.document_id,
        stored_chunk.topic,
    )
    assert "stack_name" in document_row[5]
    assert "schema_version" in document_row[6]
    assert "source_type" in chunk_row[5]
    assert "schema_version" in chunk_row[6]


def test_ingestion_can_rerun_same_corpus_without_duplicate_rows() -> None:
    repository = sqlite_repository()

    first_result = ingest_nvidia_knowledge_corpus(
        repository,
        _fixture_path(),
        run_id="run-ingest-first",
    )
    second_result = ingest_nvidia_knowledge_corpus(
        repository,
        _fixture_path(),
        run_id="run-ingest-second",
    )

    document_count = repository.connection.execute(
        "SELECT COUNT(*) FROM nvidia_knowledge_documents WHERE corpus_version = ?",
        ("official-nvidia-fixture.v1",),
    ).fetchone()[0]
    chunk_count = repository.connection.execute(
        "SELECT COUNT(*) FROM nvidia_knowledge_chunks WHERE corpus_version = ?",
        ("official-nvidia-fixture.v1",),
    ).fetchone()[0]

    assert second_result.run_id == "run-ingest-second"
    assert second_result.document_count == first_result.document_count
    assert second_result.chunk_count == first_result.chunk_count
    assert document_count == first_result.document_count
    assert chunk_count == first_result.chunk_count


def test_ingestion_rejects_non_official_sources_before_persistence(tmp_path: Path) -> None:
    repository = sqlite_repository()
    invalid_corpus_path = tmp_path / "invalid-nvidia-corpus.json"
    invalid_corpus_path.write_text(
        json.dumps(
            {
                "schema_version": "nvidia_knowledge.v1",
                "corpus_version": "invalid-corpus.v1",
                "documents": [
                    {
                        "schema_version": "nvidia_knowledge.v1",
                        "corpus_version": "invalid-corpus.v1",
                        "document_id": "third-party-nvidia-summary",
                        "title": "Third-party NVIDIA Summary",
                        "source_url": "https://example.com/nvidia-summary",
                        "source_type": "third_party_article",
                        "ingested_at": "2026-06-23T00:00:00Z",
                        "metadata": {
                            "stack_id": "third-party",
                            "stack_name": "Third-party NVIDIA Summary",
                            "topic": "model_serving",
                            "brief_description": "Unsupported source.",
                            "technical_description": "Unsupported source.",
                            "categories": ["summary"],
                            "use_cases": ["summary"],
                            "supported_gap_types": ["model_serving"],
                        },
                    }
                ],
                "chunks": [
                    {
                        "schema_version": "nvidia_knowledge.v1",
                        "corpus_version": "invalid-corpus.v1",
                        "chunk_id": "third-party-nvidia-summary:0",
                        "document_id": "third-party-nvidia-summary",
                        "chunk_index": 0,
                        "topic": "model_serving",
                        "text": "Third-party summary about NVIDIA.",
                        "metadata": {},
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="source_url_not_official_nvidia"):
        ingest_nvidia_knowledge_corpus(
            repository,
            invalid_corpus_path,
            run_id="run-invalid-ingest",
        )

    assert (
        repository.connection.execute("SELECT COUNT(*) FROM nvidia_knowledge_documents").fetchone()[0]
        == 0
    )
    assert repository.connection.execute("SELECT COUNT(*) FROM nvidia_knowledge_chunks").fetchone()[0] == 0


def _fixture_path() -> Path:
    return Path(__file__).parent / "fixtures" / "nvidia_knowledge_official_fixture.json"
