# Legacy Capital AI Retrieval System

Plataforma de pesquisa documental para analistas de equities. O foco é **retrieval de alta qualidade** com respostas grounded em evidências indexadas — nunca alucinação.

## Arquitetura

```
Fontes (SEC, CVM, BACEN, RI, News)
    → Ingestão automática
    → Parsing (PDF/HTML)
    → Chunking + metadados
    → Embeddings + BM25 + Qdrant
    → Busca híbrida (RRF) + Reranking
    → LLM grounded + citações
```

### Stack

| Componente | Tecnologia |
|------------|------------|
| API | FastAPI |
| Embeddings | sentence-transformers (local) ou OpenAI |
| Vector DB | Qdrant |
| BM25 | rank_bm25 |
| Reranking | cross-encoder/ms-marco-MiniLM-L-6-v2 |
| LLM | OpenAI (opcional) ou modo extractivo local |
| Dados estruturados | PostgreSQL + pandas |

## Setup

### Pré-requisitos

- Python 3.11+
- Docker (para Qdrant e PostgreSQL)

### Instalação

```bash
# Clonar e entrar no diretório
cd legacy_case

# Criar ambiente virtual
python -m venv .venv
.venv\Scripts\activate   # Windows
# source .venv/bin/activate  # Linux/Mac

# Instalar dependências
pip install -e ".[dev]"

# Configurar variáveis de ambiente
copy .env.example .env

# Subir infraestrutura
docker compose up -d
```

### Dados de demonstração (offline, legado)

Para testes rápidos sem internet (não é o fluxo padrão):

```bash
python scripts/seed_demo_data.py
python scripts/index.py
```

### Testes em modo produção — Case A (padrão)

Fluxo recomendado com **dados reais da SEC**:

```bash
copy .env.example .env
# Edite SEC_USER_AGENT com seu email real

docker compose up -d qdrant postgres
python scripts/prod_test.py full
```

Guia completo: [docs/PROD_TEST.md](docs/PROD_TEST.md)

## Uso

### Ingestão automática

```bash
python scripts/ingest.py --source sec --company MSFT --since 2023-01-01

# BACEN (IF.data + SCR)
python scripts/ingest.py --source bacen

# Notícias (RSS)
python scripts/ingest.py --source news --company NVDA

# CVM / RI (usa cache local ou arquivos ingeridos manualmente)
python scripts/ingest.py --source cvm --company BBDC4
```

### Indexação

```bash
python scripts/index.py
```

### Consulta

```bash
python scripts/query.py "What is Microsoft capex guidance for 2025?"
```

### API

```bash
uvicorn legacy_retrieval.api.main:app --reload --port 8000
```

Endpoints:
- `GET /health`
- `POST /query` — `{"question": "...", "top_k": 10}`
- `GET /market-share/{institution}`

### Eval Harness

```bash
python -m legacy_retrieval.eval.run --k 10
python -m legacy_retrieval.eval.run --k 10 --output eval/results.json
```

### Validação dos Cases

```bash
python scripts/validate_cases.py
```

## Origem dos dados

| Fonte | Tipo | Cases |
|-------|------|-------|
| SEC EDGAR | Filings 10-K, 10-Q, 8-K | A, C |
| CVM | Documentos periódicos BR | B |
| BACEN IF.data / SCR | Dados estruturados de crédito | B |
| Investor Relations | Earnings releases, apresentações | A, B, C |
| RSS/News | Notícias financeiras | A |

## Decisões de design

### Chunking

- Tamanho: 512 tokens (palavras), overlap 64
- Preserva marcadores de página `[Page N]` de PDFs
- Metadados: empresa, tipo, data, URL

### Embeddings

- **Local (padrão):** `all-MiniLM-L6-v2` — sem custo, funciona offline
- **OpenAI:** `text-embedding-3-small` — melhor qualidade semântica

### Retrieval

1. BM25 (termos exatos: capex, RPO, provisões)
2. Busca vetorial (similaridade semântica)
3. Fusão RRF (Reciprocal Rank Fusion, k=60)
4. Reranking cross-encoder nos top-20 → top-10

### Geração

- Prompt grounded: responde **apenas** com evidências
- Citações: `[Evidence N]` com doc_id, empresa, trecho
- Recusa quando score de evidência é insuficiente

### Dados estruturados

- BACEN SCR → cálculo de market share
- Extração regex de RPO/capex de filings
- Backtest engine: YoY growth, acceleration, retorno pós-earnings

## Resultados do Eval (demo)

Com dados de demonstração (`seed_demo_data` + `index`):

| Métrica | Valor (demo) |
|---------|----------------|
| Recall@10 | 1.00 |
| Precision@10 | 0.14 |
| MRR | 0.80 |
| Taxa de resposta correta | 89% |
| Taxa de recusa correta | 100% |

Execute `python -m legacy_retrieval.eval.run` após seed + index para métricas atualizadas.

## Limitações

- Sites de RI têm layouts heterogêneos — fetchers usam cache local configurável
- Parsing de tabelas em PDFs financeiros pode perder estrutura
- CVM API requer integração adicional para produção
- Backtest usa dados sintéticos no demo; produção requer preços de mercado reais
- Embeddings locais são menos precisos que modelos maiores para português

## Melhorias futuras

- [ ] Parser de tabelas dedicado (Docling/unstructured)
- [ ] Agendamento de ingestão (Celery/cron)
- [ ] PGVector como alternativa unificada
- [ ] Fine-tuning de reranker em queries financeiras
- [ ] Interface web (NotebookLM-style)
- [ ] Integração ANP e mais APIs públicas

## Estrutura do projeto

```
legacy_case/
├── src/legacy_retrieval/   # Código principal
├── scripts/                # CLI: ingest, index, query, seed, validate
├── eval/questions.jsonl    # Gold dataset (~10 perguntas)
├── tests/                  # pytest
├── data/                   # Dados (gitignored)
├── docker-compose.yml
├── PLANO.md
└── docs/PRESENTACAO.md
```

## Testes

```bash
pytest tests/ -v
ruff check src tests scripts
```
