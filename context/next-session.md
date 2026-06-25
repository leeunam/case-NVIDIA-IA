# Brief Para Próximas Sessões

## Estado do Projeto

O MVP de scraping está implementado como walking skeleton funcional e auditável. Ele transforma consulta em plano de busca, executa descoberta, deduplica candidatas, coleta páginas públicas, extrai `StartupProfile`, estrutura evidências e mede qualidade da coleta.

Esse MVP é um walking skeleton pronto para alimentar a próxima etapa, não uma camada final de scraping production-grade. A coleta atual usa `urllib` + `html.parser`; ainda não há Playwright, trafilatura, BeautifulSoup, Firecrawl ou Scrapy integrados. O roadmap para hardening incremental está em `context/roadmap-scraping-hardening.md`.

O épico local de avaliação AI-native também está implementado: schema `ai_native_assessment.v1`, classificador determinístico, riscos de wrapper/API-dependency, gaps técnicos iniciais, sinal preliminar de oportunidade, qualidade do diagnóstico, persistência JSON/SQL e branch no grafo.

O primeiro walking skeleton downstream também está implementado: `nvidia_knowledge.v1` com corpus local oficial e BM25 lexical, `nvidia_recommendation.v1` para uma recomendação técnica citada, hipótese e bloqueio, e `executive_briefing.v1` determinístico para recommendation set suportado.

Validação atual: a suíte antiga ampla foi removida por estar inválida para o escopo atual. Existe suíte local focada no downstream atual com `PYTHONPATH=src python3 -m unittest discover -s tests`.

## Arquitetura Fechada Para o Próximo Ciclo

O sistema deve atuar como:

- qualification engine;
- technical diagnostic engine;
- sales enablement briefing engine.

O primeiro workflow do MVP é analisar uma startup profundamente. A decisão primária do produto é descobrir quais startups abordar e priorizar a aproximação pela prioridade final da oportunidade NVIDIA calculada em Recommendation.

## Próxima Implementação Recomendada

Próximo ciclo recomendado: completar `Human Review Briefing` e workflow downstream, ainda com walking skeleton testável:

1. Implementar `Human Review Briefing` para hipótese, bloqueio, falta de fonte oficial, conflito e alto wrapper risk.
2. Conectar assessment, retrieval, recommendation e briefing em runner local downstream sem LangGraph obrigatório.
3. Adicionar branches explícitos `ready_for_briefing`, `briefing_generated` e `human_review_requested`.
4. Persistir retrievals, recommendations e briefings em JSON/SQL quando a linha local estiver validada.
5. Depois disso, evoluir busca vetorial, ranking híbrido e programa/Inception por métricas e fixtures.

Se o objetivo da próxima sessão for melhorar coleta antes do diagnóstico, use `context/roadmap-scraping-hardening.md`. O critério para escolher esse caminho deve ser evidência de que a coleta simples está produzindo muitos `unknown`, páginas vazias, texto ruidoso ou perda clara de conteúdo JavaScript.

## Contratos Que Não Devem Ser Quebrados

- Campos sem evidência suficiente retornam `unknown`.
- Recomendações fracas devem ser bloqueadas ou rebaixadas.
- Evidência pública fraca pode gerar hipótese de baixa confiança para revisão humana, sem investigação profunda adicional.
- Revisão humana deve receber briefing com startup, área, descobertas, gargalos, riscos e perguntas pendentes.
- NVIDIA Inception só deve ser recomendado quando houver gap técnico ou comercial específico.
- LangGraph orquestra estado e branches; LangChain pode apoiar chains, retrievers, prompts e tools dentro de adaptadores testáveis.
- LiteLLM pode ser usado como gateway/adaptador para Grok, Groq, OpenRouter, Ollama ou outros modelos gratuitos/baratos.
- LlamaIndex pode entrar em `NVIDIA Knowledge` se RAG, busca vetorial/híbrida, metadados, persistência de índice, citações ou reranking ficarem complexos.
- O LLM gerador, como Grok ou outro modelo gratuito, deve ficar desacoplado do modelo de embedding.
- Retrieval deve cobrir BM25 lexical + vetorial com ranking reprodutível; Postgres/pgvector é o vector DB local preferido; reranking do top K entra com métricas, não por preferência de framework.

## Documentos Principais

- `AGENTS.md`: regras operacionais e arquitetura de trabalho.
- `context/project-scope.md`: escopo arquitetural consolidado.
- `context/domain-model.md`: entidades, vocabulário e regras de domínio.
- `context/architecture-grilling-coverage.md`: validação arquitetural e lacunas de cobertura.
- `context/scraping-mvp-status.md`: status do MVP de scraping implementado.
- `context/roadmap-scraping-hardening.md`: plano para tornar scraping mais robusto quando houver falhas medidas.
- `context/roadmap-pipeline-avaliação.md`: avaliação AI-native implementada.
- `context/roadmap-nvidia-knowledge-recommendation-briefing.md`: próximo roadmap downstream.
- `context/frameworks-and-retrieval-strategy.md`: uso de LangGraph, LangChain, LiteLLM, LlamaIndex, BM25, pgvector, embeddings e reranking.
- `context/adr/`: decisões arquiteturais aceitas.
