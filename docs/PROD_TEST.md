# Testes em modo produção — Case A

Este é o **fluxo padrão de testes** do projeto. Não usa dados demo — busca documentos reais da SEC e indexa no Qdrant.

## O que a IA faz aqui?

| Etapa | Tecnologia | Função | Custo |
|-------|-----------|--------|-------|
| Entender a pergunta (semântica) | Embeddings locais (MiniLM) | Converte pergunta e chunks em vetores | Grátis |
| Ranquear relevância | Cross-encoder local | Compara pergunta × trecho | Grátis |
| Busca por palavra-chave | BM25 | "capex", "capital expenditure" | Grátis |
| Sintetizar resposta | LLM (opcional) | Resume evidências com citações | Grátis (local/ollama) ou pago (OpenAI) |

**A IA não "sabe" sobre empresas.** Ela só:
1. Ajuda a **encontrar** os trechos certos (embeddings + reranker)
2. Opcionalmente **escreve** a resposta a partir desses trechos (LLM)

## Opções gratuitas para testar

### Opção 1 — 100% grátis (recomendada para começar)

```env
EMBEDDING_PROVIDER=local
LLM_PROVIDER=local
```

Resposta extractiva (copia trechos relevantes). Retrieval completo funciona.

### Opção 2 — LLM grátis com Ollama

1. Instale [Ollama](https://ollama.com)
2. `ollama pull llama3.2`
3. No `.env`:
   ```env
   LLM_PROVIDER=ollama
   OLLAMA_MODEL=llama3.2
   ```

### Opção 3 — OpenAI (pago, melhor qualidade de texto)

```env
OPENAI_API_KEY=sk-...
LLM_PROVIDER=openai
```

## Pré-requisitos

- Python 3.11+
- Docker Desktop
- `.env` com `SEC_USER_AGENT` contendo seu email real (exigência da SEC)

```bash
copy .env.example .env
# Edite SEC_USER_AGENT com seu email
```

## Fluxo completo (um comando)

```bash
pip install -e ".[dev]"
python scripts/prod_test.py full
```

Isso executa:
1. `docker compose up -d` (Qdrant + Postgres)
2. Ingestão SEC + news para MSFT, AMZN, GOOGL, META, NVDA, ORCL, CRWV
3. Indexação no Qdrant (collection fresh)
4. Smoke test com 4 perguntas do Case A

## Passo a passo manual

```bash
# 1. Infraestrutura
docker compose up -d qdrant postgres

# 2. Ingestão real (Case A)
python scripts/ingest_case_a.py --since 2023-01-01 --max 10

# 3. Indexação
python scripts/index.py --fresh

# 4. Testar perguntas
python scripts/prod_test.py smoke

# 5. API (opcional)
uvicorn legacy_retrieval.api.main:app --reload --port 8000
python scripts/prod_test.py smoke --api
```

## De onde vêm os dados (Case A)?

### Camada 1 — SEC EDGAR (principal, grátis, oficial)

Filings 10-K, 10-Q, 8-K. A maioria dos earnings releases US acaba aqui.
**Não precisa scraper por site** para o núcleo do Case A.

### Camada 2 — Sites de RI (scraper configurável)

Apresentações, transcripts e releases que às vezes aparecem no site antes da SEC.
Config em [`config/ir_sites.yaml`](../config/ir_sites.yaml) — um bloco por empresa, sem parser hardcoded.

```bash
python scripts/ingest_case_a.py   # inclui SEC + RI + news
```

### Camada 3 — Notícias RSS (Yahoo Finance, grátis)

Headlines e artigos recentes sobre capex/AI.

### Existe um serviço que faz tudo?

| Serviço | O que cobre | Custo | Recomendação |
|---------|-------------|-------|--------------|
| **SEC EDGAR** | Filings oficiais US | Grátis | ✅ Já integrado |
| **sec-api.io** | Busca avançada na SEC | Pago | Opcional depois |
| **Financial Modeling Prep** | Earnings, transcripts, news | Freemium | Boa alternativa paga |
| **Polygon.io / Benzinga** | News + market data | Pago | Para news em escala |
| **Bloomberg / Refinitiv** | Tudo | Enterprise | Fora do escopo MVP |
| **Scraper próprio (RI)** | PDFs/apresentações por site | Grátis | ✅ Implementado |

**Conclusão:** não existe um serviço gratuito único que cubra sites de RI + SEC + news.
A estratégia correta é **SEC como base** + **scraper configurável por empresa** + **RSS de notícias**.

Para adicionar uma empresa nova: edite `config/ir_sites.yaml` (URLs + padrões de link).

| Empresa | Fonte |
|---------|-------|
| MSFT, AMZN, GOOGL, META, NVDA, ORCL, CRWV | SEC EDGAR + site de RI + RSS |

## Deploy completo com API no Docker

```bash
docker compose up -d --build
# API em http://localhost:8000
# Docs em http://localhost:8000/docs
```

**Nota:** a API no Docker precisa que os dados já estejam indexados em `./data`. Rode `prod_test.py full` antes, ou monte um job de ingestão.

## Entender o pipeline

```bash
python scripts/prod_test.py explain
```
