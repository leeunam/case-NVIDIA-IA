# Collection Adapters

Este documento explica quando usar cada estratégia de Collection sem alterar os contratos do domínio. Todas as estratégias devem devolver `PageCollectionResult`, com `CollectedPage` e `PageCollectionError` auditáveis.

## Caminho padrão

Use Playwright como caminho real de produção para páginas públicas modernas, SPAs e sites onde HTML estático tende a perder conteúdo. O caminho `urllib` + `html.parser` permanece apenas como harness determinístico de teste/debug.

Use `trafilatura` para extrair texto principal de páginas institucionais, blogs e notícias depois que o HTML estiver disponível. Use BeautifulSoup para título, links, metadados e fallback de parsing HTML. Ambos ficam atrás do `StaticHTMLExtractionAdapter`.

Firecrawl e Scrapy não substituem esse baseline. Eles são caminhos opt-in de escalonamento quando a validação Playwright-first mostrar falha medida, como texto vazio, texto ruidoso, alto unknown rate ou falhas recorrentes de coleta.

Todos os adapters de Collection devem avaliar política de scraping e `robots.txt` antes de chamar providers externos. Bloqueios viram `PageCollectionError` com categoria auditável, como `blocked_domain` ou `robots_disallowed`, e não devem chamar cliente/crawler injetado.

## Firecrawl

Use Firecrawl somente como serviço externo opt-in quando a coleta local renderizada ainda produzir texto ruim, quando for útil receber markdown/JSON limpo para RAG, ou quando houver ganho medido contra Playwright + `trafilatura` + BeautifulSoup.

O `FirecrawlCollectionAdapter` recebe um cliente injetado, não exige credencial na suíte default e converte falhas em `PageCollectionError` com categoria `firecrawl_adapter_failed`.

Configuração de credenciais deve registrar apenas o nome da variável que contém a chave. Use `NVIDIA_STARTUP_INTEL_FIRECRAWL_API_KEY_ENV` para apontar para uma variável local, por exemplo `FIRECRAWL_API_KEY`. O valor da chave não deve entrar em código, fixtures, payloads persistidos, logs ou commits.

Payloads bem-sucedidos mas sem texto extraível viram `PageCollectionError` com categoria `firecrawl_empty_content`.

## Scrapy

Use Scrapy quando houver necessidade de crawling estruturado em escala, filas, profundidade maior, throttling e pipelines de itens.

O `ScrapyCollectionAdapter` recebe um crawler injetado, não substitui os contratos de domínio e devolve `PageCollectionResult`. Falhas viram `PageCollectionError` com categoria `scrapy_adapter_failed`.

O crawler injetado recebe limites explícitos de domínio e throttling derivado da política de Collection: `allowed_domains` e `throttle_seconds`. Objetos do Scrapy não devem atravessar para contextos downstream.

Itens crawlados sem texto extraível viram `PageCollectionError` com categoria `scrapy_empty_content`.

## Comparação de estratégias

Use `compare_collection_strategy_quality` para comparar resultados de Playwright/trafilatura/BeautifulSoup, Firecrawl e Scrapy a partir de `PageCollectionResult`. As métricas incluem falhas de coleta, taxa de texto `unknown`, taxa de texto vazio/baixo, tamanho médio de texto e estratégias de extração observadas.

Essas métricas servem para justificar quando Firecrawl ou Scrapy devem ser usados. A suíte default continua com fakes/fixtures, sem rede, credenciais, navegador real ou Scrapy/Firecrawl reais.

## Dependências opcionais

Firecrawl e Scrapy ficam fora do caminho padrão. Para ambientes reais, instale os extras correspondentes e injete o cliente/crawler do provider:

```bash
python -m pip install -e ".[scraping-services]"
python -m pip install -e ".[scraping-scale]"
```
