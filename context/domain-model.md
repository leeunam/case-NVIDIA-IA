# Modelo de Domínio

Este documento registra a modelagem usada para orientar novas stories, schemas e agentes.

## Entidades

### Startup Candidate

Empresa descoberta a partir de busca ou fonte pública antes de confirmação completa.

Campos principais:

- nome;
- domínio ou URL principal;
- fonte de descoberta;
- trecho de evidência;
- score inicial;
- execução de origem.

### Collected Page

Página pública coletada para uma candidata.

Campos principais:

- URL;
- título;
- texto principal;
- status HTTP;
- data de coleta;
- erro, quando houver;
- política aplicada, incluindo robots.txt quando relevante.

### Startup Profile

Perfil estruturado e versionado da startup.

Campos principais:

- nome;
- site oficial;
- resumo;
- setor;
- produto;
- clientes;
- funding;
- founders;
- tecnologias usadas;
- sinais de IA;
- localização.

Cada campo possui valor, tipo de afirmação e evidências.

### Evidence

Fonte auditável usada para sustentar uma afirmação.

Campos mínimos:

- URL;
- título;
- trecho;
- data de coleta;
- tipo de fonte;
- campo sustentado.

### AI-Native Assessment

Diagnóstico da maturidade AI-native.

Campos esperados:

- classificação;
- confiança;
- sinal preliminar de oportunidade;
- critérios avaliados;
- sinais observados;
- gaps;
- riscos;
- evidências por critério;
- campos insuficientes.

### NVIDIA Knowledge Item

Documento, trecho ou recurso oficial da base NVIDIA.

Campos esperados:

- tecnologia;
- produto ou programa;
- fonte;
- trecho;
- versão ou data de ingestão;
- aplicabilidade;
- limitações.

### NVIDIA Knowledge Chunk

Trecho recuperável de um documento oficial NVIDIA.

Campos esperados:

- identificador do chunk;
- identificador do documento;
- corpus version;
- texto do trecho;
- ordem no documento;
- tecnologia, programa ou tópico relacionado;
- tipo de fonte;
- citação associada.

### Citation

Referência usada para sustentar afirmação sobre tecnologia NVIDIA ou programa.

Campos esperados:

- título da fonte;
- URL ou referência interna;
- trecho citado;
- data de ingestão;
- tipo de fonte;
- identificador do documento e do chunk;
- limitações conhecidas.

### Recommendation

Recomendação técnica ou de programa vinculada a um gap técnico ou oportunidade comercial e a uma fonte oficial NVIDIA.

Campos esperados:

- tecnologia NVIDIA;
- gap endereçado;
- oportunidade comercial endereçada, quando aplicável;
- tipo de recomendação;
- posição no ranking do gap;
- justificativa técnica;
- justificativa comercial;
- prioridade;
- complexidade;
- prioridade final da oportunidade NVIDIA;
- próxima ação;
- evidências da startup;
- fontes NVIDIA.

### Recommendation Set

Conjunto versionado de recomendações para uma startup em uma execução.

Campos esperados:

- schema version;
- run id;
- startup;
- recomendações técnicas por gap;
- recomendações de programa por oportunidade comercial;
- recomendação top 1 por gap;
- próxima ação;
- alternativas;
- recomendações bloqueadas;
- hipóteses;
- qualidade da recomendação;
- prontidão para briefing.

### Executive Briefing

Documento final para apoiar abordagem da NVIDIA.

Campos esperados:

- resumo executivo;
- diagnóstico;
- oportunidade;
- riscos;
- recomendações;
- perguntas pendentes;
- fontes.

### Human Review Briefing

Briefing gerado quando o sistema não pode produzir recomendação final, mas deve entregar contexto suficiente para revisão humana.

Campos esperados:

- startup;
- área de atuação;
- resumo do que foi descoberto;
- evidências principais;
- sinal preliminar de oportunidade;
- gaps técnicos suspeitos;
- oportunidades comerciais suspeitas;
- riscos de wrapper/API-dependency;
- gargalos ou informações ausentes;
- conflitos encontrados;
- perguntas para validação humana;
- próxima ação sugerida.

### Briefing Claim

Afirmação individual dentro do briefing.

Campos esperados:

- texto da afirmação;
- tipo de afirmação;
- seção do briefing;
- evidências da startup, quando aplicável;
- citações NVIDIA, quando aplicável;
- nível de confiança;
- motivo de unknown ou revisão humana, quando aplicável.

### Commercial Opportunity

Oportunidade não técnica para aproximação, suporte de programa, parceria ou go-to-market.

Campos esperados:

- tipo de oportunidade;
- descrição;
- prioridade;
- confiança;
- evidências da startup;
- citações NVIDIA, quando houver recomendação de programa;
- próxima ação sugerida.

## Vocabulário Controlado

### Classification

- `ai_native`: há evidência pública suficiente de centralidade da IA no produto e profundidade técnica na stack, dados, modelos, avaliação, MLOps ou inferência.
- `ai_enabled`: IA aparece como funcionalidade relevante, mas não há evidência suficiente de que seja o núcleo do negócio ou stack.
- `non_ai`: não há sinais relevantes de uso de IA.
- `insufficient_evidence`: a coleta não sustenta classificação.

### Claim Source

- `observed`: dado aparece diretamente em fonte pública coletada.
- `inferred`: dado foi derivado por regra ou análise a partir de evidências.
- `recommended`: ação ou tecnologia sugerida pelo sistema.
- `unknown`: informação ausente ou sem suporte.

### Technical Gap Type

- `model_serving`: serving, latência, throughput, deploy ou escalabilidade de modelos.
- `llm_customization`: ajuste, avaliação, guardrails ou especialização de LLMs.
- `data_acceleration`: processamento ou ML em grandes volumes de dados.
- `voice_ai`: ASR, TTS, tradução ou atendimento por voz.
- `computer_vision`: visão computacional, vídeo, OCR ou inspeção visual.
- `robotics_simulation`: robótica, autonomia, simulação ou digital twins.
- `healthcare_ai`: saúde, imagens médicas, life sciences ou compliance setorial.
- `cybersecurity_ai`: detecção, análise ou resposta em segurança.
- `unknown`: gap ainda não sustentado por evidência.

### Commercial Opportunity Type

- `inception_program_fit`: comunidade, créditos, suporte técnico, parceiros ou go-to-market via NVIDIA Inception.
- `founder_validation`: oportunidade depende de conversa humana para validar hipótese técnica ou comercial.
- `partner_ecosystem`: possível encaixe com parceiros, comunidade ou ecossistema NVIDIA.
- `unknown`: oportunidade comercial ainda não sustentada por evidência.

### Wrapper Risk Signal

- `external_api_only`: dependência aparente de APIs externas como principal camada de IA.
- `no_proprietary_data_evidence`: ausência de evidência de dados proprietários, feedback loop ou ativo de dados.
- `no_production_inference_evidence`: ausência de evidência de infraestrutura de inferência em produção.
- `unknown`: não há evidência suficiente para avaliar o risco.

### Opportunity Signal

- `strong`: existe sinal claro de gap técnico ou oportunidade comercial, mas ainda sem confirmação por fonte NVIDIA recuperada.
- `medium`: existe sinal plausível, mas a dor ou urgência ainda exige validação.
- `low`: sinal fraco ou dependente de descoberta adicional.
- `human_review`: evidência fraca, mas sinais estratégicos justificam hipótese de baixa confiança.

### NVIDIA Opportunity Priority

- `urgent`: recommendation encontrou gap técnico ou oportunidade comercial específica com fonte oficial NVIDIA e próxima ação clara.
- `medium`: existe fit NVIDIA suportado por fonte oficial, mas dor, urgência ou evidência da startup ainda exigem validação.
- `low`: fit NVIDIA indireto ou pouco prioritário para abordagem imediata.
- `human_review`: recommendation encontrou hipótese promissora, conflito ou evidência insuficiente para uso direto.

### Knowledge Source Type

- `official_nvidia`: fonte oficial NVIDIA.
- `unknown`: origem insuficiente ou não classificada.

### Recommendation State

- `supported`: recomendação tem gap técnico ou oportunidade comercial e fonte oficial NVIDIA suficiente.
- `hypothesis`: recomendação é plausível, mas faltam fontes ou evidências para tratá-la como fato.
- `blocked`: recomendação não deve seguir para briefing final.

### Recommendation Type

- `technical`: recomendação de tecnologia ou recurso técnico NVIDIA para um gap técnico.
- `program`: recomendação de programa NVIDIA, como Inception, para uma oportunidade comercial.
- `next_action`: ação sugerida para o humano continuar a qualificação ou abordagem.

### Briefing Status

- `draft`: briefing gerado para revisão.
- `ready_for_human_review`: briefing contém hipótese, conflito ou unknown relevante.
- `ready_for_use`: briefing possui evidência e fontes suficientes para apoiar abordagem.

## Regras de Domínio

- Uma classificação AI-native sem evidência deve ser rejeitada.
- Uma recomendação NVIDIA precisa apontar para pelo menos um gap ou oportunidade.
- Um gap pode existir com baixa confiança, desde que seja marcado como inferência e inclua evidências.
- A avaliação AI-native gera sinal preliminar de oportunidade, não prioridade NVIDIA final.
- Uma tecnologia NVIDIA só deve aparecer como recomendação suportada se houver fonte oficial NVIDIA na base de conhecimento.
- A prioridade final da oportunidade NVIDIA pertence ao contexto de Recommendation, depois de recuperar fontes oficiais.
- NVIDIA Inception deve ser recomendado apenas quando houver gap técnico ou comercial específico.
- Recuperação de conhecimento NVIDIA retorna trechos citáveis; ela não decide recomendação sozinha.
- Uma recomendação técnica precisa combinar pelo menos um gap técnico da startup e pelo menos uma citação oficial NVIDIA.
- Uma recomendação de programa precisa combinar pelo menos uma oportunidade comercial específica e pelo menos uma citação oficial NVIDIA.
- Recomendação sem fonte suficiente deve ser marcada como hipótese ou bloqueada, não como fato.
- O briefing não deve transformar hipótese em dado observado.
- O briefing deve bloquear ou pedir revisão humana quando houver recomendação sem fonte, conflito crítico ou excesso de unknown em campos decisivos.
- O fluxo de revisão humana deve gerar `Human Review Briefing`; não basta retornar um status vazio.
- Quando houver baixo sinal, alto risco de wrapper ou fonte insuficiente, o briefing de revisão humana deve mostrar startup, área de atuação, descobertas, gargalos, riscos e perguntas pendentes.
- O ranking de tecnologias deve destacar a opção top 1 por gap, mas preservar alternativas relevantes quando houver incerteza.
- Risco de wrapper deve considerar principalmente dependência apenas de APIs externas, ausência de dados proprietários e ausência de infraestrutura de inferência em produção.
- Quando houver conflito entre fontes, o briefing deve mostrar o conflito em vez de escolher silenciosamente.
- Se a qualidade da coleta for insuficiente, o fluxo deve pedir nova coleta ou revisão humana antes de recomendação final.

## Eventos de Domínio

- `search_planned`
- `search_executed`
- `candidate_discovered`
- `candidate_deduplicated`
- `page_collected`
- `profile_extracted`
- `evidence_grouped`
- `collection_quality_measured`
- `ai_native_assessed`
- `knowledge_corpus_ingested`
- `knowledge_chunks_indexed`
- `nvidia_knowledge_retrieved`
- `recommendation_generated`
- `recommendation_quality_measured`
- `briefing_generated`
- `human_review_requested`
