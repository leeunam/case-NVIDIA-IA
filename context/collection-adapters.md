# Collection Adapters

Este documento explica quando usar cada estratégia de Collection sem alterar os contratos do domínio. Todas as estratégias devem devolver `PageCollectionResult`, com `CollectedPage` e `PageCollectionError` auditáveis.

## Caminho padrão

Use Playwright como caminho real de produção para páginas públicas modernas, SPAs e sites onde HTML estático tende a perder conteúdo. O caminho `urllib` + `html.parser` permanece apenas como harness determinístico de teste/debug.

Use `trafilatura` para extrair texto principal de páginas institucionais, blogs e notícias depois que o HTML estiver disponível. Use BeautifulSoup para título, links, metadados e fallback de parsing HTML. Ambos ficam atrás do `StaticHTMLExtractionAdapter`.

## Firecrawl

Use Firecrawl somente como serviço externo opt-in quando a coleta local renderizada ainda produzir texto ruim, quando for útil receber markdown/JSON limpo para RAG, ou quando houver ganho medido contra Playwright + `trafilatura` + BeautifulSoup.

O `FirecrawlCollectionAdapter` recebe um cliente injetado, não exige credencial na suíte default e converte falhas em `PageCollectionError` com categoria `firecrawl_adapter_failed`.

## Scrapy

Use Scrapy quando houver necessidade de crawling estruturado em escala, filas, profundidade maior, throttling e pipelines de itens.

O `ScrapyCollectionAdapter` recebe um crawler injetado, não substitui os contratos de domínio e devolve `PageCollectionResult`. Falhas viram `PageCollectionError` com categoria `scrapy_adapter_failed`.

## Dependências opcionais

Firecrawl e Scrapy ficam fora do caminho padrão. Para ambientes reais, instale os extras correspondentes e injete o cliente/crawler do provider:

```bash
python -m pip install -e ".[scraping-services]"
python -m pip install -e ".[scraping-scale]"
```
