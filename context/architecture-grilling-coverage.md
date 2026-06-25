# Grilling Arquitetural e Cobertura de Escopo

Este documento consolida a revisão arquitetural feita com a intenção da skill `grill-with-docs`: pressionar o desenho do produto contra as regras de negócio, registrar lacunas e manter o modelo de domínio como fonte de escopo.

Observação operacional: a revisão foi consolidada com a disciplina de `grill-with-docs` e `domain-modeling`: bounded contexts, vocabulário controlado, regras de domínio, contratos de entrada/saída, ADRs e critérios de aceite auditáveis.

## Veredito

A arquitetura está coerente até a etapa de `AI-Native Assessment`.

O desenho atual preserva a decisão evidence-first, mantém dependências fluindo para frente e separa regra de negócio de orquestração. O principal risco arquitetural agora não é o scraping nem a avaliação determinística; é avançar para recomendações NVIDIA e briefing sem antes fechar contratos versionados para conhecimento, recuperação citável, ranking por gap, qualidade da recomendação e revisão humana.

Próxima prioridade: entregar um walking skeleton de `NVIDIA Knowledge`, `Recommendation` e `Briefing` com snapshot local de fontes oficiais NVIDIA, recuperação BM25 lexical + vetorial citável, ranking híbrido reprodutível, recomendação baseada em gaps técnicos ou oportunidades comerciais e briefing versionado. Postgres/pgvector é o vector DB local preferido quando embeddings precisarem ser persistidos; vector DB externo, reranking avançado, Playwright e UI continuam fora do caminho crítico até haver falha medida.

A estratégia para LangGraph, LangChain, LiteLLM, LlamaIndex, BM25, Postgres/pgvector, busca vetorial, busca híbrida, embeddings e reranking está em `context/frameworks-and-retrieval-strategy.md` e foi registrada na ADR 0007.

## Pergunta De Decisão

O sistema deve responder, com evidência auditável:

> Esta startup brasileira justifica abordagem técnica e comercial da NVIDIA Inception agora, qual gap sustenta essa abordagem e qual recomendação NVIDIA tem fonte suficiente?

Essa pergunta é mais forte que "a startup é AI-native?". A classificação é insumo; a decisão é priorização de abordagem.

## Fluxo Auditável

1. `Discovery`
   - Entrada: consulta do usuário, região, tema, limites.
   - Saída: `SearchParams`, `SearchPlan`, `RawDiscoveryResult`, `CandidateStartup`.
   - Regra crítica: descoberta não afirma maturidade, só candidata com evidência de origem.

2. `Collection`
   - Entrada: candidatas e URLs públicas.
   - Saída: `PageCollectionResult`, páginas, erros e política aplicada.
   - Regra crítica: respeitar robots.txt, bloqueios e falhas auditáveis.

3. `Profile Extraction`
   - Entrada: páginas coletadas.
   - Saída: `StartupProfile` `startup_profile.v1`.
   - Regra crítica: campo sem suporte vira `unknown`, não inferência escondida.

4. `Evidence Quality`
   - Entrada: perfil, evidências e resultados de coleta.
   - Saída: `FieldEvidenceGroup`, `CollectionQualitySummary`.
   - Regra crítica: conflitos reduzem prontidão; não são resolvidos silenciosamente.

5. `AI-Native Assessment`
   - Entrada: `StartupProfile`, `FieldEvidenceGroup`, `CollectionQualitySummary`.
   - Saída: `AINativeAssessment` `ai_native_assessment.v1`.
   - Status: implementado como walking skeleton determinístico.
   - Regra crítica: avaliação não faz scraping, RAG, LLM ou chamada externa.

6. `NVIDIA Knowledge`
   - Entrada: corpus versionado de documentos oficiais NVIDIA.
   - Saída esperada: documentos, chunks, citações e resultados recuperados.
   - Status: próximo contexto a implementar.
   - Regra crítica: afirmação sobre tecnologia NVIDIA precisa de fonte citável ou deve ser marcada como hipótese.

7. `Recommendation`
   - Entrada: assessment pronto para recomendação, gaps técnicos, oportunidades comerciais e trechos NVIDIA recuperados.
   - Saída esperada: recomendações ranqueadas por gap, top 1 destacado e qualidade da recomendação.
   - Status: próximo contexto a implementar depois da base de conhecimento mínima.
   - Regra crítica: recomendar NVIDIA Inception somente quando houver gap técnico ou comercial específico.

8. `Briefing`
   - Entrada: perfil, diagnóstico, recomendações, fontes, conflitos e unknowns.
   - Saída esperada: `ExecutiveBriefing` versionado.
   - Status: planejado.
   - Regra crítica: briefing deve separar observado, inferido, recomendado e desconhecido.

## Cobertura Por Bounded Context

| Contexto | Status | Cobertura Atual | Lacuna Antes De Escalar |
| --- | --- | --- | --- |
| Discovery | Implementado | Busca planejada, execução via `SearchClient`, Brave adapter, deduplicação | Calibrar recall com casos reais antes de adicionar novos provedores |
| Collection | Implementado como MVP | `urllib`, política de scraping, robots.txt, erros auditáveis | Hardening só quando métricas mostrarem páginas vazias, JS ou texto ruidoso |
| Profile Extraction | Implementado | `startup_profile.v1`, evidência por campo, `unknown` | Melhorar extração quando campos críticos ficarem desconhecidos em excesso |
| Evidence Quality | Implementado | conflitos, suficiência e prontidão | Tornar qualidade mais granular por startup quando houver runs com várias candidatas |
| AI-Native Assessment | Implementado | `ai_native_assessment.v1`, classificação, gaps, riscos, sinal preliminar de oportunidade | Calibrar regras com startups reais e revisar thresholds |
| NVIDIA Knowledge | Não implementado | Modelo conceitual no domínio | Definir schema, snapshot local de fontes oficiais NVIDIA, chunks e retrieval citável |
| Recommendation | Não implementado | Regras no domínio e ADRs | Definir schema, ranking por gap técnico ou oportunidade comercial, fonte NVIDIA oficial obrigatória e quality gate |
| Briefing | Não implementado | Entidade conceitual | Definir formato, claims rotulados, perguntas pendentes e export |
| Workflow Humano | Parcial | `next_action` para recomendação ou revisão após assessment | Adicionar `ready_for_briefing`, fila/artefato de revisão e motivo acionável |
| Persistência | Parcial | JSON/SQL para scraping e assessment | Persistir knowledge snapshots, retrievals, recommendations e briefings |

## Regras Que Devem Ficar Em Código

- `AI-Native Assessment` só pode consumir perfil, evidências agrupadas e qualidade de coleta.
- Classificação `ai_native` exige evidência de centralidade da IA além de menção genérica.
- Risco de wrapper/API-dependency é hipótese quando faltar evidência direta.
- Gap técnico pode ser hipótese de baixa confiança, mas deve carregar severidade, confiança e evidências ou razão de insuficiência.
- Recuperação NVIDIA retorna trechos citáveis, não recomendações.
- Recomendação técnica NVIDIA exige pelo menos um gap técnico da startup e uma fonte oficial NVIDIA.
- Recomendação de programa NVIDIA exige pelo menos uma oportunidade comercial específica e uma fonte oficial NVIDIA.
- Prioridade final da oportunidade NVIDIA é calculada em Recommendation, não no assessment.
- Recomendação sem fonte deve ser `hypothesis`, nunca fato.
- Inception não é recomendação padrão; precisa de gap técnico ou comercial específico.
- Briefing deve preservar conflitos e unknowns, não escolher a versão mais conveniente.
- Workflow deve bloquear briefing final quando recomendação estiver sem fonte ou com conflito crítico.
- Workflow de human review deve gerar briefing detalhado, não apenas status de bloqueio.

## Lacunas Encontradas

1. Documentos principais estavam parcialmente defasados: README, AGENTS e alguns status ainda tratavam a avaliação AI-native como próxima etapa, embora o código e o roadmap indiquem implementação.
2. Falta schema versionado para `NVIDIA Knowledge`: documento, chunk, citação, versão do corpus e resultado recuperado.
3. Falta snapshot local mínimo de fontes oficiais NVIDIA para testar recomendações sem rede.
4. Falta contrato de retrieval: entrada por gap, saída com citações, score e motivo de match.
5. Falta schema de recomendação com top 1 por gap, alternativas, prioridade, complexidade, próxima ação e quality gate.
6. Falta regra implementável para diferenciar recomendação técnica, recomendação comercial e hipótese.
7. Falta schema de briefing com claims rotulados por tipo de afirmação.
8. Falta branch `ready_for_briefing` depois de recomendação.
9. Falta persistência para knowledge snapshots, retrievals, recommendations e briefings.
10. Falta métrica de produto para "recomendação útil": recomendação com fonte NVIDIA, evidência da startup e gap específico.
11. `ai_native_assessment.v1` ainda expõe `nvidia_opportunity_urgency`; pela ADR 0006, downstream deve tratar esse campo como sinal preliminar até uma migração de schema.
12. Falta implementar `Human Review Briefing` para baixo sinal, alto wrapper risk, conflito ou ausência de fonte oficial NVIDIA.

## Escopo Recomendado

### Ciclo 0: Alinhamento Documental

Atualizar AGENTS, README, next-session e status para refletir que `AI-Native Assessment` já existe como walking skeleton.

### Ciclo 1: NVIDIA Knowledge Mínimo

Criar `nvidia_knowledge.py` com:

- `nvidia_knowledge.v1`;
- documentos e chunks versionados;
- citação com título, URL ou referência, data de ingestão e trecho;
- corpus fixture local com fontes oficiais NVIDIA;
- busca BM25 lexical determinística por gap;
- testes sem rede.

### Ciclo 2: Recommendation Por Gap

Criar `nvidia_recommendation.py` com:

- `nvidia_recommendation.v1`;
- entrada baseada em `AINativeAssessment`;
- recomendação técnica top 1 por gap e alternativas;
- recomendação de programa por oportunidade comercial;
- prioridade final da oportunidade NVIDIA;
- justificativa técnica e comercial;
- fonte oficial NVIDIA obrigatória para fato;
- hipótese explícita quando faltar fonte;
- quality gate `ready_for_briefing`.

### Ciclo 3: Briefing Executivo

Criar `briefing.py` com:

- `executive_briefing.v1`;
- resumo executivo curto;
- diagnóstico, oportunidade, riscos e recomendações;
- versão de revisão humana com descobertas, gargalos, riscos e perguntas pendentes;
- perguntas pendentes;
- anexos de evidência;
- claims rotulados como observado, inferido, recomendado ou desconhecido.

### Ciclo 4: Workflow Completo

Criar ou estender grafo para conectar:

`scraping -> assessment -> knowledge retrieval -> recommendation -> briefing -> human review`.

O grafo deve manter nós finos e branches explícitos:

- `needs_more_collection_or_human_review`;
- `ready_for_recommendation`;
- `ready_for_briefing`;
- `briefing_generated`;
- `human_review_requested`.

### Ciclo 5: Calibração E Hardening

Usar outputs reais para decidir se o gargalo está em:

- scraping fraco;
- regras de assessment;
- corpus NVIDIA insuficiente;
- retrieval ruim;
- recommendation quality gate muito permissivo ou restritivo.

Só então adicionar ferramentas mais pesadas.

## Perguntas De Grilling Abertas

Estas decisões não bloqueiam o próximo walking skeleton, mas precisam ser respondidas antes de produção:

1. Quais famílias de tecnologia NVIDIA entram no primeiro snapshot oficial?
2. Quem aprova uma hipótese de baixa confiança marcada como `human_review`?
3. Qual é o formato final preferido do briefing: página curta, tabela comparativa ou relatório narrativo?
4. Qual é o mínimo de citações oficiais NVIDIA para uma recomendação ser considerada pronta?
5. O briefing deve ser sempre em português ou pode preservar citações e nomes técnicos em inglês?
6. Como tratar startup estratégica com alta oportunidade comercial, mas baixa evidência pública?
7. Qual threshold torna excesso de `unknown` inaceitável para abordagem comercial?
8. Quais oportunidades comerciais além de Inception entram no primeiro escopo?
9. Quais evidências de "produção" realmente contam: cliente pago, case público, documentação técnica, vaga de engenharia, ou combinação?
10. Quando uma recomendação deve ser bloqueada em vez de seguir como hipótese?

## Definition Of Done Do Projeto

- Descoberta, coleta, perfil, evidências e qualidade geram artefatos auditáveis.
- Assessment AI-native classifica com evidências, gaps, riscos, sinal preliminar e prontidão.
- Base NVIDIA oficial é versionada e retorna trechos citáveis.
- Recomendações técnicas ligam gap da startup a fonte NVIDIA, com prioridade e complexidade.
- Recomendações de programa ligam oportunidade comercial a fonte NVIDIA.
- Briefing diferencia observado, inferido, recomendado e desconhecido.
- Workflow humano recebe motivos concretos para revisão.
- Persistência permite reprocessar downstream sem repetir scraping.
- Testes locais não dependem de rede, credenciais, Postgres real, LangGraph instalado ou provedores externos.
