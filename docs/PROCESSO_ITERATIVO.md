# Processo de melhoria iterativa (diário de bordo)

Este documento registra **como** o retrieval deste projeto evolui: cada mudança nasce de um diagnóstico medido pelo eval harness, entra isolada, e é aceita ou revertida pelos números — nunca por impressão. Vale mais que os números finais: é o processo que garante que eles continuam verdadeiros quando a base cresce.

## O ciclo

```
medir (eval) → diagnosticar por pergunta → mudar UMA coisa → medir de novo → registrar aqui
```

## Regras do processo

1. **Rótulos gold só mudam com justificativa documentada.** Corrigir um rótulo errado é manutenção; ajustar rótulos para subir métrica é fraude de eval. Toda mudança de rótulo fica registrada no `notes` da pergunta e no histórico do git.
2. **Toda falha é triada em uma de três categorias** antes de qualquer correção:
   - *Erro de rótulo* — o documento esperado está errado ou falta uma alternativa legítima (ex.: 8-K e 10-Q do mesmo dia com o mesmo fato). Corrige-se o rótulo.
   - *Lacuna de retrieval* — o sistema não encontra o documento certo. Vira melhoria de arquitetura (e só entra se as métricas melhorarem).
   - *Lacuna de geração* — o retrieval acerta e o LLM erra a síntese ou recusa indevidamente. Vira ajuste de prompt/modelo.
3. **Métricas de retrieval são separadas das de geração.** Recall/Precision/MRR não dependem de LLM: rodam grátis, determinísticas, em `--retrieval-only` — é o modo de iteração e o gate do CI. Taxa de resposta/recusa dependem do modelo de geração e são reportadas com o modelo identificado.
4. **Toda melhoria aceita ganha proteção contra regressão** — um teste unitário e/ou presença no smoke eval do CI.
5. **Número bom demais é suspeito.** Recall 1.00 não foi celebrado; foi tratado como sinal de gold set saturado (ver iteração 6).

## Histórico de iterações

| # | Mudança | Recall@10 | MRR | O que o eval revelou |
|---|---------|-----------|-----|----------------------|
| 1 | Baseline (14 perguntas, modelos EN-only, pool 20) | 0.57 | 0.52 | Ponto de partida medido antes de otimizar |
| 2 | Embeddings e reranker multilíngues, pool 50, threshold recalibrado | 0.79 | 0.73 | Perguntas em PT recusavam silenciosamente: os modelos eram EN-only numa base bilíngue |
| 3 | Métricas no sistema real (pós-rerank, dedupe por documento) + correção de 1 rótulo | 0.83 | 0.79 | O harness media o ranking pré-rerank — o sistema errado |
| 4 | Grupos de documentos alternativos nos rótulos | 0.96 | 0.82 | Exigir o 8-K E o 10-Q do mesmo dia media semântica errada ("necessários" vs "equivalentes") |
| 5 | Query decomposition multi-entidade | 1.00 | 0.875 | Perguntas comparando N empresas diluíam o top-k; sub-query por entidade + intercalação |
| 6 | Smoke eval como gate no CI | — | — | Retrieval sem LLM roda de graça no Actions; regressão agora quebra o build |
| 7 | **Expansão do gold set: 14 → 42 perguntas** | **0.94** | **0.75** | A queda é o resultado esperado e desejado — ver abaixo |

## Iteração 7 — por que expandimos o gold set (e por que o recall caiu)

Recall 1.00 em 14 perguntas não significava "retrieval perfeito"; significava que **o gold set tinha ficado fácil para o sistema atual**. Três problemas de um conjunto pequeno:

1. **Saturação** — no teto, o eval para de discriminar: qualquer mudança parece neutra e o ciclo de melhoria morre.
2. **Variância** — com 12 respondíveis, uma pergunta vale ~8 pontos de recall. Diferenças reais entre duas arquiteturas somem no ruído.
3. **Overfitting de decisões** — modelos, thresholds e a própria decomposição foram escolhidos olhando essas 14 perguntas. Elas viraram, na prática, um *dev set*. Perguntas novas funcionam como *test set*: medem generalização, não memorização das escolhas.

Método da expansão: os fatos foram minerados do corpus real (série de RPO extraída no Case C, greps por guidance/capex nos filings, metadados IPE da CVM) e **cada rótulo foi verificado contra o conteúdo do documento antes de entrar**. 28 perguntas novas: 10 single-doc EN, 6 multi-período, 4 multi-documento (testam a decomposição, incluindo uma em PT), 6 sobre docs CVM em PT, 2 estruturadas BACEN e 4 não-respondíveis.

Resultado: recall caiu de 1.00 para 0.94 — e isso é o eval funcionando. As perguntas novas encontraram **duas falhas reais** que as 14 originais não enxergavam:

- **q27 (Datadog)** e **q28 (HubSpot)**: o RPO dessas empresas só existe nas notas contábeis dos 10-Q/10-K (não nos press releases). O reranker prefere press releases de *outras empresas* que mencionam "remaining performance obligation" com destaque a filings da empresa certa onde o termo está enterrado — prioriza tópico sobre entidade.
- Triagem: lacuna de retrieval (não é rótulo — os documentos recuperados da empresa certa não contêm o fato). Fica registrada como falha conhecida.
- Um erro de rótulo também apareceu e foi corrigido com justificativa: o 10-Q da Oracle de 11/12/2025 é alternativa legítima ao 8-K de 10/12/2025 (q20).

## Backlog priorizado (cada item nasce de um diagnóstico)

| Prioridade | Melhoria | Diagnóstico que a motiva |
|------------|----------|--------------------------|
| 1 | Boost/filtro por entidade no retrieval (empresa detectada na pergunta → priorizar chunks daquela empresa) | q27/q28: reranker escolhe tópico certo na empresa errada |
| 2 | Eval de resposta com LLM-as-judge contra fatos gold | Hoje medimos "achou o documento" e "recusou certo"; um erro de síntese (ex.: citar a entidade individual em vez do grupo no market share) só foi pego manualmente |
| 3 | Parser de tabelas (Docling) para notas de 10-Q/10-K | RPO de 8 das 15 empresas do Case C está em tabelas que o parser de texto não estrutura |
| 4 | Ingestão agendada (cron) | A ingestão já é idempotente; falta só o agendamento para a base ficar viva |
| 5 | Expandir o smoke do CI com as categorias novas | O gate atual cobre 6 perguntas; as falhas q27/q28 deveriam virar casos de regressão quando resolvidas |

## Notas operacionais

- **Cota de LLM**: o free tier do Groq (100k tokens/dia no 70B) não sustenta evals frequentes com geração. Por isso: `--retrieval-only` para iterar (grátis), eval completo com LLM apenas em marcos. Modelos menores (8B) distorcem a taxa de resposta (58% vs 100% do 70B) — nunca comparar taxas de resposta entre modelos diferentes.
- **Windows + Smart App Control**: DLLs de versões muito novas de `grpcio` e `scikit-learn` são bloqueadas ("política de Controle de Aplicativo"). Pins no `pyproject.toml` documentam os limites.
