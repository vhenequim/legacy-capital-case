# Plano: Legacy Capital AI Retrieval System

## O que entendi

Este não é um projeto de chatbot. É uma **plataforma de pesquisa para analistas de equities**, no estilo NotebookLM, com estas características centrais:

| Princípio | Significado prático |
|-----------|---------------------|
| **Retrieval é o coração** | O critério principal é "encontrou os documentos certos?", não a fluência do LLM |
| **Zero alucinação** | Toda resposta vem da base indexada; sem evidência → "não encontrei" |
| **Base conectada** | Sem upload manual; ingestão automática e reproduzível de fontes oficiais |
| **Arquitetura genérica** | Os 3 cases validam a plataforma, não geram lógica hardcoded por caso |
| **Dados heterogêneos** | PDFs, transcripts, notícias **e** séries estruturadas (BACEN, ANP, CSV) conversam no retrieval |
| **Eval-first** | Construir harness de avaliação **antes** de otimizar retrieval |

### Os três cases (mesma habilidade, dificuldades diferentes)

- **Case A** — Consolidar capex de hyperscalers (MSFT, AMZN, GOOG, META, etc.) espalhado em earnings, calls e notícias; cruzar com comentários da NVIDIA sobre demanda.
- **Case B** — Guidance vs entrega ao longo do tempo (Bradesco/provisões); mudança de sentimento trimestral; estratégia declarada vs market share calculado com IF.data/SCR.data do BACEN.
- **Case C** — Extrair RPO trimestral de ~15 empresas SaaS, calcular YoY growth e aceleração, cruzar com retorno da ação no pregão seguinte à divulgação.

### Estado atual do repositório

- [`prd.md`](prd.md) — visão de produto e filosofia
- [`case.md`](case.md) — requisitos técnicos, cases, eval harness e critérios de avaliação

### Critérios de sucesso (pesos do case)

- Retrieval: 25%
- Eval Harness: 25%
- Resolução dos Cases: 15%
- Apresentação: 15%
- Ingestão + dados heterogêneos: 10%
- Qualidade do código: 10%

---

## Arquitetura proposta (Python)

### Stack

| Camada | Tecnologia |
|--------|---------------------|
| API | FastAPI |
| Orquestração RAG | LlamaIndex |
| Embeddings | OpenAI ou sentence-transformers (local) |
| Vector DB | Qdrant |
| BM25 | rank_bm25 |
| Reranking | cross-encoder/ms-marco-MiniLM |
| LLM | OpenAI/Anthropic via API |
| Dados estruturados | PostgreSQL + pandas |
| Testes | pytest |

---

## Fases de implementação

1. **Fase 0** — Fundação do projeto
2. **Fase 1** — Eval Harness primeiro (prioridade máxima)
3. **Fase 2** — Pipeline de ingestão
4. **Fase 3** — Indexação e retrieval
5. **Fase 4** — Geração grounded
6. **Fase 5** — Camada de dados estruturados
7. **Fase 6** — Validação dos 3 cases
8. **Fase 7** — Documentação e apresentação

**Estimativa total:** ~3-4 semanas para MVP completo com os 3 cases e eval reportando métricas.
