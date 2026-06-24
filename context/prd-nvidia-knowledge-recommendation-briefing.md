---
title: "PRD: NVIDIA Knowledge, Recommendation e Briefing"
labels:
  - ready-for-agent
status: proposed
issue_url: https://github.com/leeunam/case-NVIDIA-IA/issues/3
---

# PRD: NVIDIA Knowledge, Recommendation e Briefing

## Problem Statement

O gerente de Startups & VCs da NVIDIA no Brasil precisa decidir se uma startup brasileira merece abordagem técnica e comercial agora, por qual motivo, com quais evidências públicas e com qual tecnologia ou programa NVIDIA. O projeto já possui um walking skeleton para descoberta, coleta, perfil estruturado, qualidade de evidência e `AI-Native Assessment`, mas ainda não transforma gaps técnicos e oportunidades comerciais em recomendações NVIDIA citáveis nem em um briefing executivo pronto para decisão humana.

O problema atual é que o fluxo termina antes da parte mais valiosa para a decisão: conectar o diagnóstico da startup a conhecimento oficial NVIDIA, calcular a prioridade final da oportunidade NVIDIA e produzir um artefato de sales enablement que diferencie dado observado, inferência, recomendação e desconhecido. Sem essa etapa, o sistema pode apontar maturidade AI-native ou riscos de wrapper, mas ainda não responde de forma auditável qual ação a NVIDIA deve tomar.

O risco arquitetural principal é avançar para recomendações com RAG, LLMs ou frameworks sem contratos explícitos. Uma recomendação convincente sem citação oficial NVIDIA, sem gap específico ou sem evidência da startup deve ser tratada como hipótese ou bloqueio, não como fato. A próxima fase precisa fechar os contratos de `NVIDIA Knowledge`, `Recommendation`, `Briefing` e `Human Review` mantendo a arquitetura evidence-first, o fluxo de dependências para frente e a suíte local sem rede, credenciais, Postgres real, LangGraph obrigatório ou provedores externos.

## Solution

Construir uma linha vertical downstream que começa em artefatos já existentes (`StartupProfile`, `FieldEvidenceGroup`, `CollectionQualitySummary` e `AINativeAssessment`) e termina em `ExecutiveBriefing` ou `Human Review Briefing`. A solução deve criar uma base versionada de conhecimento NVIDIA com fontes oficiais salvas localmente, recuperar trechos citáveis por BM25 lexical e busca vetorial versionada, combinar os resultados em ranking híbrido reprodutível, mapear gaps técnicos e oportunidades comerciais para recomendações NVIDIA suportadas e gerar um briefing versionado.

A primeira entrega deve ser um walking skeleton testável. O caminho mínimo começa com corpus local oficial, chunking determinístico e BM25 como baseline. Em seguida entra o contrato de embedding com fake determinístico, busca vetorial local, merge híbrido auditável e persistência futura em Postgres/pgvector. LlamaIndex pode entrar apenas como adapter de `NVIDIA Knowledge` quando houver necessidade medida de ingestão, índice, metadados, citações, persistência ou reranking; `Recommendation` não deve depender de objetos internos do LlamaIndex.

LangGraph deve orquestrar os nós downstream, mas regra de negócio continua em módulos de domínio. LangChain e LiteLLM podem ser usados em adapters de LLM, prompts, tools, structured output ou retrievers, sem decidir tecnologia NVIDIA, prioridade final ou readiness. A primeira versão do briefing deve ser determinística; geração narrativa por LLM pode ser adicionada depois atrás de `LLMClient`, schema versionado e quality gates.

O resultado esperado é um conjunto de artefatos auditáveis:

- `NVIDIAKnowledgeRetrieval` com documentos, chunks, citações, scores e estratégia de retrieval.
- `NVIDIARecommendationSet` com recomendações técnicas e de programa, ranking top 1 por gap ou oportunidade, prioridade final da oportunidade NVIDIA, complexidade, próxima ação e quality gate.
- `ExecutiveBriefing` com claims rotulados e fontes.
- `Human Review Briefing` quando houver baixo sinal, alto wrapper risk, conflito, excesso de `unknown` ou falta de fonte oficial NVIDIA.

## User Stories

1. As a gerente de Startups & VCs da NVIDIA, I want to receive a recommendation tied to a specific startup gap, so that I can decide whether outreach is worth my time.
2. As a gerente de Startups & VCs da NVIDIA, I want every NVIDIA recommendation to cite an official NVIDIA source, so that I can trust the recommendation in a commercial conversation.
3. As a gerente de Startups & VCs da NVIDIA, I want the system to calculate final NVIDIA opportunity priority after recommendations, so that AI maturity is not confused with outreach urgency.
4. As a gerente de Startups & VCs da NVIDIA, I want the briefing to show what was observed, inferred, recommended, and unknown, so that I can prepare a precise conversation with the founder.
5. As a gerente de Startups & VCs da NVIDIA, I want NVIDIA Inception to be recommended only when a technical gap or commercial opportunity supports it, so that the system does not produce a generic Inception pitch.
6. As a gerente de Startups & VCs da NVIDIA, I want technical recommendations and program recommendations separated, so that I can distinguish product fit from ecosystem or go-to-market fit.
7. As a gerente de Startups & VCs da NVIDIA, I want a top 1 recommendation per gap or opportunity, so that I can focus outreach on the most defensible angle.
8. As a gerente de Startups & VCs da NVIDIA, I want alternatives preserved when confidence is close, so that I can understand the tradeoff before outreach.
9. As a gerente de Startups & VCs da NVIDIA, I want a concise executive summary, so that I can quickly decide whether to review, approach, or deprioritize a startup.
10. As a gerente de Startups & VCs da NVIDIA, I want risks and unknowns visible in the briefing, so that I do not overstate the startup's technical maturity.
11. As a gerente de Startups & VCs da NVIDIA, I want a human review briefing when the system cannot safely recommend, so that weak evidence still becomes actionable review context.
12. As a gerente de Startups & VCs da NVIDIA, I want questions for founder validation, so that I can close evidence gaps in a meeting.
13. As a gerente de Startups & VCs da NVIDIA, I want wrapper/API-dependency risks surfaced alongside recommendations, so that I can avoid prioritizing shallow LLM wrappers as strategic opportunities.
14. As a technical reviewer, I want retrieved NVIDIA chunks to include source title, URL or reference, ingestion date, chunk identifier, and excerpt, so that I can audit each citation.
15. As a technical reviewer, I want retrieval output to show BM25 score, vector score, hybrid score, and ranking strategy when available, so that I can inspect why a citation was selected.
16. As a technical reviewer, I want the system to reject non-official NVIDIA sources for supported recommendations, so that unsupported knowledge does not enter factual outputs.
17. As a technical reviewer, I want recommendations without enough official source support to be marked as hypothesis or blocked, so that weak retrieval cannot become a factual briefing.
18. As a technical reviewer, I want a recommendation to reference both startup evidence and NVIDIA citation, so that both sides of the fit are traceable.
19. As a technical reviewer, I want the briefing to preserve conflicting evidence, so that contradictions are reviewed instead of silently resolved.
20. As a technical reviewer, I want explicit reasons when retrieval is insufficient, so that I can improve the corpus or query mapping.
21. As a technical reviewer, I want gap-to-technology ranking to consider gap severity, assessment confidence, source quality, and retrieval score, so that the top recommendation is defensible.
22. As a technical reviewer, I want program recommendations to use commercial opportunity vocabulary, so that go-to-market fit is not modeled as a technical gap.
23. As a technical reviewer, I want `AI-Native Assessment` output treated as input only, so that downstream recommendation does not redo scraping or reclassify maturity.
24. As a technical reviewer, I want the legacy preliminary opportunity field from assessment treated as signal, so that final priority remains owned by Recommendation.
25. As a developer, I want a versioned `NVIDIA Knowledge` schema, so that documents, chunks, citations, and retrieval results remain stable across implementations.
26. As a developer, I want a local NVIDIA corpus fixture, so that tests can validate retrieval without network calls.
27. As a developer, I want deterministic chunking, so that retrieval output remains stable between runs.
28. As a developer, I want BM25 lexical retrieval first, so that the project has an auditable retrieval baseline before embeddings.
29. As a developer, I want an `EmbeddingClient` contract, so that embedding provider, model, version, dimension, language, and cost can change without changing domain logic.
30. As a developer, I want fake deterministic embeddings for tests, so that the local suite can validate vector retrieval without external providers.
31. As a developer, I want vector retrieval to record embedding model, embedding version, corpus version, index parameters, and tie-breakers, so that semantic retrieval is reproducible.
32. As a developer, I want hybrid retrieval to merge lexical and vector candidates while preserving original scores, so that ranking remains explainable.
33. As a developer, I want duplicate chunks merged deterministically, so that the same citation does not appear multiple times with conflicting ranks.
34. As a developer, I want stable tie-breaking by document identifier and chunk index, so that equal scores do not create nondeterministic outputs.
35. As a developer, I want Postgres/pgvector planned as the local vector DB path, so that embeddings can later be persisted with auditable metadata.
36. As a developer, I want the local suite to use in-memory or fake vector storage, so that Postgres is not required for every test run.
37. As a developer, I want migrations for pgvector to be explicit, so that production-like development can create the vector extension and embedding tables safely.
38. As a developer, I want LlamaIndex behind a retriever adapter, so that Recommendation depends on project contracts, not framework objects.
39. As a developer, I want LangChain behind adapter seams, so that prompts, tools, structured outputs, and LLM clients do not leak into domain schemas.
40. As a developer, I want LiteLLM behind `LLMClient`, so that Grok, Groq, OpenRouter, Ollama, or another provider can be swapped without touching Recommendation.
41. As a developer, I want the LLM generator and embedding model decoupled, so that retrieval quality is chosen independently from generation provider.
42. As a developer, I want deterministic briefing generation first, so that the schema and quality gates are validated before adding LLM narrative generation.
43. As a developer, I want every downstream artifact to include `schema_version`, run identifier, startup identifier, and references to evidence or citations used, so that historical runs are auditable.
44. As a developer, I want JSON persistence for downstream artifacts, so that debugging and reprocessing remain simple during the walking skeleton phase.
45. As a developer, I want SQL persistence for retrievals, recommendations, and briefings, so that downstream history can be queried by run and startup.
46. As a developer, I want reprocessing of recommendations without repeating scraping, so that corpus and ranking changes can be tested cheaply.
47. As a developer, I want reprocessing of briefings without repeating retrieval when corpus version is unchanged, so that formatting changes do not recompute knowledge.
48. As a developer, I want graph nodes for retrieval, recommendation, and briefing to call small domain functions, so that LangGraph remains orchestration only.
49. As a developer, I want the local workflow runner to cover the full downstream path, so that tests do not require LangGraph installed.
50. As a developer, I want graph branches for `ready_for_recommendation`, `ready_for_briefing`, `briefing_generated`, and `human_review_requested`, so that the workflow exposes actionable status.
51. As a developer, I want every branch to carry an audit reason, so that operators know why the flow advanced or stopped.
52. As a developer, I want errors from retrievers, LLM adapters, or storage to become structured workflow data, so that one failure does not erase evidence.
53. As a product owner, I want retrieval quality metrics, so that I can see whether BM25, vector, or hybrid search is improving useful citations.
54. As a product owner, I want recommendation quality metrics, so that I can track recommendations with NVIDIA citation, startup evidence, gap specificity, and readiness.
55. As a product owner, I want human review rates by reason, so that I can identify whether the bottleneck is evidence collection, NVIDIA corpus coverage, retrieval, or recommendation gates.
56. As a product owner, I want gaps without recommendations listed, so that corpus expansion can target the missing NVIDIA knowledge.
57. As a product owner, I want briefings blocked by unknown, conflict, wrapper risk, or missing citation counted, so that readiness thresholds can be calibrated.
58. As a maintainer, I want no network dependency in tests, so that validation is fast and deterministic.
59. As a maintainer, I want no credentials required in tests, so that contributors can validate behavior locally.
60. As a maintainer, I want no real Postgres required in the core suite, so that SQL and pgvector remain optional integration paths.
61. As a maintainer, I want no mandatory LangGraph dependency for the local suite, so that orchestration remains testable through a local runner.
62. As a maintainer, I want no mandatory LlamaIndex dependency in the first slice, so that framework complexity follows measured need.
63. As a future RAG maintainer, I want reranking to operate only on candidate top K, so that it cannot generate new facts or hide low retrieval quality.
64. As a future RAG maintainer, I want reranker output to preserve original chunk, citation, score, and rationale, so that reranking remains auditable.
65. As a future briefing agent, I want briefing claims to carry confidence and source references, so that narrative output cannot blur factual status.
66. As a future briefing agent, I want supported recommendations, hypotheses, and blocked recommendations represented separately, so that the final artifact is safe to use.
67. As a future workflow operator, I want human review to include startup, area, discoveries, gaps, risks, conflicts, unknowns, and pending questions, so that manual review starts with context rather than an empty status.
68. As a future workflow operator, I want downstream artifacts persisted with corpus version and retrieval strategy, so that changes in NVIDIA knowledge can be audited.

## Implementation Decisions

- Build the next phase as four bounded contexts: `NVIDIA Knowledge`, `Recommendation`, `Briefing`, and downstream `Workflow`.
- Treat existing upstream contracts as fixed inputs: `StartupProfile`, `FieldEvidenceGroup`, `CollectionQualitySummary`, and `AINativeAssessment`.
- Do not repeat discovery, scraping, extraction, evidence grouping, or AI-native classification in downstream modules.
- Introduce schema version `nvidia_knowledge.v1` for official NVIDIA documents, chunks, citations, retrieval queries, retrieved chunks, retrieval quality, and retrieval result sets.
- Introduce schema version `nvidia_recommendation.v1` for recommendation sets, technical recommendations, program recommendations, blocked recommendations, hypotheses, recommendation quality, final NVIDIA opportunity priority, and next action.
- Introduce schema version `executive_briefing.v1` for executive briefings, human review briefings, briefing claims, evidence references, citation references, pending questions, and status.
- Keep `Evidence` and `Citation` separate. Startup-side public support remains `Evidence`; NVIDIA-side official support remains `Citation`.
- Require every downstream output to carry `schema_version`, run identifier, startup identifier, corpus version when applicable, and references to the evidence or citations used.
- The first `NVIDIA Knowledge` slice must load an offline corpus of official NVIDIA sources. Sources without official NVIDIA origin must be rejected or marked invalid for supported recommendations.
- Each NVIDIA document must include corpus version, source title, source URL or internal reference, source type, ingestion date, and serializable metadata.
- Each NVIDIA chunk must preserve document reference, chunk identifier, chunk order, text, topic or technology metadata, source type, and associated citation.
- Chunking must be deterministic, discard empty chunks, preserve source order, and produce stable identifiers.
- BM25 lexical retrieval is the first retrieval baseline and must not call LLMs, embeddings, vector DBs, network, or external services.
- BM25 retrieval must accept gap type, commercial opportunity type, description, startup signals, or normalized query terms.
- BM25 retrieval output must include score, rank, matched chunks, citation metadata, retrieval strategy, and an audit rationale.
- Retrieval quality must indicate whether the returned citations are sufficient to support a recommendation and must include reasons when insufficient.
- Add an `EmbeddingClient` contract before adding real embeddings. The contract records model, version, dimension, expected language behavior, corpus version, and rebuild requirements.
- Use fake deterministic embeddings in the local suite. Real embedding providers enter only through adapters.
- Vector retrieval must return chunks, vector scores, metadata, citation references, embedding metadata, and deterministic tie-breakers.
- Vector retrieval must not call LLMs or network in domain logic.
- Hybrid retrieval must combine lexical and vector candidates, deduplicate chunks, preserve original scores, and record ranking strategy.
- Acceptable initial hybrid ranking strategies include weighted score fusion or reciprocal rank fusion, as long as weights, parameters, and tie-breakers are explicit.
- Search results with equal scores must be ordered by stable metadata such as document identifier and chunk index.
- Postgres/pgvector is the preferred vector DB path once embedding persistence is needed. The first implementation may use in-memory or fake vector storage for local validation.
- The pgvector path requires explicit migration for vector extension, NVIDIA document/chunk metadata, embedding payloads, corpus version, embedding model, embedding version, and vector dimension.
- Approximate vector indexes such as HNSW or IVFFlat are not part of the first persistence requirement and should be added only when corpus size or latency justifies them.
- LlamaIndex may be used only behind a `NVIDIA Knowledge` adapter if the local implementation becomes too complex for ingestion, metadata-rich indices, citation handling, persistent indexes, hybrid retrieval, or reranking.
- Domain contracts must expose project dataclasses or schemas, not LlamaIndex nodes, LangChain documents, provider SDK objects, or framework-specific result objects.
- LangGraph owns workflow orchestration: state, checkpoints, retries, branches, and human-in-the-loop.
- Downstream graph nodes should be thin: retrieve NVIDIA knowledge, build recommendations, generate briefing, persist artifacts, and decide next action.
- LangGraph nodes must not implement ranking, recommendation rules, citation sufficiency, briefing claim typing, or business priority directly.
- The local workflow runner is the primary test seam. It must execute the downstream path without LangGraph installed.
- LangChain may be used inside adapters for LLM calls, prompts, tools, structured output, or retrievers, but it is not the global orchestrator and does not replace domain schemas.
- LiteLLM may be used behind `LLMClient` for provider switching, retries, endpoints, timeouts, and cost control.
- The LLM generator and embedding model are explicitly decoupled. Choosing Grok or another free LLM does not imply the same provider for embeddings.
- Recommendation consumes assessment gaps, wrapper risks, commercial opportunities, and retrieved NVIDIA citations.
- Recommendation must not invent new startup facts or mutate evidence.
- Recommendation must distinguish `technical`, `program`, and `next_action` recommendation types.
- A technical recommendation requires a technical gap and at least one official NVIDIA citation.
- A program recommendation requires a commercial opportunity or specific gap that justifies the program and at least one official NVIDIA citation.
- NVIDIA Inception is not a default recommendation. It is supported only when a specific gap or commercial opportunity justifies it.
- A recommendation without sufficient source support is `hypothesis` or `blocked`, never `supported`.
- Final NVIDIA opportunity priority is calculated only in Recommendation after matching startup evidence to official NVIDIA citation.
- The priority vocabulary is `urgent`, `medium`, `low`, and `human_review`.
- Recommendation quality must calculate `ready_for_briefing` and reasons for failure.
- High wrapper risk, critical conflict, weak startup evidence, missing official citation, or excessive unknowns can force `human_review_requested`.
- Briefing generation starts deterministic. It summarizes structured artifacts into a versioned briefing without LLM narrative generation.
- Briefing claims must be typed as `observed`, `inferred`, `recommended`, or `unknown`.
- Briefing must include executive summary, startup profile highlights, AI-native diagnosis, opportunity, gaps, risks, recommendations, pending questions, evidence references, citation references, and next action.
- Human review must generate a full `Human Review Briefing`, not just a status flag.
- Human Review Briefing must include startup, area of atuação, what was discovered, main evidence, suspected gaps, commercial opportunities, wrapper risks, conflicts, unknowns, reasons for review, and validation questions.
- Persist downstream artifacts in JSON processed outputs for debugging and reprocessing.
- Extend SQL persistence to store knowledge snapshots or corpus metadata, retrievals, recommendations, and briefings as payloads by run and startup.
- Reprocessing recommendation should not require repeating scraping when startup evidence and assessment are already persisted.
- Reprocessing briefing should not require repeating retrieval when corpus version and retrieval result set are unchanged.
- Metrics must be produced for retrieval readiness, recommendations with official citation, recommendations with startup evidence, gaps without recommendation, briefings blocked, and human review reason counts.

## Testing Decisions

- The highest-value test seam is a local downstream workflow runner that consumes persisted or fixture upstream artifacts plus a local NVIDIA corpus and returns retrieval, recommendation, briefing, and `next_action`.
- This single workflow seam should cover the successful path, missing NVIDIA citation path, high wrapper risk path, conflict path, and human review path.
- Module-level tests are still needed for deterministic retrieval, vector search, hybrid ranking, recommendation rules, briefing claims, serialization, and persistence, but the primary confidence should come from the highest workflow seam.
- Tests should assert external behavior and schema contracts, not private helper implementation.
- The local suite must not depend on network, credentials, real Postgres, LangGraph installed, LlamaIndex installed, LiteLLM configured, LangChain configured, or any external LLM/embedding provider.
- Retrieval tests should use a small official NVIDIA corpus fixture with stable corpus version and stable chunk identifiers.
- BM25 tests should cover relevant match, no match, ranking order, duplicate handling, and citation sufficiency.
- Embedding tests should use fake deterministic embeddings and verify model metadata, vector dimension, stable ordering, and rebuild requirements.
- Vector retrieval tests should cover semantic match, no match, tie-breaking, and metadata preservation.
- Hybrid retrieval tests should cover lexical winner, vector winner, merged duplicate, and deterministic tie.
- Recommendation tests should cover at least four technical gap types from the controlled vocabulary.
- Program recommendation tests should cover Inception allowed, Inception blocked, and commercial opportunity requiring human validation.
- Recommendation quality tests should cover `supported`, `hypothesis`, `blocked`, `ready_for_briefing`, and `human_review_requested`.
- Briefing tests should verify that every claim is typed and that observed, inferred, recommended, and unknown claims are not mixed.
- Briefing tests should verify that missing funding, clients, founders, technologies, or NVIDIA fit remains `unknown` or question, not invented text.
- Human review tests should verify that the system produces a detailed briefing for low signal, high wrapper risk, critical conflict, and missing official NVIDIA citation.
- Workflow tests should use a local runner, mirroring the existing pattern where LangGraph remains optional.
- SQL repository tests should use SQLite for payload persistence. pgvector behavior should be isolated behind adapter or migration tests that are optional until Postgres integration is configured.
- JSON persistence tests should verify that downstream artifacts can be saved and reloaded with schema version, run identifier, startup identifier, corpus version, and citation references intact.
- Adapter tests for LangChain, LiteLLM, LlamaIndex, real embeddings, and pgvector should use fakes or contract tests first. Real integration tests can be optional and excluded from the default local suite.
- Retrieval metrics tests should validate recall/precision calculations over fixture expectations before changing model, embedding, ranking strategy, or framework.
- Prior art for test shape exists in the current pipeline, scraping graph, AI-native assessment, startup profile, collection quality, evidence grouping, JSON persistence, and SQL repository patterns, even though the old automated suite is not currently valid.

## Out of Scope

- Reworking Discovery, Collection, Profile Extraction, Evidence Quality, or AI-Native Assessment.
- Adding Playwright, Scrapy, Firecrawl, BeautifulSoup, trafilatura, or scraping hardening as part of this PRD.
- Calling live NVIDIA documentation during tests.
- Using non-official NVIDIA sources to support factual recommendations.
- Recommending NVIDIA technologies directly from an LLM prompt without retrieved citation support.
- Treating LlamaIndex, LangChain, LiteLLM, pgvector, or any framework as a replacement for domain contracts.
- Requiring a real LLM, embedding provider, network, credentials, Postgres, or LangGraph in the default local suite.
- Building a UI or dashboard.
- Automating contact with startups.
- Enriching with private data, CRM records, authenticated sources, paid databases, funding APIs, or founder outreach data.
- Producing a definitive commercial ranking without human review.
- Adding neural reranking before BM25, vector retrieval, hybrid ranking, and metrics expose a measured need.
- Using a managed external vector database before validating local Postgres/pgvector or in-memory vector retrieval.
- Persisting or executing untrusted macros, notebooks, scripts, or fetched web content as part of corpus ingestion.

## Further Notes

The implementation should preserve the current walking skeleton philosophy: complete the downstream line before optimizing scale. The first slice can be small if it proves the contracts: one local official NVIDIA corpus fixture, deterministic chunks, BM25 retrieval, one or two supported recommendations, one blocked recommendation, one executive briefing, and one human review briefing.

The controlled vocabulary in the domain model should remain the source for classifications, technical gaps, commercial opportunities, wrapper risk signals, recommendation states, recommendation types, final opportunity priority, knowledge source type, and briefing status.

The most important product metric for this phase is not retrieval sophistication by itself. It is the rate of recommendations that have both startup evidence and official NVIDIA citation tied to a specific gap or commercial opportunity, and the rate of briefings that are useful without critical rework.

Validation note: the project currently has no valid automated suite. This PRD assumes the next implementation also reconstructs a focused local validation suite for the downstream contracts instead of relying on the removed tests.
