from nvidia_startup_intel.briefing import ExecutiveBriefing
from nvidia_startup_intel.downstream_artifacts import build_downstream_artifact_snapshot
from nvidia_startup_intel.nvidia_knowledge import NVIDIAKnowledgeRetrieval


def test_downstream_artifact_snapshot_projects_storage_neutral_payloads() -> None:
    retrieval = NVIDIAKnowledgeRetrieval(
        schema_version="nvidia_knowledge.v1",
        run_id="run-snapshot",
        corpus_version="official-nvidia-fixture.v1",
        query="model serving",
        results=(),
        documents=(),
    )
    briefing = ExecutiveBriefing(
        schema_version="executive_briefing.v1",
        run_id="run-snapshot",
        startup_identifier="VetAI",
        status="ready_for_use",
        executive_summary="VetAI has a supported NVIDIA opportunity.",
        diagnosis="AI-native",
        opportunity="high",
        risks=(),
        recommendations=(),
        pending_questions=(),
        claims=(),
        evidence_references=(),
        citation_references=(),
        next_action="prepare_technical_outreach",
        audit_reasons=(),
    )

    snapshot = build_downstream_artifact_snapshot(
        {
            "run_id": "run-snapshot",
            "retrievals": (retrieval,),
            "executive_briefing": briefing,
        }
    )

    assert snapshot.run_id == "run-snapshot"
    assert snapshot.startup_identifier == "VetAI"
    assert snapshot.retrievals[0].corpus_version == "official-nvidia-fixture.v1"
    assert snapshot.retrievals[0].retrieval_strategy == "none"
    assert snapshot.retrievals[0].payload["schema_version"] == "nvidia_knowledge.v1"
    assert snapshot.briefings[0].briefing_type == "executive"
    assert snapshot.briefings[0].status == "ready_for_use"
    assert snapshot.briefings[0].filename == "briefing.json"
    assert snapshot.briefings[0].payload["startup_identifier"] == "VetAI"
