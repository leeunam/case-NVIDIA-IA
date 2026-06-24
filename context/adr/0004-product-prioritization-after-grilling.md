# ADR 0004: Priorização do Produto Após Grilling

Status: aceito, atualizado por ADR 0006

## Contexto

A sessão de grilling esclareceu que o sistema não deve ser apenas um classificador técnico. Ele precisa ajudar a NVIDIA a decidir quais startups abordar, com diagnóstico técnico suficiente para sustentar recomendação e briefing comercial.

## Decisão

O produto terá três papéis no mesmo fluxo:

1. qualification engine;
2. technical diagnostic engine;
3. sales enablement briefing engine.

O primeiro workflow do MVP será análise profunda de uma startup. A priorização usará oportunidade NVIDIA, com a ressalva posterior da ADR 0006: assessment gera sinal preliminar e recommendation calcula a prioridade final. Quando a evidência pública for fraca, mas houver sinal estratégico, o sistema pode gerar hipótese de baixa confiança para revisão humana.

Uma startup será considerada AI-native quando a IA moldar a arquitetura do sistema, a interface do usuário, o modelo de negócios e as operações internas, permitindo respostas adaptáveis e dinâmicas aos usuários.

Risco de wrapper/API-dependency será avaliado principalmente por:

- dependência apenas de APIs externas;
- ausência de dados proprietários;
- ausência de infraestrutura de inferência em produção.

## Consequências

Benefícios:

- MVP mais alinhado com decisão real de abordagem;
- recomendações mais úteis para o gerente de Startups & VCs;
- critérios explícitos para baixa confiança e revisão humana.

Custos:

- o diagnóstico precisa calcular sinal preliminar de oportunidade, não apenas maturidade;
- recomendações fracas devem ser bloqueadas ou rebaixadas;
- o briefing precisa ser desenhado para ação comercial e técnica.

## Impacto no Código

O módulo `ai_native_assessment.py` deve incluir sinal preliminar de oportunidade, risco de wrapper e hipótese de baixa confiança. O futuro motor de recomendação deve calcular prioridade final NVIDIA, ranquear tecnologias por gap e destacar a opção top 1, recomendando NVIDIA Inception apenas quando houver gap técnico ou comercial específico.
