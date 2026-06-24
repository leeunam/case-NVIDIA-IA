# Escopo Arquitetural do Projeto

## Tese do Produto

O sistema existe para responder uma pergunta operacional:

> Quais startups brasileiras têm sinais públicos suficientes de maturidade AI-native para justificar abordagem técnica e comercial da NVIDIA Inception, e quais tecnologias NVIDIA podem destravar valor real para elas?

A resposta precisa ser auditável. O sistema pode inferir, classificar e recomendar, mas deve mostrar quais evidências sustentam cada passo e onde a informação continua desconhecida.

## Decisões de Produto Após Grilling

- Decisão primária: encontrar quais startups abordar e priorizar a aproximação.
- Primeiro workflow de MVP: analisar uma startup profundamente, com briefing útil para decisão humana.
- Papel do sistema: combinar qualificação, diagnóstico técnico e sales enablement briefing no mesmo fluxo.
- Critério de priorização: prioridade final da oportunidade NVIDIA, calculada após cruzar gaps ou oportunidades comerciais com fontes oficiais NVIDIA.
- Público final do briefing: gerente de Startups & VCs da NVIDIA.
- Quando evidência pública for fraca, mas a startup parecer estratégica, o sistema deve gerar hipótese de baixa confiança para revisão humana, sem investigação profunda adicional.
- Outputs inaceitáveis: recomendações fracas e excesso de `unknown`.

## Problema Que o Sistema Resolve

O gerente de Startups & VCs precisa priorizar tempo, suporte técnico e abordagem comercial. A dificuldade não é apenas encontrar empresas que dizem usar IA, mas separar:

- startups com IA como núcleo do produto, dados, operação ou defensibilidade;
- startups que usam IA como feature incremental;
- empresas que apenas embrulham APIs ou LLMs sem capacidade técnica própria evidente;
- empresas sem evidência pública suficiente para avaliação.

Neste projeto, uma startup AI-native é aquela em que evidências públicas mostram centralidade da IA no produto e profundidade técnica suficiente na stack, dados, modelos, avaliação, MLOps ou inferência.

## Resultado Esperado

Para cada startup analisada, o sistema deve produzir:

- perfil estruturado com fontes;
- diagnóstico AI-native com nível de confiança;
- gaps técnicos e riscos;
- recomendações NVIDIA com justificativa técnica e comercial;
- briefing executivo com próxima ação sugerida;
- lista explícita de campos `unknown` e pontos que exigem revisão humana.
- quando a saída for revisão humana, briefing detalhado com contexto suficiente para análise manual.

## Princípios de Arquitetura

1. Evidência é artefato de primeira classe.
2. O pipeline deve aceitar execução parcial e reprocessamento sem repetir coleta desnecessária.
3. Módulos de domínio devem ser determinísticos sempre que possível.
4. Agentes e LangGraph coordenam trabalho; regras críticas ficam em código, schemas e avaliações.
5. Integrações externas entram por adaptadores testáveis.
6. O sistema deve falhar de forma auditável, preservando erros e fontes consultadas.
7. O MVP deve entregar uma linha vertical completa antes de otimizar escala.
8. LangChain pode apoiar chains, retrievers, prompts e tools; LangGraph continua responsável por orquestração, estado e branches.
9. LiteLLM pode apoiar troca de provedores de LLM, como Grok, Groq, OpenRouter, Ollama ou outros modelos gratuitos/baratos.
10. LlamaIndex pode apoiar RAG em `NVIDIA Knowledge` quando houver necessidade medida de ingestão, índice, busca vetorial/híbrida, citações e reranking.
11. Pydantic pode continuar útil para schemas versionados.
12. Retrieval NVIDIA deve cobrir busca BM25 lexical e vetorial reprodutíveis, com merge/ranking híbrido auditável.
13. Postgres local com `pgvector` é o vector DB preferido quando embeddings precisarem ser persistidos.
14. O LLM gerador e o embedding ficam desacoplados por interfaces; a escolha de embedding depende de qualidade de retrieval, não do fornecedor do LLM.

Guia técnico: `context/frameworks-and-retrieval-strategy.md`.

## Capacidades

### 1. Descoberta e Coleta

Status: implementado como MVP.

O MVP atual é suficiente como walking skeleton auditável para alimentar avaliação AI-native, mas não deve ser tratado como scraping production-grade. A coleta usa `urllib` + `html.parser`, ainda não renderiza JavaScript e ainda não possui extração avançada com Playwright, trafilatura, BeautifulSoup, Firecrawl ou Scrapy. A evolução dessa camada está separada em `context/roadmap-scraping-hardening.md` e deve ser guiada por falhas medidas de coleta.

Entrada:

- consulta do usuário;
- limite de resultados;
- fontes prioritárias opcionais.

Saída:

- `SearchParams`;
- `SearchPlan`;
- `RawDiscoveryResult`;
- `CandidateStartup`;
- `PageCollectionResult`;
- `StartupProfile`;
- `FieldEvidenceGroup`;
- `CollectionQualitySummary`.

### 2. Avaliação AI-Native

Status: implementado como walking skeleton determinístico.

Entrada:

- perfis estruturados;
- evidências agrupadas por campo;
- qualidade da coleta.

Saída:

- classificação: `ai_native`, `ai_enabled`, `non_ai` ou `insufficient_evidence`;
- score de confiança;
- sinal preliminar de oportunidade;
- sinais positivos;
- gaps técnicos;
- riscos de wrapper/API-dependency;
- evidências usadas por critério.
- qualidade do diagnóstico e `ready_for_recommendation`;
- persistência JSON/SQL.

O módulo atual é `src/nvidia_startup_intel/ai_native_assessment.py`. Ele não usa LLM, RAG, scraping adicional ou chamadas externas.

### 3. Conhecimento NVIDIA

Status: próximo contexto a implementar.

Entrada:

- documentos oficiais NVIDIA;
- corpus versionado;
- gaps técnicos da startup.

Saída esperada:

- documentos, chunks e citações;
- trechos recuperados com fonte e score;
- tecnologias candidatas;
- restrições e aplicabilidade;
- citações usadas para recomendação.

Roadmap: `context/roadmap-nvidia-knowledge-recommendation-briefing.md`.

### 4. Recomendação

Status: próximo contexto depois do knowledge mínimo.

Entrada:

- diagnóstico AI-native;
- gaps técnicos e oportunidades comerciais;
- resultados do RAG NVIDIA.

Saída esperada:

- recomendações técnicas;
- justificativa de negócio;
- prioridade final da oportunidade NVIDIA;
- ranking de tecnologias candidatas por gap, com a tecnologia top 1 destacada;
- complexidade de implementação;
- próxima ação sugerida;
- evidências da startup e fontes NVIDIA.

Roadmap: `context/roadmap-nvidia-knowledge-recommendation-briefing.md`.

### 5. Briefing Executivo

Status: escopo definido, ainda não implementado.

Entrada:

- perfil;
- diagnóstico;
- recomendações;
- evidências e incertezas.

Saída esperada:

- briefing versionado;
- resumo executivo;
- matriz de oportunidade;
- recomendações NVIDIA;
- perguntas para validação humana;
- anexos de evidência.
- variação de `Human Review Briefing` para baixo sinal, alto wrapper risk, conflito ou falta de fonte oficial.

Roadmap: `context/roadmap-nvidia-knowledge-recommendation-briefing.md`.

## Fora de Escopo Até Validação do MVP

- CRM completo.
- Envio automático de e-mails.
- Scraping autenticado.
- Compra de dados privados.
- UI complexa.
- Classificação sem revisão quando a coleta for insuficiente.
- Recomendação de NVIDIA Inception sem gap técnico ou comercial específico.
- Encerrar `human_review_requested` sem briefing contextual.
- Otimização distribuída de crawling.

## Métricas de Qualidade

- percentual de startups com site oficial encontrado;
- completude média do perfil;
- evidências por campo;
- conflitos por campo;
- taxa de `unknown`;
- taxa de startups prontas para avaliação;
- recomendações com citação NVIDIA;
- recomendações com evidência da startup;
- briefings aprovados sem retrabalho crítico.

## Refinamentos Não Bloqueantes

Estas decisões podem ser feitas durante implementação ou validação com usuário real; não bloqueiam o início das próximas sessões:

- fonte pública preferida para funding e clientes;
- pessoa responsável por aprovar recomendações de baixa confiança;
- formato final do briefing: página curta, tabela comparativa ou relatório narrativo;
- limite quantitativo de `unknown` que torna uma análise inútil para decisão de abordagem.
