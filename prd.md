# Legacy Capital AI Retrieval System

## Contexto

Este projeto não consiste em construir apenas um chatbot ou uma aplicação de RAG tradicional. O objetivo é desenvolver a fundação de uma plataforma de pesquisa para uma equipe de equities.

O trabalho diário de um analista consiste em responder perguntas que exigem reunir informações espalhadas por centenas ou milhares de documentos produzidos ao longo de vários anos.

Hoje essas informações estão distribuídas entre:

- Earnings Releases
- Earnings Call Transcripts
- apresentações para investidores
- notícias
- filings na SEC
- documentos enviados à CVM
- bases públicas como BACEN e ANP

Cada documento responde apenas uma pequena parte de uma pergunta.

O verdadeiro desafio não é ler um documento, mas descobrir rapidamente quais documentos relevantes existem e conectá-los para responder perguntas complexas.

A plataforma deve automatizar exatamente esse processo.

---

# O produto que deve ser construído

Imagine algo semelhante ao NotebookLM.

A diferença é que:

- os documentos não são enviados manualmente;
- a base é alimentada automaticamente;
- o sistema suporta centenas ou milhares de documentos;
- também entende dados estruturados;
- toda resposta possui rastreabilidade completa.

O objetivo principal não é gerar texto bonito.

O objetivo é encontrar exatamente os documentos corretos.

O retrieval é o coração do projeto.

---

# Filosofia do sistema

A IA não deve responder usando conhecimento próprio.

Toda resposta deve ser consequência direta da base indexada.

Em outras palavras:

Pergunta

↓

Retriever encontra evidências

↓

LLM sintetiza apenas essas evidências

↓

Resposta com citações

Caso nenhuma evidência exista, o sistema deve responder que não sabe.

Nunca inventar.

---

# Escopo da plataforma

O projeto deve ser pensado como uma plataforma reutilizável.

Não desenvolver lógica específica para responder apenas aos exemplos fornecidos.

Os exemplos existem apenas para provar que a arquitetura realmente funciona.

Idealmente, qualquer nova empresa ou nova fonte de documentos deveria poder ser adicionada apenas configurando uma nova rotina de ingestão.

---

# Camada de ingestão

A ingestão é provavelmente o aspecto mais importante deste projeto.

Não queremos uma interface onde alguém faz upload de PDFs.

Queremos um sistema conectado às fontes oficiais.

Sempre que novos documentos forem publicados, deve existir um processo reproduzível capaz de buscá-los automaticamente, tratá-los, indexá-los e disponibilizá-los para consulta.

Isso transforma a base em um sistema vivo.

---

# Dados esperados

O sistema precisa trabalhar simultaneamente com informações de naturezas diferentes.

## Documentos textuais

- PDFs
- Conference Calls
- Earnings Releases
- Notícias
- Press Releases

## Dados estruturados

- séries temporais
- CSV
- APIs públicas
- tabelas financeiras
- indicadores econômicos

Esses dois mundos devem conversar naturalmente durante o retrieval.

---

# Como o sistema será avaliado

O principal critério não é qualidade da resposta.

Também não é a qualidade do LLM.

O principal critério é:

"o sistema encontrou os documentos corretos?"

Um LLM excelente produz respostas ruins quando recebe documentos errados.

Portanto praticamente toda a arquitetura deve priorizar qualidade de recuperação.

---

# Os três casos de uso

Os exemplos apresentados pela Legacy não são problemas independentes.

Todos medem exatamente a mesma habilidade.

Recuperar informações espalhadas em diferentes documentos, períodos e fontes.

Cada case apenas enfatiza uma dificuldade diferente.

---

# Caso A — NVIDIA e Capex

Este caso mede a capacidade do sistema de consolidar informações distribuídas entre diversas empresas.

Nenhuma empresa possui a resposta completa.

A Microsoft informa parte do investimento.

A Amazon informa outra.

A Meta informa outra.

A NVIDIA comenta a demanda.

O sistema precisa encontrar todos esses fragmentos e produzir uma visão consolidada.

O desafio não está em calcular números.

Está em descobrir onde cada pedaço da informação está escondido.

---

# Caso B — Bancos brasileiros

Aqui o desafio muda.

Agora o sistema precisa conectar documentos separados pelo tempo.

Uma informação é dita hoje.

A confirmação (ou não) aparece meses depois.

Isso exige recuperação temporal.

Além disso, parte das respostas depende de cruzar documentos textuais com bases estruturadas do Banco Central.

O sistema deixa de ser apenas um buscador de PDFs.

Ele passa a integrar diferentes tipos de informação.

---

# Caso C — Backtest

O terceiro caso introduz análises quantitativas.

O sistema deve extrair automaticamente séries históricas dos documentos.

Depois calcular indicadores derivados.

Por fim relacionar esses indicadores com preços de mercado.

Neste caso o retrieval não termina na recuperação dos documentos.

Ele serve de etapa inicial para uma análise estatística.

---

# O que caracteriza uma boa solução

Uma boa solução provavelmente possuirá:

- pipeline de ingestão
- parser de documentos
- chunking robusto
- embeddings
- banco vetorial
- busca híbrida
- reranking
- geração de respostas baseada apenas nas evidências
- citações
- sistema de avaliação automatizado

Mais importante que escolher a melhor tecnologia é justificar as decisões tomadas.

---

# O Eval Harness

O projeto deve ser desenvolvido orientado por avaliação.

Antes de otimizar retrieval, deve existir um conjunto de perguntas cuja resposta correta já seja conhecida.

Esse conjunto servirá para medir objetivamente se alterações na arquitetura realmente melhoram o sistema.

Sem isso, não é possível afirmar que o retrieval evoluiu.

---

# Objetivo final

Ao final do projeto deve existir uma plataforma genérica de pesquisa documental capaz de responder perguntas complexas sobre empresas utilizando exclusivamente documentos oficiais e dados públicos, sempre apresentando evidências e recusando responder quando não houver informação suficiente.

Os três casos apresentados pela Legacy devem funcionar naturalmente sobre essa plataforma, sem implementação específica para cada um deles.