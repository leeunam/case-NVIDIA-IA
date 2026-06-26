# ADR 0008: Adapters de Producao Sem Substituir o Core Deterministico

Status: aceito

O projeto vai evoluir para scraping robusto, retrieval hibrido com BM25/vetorial/reranking, LangGraph real, LLM real via Groq/LiteLLM e Postgres/pgvector. A decisao e manter os modulos deterministiscos atuais como contratos de dominio e suite default, introduzindo Playwright, BeautifulSoup, Scrapy, Firecrawl, trafilatura, rank-bm25, LangChain, embeddings reais, rerankers, LangGraph checkpointer e Groq apenas atras de adapters opt-in. Isso evita que frameworks, rede, navegador, banco real ou credenciais virem pre-requisito da validacao local, enquanto permite um caminho de producao funcional e mensurado por precision, recall, F1, latencia, custo e rastreabilidade.
