---
title: "PRD Técnico/Arquitetural: NVIDIA Knowledge, Recommendation e Briefing"
labels:
  - ready-for-agent
status: proposed
issue_url: https://github.com/leeunam/case-NVIDIA-IA/issues/4
---

# PRD Técnico/Arquitetural: NVIDIA Knowledge, Recommendation e Briefing

## Problem Statement

O gerente de Startups & VCs da NVIDIA no Brasil precisa decidir se uma startup brasileira merece abordagem técnica e comercial agora, por qual gap, com quais evidências públicas e com qual tecnologia ou programa NVIDIA. O projeto já possui um walking skeleton upstream para descoberta, coleta pública, perfil estruturado, evidência, qualidade de coleta e avaliação AI-native determinística, mas ainda não possui a parte downstream que transforma diagnóstico em recomendação NVIDIA citável e briefing executivo.

O problema técnico é fechar essa próxima fase sem quebrar a arquitetura evidence-first. O sistema não pode deixar uma camada RAG, um prompt, um framework ou um LLM escolher tecnologia NVIDIA, prioridade comercial ou narrativa de briefing sem contratos auditáveis. Toda recomendação suportada precisa ligar, no mínimo, um gap técnico ou uma oportunidade comercial da startup a uma citação oficial NVIDIA. Quando faltar evidência, houver conflito, existir alto wrapper risk ou a fonte oficial não for suficiente, o output deve virar hipótese, bloqueio ou Human Review Briefing, não recomendação final.

O risco arquitetural é introduzir BM25, busca vetorial, Postgres/pgvector, LangGraph, LangChain, LiteLLM e LlamaIndex ao mesmo tempo e espalhar regra de negócio entre bibliotecas. A próxima fase precisa criar contratos próprios para conhecimento, retrieval, recomendação, briefing, workflow e persistência, mantendo a suíte local sem rede, sem credenciais, sem Postgres real obrigatório, sem LangGraph obrigatório e sem provedores externos obrigatórios.

## Solution

Construir uma linha vertical downstream, pequena e testável, que consome os artefatos upstream já existentes e produz dois resultados possíveis: Executive Briefing pronto para uso humano ou Human Review Briefing com motivos acionáveis.

A solução deve criar uma camada `NVIDIA Knowledge` com corpus versionado de fontes oficiais NVIDIA, documentos, chunks, citações e resultados recuperados. O primeiro retrieval deve ser BM25 lexical determinístico, seguido por um contrato de embeddings, busca vetorial reprodutível e ranking híbrido que preserve scores e metadados. Postgres/pgvector será o caminho local preferido para persistência vetorial quando embeddings precisarem sair do modo em memória ou fixture. LlamaIndex pode ser usado depois como adapter de conhecimento se a complexidade de ingestão, índice, metadados, citações ou reranking justificar.

Sobre esse retrieval, a solução deve criar `Recommendation`: um motor determinístico que cruza gaps técnicos, oportunidades comerciais, wrapper risks, evidências da startup e citações NVIDIA para gerar recomendações técnicas, recomendações de programa, hipóteses, bloqueios, prioridade final da oportunidade NVIDIA, complexidade e próxima ação. A avaliação AI-native continua gerando apenas sinal preliminar; a prioridade final pertence a Recommendation.

Por fim, a solução deve criar `Briefing`: um artefato versionado com claims rotulados como observado, inferido, recomendado ou desconhecido. A primeira versão deve ser determinística. LangChain e LiteLLM podem entrar apenas atrás de adapters para geração narrativa futura, structured output, prompts ou tools, sem substituir os contratos de domínio. LangGraph deve orquestrar nós finos e branches, mas não conter ranking, regras de recomendação ou decisão de briefing.

## User Stories

1. As a gerente de Startups & VCs da NVIDIA, I want an executive briefing that connects a startup diagnosis to NVIDIA technologies or programs, so that I can decide whether to approach the startup.
2. As a gerente de Startups & VCs da NVIDIA, I want each recommendation to name the startup gap or commercial opportunity it addresses, so that outreach is grounded in a concrete reason.
3. As a gerente de Startups & VCs da NVIDIA, I want each supported NVIDIA recommendation to cite an official NVIDIA source, so that I can use it confidently in a commercial or technical conversation.
4. As a gerente de Startups & VCs da NVIDIA, I want the final NVIDIA opportunity priority to be calculated after Recommendation, so that AI-native maturity is not treated as commercial priority by itself.
5. As a gerente de Startups & VCs da NVIDIA, I want NVIDIA Inception recommended only when there is a specific gap or commercial opportunity, so that the briefing does not become a generic program pitch.
6. As a gerente de Startups & VCs da NVIDIA, I want technical recommendations separated from program recommendations, so that I can distinguish engineering fit from ecosystem or go-to-market fit.
7. As a gerente de Startups & VCs da NVIDIA, I want the top recommendation per gap highlighted, so that the next conversation has a clear primary angle.
8. As a gerente de Startups & VCs da NVIDIA, I want alternatives preserved when confidence is close, so that I can see tradeoffs instead of a false single answer.
9. As a gerente de Startups & VCs da NVIDIA, I want wrapper/API-dependency risk shown near the recommendation, so that I do not overprioritize shallow LLM wrappers.
10. As a gerente de Startups & VCs da NVIDIA, I want unknowns and conflicts visible in the briefing, so that I can avoid overstating facts in founder outreach.
11. As a gerente de Startups & VCs da NVIDIA, I want a Human Review Briefing when the system cannot safely recommend, so that low-confidence but strategic startups still produce actionable review context.
12. As a gerente de Startups & VCs da NVIDIA, I want founder validation questions generated from unknowns, conflicts, wrapper risks and hypotheses, so that a human can close the most important gaps.
13. As a gerente de Startups & VCs da NVIDIA, I want the briefing to include next action, so that the output ends in a decision path rather than a passive report.
14. As a technical reviewer, I want NVIDIA-side citations separate from startup-side evidence, so that audit trails do not mix source types.
15. As a technical reviewer, I want retrieved chunks to include source title, official URL or reference, ingestion date, corpus version, document id, chunk id and excerpt, so that I can audit every factual NVIDIA claim.
16. As a technical reviewer, I want retrieval results to expose lexical score, vector score and hybrid score when available, so that ranking is explainable.
17. As a technical reviewer, I want retrieval results to record strategy, parameters and tie-breakers, so that repeated runs are reproducible.
18. As a technical reviewer, I want non-official NVIDIA sources rejected or marked invalid for supported recommendations, so that unofficial material cannot become a factual claim.
19. As a technical reviewer, I want Recommendation to mark unsupported fit as hypothesis or blocked, so that weak retrieval does not become a final briefing.
20. As a technical reviewer, I want Recommendation to preserve critical conflicts from upstream evidence, so that the system does not silently pick the convenient source.
21. As a technical reviewer, I want high wrapper risk to trigger human review when recommendation support is weak, so that shallow AI usage is not hidden behind a plausible NVIDIA match.
22. As a technical reviewer, I want commercial opportunities modeled separately from technical gaps, so that go-to-market fit is not forced into technical vocabulary.
23. As a technical reviewer, I want the legacy preliminary opportunity field from assessment treated only as signal, so that Recommendation owns final NVIDIA priority.
24. As a developer, I want a versioned NVIDIA Knowledge schema, so that documents, chunks, citations, retrieval queries and retrieval results stay stable across implementations.
25. As a developer, I want a local official NVIDIA corpus fixture, so that the default validation path has no network dependency.
26. As a developer, I want deterministic chunking, so that chunk identifiers and citation references remain stable between runs.
27. As a developer, I want BM25 lexical retrieval as the first baseline, so that recommendation has an auditable retrieval path before embeddings.
28. As a developer, I want BM25 queries derived from gap type, commercial opportunity type, description and startup signals, so that retrieval is tied to the diagnosis instead of generic search.
29. As a developer, I want retrieval quality to explain insufficient results, so that corpus gaps and query mapping gaps can be fixed deliberately.
30. As a developer, I want an EmbeddingClient contract before real embeddings, so that model, version, dimension, language behavior and rebuild requirements are explicit.
31. As a developer, I want fake deterministic embeddings in the local suite, so that vector retrieval can be tested without providers.
32. As a developer, I want vector retrieval to record corpus version, embedding model, embedding version, dimension, distance metric and tie-breakers, so that semantic search is reproducible.
33. As a developer, I want hybrid retrieval to merge lexical and vector candidates while preserving original scores, so that rank explanations remain inspectable.
34. As a developer, I want duplicate chunks deduplicated deterministically, so that one citation does not appear multiple times with inconsistent rank.
35. As a developer, I want Postgres/pgvector planned as the local vector persistence path, so that metadata, embeddings, runs and downstream artifacts can live in one auditable store.
36. As a developer, I want the default suite to use in-memory or fake vector storage, so that real Postgres is optional for local validation.
37. As a developer, I want pgvector migrations to be explicit, so that vector extension, chunk metadata, embedding metadata and dimensions are controlled.
38. As a developer, I want approximate vector indexes deferred until corpus size or latency justifies them, so that recall is not traded for speed before measurement.
39. As a developer, I want LlamaIndex behind a retriever adapter, so that domain contracts do not expose framework-specific nodes or result objects.
40. As a developer, I want LangChain behind adapter seams, so that prompts, tools, retrievers and structured outputs do not leak into domain schemas.
41. As a developer, I want LiteLLM behind an LLMClient adapter, so that Grok, Groq, OpenRouter, Ollama or another provider can be swapped without touching domain logic.
42. As a developer, I want the LLM generator decoupled from the embedding model, so that retrieval quality is chosen by evidence, language support, cost and stability.
43. As a developer, I want deterministic briefing generation first, so that claim typing and quality gates are validated before narrative LLM generation.
44. As a developer, I want every downstream artifact to include schema version, run id, startup identifier, corpus version when applicable and source references, so that audit history is complete.
45. As a developer, I want JSON persistence for downstream artifacts during the walking skeleton, so that debugging and reprocessing remain simple.
46. As a developer, I want SQL persistence for knowledge snapshots, retrievals, recommendations and briefings, so that runs can be queried and reprocessed by startup.
47. As a developer, I want recommendation reprocessing without repeating scraping, so that retrieval and ranking changes can be validated cheaply.
48. As a developer, I want briefing reprocessing without repeating retrieval when corpus version and retrieval result set are unchanged, so that formatting changes are isolated.
49. As a developer, I want a local downstream workflow runner as the primary integration seam, so that the full path can be tested without LangGraph installed.
50. As a developer, I want LangGraph nodes for retrieval, recommendation, briefing, persistence and branch decisions to stay thin, so that rule logic remains in tested domain modules.
51. As a developer, I want branches for ready_for_recommendation, ready_for_briefing, briefing_generated and human_review_requested, so that workflow state is actionable.
52. As a developer, I want every branch to include an audit reason, so that users understand why the flow advanced or stopped.
53. As a developer, I want retriever, LLM and storage errors represented as structured workflow data, so that failures do not erase evidence or stop the whole run silently.
54. As a product owner, I want retrieval metrics for recall and precision on fixture expectations, so that retrieval changes are measured instead of chosen by preference.
55. As a product owner, I want recommendation metrics for citation support, startup evidence support, gap specificity and readiness, so that recommendation quality is visible.
56. As a product owner, I want human review reason counts, so that bottlenecks can be traced to collection, corpus coverage, retrieval, recommendation gates or briefing thresholds.
57. As a product owner, I want gaps without recommendations reported, so that the NVIDIA corpus can be expanded intentionally.
58. As a product owner, I want briefings blocked by missing citation, unknowns, conflict or wrapper risk counted, so that quality gates can be calibrated.
59. As a maintainer, I want no network, credentials, real Postgres, LangGraph, LlamaIndex, LangChain, LiteLLM, real LLM or real embedding provider required in the default suite, so that local validation stays deterministic.
60. As a maintainer, I want optional integration tests isolated from default validation, so that real pgvector, real embeddings or framework adapters can be validated without making the suite fragile.
61. As a future RAG maintainer, I want reranking limited to the retrieved top K, so that a reranker cannot invent facts or hide retrieval failure.
62. As a future RAG maintainer, I want reranker output to preserve chunk, citation, original scores and rationale, so that reranking remains auditable.
63. As a future briefing agent, I want every briefing claim to carry type, confidence and source references, so that narrative output cannot blur fact, inference, recommendation and unknown.
64. As a future workflow operator, I want Human Review Briefing to include startup, area, discoveries, suspected gaps, commercial opportunities, wrapper risks, conflicts, unknowns, reasons and validation questions, so that manual review starts with context.

## Implementation Decisions

- Build this phase as four bounded contexts: NVIDIA Knowledge, Recommendation, Briefing and downstream Workflow.
- Treat upstream contracts as fixed inputs: Startup Profile, grouped evidence, collection quality and AI-Native Assessment.
- Do not repeat discovery, scraping, extraction, evidence grouping or AI-native classification in downstream modules.
- Preserve dependency direction: Knowledge retrieves official NVIDIA citations; Recommendation decides fit and final priority; Briefing presents claims and next action.
- Introduce a versioned NVIDIA Knowledge contract covering official documents, deterministic chunks, citations, retrieval query, retrieved chunk, retrieval quality and retrieval result set.
- Introduce a versioned Recommendation contract covering technical recommendations, program recommendations, alternatives, hypotheses, blocked recommendations, recommendation quality, final NVIDIA opportunity priority and next action.
- Introduce a versioned Briefing contract covering Executive Briefing, Human Review Briefing, briefing claims, source references, pending questions and briefing status.
- Keep startup-side Evidence and NVIDIA-side Citation as separate concepts throughout schemas, persistence and briefing.
- Every downstream output must carry schema version, run id, startup identifier, source references and corpus version where applicable.
- The first Knowledge slice must load a small offline corpus of official NVIDIA sources sufficient to cover representative gap types and Inception/program fit.
- Source validation must reject or invalidate non-official NVIDIA material for supported recommendations.
- Document metadata must include corpus version, title, source reference, source type, ingestion date and serializable metadata.
- Chunking must be deterministic, discard empty chunks, preserve source order and create stable identifiers.
- BM25 lexical retrieval is the first retrieval baseline and must run without LLMs, embeddings, vector DB, network or external services.
- BM25 retrieval input should be derived from gap type, commercial opportunity type, gap description, startup signals and controlled vocabulary.
- BM25 retrieval output must include rank, score, matched chunk, citation metadata, retrieval strategy and a short audit rationale.
- Retrieval quality must state whether returned citations are sufficient to support Recommendation and must include failure reasons when insufficient.
- Add an EmbeddingClient contract before adding real embeddings. It must describe model, version, dimension, language behavior, corpus version and rebuild requirements.
- Use fake deterministic embeddings for local tests and fixture examples.
- Vector retrieval must return chunks, vector scores, citation references, embedding metadata and deterministic tie-breakers.
- Vector retrieval must not call LLMs or network from domain logic.
- Hybrid retrieval must combine lexical and vector candidates, deduplicate chunks, preserve original scores and record ranking strategy.
- Accept weighted score fusion or reciprocal rank fusion as initial hybrid strategies if weights, parameters and tie-breakers are explicit.
- Equal scores must be ordered by stable metadata such as document identifier and chunk index.
- Postgres/pgvector is the preferred local vector DB path when embeddings need persistence or SQL filtering.
- The first pgvector slice should provide explicit migrations for vector extension, document/chunk metadata, embedding payloads, corpus version, embedding model, embedding version and vector dimension.
- HNSW or IVFFlat indexes are deferred until corpus size or latency creates a measured need.
- LlamaIndex may be adopted only behind a Knowledge adapter when ingestion, metadata-rich indices, persistent vector indices, citations, hybrid retrieval or reranking become more complex than the local implementation should own.
- Domain contracts must expose project-owned schemas or dataclasses, not objects from LlamaIndex, LangChain, provider SDKs or vector DB clients.
- LangGraph owns orchestration: state, checkpoints, retries, branches and human-in-the-loop.
- Downstream graph nodes should be thin: retrieve knowledge, generate recommendations, generate briefing, persist artifacts and decide next action.
- LangGraph nodes must not implement retrieval ranking, recommendation rules, citation sufficiency, briefing claim typing or business priority.
- The local workflow runner is the primary integration seam for default validation; it should mirror the LangGraph path without requiring LangGraph.
- LangChain may be used inside adapters for LLM calls, prompts, structured output, tools or retriever wrappers, but it is not the workflow orchestrator or schema layer.
- LiteLLM may be used behind LLMClient for provider switching, retries, endpoints, timeouts and cost control.
- The LLM generator and embedding model are explicitly decoupled.
- Recommendation consumes assessment gaps, wrapper risks, commercial opportunities and retrieved NVIDIA citations.
- Recommendation must not invent startup facts, mutate evidence or infer new NVIDIA facts without citations.
- A technical recommendation requires a technical gap and at least one official NVIDIA citation.
- A program recommendation requires a commercial opportunity or specific gap that justifies the program and at least one official NVIDIA citation.
- NVIDIA Inception is not a default recommendation; unsupported Inception fit must be blocked or marked as hypothesis.
- A recommendation without sufficient source support is hypothesis or blocked, never supported.
- Final NVIDIA Opportunity Priority is calculated only after matching startup evidence to official NVIDIA citation.
- Recommendation quality must calculate ready_for_briefing and reasons for failure.
- High wrapper risk, critical conflict, weak evidence, missing official citation or excessive unknowns can force human_review_requested.
- Briefing generation starts deterministic and can later gain LLM narrative generation behind LLMClient, structured output validation and quality gates.
- Briefing claims must be typed as observed, inferred, recommended or unknown.
- Executive Briefing must include summary, profile highlights, AI-native diagnosis, opportunity, risks, recommendations, evidence references, citation references, pending questions and next action.
- Human Review Briefing must be a complete artifact, not a status flag.
- Human Review Briefing must include discoveries, main evidence, suspected gaps, commercial opportunities, wrapper risks, conflicts, unknowns, reasons for review and validation questions.
- JSON persistence remains useful for walking skeleton debugging and processed artifacts.
- SQL persistence should extend the existing run-oriented payload pattern to downstream retrievals, recommendations and briefings.
- Reprocessing recommendation must not require repeating scraping when startup evidence and assessment are already persisted.
- Reprocessing briefing must not require repeating retrieval when corpus version and retrieval result set are unchanged.
- Metrics must cover retrieval readiness, recommendations with official citation, recommendations with startup evidence, gaps without recommendation, briefings blocked and human review reasons.

## Testing Decisions

- The primary test seam is one local downstream workflow runner that consumes fixture upstream artifacts plus a local official NVIDIA corpus and returns retrieval, recommendation, briefing and next_action.
- This seam should cover successful briefing, missing citation, high wrapper risk, critical conflict, insufficient evidence and human review.
- Module-level tests remain necessary for deterministic chunking, BM25, embedding contract, vector retrieval, hybrid ranking, recommendation rules, briefing claims, serialization and persistence.
- Good tests should assert external behavior and versioned contracts, not private helper functions or framework internals.
- The default suite must not require network, credentials, real Postgres, LangGraph, LlamaIndex, LangChain, LiteLLM, real LLMs or real embedding providers.
- Retrieval tests should use a small official NVIDIA corpus fixture with stable corpus version and stable chunk identifiers.
- BM25 tests should cover relevant match, no match, ranking order, duplicate handling and citation sufficiency.
- Embedding tests should use fake deterministic embeddings and verify model metadata, vector dimension, stable ordering and rebuild requirements.
- Vector retrieval tests should cover semantic match, no match, tie-breaking and metadata preservation.
- Hybrid retrieval tests should cover lexical winner, vector winner, duplicate merge and deterministic tie.
- Recommendation tests should cover multiple technical gap types from the controlled vocabulary.
- Program recommendation tests should cover Inception allowed, Inception blocked and commercial opportunity requiring human validation.
- Recommendation quality tests should cover supported, hypothesis, blocked, ready_for_briefing and human_review_requested.
- Briefing tests should verify that claims are typed and that observed, inferred, recommended and unknown claims are not mixed.
- Briefing tests should verify that missing funding, customers, founders, technologies or NVIDIA fit remains unknown or becomes a pending question.
- Human review tests should verify detailed briefing output for low signal, high wrapper risk, critical conflict and missing official citation.
- Workflow tests should use the local runner as the highest seam, matching the existing pattern where LangGraph remains optional.
- SQL repository tests should use SQLite for payload persistence in the default suite.
- pgvector behavior should be isolated behind optional adapter or migration tests until Postgres integration is configured.
- JSON persistence tests should verify save/reload of schema version, run id, startup identifier, corpus version and citation references.
- Adapter tests for LangChain, LiteLLM, LlamaIndex, real embeddings and pgvector should start as fakes or contract tests.
- Real integration tests may be added later but must be excluded from default local validation until dependencies and credentials are explicitly configured.
- Retrieval metrics tests should validate fixture recall and precision before changing retrieval model, embedding model, ranking strategy or framework.

## Out of Scope

- Reworking Discovery, Collection, Profile Extraction, Evidence Quality or AI-Native Assessment.
- Scraping hardening, Playwright, Scrapy, Firecrawl, BeautifulSoup or trafilatura.
- Calling live NVIDIA documentation during the default validation path.
- Using non-official NVIDIA sources to support factual recommendations.
- Letting an LLM recommend NVIDIA technology without retrieved official citation support.
- Treating LangGraph, LangChain, LiteLLM, LlamaIndex or pgvector as replacements for domain contracts.
- Requiring a real LLM, embedding provider, network, credentials, Postgres or LangGraph in the default local suite.
- Building a UI, dashboard or CRM workflow.
- Automating startup outreach.
- Enriching with private data, authenticated sources, paid databases, funding APIs or CRM records.
- Producing definitive commercial ranking without human review.
- Adding neural reranking before lexical, vector, hybrid retrieval and metrics demonstrate a need.
- Using an external managed vector database before validating local Postgres/pgvector or in-memory retrieval.

## Further Notes

This PRD complements the existing product roadmap by sharpening the technical seams for agents. The smallest valuable slice is: local official NVIDIA corpus, deterministic chunks, BM25 retrieval, one supported technical recommendation, one blocked or hypothesis recommendation, deterministic Executive Briefing and deterministic Human Review Briefing.

The most important product metric for this phase is the rate of recommendations that have both startup evidence and official NVIDIA citation tied to a specific gap or commercial opportunity. Retrieval sophistication is useful only insofar as it improves that metric without sacrificing traceability.

The current repository has no valid automated suite. The implementation of this PRD should rebuild a focused local validation suite around the downstream workflow seam rather than relying on removed tests.
