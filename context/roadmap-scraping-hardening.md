# Roadmap: Scraping Hardening e Extração Pública Robusta

Objetivo: evoluir o MVP de scraping de um walking skeleton funcional para uma camada de coleta pública mais robusta, sem quebrar os contratos de evidência, perfil e qualidade já validados.

Este roadmap não substitui o MVP atual. Ele define melhorias incrementais para quando os outputs reais mostrarem que a coleta simples com `urllib` + `html.parser` não é suficiente.

## Princípios

- Preservar evidência, URLs, trechos e data de coleta.
- Medir falhas antes de adicionar ferramentas pesadas.
- Adicionar uma ferramenta por vez, com teste local e fixture.
- Não usar scraping autenticado nem burlar paywall, login, robots.txt ou proteção anti-bot.
- Não transformar hardening de scraping em reescrita do pipeline.
- Manter `StartupProfile`, `FieldEvidenceGroup` e `CollectionQualitySummary` como contratos de saída.
- Campos sem evidência continuam como `unknown`.

## Estado Atual

O MVP atual:

- usa `urllib` + `html.parser`;
- executa busca via `SearchClient`, com Brave Search como adaptador real;
- coleta páginas públicas com limites de profundidade e quantidade;
- respeita `robots.txt` quando recebe `RobotsCache`;
- extrai texto simples e perfil estruturado;
- mede qualidade da coleta;
- não possui suíte automatizada válida no estado atual; a suíte antiga foi removida por estar inválida para o escopo atual.

O MVP atual ainda não:

- renderiza JavaScript com Playwright;
- usa trafilatura para texto principal;
- usa BeautifulSoup para parsing HTML mais robusto;
- usa Firecrawl para extração limpa orientada a RAG;
- usa Scrapy para crawling em escala;
- compara estratégias de coleta para a mesma página.

## Quando Fazer Este Épico

Execute este roadmap quando pelo menos um destes sinais aparecer em avaliação real:

- muitas startups prontas para abordagem aparecem como `insufficient_evidence`;
- páginas oficiais coletadas retornam pouco texto útil;
- páginas relevantes dependem claramente de JavaScript;
- evidências importantes aparecem em blogs/notícias, mas o texto extraído é ruidoso;
- a taxa de `unknown` impede avaliação AI-native útil;
- o briefing fica fraco por falta de evidência pública mesmo quando as fontes existem.

## Story 01: Medir falhas de coleta por startup

Como desenvolvedor, quero registrar motivos de baixa qualidade da coleta para decidir qual ferramenta de hardening resolve o problema real.

Critérios de aceite:

- A qualidade diferencia página vazia, pouco texto, erro HTTP, bloqueio por política, bloqueio por robots e conteúdo insuficiente.
- O resumo aponta quais startups precisam de nova coleta ou revisão humana.
- Existe teste com pelo menos três tipos de falha.
- Nenhuma nova dependência externa é introduzida nesta story.

## Story 02: Melhorar extração HTML estática

Como desenvolvedor, quero melhorar parsing de páginas HTML públicas simples antes de usar navegador real.

Critérios de aceite:

- A extração preserva URL, título, status e trecho de evidência.
- A implementação melhora texto principal em fixtures com navegação, rodapé e scripts ruidosos.
- A dependência escolhida deve ser justificada entre BeautifulSoup e trafilatura.
- Testes continuam sem rede.
- O fallback para parser atual permanece disponível.

## Story 03: Adicionar estratégia de extração de texto principal

Como usuário do diagnóstico, quero que blogs, páginas institucionais e notícias gerem texto limpo o bastante para sustentar evidências.

Critérios de aceite:

- A estratégia extrai conteúdo principal sem inventar dados.
- A estratégia reduz ruído de menus, rodapés e scripts em fixtures.
- A saída mantém snippets auditáveis.
- Falha de extração vira erro auditável, não exceção que interrompe o pipeline.

## Story 04: Detectar necessidade de renderização JavaScript

Como desenvolvedor, quero detectar quando a página provavelmente precisa de Playwright antes de pagar o custo de navegador real.

Critérios de aceite:

- O sistema identifica páginas com pouco texto estático e sinais de app client-side.
- O output marca `needs_js_rendering` ou equivalente na qualidade da coleta.
- A decisão é testável com HTML fixture.
- Nenhum navegador real é necessário nesta story.

## Story 05: Adicionar Playwright como fallback seletivo

Como operador do pipeline, quero renderizar apenas páginas que realmente precisam de JavaScript para coletar evidências públicas importantes.

Critérios de aceite:

- Playwright é usado somente quando a política permitir e a coleta estática for insuficiente.
- A coleta respeita limites de tempo, profundidade e quantidade.
- O resultado preserva as mesmas estruturas de `PageCollectionResult`.
- Testes unitários usam fixtures ou cliente fake; testes com navegador real ficam opcionais.
- Erros de navegador são registrados sem quebrar a execução inteira.

## Story 06: Avaliar Firecrawl ou serviço externo apenas como adaptador

Como mantenedor, quero que serviços externos de extração sejam adaptadores substituíveis, não regra de domínio.

Critérios de aceite:

- Existe interface explícita para provedor externo.
- Testes usam fake provider.
- Credenciais não são exigidas na suíte local.
- Falhas do provedor viram erro auditável.
- A decisão de usar Firecrawl é baseada em ganho medido contra coleta local.

## Story 07: Planejar crawling estruturado em escala

Como mantenedor, quero decidir se Scrapy é necessário somente depois de validar o fluxo de uma startup profundamente.

Critérios de aceite:

- Existe análise de necessidade: volume, profundidade, tipos de fonte e limites de domínio.
- Scrapy não substitui os contratos de domínio.
- Crawling em escala preserva robots.txt, rate limit e erros auditáveis.
- O escopo não inclui scraping autenticado.

## Definition of Done

- [ ] Falhas de coleta são categorizadas de forma auditável.
- [ ] Extração estática é mais robusta em fixtures reais.
- [ ] Conteúdo JS-heavy é detectado antes de usar navegador.
- [ ] Playwright entra apenas como fallback seletivo, se necessário.
- [ ] Serviços externos entram por adaptadores testáveis, se necessário.
- [ ] Os contratos de saída atuais continuam compatíveis.
- [ ] Nova suíte local de validação passa sem rede, credenciais ou navegador real obrigatório.

## Relação Com AI-Native Assessment

O hardening de scraping melhora a qualidade dos inputs, mas não deve bloquear todo o desenvolvimento do diagnóstico AI-native.

A avaliação AI-native deve conseguir consumir os artefatos atuais e retornar `insufficient_evidence` quando a coleta for fraca. Esses resultados devem retroalimentar este roadmap, mostrando quais melhorias de scraping têm maior impacto.
