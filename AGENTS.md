# Objetivo do Projeto

Construir uma ferramenta de inteligência para apoiar o gerente de Startups & VCs da NVIDIA no Brasil a identificar, qualificar e nutrir startups brasileiras com potencial AI-native para o programa NVIDIA Inception.

O sistema deve encontrar startups brasileiras com sinais de uso intensivo de IA, coletar dados públicos, estruturar evidências, avaliar possíveis gaps na stack de IA, consultar uma base de conhecimento sobre tecnologias NVIDIA e gerar um briefing executivo com recomendações técnicas e comerciais.

O contexto estratégico é que grandes labs de IA estão subindo na cadeia de valor e ameaçando startups que dependem apenas de wrappers de LLM. O projeto deve ajudar a diferenciar startups com potencial real de AI-native services daquelas com uso superficial de IA.

# Escopo Atualizado do Produto

O produto deve evoluir em quatro capacidades integradas, cada uma com contrato de entrada e saída auditável:

1. **Descoberta e evidências públicas**: encontrar candidatas, coletar páginas públicas, extrair perfil estruturado e medir qualidade da coleta. Esta capacidade já possui MVP funcional, resumido em `context/scraping-mvp-status.md`. O MVP é um walking skeleton auditável, não scraping production-grade; o hardening incremental está planejado em `context/roadmap-scraping-hardening.md`.
2. **Avaliação de maturidade AI-native**: transformar `StartupProfile` e evidências em diagnóstico de maturidade, gaps técnicos e riscos de dependência superficial de APIs ou wrappers. Esta capacidade já possui walking skeleton determinístico em `ai_native_assessment.v1`.
3. **Conhecimento NVIDIA e recomendação**: consultar uma base versionada de tecnologias NVIDIA, recuperar trechos com citações e gerar recomendações técnicas e comerciais vinculadas aos gaps observados. O core local já existe; o hardening de produção está em `context/production-retrieval-and-scraping-architecture.md`.
4. **Briefing executivo e workflow humano**: produzir um briefing com evidências, incertezas, recomendações, prioridade de abordagem e próximos passos para NVIDIA Inception.

Fora do MVP imediato:

- Enriquecimento com dados privados, CRM ou informações não públicas.
- Automação de contato com startups.
- Ranking comercial definitivo sem revisão humana.
- Interface web sofisticada antes de o fluxo de evidências, maturidade, RAG e briefing estar validado.

Decisões do grilling de produto:

- A decisão primária é descobrir quais startups abordar e priorizar a aproximação.
- O primeiro workflow do MVP é analisar uma startup profundamente.
- O sistema deve atuar como qualification engine, technical diagnostic engine e sales enablement briefing engine.
- A priorização deve favorecer a prioridade final da oportunidade NVIDIA calculada no contexto de Recommendation.
- Evidência pública fraca pode gerar hipótese de baixa confiança para revisão humana quando houver sinal estratégico.
- O briefing é para o gerente de Startups & VCs da NVIDIA.
- Saídas inaceitáveis: recomendações fracas e excesso de `unknown`.

# Arquitetura de Domínio

Use os seguintes bounded contexts como guia para código, testes e documentação:

- `Discovery`: planejamento de busca, execução com provedor, candidatas e deduplicação.
- `Collection`: política de scraping, robots.txt, coleta de páginas e erros auditáveis.
- `Profile Extraction`: schema `startup_profile.v1`, campos observados/inferidos e evidências por campo.
- `Evidence Quality`: conflitos, suficiência de evidência, métricas de qualidade e prontidão para avaliação.
- `AI-Native Assessment`: classificação AI-native, AI-enabled ou non-AI, sinais de profundidade técnica, gaps e riscos.
- `NVIDIA Knowledge`: ingestão de documentos oficiais NVIDIA, chunks, busca lexical BM25 e vetorial reprodutíveis, ranking híbrido, Postgres/pgvector como vector DB local preferido, futura camada LlamaIndex/reranking quando houver necessidade medida e citações.
- `Recommendation`: mapeamento entre gaps e tecnologias NVIDIA, justificativa técnica/comercial, prioridade e complexidade.
- `Briefing`: síntese executiva, incertezas, recomendações, fontes e próxima ação.

Dependências devem fluir nessa ordem. Evite ciclos entre contextos. Um contexto posterior pode ler artefatos de um anterior, mas não deve alterar evidências brutas.

# Contratos Arquiteturais

- O scraping entrega `StartupProfile`, grupos de evidência e `CollectionQualitySummary`.
- A avaliação AI-native deve consumir apenas perfis, evidências e qualidade da coleta; não deve repetir scraping.
- O RAG NVIDIA deve retornar trechos citáveis de uma base versionada; recomendações sem fonte devem ser marcadas como hipótese, não como fato.
- O briefing deve diferenciar dado observado, inferência, recomendação e desconhecido.
- NVIDIA Inception só deve ser recomendado quando houver gap técnico ou comercial específico.
- Baixo sinal, alto risco de wrapper, conflito ou ausência de fonte oficial devem gerar `Human Review Briefing` com startup, área, descobertas, gargalos, riscos e perguntas pendentes.
- Risco de wrapper/API-dependency considera principalmente dependência apenas de APIs externas, ausência de dados proprietários e ausência de infraestrutura de inferência em produção.
- Toda saída de uma etapa deve conter `schema_version`, identificador de execução e referência às evidências usadas.
- Dados ausentes continuam como `unknown`; nunca preencha lacunas com suposições.

# Decisões Arquiteturais Atuais

- O MVP usa módulos Python pequenos e testáveis como fonte da regra de negócio.
- LangGraph é camada de orquestração, não local para parsing, classificação, deduplicação ou recomendação.
- LangChain pode ser usado para chains, retrievers, prompts e tools dentro de adaptadores testáveis; não substitui os contratos de domínio nem o grafo de estado.
- LiteLLM pode ser usado como gateway/adaptador para Grok, Groq, OpenRouter, Ollama ou outros modelos gratuitos/baratos.
- LlamaIndex pode ser usado como adapter de RAG em `NVIDIA Knowledge` quando ingestão, indexação, citações, busca vetorial/híbrida e reranking justificarem a complexidade.
- Pydantic pode ser usado para novos schemas versionados.
- Busca NVIDIA deve cobrir BM25 lexical e vetorial com merge/ranking reprodutível; reranking do top K entra depois de métricas.
- Vector DB deve ser Postgres local com `pgvector` antes de considerar serviço externo dedicado.
- O LLM gerador, como Grok ou outro modelo gratuito, deve ficar desacoplado de `EmbeddingClient`; escolha embedding por qualidade de retrieval, idioma, custo e estabilidade, não por fornecedor do LLM.
- A suíte local não deve depender de rede, credenciais, Postgres real, LangGraph instalado ou provedores externos.
- Provedores externos entram por interfaces explícitas (`SearchClient`, futuros retrievers, futuros LLM clients).
- Persistência JSON permanece útil para debug, mas o histórico auditável deve evoluir para Postgres.
- Detalhes de framework, retrieval e produção estão em `context/production-retrieval-and-scraping-architecture.md`.

# Modo de Trabalho com IA

- Trabalhe em ciclos pequenos, com entregas verticais e testáveis.
- Prefira um walking skeleton funcional a uma arquitetura completa sem validação.
- Cada mudança deve preservar evidências, fontes e rastreabilidade.
- Não invente dados sobre startups, tecnologias, clientes, funding ou founders.
- Se uma informação pública não for encontrada, use `unknown` e registre a fonte consultada quando fizer sentido.
- Ao propor arquitetura, separe visão final de MVP implementável.
- Ao editar roadmaps, preserve a intenção de produto e melhore critérios de aceite, escopo e testabilidade.

# Modo de Aprendizado Guiado

Quando o usuário pedir `modo aprendizado`, `implementação guiada`, `quero escrever na mão` ou algo equivalente, a IA deve mudar o modo de trabalho para ensino prático sem abandonar a arquitetura do projeto.

Nesse modo:

- Não edite arquivos diretamente, a menos que o usuário peça explicitamente.
- Trabalhe em uma issue, story ou fatia vertical pequena por vez.
- Antes de escrever código, explique qual módulo será tocado, qual contrato ele preserva e qual teste provará o comportamento.
- Mostre o caminho do arquivo, o ponto de inserção e um bloco pequeno de código para o usuário copiar manualmente.
- Explique o código novo linha a linha ou bloco a bloco, focando na regra de negócio, no contrato público e no motivo técnico.
- Peça para o usuário rodar ou autorize rodar a suíte local depois de cada fatia pequena.
- Depois que o usuário escrever o código, leia o diff e revise aderência a arquitetura, testes, rastreabilidade e estilo.
- Não despeje implementações grandes. Prefira blocos de até cerca de 40 a 60 linhas, seguidos de explicação e validação.
- Preserve TDD: primeiro teste observável, depois implementação mínima, depois refactor.
- Testes devem usar interfaces públicas e fixtures locais; não dependa de rede, credenciais, Postgres real, LangGraph instalado, LLM real ou embedding real na suíte default.
- Se a explicação envolver stack futura, diferencie o que já existe no código do que ainda é roadmap.

Use `README.md`, `CONTEXT.md`, `context/domain-model.md`, os módulos em `src/nvidia_startup_intel` e seus testes correspondentes como roteiro de estudo. Diferencie sempre o que já existe no código do que está descrito como hardening de produção.

# Comandos de Setup/Test

Estado atual da validação:

- Existe suíte local padrão em pytest, sem rede, credenciais, Postgres real, LangGraph obrigatório ou provedores externos.
- A suíte antiga ampla foi removida por estar inválida para o escopo anterior; a suíte atual cobre os contratos locais reconstruídos.
- Ruff e mypy estão configurados com baseline permissivo para a fase atual.

Comandos de validação local:

```bash
python -m pytest -q
python -m ruff check .
python -m mypy src
```

Se algum comando não existir ainda, não assuma que ele funciona. Informe isso no final da tarefa.

# Stack Escolhida

## Extração de Dados

- Playwright: scraping de sites dinâmicos que dependem de JavaScript.
- BeautifulSoup: parsing de páginas HTML simples.
- Scrapy: crawling estruturado em maior escala.
- Firecrawl: extração de páginas web em formato limpo para RAG.
- trafilatura: extração de texto principal de páginas, blogs e notícias.

Use a ferramenta mais simples que preserve o motor principal robusto. Playwright + extração estática robusta são o caminho real de coleta; o caminho determinístico simples existe para testes, debug e comparação.

Estado atual:

- O motor principal de coleta real é Playwright-first, com extração por `StaticHTMLExtractionAdapter` para trafilatura + BeautifulSoup na instalação base do projeto.
- A coleta determinística com biblioteca padrão (`urllib` + `html.parser`) permanece como harness local/fallback de teste e debug.
- A coleta consulta `robots.txt` automaticamente quando recebe um `RobotsCache`, bloqueia URLs não permitidas e respeita `crawl-delay`.
- Existe contrato injetável de extração HTML e adapter `StaticHTMLExtractionAdapter` para trafilatura + BeautifulSoup com fallback local.
- Existe `PlaywrightPageRenderer` como motor primário de renderização da CLI real; a suíte default usa renderer fake para não exigir navegador real.
- Ainda não há Scrapy ou Firecrawl integrados no código.
- O scraping atual pode perder conteúdo em sites JavaScript-heavy ou páginas com extração de texto ruidosa; isso é limitação conhecida do MVP.
- Melhorias de scraping devem seguir `context/roadmap-scraping-hardening.md` e ser guiadas por falhas medidas, como excesso de `unknown`, baixa completude, páginas vazias ou necessidade clara de renderização JavaScript.
- A busca web real possui adaptador `BraveSearchClient`, configurável por `BRAVE_SEARCH_API_KEY`, `BRAVE_SEARCH_ENDPOINT` e `NVIDIA_STARTUP_INTEL_SEARCH_PROVIDER=brave`.
- A nova suíte local não deve fazer chamadas externas; use clientes fake/fixtures para preservar determinismo.

## Modelagem do Fluxo de Trabalho

- LangGraph: estado, nós, transições condicionais, checkpoints, retry, intervenção humana e controle do fluxo multiagente.
- LangChain: adaptadores de LLM, prompts, tools, structured output e retrievers dentro de nós, quando necessário.
- LiteLLM: gateway/adaptador para trocar provedores de LLM sem afetar regra de negócio.
- LlamaIndex: candidato para ingestão, indexação, retrieval, citações e reranking da base oficial NVIDIA.
- Postgres/pgvector: vector DB local preferido para persistir embeddings e consultar similaridade quando a busca vetorial sair do modo local/fake.
- Search Planner Agent: transforma a consulta do usuário em termos de busca e fontes prioritárias.
- Scraper Agent: coleta informações públicas de sites, notícias, diretórios e páginas institucionais.
- Extractor Agent: transforma conteúdo não estruturado em dados estruturados.
- Startup Classifier Agent: classifica a empresa como AI-native, AI-enabled ou non-AI.
- Evidence Validator Agent: valida se as afirmações possuem fontes suficientes.
- NVIDIA RAG Agent: consulta a base de conhecimento de tecnologias NVIDIA.
- Recommendation Agent: cruza o perfil da startup com as tecnologias NVIDIA.
- Briefing Agent: gera o relatório final para o gerente de Startups & VCs.

LangGraph deve orquestrar módulos testáveis. Evite colocar toda a regra de negócio dentro dos agentes.

Estado atual do pacote `src/nvidia_startup_intel`:

- `search_params.py`: interpreta a consulta do usuário em parâmetros estruturados.
- `search_plan.py`: gera termos e fontes de busca sem executar busca web.
- `search_execution.py`: executa o plano com `SearchClient`, normaliza respostas do Brave e registra erros sem interromper a execução.
- `discovery.py`: transforma resultados brutos em candidatas auditáveis.
- `startup_deduplication.py`: consolida candidatas duplicadas preservando evidências.
- `page_collection.py`: coleta páginas públicas relevantes com limites de profundidade e quantidade.
- `scraping_policy.py`: centraliza rate limit, bloqueio manual de domínios, login e classificação de erros.
- `robots.py`: consulta e cacheia `robots.txt` por domínio, com modo conservador configurável em caso de erro.
- `startup_profile.py`: extrai perfil estruturado com evidências e `unknown` quando faltar suporte.
- `evidence.py`: agrupa afirmações por campo e marca conflitos.
- `collection_quality.py`: mede qualidade da execução e decide prontidão para avaliação AI-native.
- `ai_native_assessment.py`: classifica maturidade AI-native, calcula sinal preliminar de oportunidade e gera gaps/riscos com evidências.
- `persistence.py`: salva artefatos raw/processed por execução em JSON.
- `sql_repository.py`: persiste execuções em tabelas relacionais via DB-API; testes usam SQLite e desenvolvimento pode usar Postgres via Docker Compose.
- `normalization.py`: concentra normalização compartilhada de texto, nomes, URLs e domínios.
- `pipeline.py`: fachada de orquestração para CLI, aplicação ou futuros nós LangGraph, incluindo helper de assessment.
- `scraping_graph.py`: define nós de scraping e avaliação, runner local testável e builder opcional de LangGraph.
- `nvidia_knowledge.py`: representa documentos, chunks, citações, BM25 lexical e resultados recuperados da base NVIDIA.
- `nvidia_recommendation.py`: cruza gaps com tecnologias NVIDIA e produz recomendações técnicas suportadas, hipóteses ou bloqueios.
- `briefing.py`: consolida diagnóstico, recomendações, evidências e próxima ação em um briefing executivo versionado determinístico.

Próximos módulos ou extensões esperados, quando as stories correspondentes forem implementadas:

- `workflow_graph.py` ou extensão de `scraping_graph.py`: conecta scraping, avaliação, RAG, recomendação e briefing mantendo nós finos.
- extensões vetoriais/híbridas de `nvidia_knowledge.py`: `EmbeddingClient`, busca vetorial local, ranking híbrido e futura persistência pgvector.
- extensões de `nvidia_recommendation.py`: recomendações de programa, gate de NVIDIA Inception, métricas e quality gates adicionais.
- extensão de `briefing.py`: `Human Review Briefing` detalhado para bloqueios, hipóteses, conflitos, alto wrapper risk ou ausência de fonte oficial.

Ao evoluir LangGraph:

- Use `pipeline.py` e `scraping_graph.py` como superfície inicial dos nós do grafo.
- Mantenha regras de negócio nos módulos específicos, não dentro dos nós.
- Cada nó deve receber e devolver estado explícito, chamando funções de domínio como `plan_startup_search`, `build_candidates`, `collect_pages_for_candidates`, `extract_profiles_for_candidates`, `structure_profile_evidence`, `summarize_collection_quality` e `assess_profiles_ai_native`.
- Checkpoints, retry, intervenção humana e branches devem ficar no grafo; parsing, deduplicação, extração, evidência e qualidade continuam em funções puras ou quase puras.
- Adicione branches explícitos para `needs_more_collection_or_human_review`, `ready_for_ai_native_assessment`, `ready_for_recommendation` e `ready_for_briefing`.
- Não chame LLM ou RAG dentro de funções puras; use adaptadores injetados e fixtures nos testes.
- Use `LLMClient`, `EmbeddingClient` e retrievers como interfaces explícitas para Grok, outros modelos gratuitos, embeddings ou rerankers.
- Retrieval NVIDIA deve implementar busca BM25 lexical e vetorial reprodutíveis; Postgres/pgvector entra como vector DB local preferido para persistência; LlamaIndex e reranking entram por adapter quando o contrato básico estiver validado.

# Padrões de Código

- Prefira funções pequenas, puras e testáveis para parsing, normalização, classificação e recomendação.
- Use schemas explícitos para dados estruturados de startups, fontes, evidências e briefings.
- Todo campo extraído deve poder apontar para uma ou mais evidências.
- Diferencie dado observado, inferência e recomendação.
- Evite lógica crítica em prompts soltos; quando possível, represente regras em código, schemas ou avaliações.
- Escreva testes para casos felizes, dados ausentes, fontes conflitantes e respostas sem evidência suficiente.

# O Que Alterar e Não Alterar

Pode alterar:

- Arquivos de roadmap e contexto quando a mudança melhorar clareza, escopo, critérios de aceite ou testabilidade.
- Estrutura de código relacionada diretamente à story em andamento.
- Schemas, fixtures e testes necessários para validar a entrega.

Não alterar sem necessidade:

- Escopo estratégico do projeto.
- Tecnologias centrais já escolhidas, a menos que exista justificativa técnica.
- Arquivos ou dados não relacionados à tarefa atual.
- Evidências coletadas manualmente pelo usuário.

# Como Validar Mudança

Para documentação:

- Verifique se cada story tem usuário, objetivo e critérios de aceite.
- Verifique se o escopo da story cabe em uma entrega pequena.
- Verifique se existe uma forma clara de testar ou revisar a entrega.

Para código:

- Rode os testes disponíveis.
- Valide exemplos com fixtures locais.
- Garanta que campos sem evidência retornem `unknown` em vez de conteúdo inventado.
- Confirme que outputs estruturados seguem o schema esperado.

# Formato Esperado de PR/Commit

Use commits pequenos e descritivos:

```text
docs: refine scraping roadmap stories
feat: add startup profile schema
test: add extraction fixtures
fix: preserve evidence URLs in startup profile
```

Toda mudança relevante deve explicar:

- o que foi alterado;
- por que foi alterado;
- como foi validado;
- riscos ou limitações restantes.

# Versionamento e Commits com IA

Antes de implementar uma issue, a IA deve confirmar a branch atual com:

```bash
git status --branch --short
```

Se a branch atual não for adequada para a issue, use uma branch curta e descritiva no padrão:

```text
feat/issue-<numero>-<slug-curto>
fix/issue-<numero>-<slug-curto>
docs/issue-<numero>-<slug-curto>
```

Regras para commits:

- Trabalhe em uma issue ou fatia vertical por vez.
- Não implemente todos os issues abertos em uma única passagem.
- Não use `git add .`.
- Adicione ao commit apenas arquivos diretamente relacionados à mudança.
- Não commite `.tools/`, arquivos temporários, credenciais, caches ou alterações não relacionadas.
- Não commite mudanças de outro usuário sem entender e mencionar por que elas fazem parte da entrega.
- Rode a suíte local disponível antes de commitar; se não houver suíte válida ou algum comando não existir, informe isso no resumo.
- Prefira commits pequenos, em Conventional Commits, como `feat:`, `fix:`, `test:` e `docs:`.
- Para implementação com TDD, faça commits que preservem a história da fatia: teste/comportamento, implementação mínima e eventual refactor.

O corpo do commit deve registrar:

- o que mudou;
- por que mudou;
- como foi validado;
- riscos ou limitações restantes.

# Issue Tracker

O issue tracker do projeto é o GitHub Issues do repositório `leeunam/case-NVIDIA-IA`.

Use o label `ready-for-agent` para PRDs e issues prontas para agentes. O label já existe no repositório.

Neste workspace, o GitHub CLI foi instalado localmente em:

```bash
.tools/gh/bin/gh
```

Para publicar um PRD como issue:

```bash
.tools/gh/bin/gh issue create --repo leeunam/case-NVIDIA-IA --title "PRD: <titulo>" --label ready-for-agent --body-file <arquivo-prd.md>
```

Se `.tools/gh/bin/gh` não existir em outro clone, instale `gh` no sistema ou baixe o GitHub CLI oficial novamente. Não versione `.tools/`.

# Prioridades

1. Evidência e rastreabilidade antes de volume de dados.
2. Walking skeleton antes de arquitetura multiagente completa.
3. Schemas e testes antes de automações sofisticadas.
4. MVP funcional antes de otimização de scraping em escala.
5. Clareza de recomendação técnica e comercial antes de interface visual.
6. Modelagem de domínio antes de novos agentes.
7. Critérios de aceite verificáveis antes de novas integrações externas.

# Estado Atual do MVP de Scraping

O status do MVP de scraping está resumido em `context/scraping-mvp-status.md`. O pacote `src/nvidia_startup_intel` contém a implementação. O plano para evoluir scraping simples para uma camada mais robusta está em `context/roadmap-scraping-hardening.md`.

Definition of Done atual:

- Consulta por região ou tema gera parâmetros, plano de busca e candidatas.
- O plano de busca pode ser executado contra provedor real configurável via `SearchClient`.
- O pipeline aceita fixtures locais de ponta a ponta e a suíte local atual é a validação padrão.
- Perfil estruturado usa schema versionado `startup_profile.v1`.
- Campos sem evidência suficiente retornam `unknown`.
- Evidências são preservadas por campo e conflitos são marcados.
- Resultados intermediários podem ser persistidos em JSON com separação `raw/` e `processed/`.
- Execuções podem ser persistidas em tabelas relacionais e o projeto inclui `docker-compose.yml` com Postgres.
- A coleta pode consultar e respeitar `robots.txt` automaticamente.
- Existe relatório simples de qualidade da coleta.
- Existe superfície de orquestração compatível com LangGraph e runner local.
- O output já alimenta assessment AI-native, retrieval NVIDIA, recommendation e briefing no fluxo local.

Limitações conhecidas:

- O adaptador real implementado é Brave Search; outros provedores exigem novos `SearchClient`.
- A coleta real deve ser Playwright-first com extração estática robusta; o caminho `urllib` + `html.parser` continua apenas como harness/fallback de teste e debug.
- Smoke real de Playwright, qualidade de trafilatura/BeautifulSoup, Firecrawl e Scrapy devem evoluir por stories específicas de hardening, com testes locais e contratos preservados.
- Postgres em desenvolvimento requer `docker compose up -d postgres` e driver `psycopg` instalado para uso real via `postgres_repository_from_env`.
- `build_langgraph` requer a dependência opcional `langgraph`; a próxima suíte deve usar o runner local para não tornar validação dependente dessa instalação.
