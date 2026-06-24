---
title: "PRD: Avaliação AI-Native e Gaps de Stack"
labels:
  - ready-for-agent
status: implemented
issue_url: https://github.com/leeunam/case-NVIDIA-IA/issues/2
---

# PRD: Avaliação AI-Native e Gaps de Stack

## Problem Statement

O gerente de Startups & VCs da NVIDIA no Brasil precisa decidir quais startups brasileiras justificam uma abordagem técnica e comercial para o NVIDIA Inception. O MVP de scraping já encontra candidatas, coleta páginas públicas, extrai `StartupProfile`, agrupa evidências e mede qualidade da coleta, mas ainda não transforma esses artefatos em diagnóstico de maturidade AI-native.

Hoje, o risco central é tratar toda startup que menciona IA como oportunidade equivalente. Isso não resolve a decisão operacional: separar startups em que IA molda produto, arquitetura, modelo de negócios e operação daquelas que apenas usam IA como feature incremental ou dependem superficialmente de APIs externas. Sem uma avaliação auditável, o sistema pode gerar recomendações fracas, excesso de `unknown` ou priorização comercial sem base técnica.

## Solution

Criar a capacidade de `AI-Native Assessment` como próximo passo do walking skeleton. Ela deve consumir somente os artefatos já produzidos pelo scraping: `StartupProfile`, `FieldEvidenceGroup` e `CollectionQualitySummary`. A avaliação não deve repetir scraping nem consultar provedores externos.

A solução deve produzir um diagnóstico versionado `ai_native_assessment.v1` com classificação, confiança, sinal preliminar de oportunidade, critérios avaliados, sinais positivos, gaps técnicos, riscos de dependência superficial de APIs ou wrappers, campos insuficientes e evidências usadas por critério. Quando a coleta não estiver pronta, o diagnóstico deve retornar `insufficient_evidence` e encaminhar para nova coleta ou revisão humana.

O primeiro classificador deve ser determinístico, testável com fixtures locais e explícito o bastante para validar o fluxo antes de introduzir LLMs. A orquestração deve entrar no grafo como nó fino depois da medição de qualidade, mantendo as regras de classificação, gaps, riscos e sinal preliminar em módulo de domínio.

## User Stories

1. As a gerente de Startups & VCs da NVIDIA, I want to see whether a startup is `ai_native`, `ai_enabled`, `non_ai`, or `insufficient_evidence`, so that I can prioritize my outreach with technical confidence.
2. As a gerente de Startups & VCs da NVIDIA, I want each classification to show the evidence used, so that I can trust the diagnosis before approaching a founder.
3. As a gerente de Startups & VCs da NVIDIA, I want the assessment to distinguish observed data from inferred claims, so that I can avoid treating hypotheses as facts.
4. As a gerente de Startups & VCs da NVIDIA, I want low-confidence strategic signals to be marked for human review, so that I do not ignore potentially valuable startups with weak public evidence.
5. As a gerente de Startups & VCs da NVIDIA, I want a score or label for NVIDIA opportunity urgency, so that I can decide which startups to approach first.
6. As a gerente de Startups & VCs da NVIDIA, I want urgent opportunities to be tied to concrete gaps, so that prioritization is not just a generic AI maturity ranking.
7. As a gerente de Startups & VCs da NVIDIA, I want weak recommendations to reduce readiness for the next stage, so that the system does not produce low-value briefings.
8. As a technical reviewer, I want the assessment to show which criteria were evaluated, so that I can inspect why the system reached a classification.
9. As a technical reviewer, I want the criteria to cover centrality of IA in product, architecture, UX, business model, and operations, so that AI-native status matches the project definition.
10. As a technical reviewer, I want the criteria to detect evidence of proprietary models, fine-tuning, evaluation, MLOps, or inference infrastructure, so that technical depth is not confused with marketing language.
11. As a technical reviewer, I want the criteria to detect evidence of proprietary data or feedback loops, so that defensibility is part of the assessment.
12. As a technical reviewer, I want the criteria to detect evidence of AI in production or a commercial offer, so that experimental AI claims do not get overvalued.
13. As a technical reviewer, I want the criteria to detect scale, latency, cost, governance, and security challenges, so that NVIDIA opportunity is connected to real technical needs.
14. As a technical reviewer, I want generic AI mentions to classify as at most `ai_enabled` unless deeper evidence exists, so that wrapper-like startups are not overclassified.
15. As a technical reviewer, I want a startup with no relevant AI evidence to classify as `non_ai` or `insufficient_evidence`, so that absence of evidence is handled explicitly.
16. As a technical reviewer, I want a startup with good AI product evidence but weak stack evidence to receive a lower confidence score, so that uncertainty is visible.
17. As a technical reviewer, I want conflicting evidence to block or reduce readiness for recommendation, so that the system does not silently choose one source.
18. As a developer, I want a versioned assessment schema, so that downstream recommendation and briefing modules can consume stable contracts.
19. As a developer, I want every assessment output to include `schema_version`, execution identifier, and evidence references, so that historical runs remain auditable.
20. As a developer, I want the assessment module to consume profile, evidence groups, and collection quality only, so that domain dependencies keep flowing forward.
21. As a developer, I want the assessment module to avoid scraping, search, RAG, or LLM calls, so that tests remain deterministic and local.
22. As a developer, I want the graph node to call tested assessment functions, so that orchestration does not hide business rules.
23. As a developer, I want the local graph runner to cover the assessment branch, so that LangGraph remains optional for the local suite.
24. As a developer, I want the graph to skip assessment when `ready_for_evaluation` is false, so that poor collection quality does not produce false certainty.
25. As a developer, I want the graph to set `next_action` to review or recollection when evidence is insufficient, so that the workflow remains actionable.
26. As a developer, I want `ready_for_recommendation` to be computed after assessment, so that NVIDIA recommendations only happen after diagnostic quality is acceptable.
27. As a developer, I want assessment serialization to use plain dictionaries, so that JSON and SQL persistence can store outputs without custom runtime objects.
28. As a developer, I want the SQL repository to store assessment payloads by run and startup, so that later recommendations can be reprocessed without redoing scraping.
29. As a developer, I want persisted assessment records to include evidence used by criterion, so that audits can trace every classification decision.
30. As a developer, I want deterministic fixtures for `ai_native`, `ai_enabled`, `non_ai`, and `insufficient_evidence`, so that behavior is easy to validate.
31. As a product owner, I want assessment quality metrics, so that I can know whether the MVP produces useful diagnostics or too many unknowns.
32. As a product owner, I want unknown fields listed explicitly, so that future work can target the most damaging collection and extraction gaps.
33. As a product owner, I want wrapper/API-dependency risks surfaced separately from AI maturity, so that promising startups are not rejected solely because evidence is incomplete.
34. As a product owner, I want wrapper/API-dependency risks to include external API reliance, no proprietary data evidence, and no production inference evidence, so that risks match the strategic thesis.
35. As a product owner, I want risk severity and confidence to be explicit, so that hypotheses do not become accusations.
36. As a product owner, I want gaps to be mapped before NVIDIA technologies are recommended, so that recommendation remains grounded in startup needs.
37. As a product owner, I want gap types to use the controlled vocabulary, so that recommendation and briefing can reuse consistent categories.
38. As a product owner, I want gap hypotheses to be allowed when evidence is weak but strategic, so that human review can validate them later.
39. As a future recommendation agent, I want technical gaps to include description, severity, confidence, and evidence, so that I can retrieve relevant NVIDIA knowledge.
40. As a future recommendation agent, I want `unknown` gaps to remain explicit, so that I do not invent NVIDIA fit where the diagnosis lacks support.
41. As a future briefing agent, I want the assessment to expose positive signals and risks separately, so that the briefing can summarize opportunity and uncertainty.
42. As a future briefing agent, I want the assessment to expose insufficient evidence fields, so that the briefing can list questions for human validation.
43. As a future workflow operator, I want the assessment stage to be rerunnable from stored scraping artifacts, so that collection and diagnosis can evolve independently.
44. As a future workflow operator, I want assessment failures to be captured as data, so that one bad startup does not break the full run.
45. As a maintainer, I want rule thresholds to be easy to adjust, so that the team can calibrate classification after reviewing real outputs.
46. As a maintainer, I want no new heavy dependencies for the first assessment version, so that the walking skeleton remains simple.
47. As a maintainer, I want tests to assert outputs and transitions, so that implementation details can change without breaking useful behavior.
48. As a maintainer, I want current scraping behavior to remain unchanged, so that the validated upstream contract is preserved.
49. As a maintainer, I want `unknown` to remain the default for unsupported information, so that the evidence-first architecture stays intact.
50. As a maintainer, I want the assessment to be documented in the roadmap and context docs, so that future RAG, recommendation, and briefing work has a clear upstream contract.

## Implementation Decisions

Domain update after ADR 0005: `ai_native` should be interpreted operationally as enough public evidence of AI centrality plus technical depth. New downstream work should treat go-to-market and Inception fit as commercial opportunities, not technical gap types.

Domain update after ADR 0006: assessment should expose an opportunity signal only. Final NVIDIA opportunity priority belongs to recommendation after official NVIDIA knowledge retrieval.

Compatibility note: the current implemented `ai_native_assessment.v1` still exposes `nvidia_opportunity_urgency`; downstream work should treat it as a legacy field carrying the preliminary opportunity signal, not final NVIDIA priority.

- Build a new `AI-Native Assessment` domain module responsible for schema, serialization, deterministic classification, gap mapping, wrapper risk detection, diagnostic quality, and preliminary opportunity signal.
- Introduce schema version `ai_native_assessment.v1`.
- The assessment input contract is `StartupProfile`, `FieldEvidenceGroup`, and `CollectionQualitySummary`.
- The assessment output contract includes company name, classification, confidence, preliminary opportunity signal, criteria results, positive signals, technical gaps, wrapper dependency risks, insufficient evidence fields, evidences, `schema_version`, run identifier, and readiness for recommendation.
- Classification vocabulary is `ai_native`, `ai_enabled`, `non_ai`, and `insufficient_evidence`.
- Opportunity priority vocabulary is `urgent`, `medium`, `low`, and `human_review`.
- Gap type vocabulary is `model_serving`, `llm_customization`, `data_acceleration`, `voice_ai`, `computer_vision`, `robotics_simulation`, `healthcare_ai`, `cybersecurity_ai`, and `unknown`. Earlier implementation notes that mention `go_to_market` should be treated as legacy and migrated to commercial opportunity vocabulary in downstream work.
- Wrapper risk signals are `external_api_only`, `no_proprietary_data_evidence`, `no_production_inference_evidence`, and `unknown`.
- The first classifier is deterministic and rule-based. LLM classification is out of scope for this PRD.
- A startup can be classified as `ai_native` only when evidence supports IA as central to product, architecture, UX, business model, or operations. Generic AI mentions are not enough.
- `ai_enabled` covers startups where IA is relevant but public evidence does not show that IA shapes the core business or stack.
- `non_ai` covers startups with enough public profile evidence but no relevant AI signal.
- `insufficient_evidence` covers cases where collection quality or profile evidence is too weak to classify.
- Low-confidence hypotheses are allowed only when marked as inference or human review, with evidence and confidence shown.
- The assessment must not call search, scraping, RAG, LLMs, external APIs, or Postgres directly from pure rule functions.
- The graph adds an assessment node after collection quality is measured.
- The graph only executes assessment automatically when collection quality is ready for evaluation.
- When collection quality is not ready, the graph sets a review or recollection next action instead of producing a normal assessment.
- A later branch should distinguish `ready_for_recommendation` from `needs_more_collection_or_human_review`.
- Persistence should store assessment payloads by run and startup while keeping JSON payload flexibility during the walking skeleton phase.
- Existing scraping contracts should remain unchanged. This feature is a downstream consumer, not a scraping rewrite.
- The implementation should preserve raw evidence and should not mutate collected pages or discovery artifacts.

## Testing Decisions

- The highest integration seam is the existing pipeline and graph boundary: assessment should be tested after profile extraction, evidence grouping, and collection quality, using local fixtures.
- Future domain validation should cover classification, criteria results, gap mapping, wrapper risks, opportunity signal, diagnostic quality, serialization, and insufficient evidence behavior.
- Graph tests should validate the ready path and blocked path using the local graph runner, not the optional LangGraph dependency.
- Repository tests should use SQLite, matching the existing DB-API persistence pattern.
- Good tests should assert external behavior and schema contracts, not internal implementation details or private helper logic.
- Tests should include at least one fixture each for `ai_native`, `ai_enabled`, `non_ai`, and `insufficient_evidence`.
- Tests should include wrapper risk cases for high, medium, low, and unknown risk.
- Tests should include at least four technical gap types from the controlled vocabulary.
- Tests should verify that unsupported fields remain `unknown` and do not get filled by assumptions.
- Tests should verify that every positive signal, gap, risk, and criterion result can point to evidence or explicitly state insufficient evidence.
- Tests should verify that weak collection quality prevents normal assessment progression.
- Tests should verify that conflicting critical evidence reduces readiness or triggers human review.
- Prior art for tests exists in current pipeline, scraping graph, collection quality, evidence, startup profile, and SQL repository tests.
- A future local validation suite must not depend on network, credentials, Postgres, LangGraph, or external providers.

## Out of Scope

- Reworking the existing scraping MVP.
- Adding Playwright, Scrapy, Firecrawl, BeautifulSoup, trafilatura, or a vector database.
- Using LLMs to classify startups.
- Consulting NVIDIA RAG or recommending NVIDIA technologies.
- Generating executive briefings.
- Building a UI.
- Automating startup outreach.
- Enriching with private data, CRM records, authenticated sources, or paid databases.
- Producing a definitive commercial ranking without human review.
- Recommending NVIDIA Inception without a specific technical or commercial gap.
- Treating weak hypotheses as facts.

## Further Notes

The current scraping and discovery MVP is good enough as upstream for this PRD because it already produces the required contracts and has deterministic local coverage. Its main limitations are recall from directory/news results, JS-heavy sites, brittle extraction from unlabeled marketing copy, and run-level rather than deeply per-startup quality. Those limitations should be observed through the assessment outputs before investing in heavier scraping infrastructure.

Validation note: the old automated suite was removed because it is invalid for the current scope. A new validation suite is required before relying on automated test results again.

Publishing note: the tracked GitHub issue URL is recorded in the frontmatter.
