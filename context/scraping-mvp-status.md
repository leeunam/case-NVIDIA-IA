# Status do MVP de Scraping

O MVP de scraping está implementado no pacote `src/nvidia_startup_intel` e serve como upstream para a avaliação AI-native.

Este status significa que existe um walking skeleton funcional e auditável para descoberta, coleta simples, extração de perfil e qualidade de evidência. Não significa que o scraping já seja production-grade ou cubra profundamente sites JavaScript-heavy, páginas com conteúdo renderizado no cliente, páginas protegidas por anti-bot ou extração robusta de conteúdo editorial complexo.

## O Que Já Funciona

- Consulta por região ou tema gera `SearchParams` e `SearchPlan`.
- O plano de busca pode executar contra `SearchClient`, com adaptador real para Brave Search.
- Resultados brutos viram candidatas auditáveis.
- Candidatas duplicadas são consolidadas preservando evidências.
- Páginas públicas são coletadas com limites de profundidade e quantidade.
- A coleta consulta `robots.txt` quando recebe `RobotsCache`, bloqueia URLs não permitidas e respeita `crawl-delay`.
- A extração HTML é injetável e possui adapter para trafilatura + BeautifulSoup.
- A CLI de coleta real usa Playwright por padrão via `PlaywrightPageRenderer`; o caminho sem navegador fica reservado para testes/debug.
- Existe smoke Playwright opt-in para validar browser instalado sem entrar na suíte default.
- Perfil estruturado usa schema `startup_profile.v1`.
- Campos sem evidência suficiente retornam `unknown`.
- Evidências são agrupadas por campo e conflitos são marcados.
- Artefatos podem ser persistidos em JSON e em SQL via DB-API.
- Existe `docker-compose.yml` com Postgres para desenvolvimento.
- A qualidade da coleta decide se o output está pronto para avaliação AI-native.
- `scraping_graph.py` oferece runner local compatível com validação local e builder opcional de LangGraph.

## O Que Ainda Não É Production-Grade

- O motor de coleta real é Playwright-first; a coleta determinística com `urllib` + `html.parser` permanece como harness local.
- Playwright real ainda precisa do browser instalado no ambiente operacional com `python -m playwright install chromium`.
- BeautifulSoup e trafilatura estão declarados na instalação base, mas a qualidade com casos reais ainda precisa ser medida.
- Ainda não há Firecrawl para extração de texto principal via serviço externo.
- Ainda não há Scrapy para crawling estruturado em escala.
- A qualidade da extração em páginas de marketing, blogs, notícias e sites modernos ainda deve ser medida com casos reais.
- O MVP mede se a coleta é suficiente para seguir no fluxo, mas ainda não compara estratégias alternativas de coleta.

## Contrato de Saída

- `SearchParams`
- `SearchPlan`
- `RawDiscoveryResult`
- `CandidateStartup`
- `PageCollectionResult`
- `StartupProfile`
- `FieldEvidenceGroup`
- `CollectionQualitySummary`

## Validação Atual

Existe suíte local padrão sem rede, credenciais, serviços externos, Postgres real, LangGraph obrigatório ou navegador real obrigatório.

## Limitações Conhecidas

- O único adaptador real de busca implementado é Brave Search.
- Outros provedores exigem novos `SearchClient`.
- O smoke Playwright real é opt-in e requer browser instalado; a suíte local continua sem navegador obrigatório.
- Melhorias como Firecrawl ou Scrapy devem ser introduzidas por necessidade medida, não todas de uma vez.
- A suíte local não deve fazer chamadas externas.
- Postgres real requer `docker compose up -d postgres` e driver `psycopg`.
- `build_langgraph` requer dependência opcional `langgraph`; a próxima suíte deve usar o runner local.

## Roadmap de Hardening

O plano para evoluir scraping além do MVP está em `context/roadmap-scraping-hardening.md`.

Esse hardening deve preservar os contratos atuais (`StartupProfile`, evidências por campo e `CollectionQualitySummary`) e deve ser guiado por falhas observadas: baixa completude, muitos `unknown`, páginas com pouco texto, erros por robots/política, conteúdo JS ausente ou fontes públicas importantes não coletadas.

## Próxima Etapa Consumidora

O épico de avaliação AI-native em `context/roadmap-pipeline-avaliação.md` já consome os artefatos acima e não repete scraping.

A próxima etapa consumidora é `context/roadmap-nvidia-knowledge-recommendation-briefing.md`, que deve usar `AINativeAssessment`, gaps e evidências para recuperar conhecimento NVIDIA citável, recomendar tecnologias e gerar briefing.
