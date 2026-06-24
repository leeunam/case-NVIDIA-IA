# ADR 0003: Walking Skeleton Antes de Escala

Status: aceito

## Contexto

O projeto menciona Playwright, Scrapy, Firecrawl, RAG, reranking, LangGraph, Postgres e interface web. Implementar tudo antes de validar a linha vertical aumentaria complexidade sem reduzir o risco central: recomendação sem evidência.

## Decisão

O projeto deve evoluir por walking skeletons:

1. scraping público simples e testável;
2. avaliação AI-native determinística com fixtures;
3. base NVIDIA mínima com recuperação citável;
4. recomendação baseada em gaps;
5. briefing executivo;
6. UI apenas quando os contratos estiverem estáveis.

Novas ferramentas entram somente quando uma story demonstrar necessidade concreta.

## Consequências

Benefícios:

- menor custo de mudança;
- validação fim a fim cedo;
- testes determinísticos;
- arquitetura guiada por uso real.

Custos:

- algumas automações avançadas ficam adiadas;
- a primeira versão terá menor cobertura de fontes e documentos.

## Impacto no Código

Não introduzir Scrapy, Playwright, Firecrawl, vector database ou reranker externo antes de existir um contrato testável com fixtures locais e fallback auditável.
