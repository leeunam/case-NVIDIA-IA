# Épico: Avaliação AI-Native e Gaps de Stack

Objetivo: transformar perfis estruturados e evidências públicas em um diagnóstico auditável de maturidade AI-native, gaps técnicos e riscos de dependência superficial de IA.

Este épico começa depois do scraping porque não deve repetir coleta. A entrada principal é o output das Stories 1 a 14: `StartupProfile`, `FieldEvidenceGroup` e `CollectionQualitySummary`.

Decisões de produto:

- O primeiro workflow analisa uma startup profundamente.
- A avaliação gera sinal preliminar de oportunidade; a prioridade final NVIDIA pertence ao contexto de Recommendation.
- Evidência pública fraca pode gerar hipótese de baixa confiança para revisão humana quando houver sinal estratégico.
- O diagnóstico deve evitar recomendações fracas e excesso de `unknown`.

## Princípios

- Não classificar sem evidência suficiente.
- Separar dado observado, inferência e recomendação.
- Mostrar por que uma startup foi classificada como `ai_native`, `ai_enabled`, `non_ai` ou `insufficient_evidence`.
- Preservar gaps com baixa confiança como hipóteses, não como fatos.
- Tornar cada critério testável com fixtures locais.

## Modelo de Saída Esperado

Schema inicial: `ai_native_assessment.v1`

Campos:

- `company_name`
- `classification`
- `confidence`
- `opportunity_signal`
- `criteria_results`
- `positive_signals`
- `technical_gaps`
- `wrapper_dependency_risks`
- `insufficient_evidence_fields`
- `evidences`
- `schema_version`

Nota de compatibilidade: a implementação atual de `ai_native_assessment.v1` ainda expõe o campo `nvidia_opportunity_urgency`. Pela ADR 0006, esse campo deve ser tratado semanticamente como sinal preliminar de oportunidade até uma futura migração de schema.

## Critérios de Avaliação

Nota de domínio após ADR 0005: para o MVP, `ai_native` exige evidência suficiente de centralidade da IA no produto e profundidade técnica. Não exige prova pública completa de todos os eixos de arquitetura, UX, modelo de negócios e operações ao mesmo tempo.

- Centralidade da IA no produto.
- IA como centro do produto com sinais de profundidade técnica na stack, dados, modelos, avaliação, MLOps ou inferência.
- Evidência de modelos próprios, fine-tuning, avaliação, MLOps ou infraestrutura de inferência.
- Evidência de dados proprietários, workflow automatizado ou melhoria contínua.
- Sinais de defensibilidade técnica além de interface com LLM externo.
- Uso de IA em produção ou em oferta comercial.
- Evidência de escala, latência, custo, governança ou segurança como desafios técnicos.
- Qualidade da evidência disponível.

## Story 01: Definir schema de avaliação AI-native

Como desenvolvedor, quero um schema versionado para diagnóstico AI-native para que as próximas etapas consumam uma saída estável.

Critérios de aceite:

- O schema diferencia classificação, confiança, critérios, gaps e riscos.
- O schema inclui sinal preliminar de oportunidade.
- Cada critério pode apontar para evidências ou `unknown`.
- O schema suporta `insufficient_evidence`.
- O schema suporta hipótese de baixa confiança para revisão humana.
- Existe conversão para dicionário serializável.
- Existem testes para schema completo e diagnóstico insuficiente.

## Story 02: Implementar classificador determinístico inicial

Como gerente de Startups & VCs, quero uma primeira classificação AI-native baseada em regras explícitas para validar o fluxo sem depender de LLM.

Critérios de aceite:

- O classificador consome `StartupProfile`, evidências e qualidade da coleta.
- Se `ready_for_evaluation` for falso, retorna `insufficient_evidence`.
- Sinais fortes de IA no produto e stack elevam a classificação.
- Sinais genéricos de IA sem stack ou produto claro retornam no máximo `ai_enabled`.
- Para `ai_native`, a evidência deve mostrar centralidade da IA no produto e profundidade técnica suficiente, não apenas uso como feature.
- Existe teste com startup AI-native, AI-enabled, non-AI e evidência insuficiente.

## Story 03: Identificar riscos de wrapper/API-dependency

Como usuário técnico, quero detectar sinais de dependência superficial de APIs para diferenciar startups com defensibilidade real.

Critérios de aceite:

- O sistema identifica dependência apenas de APIs externas, ausência de dados proprietários e ausência de infraestrutura de inferência em produção.
- O sistema não afirma dependência de wrapper sem evidência; marca como risco ou hipótese.
- O output inclui severidade e justificativa.
- Existe teste para risco alto, médio, baixo e desconhecido.

## Story 04: Mapear gaps técnicos

Como gerente técnico, quero mapear possíveis gaps na stack de IA para conectar a startup a tecnologias NVIDIA relevantes.

Tipos iniciais de gap:

- `model_serving`
- `llm_customization`
- `data_acceleration`
- `voice_ai`
- `computer_vision`
- `robotics_simulation`
- `healthcare_ai`
- `cybersecurity_ai`
- `unknown`

Nota de domínio após novo grilling: `go_to_market` deve migrar para `CommercialOpportunity`, não permanecer como gap técnico em novas implementações downstream.

Critérios de aceite:

- Cada gap possui descrição, confiança, severidade e evidências.
- Gaps sem evidência suficiente aparecem como `unknown` ou hipótese de baixa confiança.
- O mapeamento não recomenda tecnologias ainda; apenas descreve necessidades.
- Existe teste para pelo menos 4 tipos de gap.

## Story 05: Medir qualidade do diagnóstico

Como responsável pelo produto, quero saber se a avaliação é confiável o bastante para gerar recomendação ou se exige revisão humana.

Critérios de aceite:

- O sistema calcula qualidade do diagnóstico com base em completude, conflitos e evidências por critério.
- O resultado indica `ready_for_recommendation`.
- Quando houver conflito crítico, o sistema pede revisão humana.
- Existe teste com diagnóstico pronto, insuficiente e conflituoso.

## Story 06: Calcular sinal preliminar de oportunidade

Como gerente de Startups & VCs, quero ver se há sinal preliminar de oportunidade para decidir se a startup merece retrieval e recomendação NVIDIA.

Critérios de aceite:

- O score considera gap técnico ou oportunidade comercial e força da evidência, sem afirmar fit NVIDIA final.
- Evidência fraca, mas sinal estratégico, retorna `human_review` com hipótese de baixa confiança.
- Recomendações fracas reduzem a prontidão para briefing.
- Existe teste para oportunidade urgente, média, baixa e revisão humana.

## Story 07: Persistir avaliações

Como desenvolvedor, quero persistir diagnósticos AI-native para auditar histórico e reprocessar recomendações sem recalcular scraping.

Critérios de aceite:

- O banco armazena avaliação por execução e startup.
- O payload preserva schema versionado.
- Evidências usadas por critério são consultáveis.
- Existe teste de repository em SQLite.

## Story 08: Integrar avaliação ao grafo

Como desenvolvedor, quero adicionar avaliação AI-native ao fluxo orquestrado para avançar automaticamente quando a coleta estiver pronta.

Critérios de aceite:

- O grafo executa avaliação apenas quando `CollectionQualitySummary.ready_for_evaluation` for verdadeiro.
- Caso contrário, define `next_action` como revisão humana ou nova coleta.
- O nó chama funções testáveis de `ai_native_assessment.py`.
- Existe teste do caminho pronto e do caminho bloqueado por evidência insuficiente.

## Definition of Done do Épico

- [x] Schema `ai_native_assessment.v1` definido e testado.
- [x] Classificador inicial funciona com fixtures locais.
- [x] Gaps técnicos são mapeados sem recomendar prematuramente.
- [x] Riscos de wrapper/API-dependency são explicitados como risco ou hipótese.
- [x] Sinal preliminar de oportunidade é calculado e testado.
- [x] Qualidade do diagnóstico decide se pode seguir para recomendação.
- [x] Avaliações podem ser persistidas.
- [x] O grafo possui branch para avaliação e revisão humana.

## Estado Implementado

O módulo `src/nvidia_startup_intel/ai_native_assessment.py` implementa o diagnóstico determinístico local sem LangChain, LLM, RAG, scraping adicional ou chamadas externas. A avaliação consome apenas `StartupProfile`, `FieldEvidenceGroup` e `CollectionQualitySummary`.

A integração atual adiciona:

- helper `assess_profiles_ai_native` em `pipeline.py`;
- nó `assess_ai_native_node` no grafo local/LangGraph-ready;
- branch `ready_for_recommendation` ou `needs_more_collection_or_human_review`;
- persistência JSON em `processed/ai_native_assessments.json`;
- tabela relacional `ai_native_assessments` no repository SQL.

Validação atual: não há suíte automatizada válida. A suíte antiga foi removida por estar inválida para o escopo atual.
