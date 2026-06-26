# Roadmap: NVIDIA Knowledge, Recommendation e Briefing

Objetivo: completar a linha vertical depois de `ai_native_assessment.v1`, transformando gaps técnicos e riscos em recomendações NVIDIA citáveis e em briefing executivo útil para abordagem comercial e técnica.

Este roadmap começa pequeno, mas o alvo de `NVIDIA Knowledge` é busca híbrida reprodutível: BM25 lexical + vetorial + merge/ranking determinístico. A primeira fatia deve criar corpus local, chunking e busca BM25; em seguida deve adicionar embeddings versionados e busca vetorial local antes de Recommendation depender de retrieval híbrido. O vector DB preferido, quando necessário, é Postgres local com `pgvector`. Vector database externo gerenciado, reranking neural, crawling de documentação e UI ficam fora da primeira entrega até o contrato estar validado com fixtures.

A estratégia de frameworks, LiteLLM, BM25, busca vetorial, Postgres/pgvector, busca híbrida, LlamaIndex e reranking está em `context/frameworks-and-retrieval-strategy.md`.

## Status Atual

O walking skeleton downstream deste roadmap está implementado no pacote `src/nvidia_startup_intel` e coberto pela suíte local padrão. Ele mantém o caminho default sem rede, credenciais, Postgres real, LangGraph obrigatório, LlamaIndex, LangChain, LiteLLM, LLM real ou embedding provider real.

Implementado no core local:

- `NVIDIA Knowledge`: schema versionado, corpus fixture oficial, chunking determinístico, BM25 lexical, qualidade de retrieval, contrato de embedding, fake embedding determinístico, busca vetorial local e retrieval híbrido.
- `Recommendation`: recomendações técnicas por gap, recomendações de programa/Inception com gate específico, hipóteses, bloqueios, prioridade final, quality gate e métricas.
- `Briefing`: `ExecutiveBriefing` determinístico e `HumanReviewBriefing` versionado para baixo sinal, alto wrapper risk, conflitos, unknowns, hipóteses ou falta de citação oficial.
- `Workflow`: runner downstream local com branches auditáveis `ready_for_recommendation`, `ready_for_briefing`, `briefing_generated`, `human_review_requested` e `needs_more_collection_or_human_review`.
- `Persistence`: snapshots JSON e payloads SQL downstream por run e startup, permitindo reprocessamento sem repetir scraping.
- `Framework adapters`: contratos opcionais para `LLMClient`, LiteLLM, LangChain, retrievers framework-free e reranking top K sem vazar objetos externos para o domínio.
- `Postgres/pgvector`: schema, Docker Compose e adapter de busca exata SQL existem como caminho opcional; validação com Postgres real continua fora da suíte default.

Follow-ups recomendados:

- Expandir corpus oficial NVIDIA e expectativas de métricas para mais tecnologias, programas e gaps.
- Calibrar thresholds de retrieval, recomendação, wrapper risk e human review com casos revisados.
- Validar Postgres/pgvector com instância real quando houver ambiente de integração.
- Adicionar grafo downstream LangGraph somente quando checkpoints, retry ou human-in-the-loop reais forem necessários.
- Implementar adapter LlamaIndex real apenas se ingestão, índices persistentes, metadados, citações ou reranking justificarem a complexidade.
- Integrar provedores reais de LLM, embedding ou reranking somente atrás dos contratos atuais e fora da suíte padrão.

## Contrato De Entrada

- `StartupProfile` `startup_profile.v1`
- `FieldEvidenceGroup`
- `CollectionQualitySummary`
- `AINativeAssessment` `ai_native_assessment.v1`
- corpus NVIDIA versionado com fontes oficiais armazenadas localmente para teste

## Contrato De Saída

- `NVIDIAKnowledgeRetrieval` `nvidia_knowledge.v1`
- `NVIDIARecommendationSet` `nvidia_recommendation.v1`
- `ExecutiveBriefing` `executive_briefing.v1`
- `next_action` explícito: `ready_for_briefing`, `briefing_generated` ou `human_review_requested`

## Princípios

- Recuperação de conhecimento não recomenda; apenas retorna trechos citáveis.
- Recomendação sempre parte de um gap técnico ou oportunidade comercial diagnosticada.
- Tecnologia NVIDIA sem fonte oficial vira hipótese ou é bloqueada.
- Prioridade final da oportunidade NVIDIA é calculada neste contexto, não em assessment.
- Inception só aparece quando houver gap técnico ou comercial específico.
- Briefing mostra incertezas e unknowns em vez de suavizar lacunas.
- Human review também gera briefing: baixo sinal, alto wrapper risk ou falta de fonte não podem resultar em status vazio.
- A suíte local continua sem rede, credenciais, Postgres real, LangGraph obrigatório ou provedor externo.
- O LLM gerador e o embedding ficam desacoplados por interfaces; Grok ou outro LLM gratuito não define automaticamente o modelo de embedding.
- Busca vetorial só é considerada determinística quando corpus, chunking, modelo de embedding, versão, índice, parâmetros e critérios de desempate estão fixados.
- Vector DB deve ser Postgres local com `pgvector` antes de considerar serviço externo dedicado.

## Épico 1: NVIDIA Knowledge Híbrido Reprodutível

Como desenvolvedor, quero uma base NVIDIA versionada, com busca lexical e vetorial reprodutíveis, para que recomendações possam citar fontes oficiais sem depender de rede.

### Story 01: Definir schema de conhecimento NVIDIA

Critérios de aceite:

- Existe `nvidia_knowledge.py`.
- O schema inclui documento, chunk, citação e resultado recuperado.
- Cada documento possui `schema_version`, `corpus_version`, título, fonte, tipo de fonte e data de ingestão.
- Cada chunk preserva trecho, índice, tecnologia ou tópico e referência ao documento.
- Existe conversão para dicionário serializável.
- Existem testes para documento, chunk e citação.

### Story 02: Criar corpus local mínimo de fontes oficiais

Critérios de aceite:

- Existe fixture local com documentos oficiais NVIDIA suficientes para pelo menos quatro gap types ou oportunidades comerciais.
- A fixture não depende de rede nem credenciais.
- Cada trecho possui origem explícita.
- O corpus pode ser carregado em testes de forma determinística.
- O corpus rejeita ou marca como inválida qualquer fonte sem origem oficial NVIDIA.

### Story 03: Implementar chunking determinístico

Critérios de aceite:

- O chunking preserva documento de origem, ordem e trecho.
- Chunks vazios são descartados.
- O tamanho dos chunks é previsível e testável.
- A saída é estável entre execuções.

### Story 04: Implementar busca lexical BM25 por gap

Critérios de aceite:

- A busca recebe technical gap type ou commercial opportunity type, descrição e sinais da startup.
- A saída retorna chunks ranqueados com score BM25 e rationale simples.
- Pelo menos um teste cobre resultado encontrado e nenhum resultado encontrado.
- A busca não chama LLM, embedding, vector DB ou rede.

### Story 05: Medir qualidade da recuperação

Critérios de aceite:

- O resultado indica se há citação suficiente para recomendação.
- Resultado sem fonte suficiente marca motivo auditável.
- Existe teste para recuperação pronta e recuperação insuficiente.

### Story 06: Implementar contrato de embedding

Critérios de aceite:

- Existe interface `EmbeddingClient` ou equivalente.
- O schema registra `embedding_model`, `embedding_version`, dimensão, idioma esperado e `corpus_version`.
- Embeddings podem ser gerados a partir de fixture local sem rede na suíte.
- Mudança de modelo ou corpus exige rebuild explícito do índice.
- Existe fake embedding determinístico para testes.

### Story 07: Implementar busca vetorial local

Critérios de aceite:

- A busca vetorial recebe gap, oportunidade ou consulta normalizada.
- A saída retorna chunks com score vetorial, metadados e citação.
- A ordenação é reprodutível com corpus, embedding e parâmetros fixos.
- Empates usam critério estável, como `document_id` e `chunk_index`.
- A busca vetorial não chama LLM nem rede.

### Story 08: Implementar busca híbrida lexical + vetorial

Critérios de aceite:

- O retrieval combina `top_k_lexical` e `top_k_vector`.
- Chunks duplicados são mesclados preservando scores originais.
- O ranking final registra `retrieval_strategy`, `ranking_strategy`, pesos ou método de fusão.
- Existe teste para caso em que lexical vence, caso em que vetorial vence e caso de empate.
- O output continua compatível com `nvidia_recommendation.py`.

### Story 09: Persistir embeddings em Postgres/pgvector

Critérios de aceite:

- O `docker-compose.yml` usa Postgres com extensão `pgvector` ou há instrução/migration equivalente.
- Existe migration com `CREATE EXTENSION IF NOT EXISTS vector`.
- Chunks, metadados, `corpus_version`, `embedding_model`, `embedding_version` e vetor ficam persistidos de forma auditável.
- A busca vetorial pode usar consulta SQL por similaridade.
- Índices HNSW/IVFFlat só entram quando houver volume ou latência que justifique.
- A suíte local pode usar fallback/fake sem exigir Postgres real.

### Story 10: Adapter LlamaIndex opcional

Critérios de aceite:

- LlamaIndex só entra atrás de adapter de `NVIDIA Knowledge`.
- O domínio não expõe objetos internos do LlamaIndex para `Recommendation`.
- Existe fallback local sem LlamaIndex para preservar suíte simples.
- O adapter é justificado por necessidade concreta: índice persistente, metadados complexos, citações, reranking ou manutenção de RAG.

## Épico 2: Recommendation Por Gap

Como gerente de Startups & VCs, quero recomendações NVIDIA vinculadas a gaps específicos para decidir abordagem com contexto técnico e comercial.

### Story 01: Definir schema de recomendação

Critérios de aceite:

- Existe `nvidia_recommendation.py`.
- O schema inclui `schema_version`, `run_id`, startup, tipo de recomendação, gap técnico ou oportunidade comercial, tecnologia ou programa, prioridade, complexidade, justificativa técnica, justificativa comercial, próxima ação, evidências da startup e fontes oficiais NVIDIA.
- O schema inclui prioridade final da oportunidade NVIDIA calculada a partir de recomendação suportada por fonte oficial.
- O schema suporta recomendações bloqueadas e hipóteses.
- Existe conversão para dicionário serializável.

### Story 02: Mapear gaps técnicos para tecnologias candidatas

Critérios de aceite:

- O mapeamento consome `TechnicalGap` e resultados recuperados.
- O mapeamento não usa regra escondida em prompt.
- Quando não há fonte recuperada, a recomendação fica bloqueada ou hipótese.
- Existe teste para pelo menos quatro gap types.

### Story 03: Mapear oportunidades comerciais para recomendações de programa

Critérios de aceite:

- O mapeamento consome `CommercialOpportunity` e resultados recuperados.
- Inception só é candidato quando houver oportunidade comercial específica ou gap técnico que justifique suporte do programa.
- Quando não há fonte oficial recuperada, a recomendação fica bloqueada ou hipótese.
- Existe teste para oportunidade permitida e bloqueada.

### Story 04: Ranqueamento top 1 por gap ou oportunidade

Critérios de aceite:

- Cada gap com fonte suficiente destaca uma recomendação top 1.
- Cada oportunidade comercial com fonte suficiente pode destacar uma recomendação de programa top 1.
- Alternativas podem ser preservadas quando houver incerteza.
- O ranking considera severidade do gap, confiança do assessment e qualidade da fonte.
- Existe teste para empate ou baixa confiança.

### Story 05: Regra específica para NVIDIA Inception

Critérios de aceite:

- Inception só é recomendado quando houver gap técnico ou comercial específico.
- A justificativa comercial é separada da justificativa técnica.
- Inception sem gap fica bloqueado.
- Existe teste para recomendação permitida e bloqueada.

### Story 06: Quality gate de recomendação

Critérios de aceite:

- O output calcula `ready_for_briefing`.
- Recomendações sem fonte oficial NVIDIA reduzem prontidão.
- Conflitos críticos ou high wrapper risk podem exigir revisão humana.
- Existe teste para pronto, hipótese e bloqueado.

## Épico 3: Briefing Executivo

Como gerente de Startups & VCs, quero um briefing curto e auditável para decidir abordagem e preparar conversa com a startup.

### Story 01: Definir schema de briefing

Critérios de aceite:

- Existe `briefing.py`.
- O schema inclui `schema_version`, `run_id`, startup, resumo executivo, diagnóstico, oportunidade, riscos, recomendações, perguntas pendentes e fontes.
- Cada claim tem tipo: observado, inferido, recomendado ou desconhecido.
- Existe conversão para dicionário serializável.

### Story 02: Gerar briefing determinístico inicial

Critérios de aceite:

- O briefing é gerado sem LLM na primeira versão.
- A saída usa perfil, assessment e recommendation set.
- Unknowns e conflitos aparecem explicitamente.
- O briefing não inventa funding, clientes, founders ou tecnologias.

### Story 03: Criar perguntas de revisão humana

Critérios de aceite:

- Campos insuficientes viram perguntas objetivas.
- Hipóteses de gap ou wrapper risk viram perguntas de validação.
- O briefing diferencia pergunta crítica de pergunta complementar.

### Story 04: Gerar briefing para human review

Critérios de aceite:

- Quando o fluxo termina em `human_review_requested`, ainda existe um briefing versionado.
- O briefing inclui startup, área de atuação, o que foi descoberto, evidências principais, gargalos, riscos, conflitos e perguntas pendentes.
- Alto wrapper risk, baixo sinal e falta de fonte oficial NVIDIA aparecem como motivos de revisão humana.
- O briefing não apresenta hipótese como recomendação suportada.
- Existe caminho serializável para esse briefing.

### Story 05: Persistir briefing

Critérios de aceite:

- O briefing pode ser salvo em JSON processado.
- O repository SQL armazena payload por run e startup.
- Existe teste SQLite.

## Épico 4: Workflow Completo

Como mantenedor, quero conectar assessment, knowledge, recommendation e briefing no grafo sem colocar regra de negócio nos nós.

### Story 01: Criar workflow downstream

Critérios de aceite:

- Existe `workflow_graph.py` ou extensão clara do grafo atual.
- Os nós chamam funções de domínio validadas pela nova suíte local.
- O runner local cobre o caminho completo sem LangGraph instalado.

### Story 02: Branches explícitos

Critérios de aceite:

- O grafo diferencia `needs_more_collection_or_human_review`, `ready_for_recommendation`, `ready_for_briefing`, `briefing_generated` e `human_review_requested`.
- `human_review_requested` deve carregar ou referenciar um `HumanReviewBriefing`.
- Cada branch possui motivo auditável.
- Existe teste para caminho pronto, sem fonte NVIDIA e revisão humana.

### Story 03: Persistência downstream

Critérios de aceite:

- JSON e SQL armazenam retrievals, recommendations e briefings.
- Reprocessar recomendação não exige repetir scraping.
- Reprocessar briefing não exige repetir retrieval quando o snapshot de conhecimento é o mesmo.

### Story 04: Métricas de qualidade

Critérios de aceite:

- O sistema mede recomendações com fonte NVIDIA.
- Mede recomendações com evidência da startup.
- Mede gaps sem recomendação.
- Mede briefings bloqueados por unknown, conflito ou falta de fonte.

## Fora De Escopo

- Chamar documentação NVIDIA ao vivo durante testes.
- Vector database externo gerenciado e reranking neural na primeira entrega deste roadmap; Postgres/pgvector local é a opção preferida quando persistência vetorial for necessária.
- Scraping autenticado ou coleta de dados privados.
- UI web sofisticada.
- Ranking comercial definitivo sem revisão humana.
- Automação de contato com startups.

## Definition Of Done

- [x] Base NVIDIA local versionada e carregável em testes.
- [x] Retrieval BM25 lexical retorna citações auditáveis.
- [x] Retrieval vetorial local retorna citações auditáveis com embedding versionado.
- [x] Postgres/pgvector está planejado como vector DB local antes de qualquer serviço externo.
- [x] Retrieval híbrido lexical + vetorial retorna ranking reprodutível.
- [x] Contrato de retrieval permite LlamaIndex e reranking sem quebrar Recommendation.
- [x] Recomendação técnica liga gap da startup a fonte oficial NVIDIA.
- [x] Recomendação de programa liga oportunidade comercial a fonte oficial NVIDIA.
- [x] Recomendação sem fonte é hipótese ou bloqueio, não fato.
- [x] Inception só é recomendado com gap específico.
- [x] Briefing diferencia observado, inferido, recomendado e desconhecido.
- [x] Human review gera briefing detalhado com contexto suficiente para decisão humana.
- [x] Workflow possui branch `ready_for_briefing`.
- [x] Persistência downstream permite reprocessamento.
- [x] Nova suíte local de validação continua sem rede, credenciais ou serviços externos obrigatórios.
