# case-NVIDIA-IA

Desenvolvido por **Leunam Sousa de Jesus**.

## O Que É Este Projeto

Este projeto é uma ferramenta de inteligência para apoiar o gerente de Startups & VCs da NVIDIA no Brasil a descobrir, qualificar e nutrir startups brasileiras com potencial para o programa NVIDIA Inception.

A pergunta principal do sistema é:

> Esta startup brasileira merece uma abordagem da NVIDIA agora? Se sim, por qual motivo, com quais evidências e qual tecnologia ou programa NVIDIA faz sentido?

O projeto não tenta apenas encontrar startups que dizem "usamos IA". Ele tenta separar startups com IA realmente central no produto e na stack daquelas que usam IA de forma superficial, por exemplo apenas como um wrapper de API de LLM.

## Ideia Central

A arquitetura é **evidence-first**:

- toda afirmação importante precisa apontar para evidências públicas;
- inferências precisam ser marcadas como inferências;
- recomendações precisam citar fontes oficiais NVIDIA;
- dados ausentes continuam como `unknown`;
- conflitos e incertezas aparecem no briefing, não são escondidos.

Isso é importante porque uma recomendação convincente, mas sem fonte, pode atrapalhar a priorização comercial e técnica.

## Regras De Negócio Em Linguagem Simples

- Uma `Startup Candidate` é uma empresa descoberta em fonte pública.
- Um `Startup Profile` é o perfil estruturado dessa startup, com evidências.
- Uma startup é `AI-Native` quando há evidência pública de que IA é central no produto e existe profundidade técnica suficiente.
- Uma startup é `AI-Enabled` quando usa IA, mas sem prova suficiente de centralidade ou profundidade.
- `Wrapper Risk` é o risco de a startup depender principalmente de APIs externas sem dados próprios, inferência em produção ou defensibilidade técnica.
- `Technical Gap` é um gargalo técnico que tecnologia NVIDIA pode ajudar a resolver.
- `Commercial Opportunity` é uma oportunidade de programa ou relacionamento, como Inception, parceiros, créditos, comunidade ou go-to-market.
- `AI-Native Assessment` gera apenas um `Opportunity Signal`, ou seja, um sinal preliminar.
- A prioridade final da oportunidade NVIDIA é calculada no módulo de `Recommendation`, depois de cruzar gaps ou oportunidades com fontes oficiais NVIDIA.
- Se houver baixo sinal, alto risco de wrapper, conflito ou falta de fonte oficial, o sistema deve gerar um `Human Review Briefing`, não uma recomendação final.
- O `Human Review Briefing` precisa trazer startup, área de atuação, o que foi descoberto, gargalos, riscos, conflitos, evidências e perguntas para validação humana.

## Fluxo Do Sistema

O fluxo planejado é:

```text
Discovery
-> Collection
-> Profile Extraction
-> Evidence Quality
-> AI-Native Assessment
-> NVIDIA Knowledge
-> Recommendation
-> Briefing
-> Human Review
```

Em termos práticos:

1. O sistema planeja buscas sobre startups brasileiras.
2. Encontra candidatas em fontes públicas.
3. Coleta páginas públicas respeitando política de scraping e robots.txt.
4. Extrai um perfil estruturado da startup.
5. Agrupa evidências e mede a qualidade da coleta.
6. Classifica maturidade AI-native e riscos.
7. Consulta uma base versionada de fontes oficiais NVIDIA.
8. Gera recomendações técnicas ou de programa.
9. Gera briefing executivo ou briefing para revisão humana.

## Status Atual

Já existe walking skeleton implementado para:

- planejamento de busca;
- descoberta de candidatas;
- coleta pública simples com `urllib` + `html.parser`;
- política de scraping e robots.txt;
- extração de `StartupProfile` com schema `startup_profile.v1`;
- agrupamento de evidências;
- resumo de qualidade da coleta;
- avaliação AI-native determinística com schema `ai_native_assessment.v1`;
- gaps técnicos iniciais;
- riscos de wrapper/API-dependency;
- sinal preliminar de oportunidade;
- persistência JSON/SQL;
- runner local compatível com LangGraph;
- contrato local de `NVIDIA Knowledge` com corpus fixture oficial e BM25 lexical;
- contrato de embeddings com fake determinístico, busca vetorial local e retrieval híbrido reprodutível;
- caminho opcional de persistência de embeddings em Postgres/pgvector;
- `nvidia_recommendation.v1` para recomendação técnica citada, hipótese e bloqueio;
- `executive_briefing.v1` determinístico para recommendation set suportado.

Ainda não está implementado:

- `Human Review Briefing`;
- workflow completo `ready_for_briefing` / `human_review_requested`;
- validação de integração real com Postgres/pgvector fora do caminho local padrão;
- recomendações de programa/Inception;
- persistência downstream de knowledge, recommendations e briefings;
- suíte ampla de regressão para scraping e assessment.

## Próximo Escopo Recomendado

O próximo ciclo deve completar as lacunas downstream restantes:

1. Garantir briefing detalhado quando o resultado for `human_review_requested`.
2. Criar workflow downstream local com branches `ready_for_briefing` e `human_review_requested`.
3. Adicionar persistência JSON/SQL para retrievals, recommendations e briefings.
4. Implementar busca vetorial e retrieval híbrido quando houver métricas/fixtures.
5. Separar `Program Recommendation` e gate de NVIDIA Inception.

## Frameworks E Retrieval

- `LangGraph` será o orquestrador principal do workflow: estado, branches, checkpoints, retries e human-in-the-loop.
- `LangChain` pode entrar dentro de adaptadores para LLMs, prompts, tools, structured output e retrievers.
- `LiteLLM` pode entrar como gateway/adaptador para Grok, Groq, OpenRouter, Ollama ou outros modelos gratuitos/baratos.
- `LlamaIndex` é candidato para a camada RAG de `NVIDIA Knowledge` quando ingestão, índices, busca vetorial/híbrida, citações e reranking ficarem mais complexos.
- `Pydantic` pode validar novos schemas versionados.
- A busca NVIDIA deve cobrir BM25 lexical e vetorial de forma reprodutível, com ranking híbrido; reranking do top K entra quando houver métricas.
- O vector DB preferido é Postgres local com `pgvector`, aproveitando o Docker/Postgres já planejado antes de considerar serviço externo dedicado.
- O LLM gerador, como Grok ou outro modelo gratuito, deve ficar desacoplado do modelo de embedding. O embedding deve ser escolhido por qualidade de recuperação, idioma, custo e estabilidade.

O guia completo está em [Frameworks de IA, Orquestração e Retrieval](context/frameworks-and-retrieval-strategy.md).

## Documentação Principal

- [Glossário de domínio](CONTEXT.md)
- [Escopo arquitetural](context/project-scope.md)
- [Modelo de domínio detalhado](context/domain-model.md)
- [Brief para próximas sessões](context/next-session.md)
- [Grilling arquitetural e cobertura de escopo](context/architecture-grilling-coverage.md)
- [Status do MVP de scraping](context/scraping-mvp-status.md)
- [Roadmap de hardening de scraping](context/roadmap-scraping-hardening.md)
- [Roadmap de avaliação AI-native](context/roadmap-pipeline-avaliação.md)
- [Roadmap de NVIDIA Knowledge, Recommendation e Briefing](context/roadmap-nvidia-knowledge-recommendation-briefing.md)
- [Frameworks de IA, orquestração e retrieval](context/frameworks-and-retrieval-strategy.md)
- [ADRs](context/adr)

## Validação

A suíte antiga ampla de scraping/assessment foi removida por estar inválida para o escopo atual. Existe uma suíte local focada no downstream atual, sem rede, credenciais, Postgres real ou LangGraph obrigatório:

```bash
python -m pytest -q
python -m ruff check .
python -m mypy src
```

Ruff e mypy usam um baseline intencionalmente permissivo nesta primeira adoção de tooling. Ruff está limitado a erros de sintaxe/estilo críticos e Pyflakes; mypy roda sobre `src` com tolerância para imports ausentes, `strict_optional = false` e checagem de corpos não tipados. A baseline também adia categorias de erro de tipos já existentes, como `arg-type`, `assignment`, `attr-defined`, `call-overload`, `return-value` e `union-attr`. Aumentos de strictness devem entrar em fatias futuras, junto com ajustes de código específicos.

Os comandos estáticos pressupõem `ruff` e `mypy` instalados no ambiente Python usado para validação.

## Validação Opcional LLM Adapters

LiteLLM e LangChain não fazem parte da suíte local padrão. A validação default continua usando fakes e contract tests, sem rede, credenciais, chamadas reais de LLM, LiteLLM ou LangChain instalados.

Os adapters opcionais ficam atrás do contrato `LLMClient` em `framework_adapters.py`. Para validar uma integração real com LiteLLM, instale a dependência no ambiente local e configure explicitamente o provider por variáveis de ambiente:

```bash
export NVIDIA_STARTUP_INTEL_LLM_PROVIDER=litellm
export NVIDIA_STARTUP_INTEL_LLM_MODEL=<provider/model>
export NVIDIA_STARTUP_INTEL_LLM_MODEL_VERSION=<model-version>
export NVIDIA_STARTUP_INTEL_LLM_API_KEY_ENV=OPENROUTER_API_KEY
export OPENROUTER_API_KEY=<secret>
```

`NVIDIA_STARTUP_INTEL_LLM_API_KEY_ENV` guarda apenas o nome da variável que contém a credencial; a credencial não deve entrar em código, fixtures, payloads persistidos ou artefatos de briefing. Configurações opcionais aceitas pelo adapter incluem `NVIDIA_STARTUP_INTEL_LLM_API_BASE`, `NVIDIA_STARTUP_INTEL_LLM_TIMEOUT_SECONDS`, `NVIDIA_STARTUP_INTEL_LLM_TEMPERATURE` e `NVIDIA_STARTUP_INTEL_LLM_MAX_TOKENS`.

Para LangChain, configure `NVIDIA_STARTUP_INTEL_LLM_PROVIDER=langchain` e passe um chat model já instanciado para `LangChainLLMClient`. Objetos LiteLLM ou LangChain devem ser convertidos para `LLMGenerationResponse` antes de qualquer Recommendation, Briefing, workflow state ou payload de persistência.

## Validação Opcional Pgvector

A persistência de embeddings em Postgres/pgvector é um caminho de integração, não uma dependência da suíte local padrão. Para validar quando Docker e Postgres estiverem disponíveis:

```bash
docker compose up -d postgres
docker compose exec postgres psql -U nvidia_startup_intel -d nvidia_startup_intel -c "SELECT extname FROM pg_extension WHERE extname = 'vector';"
docker compose exec postgres psql -U nvidia_startup_intel -d nvidia_startup_intel -c "\\d nvidia_chunk_embeddings"
```

O schema em `db/schema.sql` cria `CREATE EXTENSION IF NOT EXISTS vector`, persiste documentos, chunks e embeddings auditáveis, e usa busca exata por similaridade SQL. Índices HNSW/IVFFlat continuam fora até haver volume ou latência medidos que justifiquem a troca.
