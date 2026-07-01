# Roteiro de Apresentação da Arquitetura

Este roteiro foi pensado para uma apresentação curta, de aproximadamente 4 a 5 minutos. A ideia é usar o Excalidraw para explicar a arquitetura do projeto nos primeiros 3 a 4 minutos e depois mostrar o fluxo no frontend em cerca de 1 minuto.

## Como abrir o Excalidraw

O arquivo do diagrama está neste caminho dentro do projeto:

```text
context/project-architecture.excalidraw
```

Se o link clicável não abrir direto pela interface do Codex ou pelo editor, abra o site do Excalidraw e importe manualmente:

1. Acesse `https://excalidraw.com`.
2. Clique no menu.
3. Escolha a opção de abrir/importar arquivo.
4. Selecione `context/project-architecture.excalidraw`.

## Roteiro para ler explicando a arquitetura

Vou começar explicando a visão geral do projeto. Esse sistema foi pensado como uma ferramenta de inteligência para apoiar a NVIDIA no Brasil a descobrir e avaliar startups brasileiras com potencial AI-native, principalmente pensando no programa NVIDIA Inception.

A ideia não é só fazer uma busca simples de startups que falam que usam IA. O objetivo é entender se a IA realmente parece central no produto, se existe algum sinal técnico mais forte, quais são os possíveis gaps da startup e onde a NVIDIA poderia entrar com tecnologia, programa ou relacionamento.

Por isso a arquitetura do projeto foi montada em cima de uma lógica evidence-first. Isso quer dizer que o sistema tenta separar o que foi observado em fonte pública, o que foi inferido a partir dessas fontes, o que é uma recomendação e o que ainda é desconhecido. Se uma informação não aparece com evidência suficiente, ela continua como `unknown`. Isso é importante porque, nesse tipo de análise, inventar uma informação deixa o briefing mais bonito, mas piora a decisão.

O primeiro bloco da arquitetura são as superfícies de uso. Hoje o projeto tem uma CLI, uma API e um frontend operacional. O ponto importante aqui é que o frontend não concentra regra de negócio. Ele serve para disparar uma análise e inspecionar os artefatos gerados. A lógica principal fica no backend, em contratos e módulos de domínio.

Depois vem a camada de orquestração. O projeto usa um runner local como caminho padrão, porque ele é mais simples de testar e não depende de serviços externos. Para uma evolução mais próxima de produção, LangGraph entra como camada de orquestração, cuidando de estado, branches, checkpoints, retomada de execução e possíveis revisões humanas. Mesmo assim, a regra de negócio não fica presa no LangGraph. O grafo só chama módulos menores e testáveis.

O fluxo principal do domínio segue uma ordem bem definida. Primeiro vem Discovery, que encontra uma startup candidate. Depois Collection coleta páginas públicas dessa startup. Em seguida, Profile Extraction transforma o conteúdo coletado em um Startup Profile estruturado. Depois Evidence Quality mede se a coleta foi boa o suficiente, se tem conflito, se tem muito `unknown` ou se precisa de revisão.

Com esse perfil pronto, entra o AI-Native Assessment. Essa etapa classifica a startup como AI-native, AI-enabled ou non-AI, além de levantar riscos, como wrapper risk. Esse wrapper risk é o risco de a startup depender basicamente de APIs externas, sem sinais de dados próprios, inferência em produção ou profundidade técnica.

Depois disso entra o bloco de NVIDIA Knowledge. Aqui o sistema consulta uma base versionada de conhecimento oficial da NVIDIA. Essa parte é importante porque existe uma diferença entre Evidence e Citation. Evidence é a fonte pública que fala sobre a startup. Citation é a fonte oficial NVIDIA que sustenta uma recomendação sobre tecnologia, programa ou stack. Então, uma recomendação boa precisa ter os dois lados bem separados.

Na camada de retrieval, a arquitetura combina busca lexical e busca vetorial. A busca lexical usa BM25, que é boa para encontrar termos exatos e manter rastreabilidade. A busca vetorial usa embeddings para encontrar trechos semanticamente próximos. O Postgres com pgvector entra como o caminho local preferido para armazenar vetores e permitir busca sem depender de um serviço externo. Depois da busca híbrida, o sistema pode aplicar reranking no top K, mas sempre preservando os chunks originais, scores e citações.

Na parte de scraping, o caminho real é Playwright-first, porque muitos sites modernos dependem de JavaScript. Depois da renderização, o projeto usa extração com trafilatura e BeautifulSoup. Scrapy e Firecrawl ficam como adapters opcionais para quando existir necessidade real de escala ou extração mais especializada. O caminho determinístico mais simples continua existindo, mas como apoio para teste, debug e comparação, não como motor principal de coleta real.

Depois do retrieval, o sistema passa para Recommendation. Essa etapa cruza os gaps técnicos ou oportunidades comerciais da startup com tecnologias e programas NVIDIA. Um ponto importante é que o assessment gera só um sinal preliminar. A prioridade final da oportunidade NVIDIA só aparece depois da recomendação, porque é nesse momento que o sistema consegue conectar o problema da startup com uma fonte oficial NVIDIA.

Por fim, vem o Briefing. O briefing pode ser executivo, quando existe suporte suficiente, ou pode virar um Human Review Briefing. Esse segundo caso acontece quando existe baixo sinal, alto risco de wrapper, conflito nas fontes, muitos desconhecidos ou falta de citação oficial. Em vez de forçar uma conclusão, o sistema entrega para o humano um resumo com a startup, área de atuação, descobertas, gargalos, riscos e perguntas pendentes.

Na parte de LLM, a arquitetura também tenta ser cuidadosa. A LLM, por exemplo usando Groq por LiteLLM, não é responsável por decidir fatos nem inventar recomendações. Ela entra principalmente para redigir uma narrativa a partir de artefatos já validados. Então a LLM melhora a comunicação do briefing, mas a decisão continua sustentada por contratos, evidências, citações e regras determinísticas.

Resumindo a arquitetura: o projeto foi desenhado para ser auditável. Cada etapa recebe um contrato, produz uma saída versionada e mantém rastreabilidade. Isso deixa o sistema mais confiável para uma situação real de negócio, porque o gerente não recebe só uma resposta pronta. Ele consegue ver de onde veio a informação, o que é certeza, o que é hipótese, quais gaps foram encontrados e por que determinada tecnologia NVIDIA foi recomendada.

## Roteiro rápido para mostrar o frontend

Para rodar o frontend localmente:

```bash
npm --prefix frontend run dev
```

Depois abra no navegador:

```text
http://127.0.0.1:5173
```

Para uma demonstração rápida sem depender de rede, API externa, Postgres, LLM real ou scraping real, use o run mockado:

```text
http://127.0.0.1:5173?run_id=mock-completed-run&section=runs
```

Para mostrar sem mock, suba também o backend API:

```bash
nvidia-startup-intel-api --host 127.0.0.1 --port 8001
```

Depois abra o frontend em modo real:

```text
http://127.0.0.1:5173?api=real&baseUrl=http://127.0.0.1:8001
```

Se a porta `8000` estiver livre, ela também pode ser usada. Nesta máquina, a porta `8000` estava ocupada, então a demo real foi validada com `8001`.

Na apresentação, eu mostraria o frontend nesta ordem:

1. **Runs**: mostrar que existe uma execução com status, entrada e artefatos gerados.
2. **Evidence**: mostrar o perfil da startup, páginas coletadas, evidências, `unknowns` e qualidade da coleta.
3. **Assessment**: mostrar a classificação AI-native, gaps técnicos e riscos como wrapper risk.
4. **NVIDIA Match**: mostrar as recomendações, a recuperação de conhecimento NVIDIA, top K e citações oficiais.
5. **Briefing**: fechar mostrando o briefing executivo ou, quando não houver segurança suficiente, o Human Review Briefing.

Uma fala curta para essa parte pode ser:

> Aqui no frontend eu não estou mostrando só uma tela final. A ideia é mostrar o caminho da decisão. Primeiro eu vejo a execução, depois as evidências coletadas, depois a avaliação da startup, depois o match com conhecimento oficial NVIDIA e, por último, o briefing. Assim o usuário consegue entender não só a recomendação, mas também de onde ela veio e quando o sistema prefere pedir revisão humana.

## Fechamento sugerido

Para fechar a apresentação, eu diria:

> Então, no geral, o projeto não é só um scraper nem só um chatbot. Ele é um pipeline de inteligência com evidência, avaliação, retrieval, recomendação e briefing. A principal preocupação da arquitetura foi deixar claro o que é dado observado, o que é inferência, o que é recomendação e o que ainda precisa de validação humana.
