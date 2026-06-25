# ADR 0002: LangGraph Como Camada de Orquestração

Status: aceito

## Contexto

O projeto prevê agentes para busca, scraping, extração, validação, RAG, recomendação e briefing. Existe risco de concentrar regra de negócio em prompts ou nós grandes demais, dificultando testes e rastreabilidade.

## Decisão

LangGraph será usado para estado, checkpoints, retries, branches e intervenção humana. A regra de negócio ficará em módulos Python testáveis.

Nós do grafo devem:

- receber e devolver estado explícito;
- chamar funções ou adaptadores pequenos;
- preservar erros e evidências;
- decidir transições com base em artefatos estruturados.

Nós do grafo não devem:

- fazer parsing crítico em prompt solto;
- esconder decisões de classificação;
- chamar integrações externas sem interface injetável;
- modificar evidências brutas.

## Consequências

Benefícios:

- testes locais sem LangGraph instalado;
- grafo substituível por runner local;
- melhor depuração por checkpoint;
- menor acoplamento entre agentes e domínio.

Custos:

- mais contratos de estado;
- necessidade de manter módulos e grafo sincronizados.

## Impacto no Código

`pipeline.py` e `scraping_graph.py` continuam como superfície inicial. Próximos grafos devem reutilizar as funções de domínio e adicionar nós finos para avaliação AI-native, RAG, recomendação e briefing.
