"""Callable ingestion entrypoint for versioned NVIDIA Knowledge corpora."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from nvidia_startup_intel.nvidia_knowledge import NVIDIAKnowledgeCorpus, load_nvidia_knowledge_corpus


SCHEMA_VERSION = "nvidia_knowledge_ingestion.v1"


class NVIDIAKnowledgeCorpusStore(Protocol):
    def save_nvidia_knowledge_corpus(self, corpus: NVIDIAKnowledgeCorpus) -> None: ...


@dataclass(frozen=True)
class NVIDIAKnowledgeIngestionResult:
    schema_version: str
    run_id: str
    corpus_version: str
    document_count: int
    chunk_count: int


def ingest_nvidia_knowledge_corpus(
    store: NVIDIAKnowledgeCorpusStore,
    corpus_path: str | Path,
    *,
    run_id: str,
) -> NVIDIAKnowledgeIngestionResult:
    """Load an official NVIDIA corpus from disk and persist documents/chunks."""

    corpus = load_nvidia_knowledge_corpus(corpus_path)
    store.save_nvidia_knowledge_corpus(corpus)
    return NVIDIAKnowledgeIngestionResult(
        schema_version=SCHEMA_VERSION,
        run_id=run_id,
        corpus_version=corpus.corpus_version,
        document_count=len(corpus.documents),
        chunk_count=len(corpus.chunks),
    )
