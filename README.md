# Legacy Capital AI Retrieval System

Plataforma de pesquisa documental para analistas de equities, no estilo NotebookLM, com **ingestão automática de fontes oficiais** e **respostas grounded com citações**. O retrieval é o coração do sistema: toda resposta vem exclusivamente da base indexada — sem evidência, o sistema recusa responder.

## Arquitetura

```
Fontes oficiais (SEC EDGAR, CVM, BACEN, RSS, Yahoo Finance)
    → Ingestão automática (fetchers por fonte, cache reproduzível)
    → Parsing (PDF via pdfplumber, HTML via BeautifulSoup)
    → Chunking (~1800 chars, overlap 200, metadados de empresa/tipo/data)
    → Indexação dupla: BM25 (léxico) + embeddings multilíngues (Qdrant)
    → Busca híbrida com fusão RRF
    → Reranking cross-encoder multilíngue
    → Geração grounded (Groq/Llama 3.3 70B) com citações [Evidence N]
    → Recusa explícita quando o score de evidência é insuficiente
```

### Stack

| Componente | Tecnologia | Por quê |
|------------|------------|---------|
| Vector DB | Qdrant (Docker) | Simples, rápido, payload com metadados |
| Léxico | rank_bm25 + tokenização regex | Termos exatos: "capex", "RPO", "provisões" |
| Fusão | Reciprocal Rank Fusion (k=60) | Combina rankings heterogêneos sem calibração |
| Embeddings | `intfloat/multilingual-e5-small` | Base bilíngue: filings SEC (EN) + CVM (PT) |
| Reranker | `cross-encoder/mmarco-mMiniLMv2-L12` | Multilíngue; logits calibram a recusa |
| LLM | Groq (Llama 3.3 70B, free tier) | Síntese grounded; trocável via .env |
| Estruturados | pandas + yfinance + API Olinda | IF.data BACEN, preços, backtest |
| API | FastAPI | `/query`, `/market-share/{inst}` |

## Origem dos dados (100% reais, ingestão automática)

| Fonte | O que traz | Cases |
|-------|-----------|-------|
| **SEC EDGAR** (`data.sec.gov`) | 10-K/10-Q/8-K/20-F/6-K + exhibits de press release | A, B, C |
| **CVM Dados Abertos** (`dados.cvm.gov.br`, IPE) | Press releases, fatos relevantes (guidance!), apresentações | B |
| **BACEN Olinda** (`olinda.bcb.gov.br`, IF.data) | Carteira de crédito por instituição → market share | B |
| **Yahoo Finance** (yfinance) | Preços diários ajustados para o backtest | C |
| **RSS Yahoo Finance** | Notícias por ticker | A |

Detalhes de implementação que importam:
- **8-K/6-K**: o documento principal é só a capa; os fetchers baixam os *exhibits* (press release real, comentário do CFO), identificados por tamanho no índice do filing — nomes variam por empresa.
- **Bancos brasileiros**: além da CVM, os ADRs (ITUB/BBD/BSBR/NU) publicam earnings na SEC via 6-K — as duas fontes se complementam.
- IDs de documento e de ponto no Qdrant são **determinísticos** (sha256) — reingestão não duplica nada.

## Como executar

### Pré-requisitos
- Python 3.11+ (testado em 3.14), Docker
- GPU opcional (acelera embeddings ~10x)

```bash
python -m venv .venv
.venv\Scripts\activate            # Windows
pip install -e ".[dev]"
copy .env.example .env            # edite: GROQ_API_KEY e SEC_USER_AGENT (seu e-mail real)
docker compose up -d qdrant postgres
```

### Pipeline completo

```bash
# 1. Ingestão dos 3 cases (SEC + CVM + BACEN + news) — ~800 docs, 30-60 min
python scripts/ingest_cases.py --case all --since 2024-01-01 --max 25

# 2. Indexação (BM25 + Qdrant)
python scripts/index.py --fresh

# 3. Eval harness
python -m legacy_retrieval.eval.run --k 10 --output eval/results.json

# 4. Consulta ad-hoc
python scripts/query.py "What was NVIDIA's Data Center revenue last quarter?"

# 5. API
uvicorn legacy_retrieval.api.main:app --port 8000
```

### Resolução dos cases

```bash
python scripts/run_case_a.py   # capex hyperscalers vs demanda NVIDIA
python scripts/run_case_b.py   # guidance vs entrega, sentimento, market share BACEN
python scripts/run_case_c.py   # backtest: aceleração de RPO vs retorno pós-earnings
```

Os Cases A e B são resolvidos **apenas com perguntas à plataforma genérica** — nenhuma lógica específica de empresa. O Case C usa a base indexada como fonte para extração estruturada (RPO) e cruza com preços.

## Eval Harness (eval-driven development)

Gold set: [`eval/questions.jsonl`](eval/questions.jsonl) — 14 perguntas **verificadas manualmente contra documentos reais**, cobrindo: documento único, multi-documento, multi-período, dado estruturado e 2 não-respondíveis.

Métricas: Recall@10, Precision@10, MRR (nível de documento), taxa de resposta correta e taxa de recusa correta.

### Resultados (base real: 822 documentos, 63.562 chunks)

| Métrica | Baseline¹ | Final² |
|---------|-----------|--------|
| Recall@10 (documento) | 0.57 | **0.96** |
| MRR | 0.52 | **0.82** |
| Precision@10 | 0.11 | 0.16³ |
| Taxa de resposta (LLM 70B) | 0.67 | **0.92** |
| Taxa de recusa correta | 1.00 | **1.00** |

¹ Embeddings/reranker apenas em inglês (all-MiniLM + ms-marco), top-k 20, métricas pré-rerank.
² Após diagnóstico pelo eval: embeddings `multilingual-e5-small`, reranker mmarco multilíngue, pool de candidatos 50, métricas no sistema completo (híbrido + rerank), rótulos com grupos de documentos alternativos (8-K e 10-Q do mesmo dia contêm o mesmo fato).
³ Precision@10 é estruturalmente baixa: cada pergunta tem 1-4 documentos relevantes e o corte é fixo em 10.

Observações honestas:
- A única falha de recall restante é a q03 (capex anual de duas empresas na mesma pergunta — os 10-K gigantes competem com dezenas de relatórios trimestrais). Query decomposition resolveria; ficou como melhoria futura.
- A **taxa de resposta depende do LLM**: 92% com Llama 3.3 70B; 58% com Llama 3.1 8B (recusa em excesso). As métricas de retrieval independem do modelo de geração.
- A recusa tem duas camadas: gate por score do reranker (barato) + recusa semântica do LLM grounded. Só o gate não basta — uma pergunta sobre a Apple (fora da base) atinge score 3.96 em trechos de "fiscal 2024 revenue" de outras empresas.

O ciclo baseline → diagnóstico → melhoria é reproduzível: cada mudança de retrieval foi validada pelo harness antes de entrar.

## Resultados dos cases

### Case C — RPO aceleração vs retorno (dados reais)
- 43 eventos trimestrais extraídos de 7 empresas (extração calibrada nos press releases; guidance em faixa é filtrado)
- Horário de divulgação real via `acceptanceDateTime` da SEC (pre/post market)
- **Resultado**: aceleração positiva → 67% de pregões seguintes positivos (média +0,75%); desaceleração → 27% (média -0,19%). Correlação agregada fraca (Pearson -0,08) — amostra pequena, sem significância estatística.

### Case B — market share real (IF.data BACEN, data-base 2026-03)
- Carteira total do sistema: R$ 7,26 tri
- Nubank: 2,03% (Nu Pagamentos + Nu Financeira) | Itaú: 11,6% | Bradesco: 10,0%

## Limitações conhecidas

- Extração de RPO cobre 7 das 15 empresas sugeridas (as demais divulgam só em tabelas de 10-Q, que o parser de texto não estrutura)
- Sem filtro temporal explícito no retrieval — perguntas multi-período dependem do reranker distinguir datas
- Transcripts de earnings calls não têm fonte gratuita estável (usamos press releases + apresentações)
- BM25 é reconstruído em memória a cada indexação (aceitável até ~100k chunks; depois, migrar para Tantivy/Elasticsearch)
- `IfDataCadastro` (nomes de instituições) estava fora do ar; nomes vêm de mapa estático de CNPJs públicos — valores vêm 100% da API

## Melhorias futuras

- Parser de tabelas (Docling) para RPO/capex em 10-Q
- Filtros de metadados no retrieval (empresa, período) + query rewriting
- Agendamento de ingestão (cron) para base viva
- Interface web estilo NotebookLM

## Estrutura

```
src/legacy_retrieval/
├── ingestion/     # sec_edgar, cvm, bacen, news, ir_scraper (config-driven)
├── parsing/       # pdf, html
├── indexing/      # chunker, embeddings, indexer (BM25 + Qdrant)
├── retrieval/     # hybrid (RRF), reranker, evidence
├── generation/    # llm (Groq/OpenAI/Ollama/extractivo) — grounded + recusa
├── structured/    # rpo, prices, market_share, backtest
├── eval/          # metrics, harness, run
└── api/           # FastAPI
scripts/           # ingest_cases, index, query, run_case_{a,b,c}, prod_test
eval/questions.jsonl  # gold set
```

## Testes

```bash
pytest tests/ -v          # 15 testes (métricas, chunker, RRF, RPO, pipeline e2e)
ruff check src tests scripts
```

> **Nota (Windows)**: se o import do Qdrant falhar com "política de Controle de Aplicativo bloqueou este arquivo", fixe `grpcio==1.76.0` — o Smart App Control bloqueia a DLL de versões muito recentes.
