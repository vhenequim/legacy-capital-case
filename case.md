# Case: Sistema de Retrieval para Research de Equities (Legacy Capital)

## Objetivo

Construir uma plataforma de Retrieval-Augmented Generation (RAG) voltada para pesquisa em equities.

A prioridade **não é a interface**, mas sim um backend sólido capaz de:

- ingerir documentos automaticamente das fontes originais;
- indexar centenas/milhares de documentos;
- responder perguntas utilizando exclusivamente a base indexada;
- citar todas as fontes utilizadas;
- nunca alucinar respostas.

O sistema deve funcionar como um NotebookLM, porém com ingestão automática e escalabilidade.

---

# Requisitos Obrigatórios

## 1. Base ligada (Connected Knowledge Base)

A base **não pode depender de upload manual** de PDFs.

O sistema deve possuir uma camada de ingestão automática capaz de buscar documentos diretamente nas fontes oficiais.

Exemplos:

- Sites de RI (Investor Relations)
- CVM
- SEC
- APIs públicas
- Banco Central
- ANP

Sempre que um novo documento surgir, deve existir um processo reproduzível para adicioná-lo à base.

---

## 2. Escala

A solução deve suportar:

- 500+ documentos inicialmente
- crescimento contínuo
- documentos grandes
- documentos pequenos
- diferentes formatos

---

## 3. Dados heterogêneos

O sistema deve lidar com:

### Texto

- PDFs
- Earnings Releases
- Earnings Calls
- Notícias

### Dados estruturados

- CSV
- tabelas
- séries temporais
- APIs públicas (BACEN, ANP etc.)

---

## 4. RAG

Toda resposta deve obedecer duas regras:

### Sempre citar a fonte

Cada resposta deve informar:

- documento
- trecho utilizado

### Nunca alucinar

Se a informação não existir na base:

Responder explicitamente:

> Não encontrei essa informação na base.

Jamais inventar.

---

# Arquitetura Esperada

A implementação deve ser genérica.

Não desenvolver algo específico apenas para os exemplos abaixo.

Os exemplos servem apenas para validar a arquitetura.

A solução deve possuir aproximadamente os seguintes módulos:

```
Ingestion

↓

Parsing

↓

Chunking

↓

Embeddings

↓

Vector Database

↓

Hybrid Retrieval

↓

LLM

↓

Resposta com citações
```

---

# Case A

## Capex de IA vs Receita da NVIDIA

Objetivo:

Relacionar:

- Capex das hyperscalers
- Receita da NVIDIA

Empresas relevantes:

- Microsoft
- Amazon
- Google
- Meta
- Oracle
- CoreWeave
- Nebius

O sistema deve conseguir responder perguntas como:

- Qual o capex agregado projetado?
- O que a NVIDIA comentou sobre demanda?
- Existe relação entre ambos?

A informação encontra-se espalhada em:

- earnings releases
- conference calls
- notícias
- tabelas financeiras

---

# Case B

## Bancos brasileiros

Empresas:

- Itaú
- Bradesco
- Santander Brasil
- Banco do Brasil
- Nubank
- outros

### Parte 1

Promessa vs entrega

Encontrar um guidance em um trimestre.

Depois localizar o resultado real meses depois.

Exemplo:

> O Bradesco afirmou que reduziria provisões.

O sistema deve verificar se isso realmente ocorreu.

---

### Parte 2

Mudança de sentimento

Comparar o discurso dos bancos ao longo do tempo.

Exemplo:

- mais otimista
- mais pessimista
- mais cauteloso

Comparação trimestre a trimestre.

---

### Parte 3

Estratégia vs Market Share

Cruzar:

Documentos do banco

com

Dados do BACEN

Usar:

- IF.data
- SCR.data

Calcular:

```
Market Share

=

Carteira do Banco

/

Carteira Total do Sistema
```

Depois comparar com a estratégia declarada.

---

# Case C

## Backtest

Objetivo:

Investigar se aceleração do RPO antecipa a reação das ações.

Empresas sugeridas:

- Salesforce
- ServiceNow
- SAP
- HubSpot
- Cloudflare
- Datadog
- Snowflake
- Akamai
- Palo Alto
- CrowdStrike
- Okta
- Atlassian
- Monday
- GitLab
- Zscaler

Processo:

Extrair:

- RPO trimestral

Calcular:

```
YoY Growth
```

Depois:

```
Acceleration

=

Growth atual

-

Growth trimestre anterior
```

Cruzar com:

Retorno da ação no primeiro pregão após divulgação.

Considerar:

- divulgação antes da abertura
- divulgação após fechamento

---

# Avaliação (Eval Harness)

Antes de otimizar retrieval, construir um sistema de avaliação.

Criar aproximadamente 10 perguntas.

Cobrir obrigatoriamente:

## Documento único

Resposta localizada em apenas um documento.

---

## Multi-documento

Resposta exige múltiplas fontes.

---

## Multi-período

Comparação entre períodos diferentes.

---

## Não respondível

A informação não existe.

O sistema deve recusar responder.

---

## Métricas

Implementar pelo menos:

- Recall@k
- Precision@k
- MRR

Além disso:

- taxa de respostas corretas
- taxa de recusas corretas

---

# Entregáveis

## 1

Repositório Git

Com histórico de commits.

---

## 2

Pipeline de ingestão automática.

---

## 3

Eval Harness executável.

---

## 4

README contendo:

- como executar
- origem dos dados
- arquitetura
- chunking
- embeddings
- retrieval
- tratamento de dados estruturados
- resultados do eval
- limitações
- melhorias futuras

---

## 5

Resolver os cases apresentados.

Idealmente:

- A
- B
- C

(O PDF menciona "um dos cases", mas anteriormente afirma que os três devem ser resolvidos. Vale confirmar essa inconsistência.)

---

## 6

Apresentação

Deve explicar:

- arquitetura
- aprendizados sobre RAG
- decisões tomadas
- vantagens
- limitações
- resultados do eval
- resolução do(s) case(s)
- escalabilidade

---

# Critérios de Avaliação

| Critério | Peso |
|----------|------|
| Qualidade do Retrieval | 25% |
| Eval Harness | 25% |
| Resolução dos Cases | 15% |
| Apresentação | 15% |
| Ingestão Automática e Dados Heterogêneos | 10% |
| Qualidade do Código | 10% |

---

# Objetivo para o Claude Code

Desenvolver uma solução completa, modular e pronta para produção seguindo boas práticas de engenharia.

Priorizar:

- arquitetura limpa
- tipagem
- testes
- modularização
- documentação
- escalabilidade
- ingestão automática
- retrieval híbrido (BM25 + Vetorial)
- reranking
- citações precisas
- suporte a documentos textuais e dados estruturados

Evitar hardcodes específicos para os exemplos.

A arquitetura deve ser genérica o suficiente para responder qualquer pergunta cuja resposta exista na base.