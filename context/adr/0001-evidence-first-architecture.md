# ADR 0001: Arquitetura Evidence-First

Status: aceito

## Contexto

O projeto precisa identificar startups brasileiras com potencial AI-native e recomendar tecnologias NVIDIA. O risco principal é produzir classificações e recomendações convincentes, mas sem evidência suficiente. Isso seria pior do que não responder, porque afetaria priorização comercial e técnica.

## Decisão

O sistema será evidence-first:

- toda afirmação relevante deve apontar para evidências;
- campos sem suporte retornam `unknown`;
- inferências e recomendações são tipos de afirmação diferentes de dados observados;
- conflitos são preservados;
- qualidade da coleta decide se o fluxo pode seguir para avaliação;
- briefings devem expor incertezas e perguntas pendentes.

## Consequências

Benefícios:

- auditoria simples;
- menor risco de alucinação;
- reprocessamento possível sem repetir coleta;
- melhor base para revisão humana.

Custos:

- mais schemas e testes;
- menor velocidade para gerar recomendações superficiais;
- necessidade de modelar evidências em todas as etapas.

## Impacto no Código

Novos módulos de avaliação, RAG, recomendação e briefing devem aceitar evidências como entrada explícita e retornar evidências usadas na saída.
