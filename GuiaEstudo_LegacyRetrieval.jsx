import React, { useState } from "react";

/**
 * Guia de Estudo — Legacy Capital AI Retrieval System
 * -----------------------------------------------------
 * Guia interativo (tema dark) que documenta a plataforma de RAG para research
 * de equities: os conceitos por trás de cada decisão e cada componente do
 * código. Todo número e escolha aqui vem do próprio repositório.
 *
 * Single-file. Sem dependências além do React. Estilos inline (theme object)
 * para renderizar de forma consistente em qualquer ambiente.
 */

// ----------------------------------------------------------------------------
// TEMA
// ----------------------------------------------------------------------------
const T = {
  bg: "#0b0d10",
  panel: "#14181d",
  panel2: "#1b2027",
  card: "#161b21",
  cardHover: "#1c232b",
  border: "#252c35",
  borderSoft: "#1f262e",
  text: "#e7ecf2",
  textDim: "#9aa6b2",
  textFaint: "#6b7681",
  accent: "#5aa9ff",
  accent2: "#7c5cff",
  green: "#3ddc97",
  amber: "#f6b53d",
  red: "#ff6b6b",
  mono: "ui-monospace, SFMono-Regular, 'SF Mono', Menlo, Consolas, monospace",
  sans: "-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif",
};

// pequenas helpers de estilo
const chip = (color) => ({
  display: "inline-block",
  padding: "2px 9px",
  borderRadius: 999,
  fontSize: 11.5,
  fontWeight: 600,
  letterSpacing: 0.2,
  color,
  background: `${color}1a`,
  border: `1px solid ${color}33`,
});

const Code = ({ children }) => (
  <code
    style={{
      fontFamily: T.mono,
      fontSize: "0.88em",
      background: "#0e1216",
      border: `1px solid ${T.borderSoft}`,
      borderRadius: 5,
      padding: "1px 6px",
      color: "#c8d3df",
    }}
  >
    {children}
  </code>
);

const Block = ({ children }) => (
  <pre
    style={{
      fontFamily: T.mono,
      fontSize: 12.5,
      lineHeight: 1.6,
      background: "#0e1216",
      border: `1px solid ${T.borderSoft}`,
      borderRadius: 8,
      padding: "12px 14px",
      overflowX: "auto",
      color: "#c8d3df",
      margin: "10px 0",
      whiteSpace: "pre",
    }}
  >
    {children}
  </pre>
);

const ulStyle = {
  margin: "8px 0",
  paddingLeft: 20,
  display: "flex",
  flexDirection: "column",
  gap: 6,
  color: T.textDim,
};

// ----------------------------------------------------------------------------
// DADOS — CONCEITOS
// ----------------------------------------------------------------------------
const CONCEPTS = [
  {
    id: "grounded",
    tag: "Fundamento",
    tagColor: T.accent,
    title: "RAG grounded com recusa",
    summary:
      "O LLM nunca responde com conhecimento próprio — só sintetiza evidências recuperadas. Sem evidência, recusa.",
    body: (
      <>
        <p>
          RAG (<b>Retrieval-Augmented Generation</b>) inverte a lógica de um chatbot comum. Em vez de o
          modelo responder pela sua memória de treino, o fluxo é:
        </p>
        <Block>{`pergunta → retriever busca evidências → LLM sintetiza SÓ essas evidências → resposta + citações`}</Block>
        <p>
          A filosofia do projeto é radical: <i>"A IA não deve responder usando conhecimento próprio.
          Toda resposta deve ser consequência direta da base indexada."</i> Isso é o que dá
          <b> rastreabilidade</b> — cada afirmação aponta para um documento e um trecho.
        </p>
        <p style={{ marginTop: 10 }}>
          Na prática isso é imposto no <Code>SYSTEM_PROMPT</Code> do gerador:
        </p>
        <Block>{`Answer ONLY using the provided evidence. Never use outside knowledge.
If evidence is insufficient, respond exactly:
"Não encontrei essa informação na base."
Always cite sources using [Evidence N] references.`}</Block>
        <p>
          <b>Por que importa para equities:</b> um analista precisa confiar na origem. Um número de
          receita "alucinado" com aparência plausível é pior do que nenhuma resposta. Por isso a recusa
          honesta ("Não encontrei essa informação na base") é tratada como um <i>acerto</i>, não como
          falha — a taxa de recusa correta no eval é <b>100%</b>.
        </p>
        <p style={{ marginTop: 10 }}>
          <b>Aplicado aqui:</b> <Code>generation/llm.py → GroundedGenerator</Code>. Temperatura 0.0
          (determinístico), degradação para modo extractivo se a API cair — o retrieval nunca depende
          do LLM estar online.
        </p>
      </>
    ),
  },
  {
    id: "hybrid",
    tag: "Retrieval",
    tagColor: T.accent2,
    title: "Busca híbrida: BM25 + vetorial + RRF",
    summary:
      "Termos exatos (BM25) e semântica (embeddings) são forças complementares, fundidas por Reciprocal Rank Fusion sem calibrar scores.",
    body: (
      <>
        <p>Nenhum retriever sozinho basta. Os dois têm pontos cegos opostos:</p>
        <ul style={ulStyle}>
          <li>
            <b>BM25 (léxico):</b> excelente para termos <i>exatos</i> e raros — <Code>capex</Code>,{" "}
            <Code>RPO</Code>, <Code>provisões</Code>, tickers. Mas não entende sinônimos: "queda de
            lucro" não casa com "profit decline".
          </li>
          <li>
            <b>Vetorial (embeddings):</b> entende <i>significado</i> — aproxima "demanda por IA" e "AI
            infrastructure spending". Mas pode ignorar o número/termo técnico exato que importa.
          </li>
        </ul>
        <p>
          A fusão usa <b>Reciprocal Rank Fusion (RRF)</b>. O truque genial do RRF: ele ignora os{" "}
          <i>scores</i> (que vivem em escalas incomparáveis — BM25 vai a dezenas, cosseno vai de 0 a 1)
          e usa apenas a <b>posição</b> no ranking:
        </p>
        <Block>{`score(doc) = Σ  1 / (k + rank_i(doc))        # k = 60

# um doc no topo dos dois rankings soma:
#   1/(60+1) + 1/(60+1) = 0.0328  → sobe para o topo do fundido`}</Block>
        <p>
          Como só a posição conta, <b>não há calibração de scores</b> — é robusto e não precisa de
          tuning. <Code>k=60</Code> é o valor canônico da literatura (Cormack et al.): amortece o peso
          das primeiras posições o suficiente para que consenso entre os dois rankings vença um
          primeiro-lugar isolado.
        </p>
        <p style={{ marginTop: 10 }}>
          <b>Aplicado aqui:</b> <Code>retrieval/hybrid.py</Code>. Cada retriever devolve top-50, o RRF
          funde, e os 50 melhores fundidos seguem para o reranker.
        </p>
      </>
    ),
  },
  {
    id: "embeddings",
    tag: "Indexação",
    tagColor: T.green,
    title: "Embeddings multilíngues (e5)",
    summary:
      "A base mistura filings SEC em inglês e documentos CVM em português. Um modelo EN-only degrada silenciosamente.",
    body: (
      <>
        <p>
          Embeddings transformam texto em vetores onde proximidade = similaridade semântica. A escolha
          do modelo foi <b>ditada pelo eval</b>, não por preferência: a base é <b>bilíngue</b> — 10-Ks
          da SEC em inglês convivem com fatos relevantes da CVM em português.
        </p>
        <p>
          O baseline usava <Code>all-MiniLM</Code> (só inglês). Resultado: perguntas em português
          recuperavam lixo e o sistema recusava demais. A troca para{" "}
          <Code>intfloat/multilingual-e5-small</Code> coloca os dois idiomas no <i>mesmo espaço
          vetorial</i> — "inadimplência" e "delinquency" ficam próximos.
        </p>
        <p style={{ marginTop: 10 }}>
          <b>Detalhe crítico dos modelos E5:</b> eles exigem prefixos assimétricos. A query e o
          documento entram com marcadores diferentes:
        </p>
        <Block>{`# indexação de um chunk:
"passage: A carteira de crédito cresceu 8% no trimestre..."

# busca:
"query: Qual o crescimento da carteira do Bradesco?"`}</Block>
        <p>
          Esquecer o prefixo degrada o recall silenciosamente. O código detecta{" "}
          <Code>"e5" in model_name</Code> e aplica automaticamente (<Code>indexing/embeddings.py</Code>).
          Vetores são normalizados (norma L2 = 1), então distância cosseno vira produto interno.
        </p>
        <p style={{ marginTop: 10 }}>
          <b>Trade-off:</b> <Code>-small</Code> (384 dims) foi escolhido por velocidade (~370 chunks/s
          em GPU modesta) e footprint. Modelos maiores dariam ganho marginal num corpus deste tamanho.
        </p>
      </>
    ),
  },
  {
    id: "rerank",
    tag: "Retrieval",
    tagColor: T.accent2,
    title: "Reranking com cross-encoder",
    summary:
      "Um segundo modelo lê pergunta e trecho JUNTOS e reordena os 50 candidatos. É lento mas preciso — por isso só nos finalistas.",
    body: (
      <>
        <p>Há uma diferença arquitetural fundamental entre o retriever e o reranker:</p>
        <ul style={ulStyle}>
          <li>
            <b>Bi-encoder (embeddings):</b> codifica query e documento <i>separadamente</i> em vetores,
            depois compara. Rápido — dá para pré-computar milhões de vetores. Mas perde interação fina
            entre as palavras da pergunta e do trecho.
          </li>
          <li>
            <b>Cross-encoder (reranker):</b> concatena <Code>(pergunta, trecho)</Code> e passa o par
            inteiro pelo modelo, que produz um único score de relevância. Vê a interação completa →
            muito mais preciso. Mas é caro: precisa de um forward pass <i>por candidato</i>.
          </li>
        </ul>
        <p>
          A solução é uma <b>cascata (retrieve-then-rerank)</b>: o híbrido barato reduz 63k chunks para
          50 candidatos; o cross-encoder caro reordena só esses 50 e devolve o top-10.
        </p>
        <Block>{`63.562 chunks
   │  BM25 + vetorial + RRF  (barato, aproximado)
   ▼
50 candidatos
   │  cross-encoder mmarco-mMiniLMv2  (caro, preciso)
   ▼
top-10 → evidência para o LLM`}</Block>
        <p>
          O modelo <Code>cross-encoder/mmarco-mMiniLMv2-L12</Code> é multilíngue (mesma razão dos
          embeddings). Bônus: os <b>logits do reranker calibram a recusa</b> — trechos relevantes
          pontuam &gt; 0, irrelevantes &lt; -4. Ver "Recusa em duas camadas".
        </p>
        <p style={{ marginTop: 10 }}>
          <b>Aplicado aqui:</b> <Code>retrieval/reranker.py</Code>. Se o modelo não carregar, o sistema
          degrada para a ordem do RRF em vez de quebrar.
        </p>
      </>
    ),
  },
  {
    id: "chunking",
    tag: "Indexação",
    tagColor: T.green,
    title: "Chunking com metadados",
    summary:
      "~1800 caracteres, overlap de 200, quebra em parágrafos. Cada chunk carrega empresa, tipo, data e página — e sabe de onde veio.",
    body: (
      <>
        <p>
          Documentos financeiros são grandes demais para caber num único embedding (e no contexto do
          LLM). O <b>chunking</b> os divide em pedaços recuperáveis. Três decisões importam:
        </p>
        <ul style={ulStyle}>
          <li>
            <b>Tamanho ~1800 chars (~300 tokens):</b> grande o bastante para preservar o contexto de
            uma tabela financeira ou um parágrafo de guidance inteiro, sem fragmentar o número da sua
            explicação.
          </li>
          <li>
            <b>Overlap de 200 chars:</b> uma janela deslizante garante que um fato na fronteira entre
            dois chunks não seja cortado ao meio em ambos.
          </li>
          <li>
            <b>Quebra por parágrafo primeiro:</b> o chunker respeita <Code>\n\n</Code> e só parte
            palavra-a-palavra quando um parágrafo isolado excede o limite — mantém unidades semânticas
            intactas.
          </li>
        </ul>
        <p>
          Cada chunk carrega <b>metadados</b>: <Code>company</Code>, <Code>doc_type</Code>,{" "}
          <Code>published_at</Code>, <Code>page</Code>, <Code>url</Code>. É isso que permite a citação
          precisa ("Bradesco, earnings_release, pág. 4") e abre caminho para filtros futuros.
        </p>
        <p style={{ marginTop: 10 }}>
          <b>Determinismo:</b> o ID do chunk é <Code>sha256(doc_id : índice : texto[:200])</Code>.
          Reingerir o mesmo documento gera o mesmo ID — <b>nada duplica</b>. O mesmo vale para o ID do
          ponto no Qdrant (o <Code>hash()</Code> do Python foi evitado de propósito, pois é salteado por
          processo).
        </p>
        <p style={{ marginTop: 10 }}>
          <b>Aplicado aqui:</b> <Code>indexing/chunker.py</Code>. 822 documentos → 63.562 chunks.
        </p>
      </>
    ),
  },
  {
    id: "eval",
    tag: "Método",
    tagColor: T.amber,
    title: "Eval-driven development",
    summary:
      "O harness de avaliação veio ANTES da otimização. Cada melhoria de retrieval foi medida, não adivinhada.",
    body: (
      <>
        <p>
          O princípio mais importante do projeto, e o de maior peso na avaliação (Eval Harness = 25%,
          empatado com Retrieval). A regra: <b>construir a medição antes de otimizar</b>.
        </p>
        <p>
          O motivo é sutil e específico de RAG: <b>o retrieval quebra silenciosamente</b>. Um LLM
          produz texto plausível mesmo recebendo contexto errado. Sem um conjunto de perguntas com
          resposta conhecida, você não tem como saber se uma mudança ajudou ou piorou — está no
          achismo.
        </p>
        <p style={{ marginTop: 10 }}>
          O <b>gold set</b> tem 14 perguntas verificadas manualmente contra documentos reais, cobrindo
          as 5 categorias exigidas:
        </p>
        <ul style={ulStyle}>
          <li><b>Documento único</b> — resposta num só doc</li>
          <li><b>Multi-documento</b> — exige juntar fontes (ex.: capex Amazon + Meta)</li>
          <li><b>Multi-período</b> — comparar trimestres (evolução da inadimplência)</li>
          <li><b>Estruturado</b> — dado tabular do BACEN</li>
          <li><b>Não-respondível</b> — Apple e Petrobras não estão na base → deve recusar</li>
        </ul>
        <p>
          O ciclo <b>baseline → diagnóstico → melhoria</b> foi real e reproduzível. Cada mudança
          (embeddings multilíngues, pool de 50, threshold de recusa) só entrou depois de o harness
          confirmar o ganho. Ver a aba <b>Resultados</b> para o antes/depois.
        </p>
        <p style={{ marginTop: 10 }}>
          <b>Aplicado aqui:</b> <Code>eval/harness.py</Code>, <Code>eval/metrics.py</Code>,{" "}
          <Code>eval/questions.jsonl</Code>.
        </p>
      </>
    ),
  },
  {
    id: "refusal",
    tag: "Fundamento",
    tagColor: T.accent,
    title: "Recusa em duas camadas",
    summary:
      "Gate barato por score do reranker + recusa semântica do LLM grounded. Só o gate não basta.",
    body: (
      <>
        <p>
          "Nunca alucinar" exige mais do que uma instrução no prompt. O sistema recusa em{" "}
          <b>duas camadas independentes</b>:
        </p>
        <ol style={{ ...ulStyle, listStyle: "decimal" }}>
          <li>
            <b>Gate por score (barato):</b> se o maior logit do reranker &lt;{" "}
            <Code>-2.0</Code>, recusa antes mesmo de chamar o LLM. Calibrado empiricamente no
            mmarco: relevantes &gt; 0, irrelevantes &lt; -4.
          </li>
          <li>
            <b>Recusa semântica (LLM grounded):</b> mesmo com evidência que passou no gate, o LLM pode
            concluir que ela não responde à pergunta e devolver "Não encontrei essa informação na base".
          </li>
        </ol>
        <p style={{ marginTop: 10 }}>
          <b>Por que as duas?</b> Um exemplo real do próprio projeto: uma pergunta sobre a <b>Apple</b>{" "}
          (fora da base) atinge score <b>3.96</b> em trechos de "fiscal 2024 revenue" de <i>outras</i>{" "}
          empresas. O gate por score sozinho deixaria passar — a evidência <i>parece</i> relevante
          lexicalmente. A camada semântica do LLM é quem percebe que nenhum daqueles trechos é sobre a
          Apple e recusa.
        </p>
        <p style={{ marginTop: 10 }}>
          <b>Consequência medida:</b> a taxa de resposta depende do LLM — 92% com Llama 3.3 70B vs 58%
          com o 8B (que recusa em excesso). Mas as <i>métricas de retrieval independem do modelo de
          geração</i>. Exatamente a tese do case: o retrieval é o que importa.
        </p>
        <p style={{ marginTop: 10 }}>
          <b>Aplicado aqui:</b> <Code>_should_refuse()</Code> em <Code>generation/llm.py</Code>.
        </p>
      </>
    ),
  },
  {
    id: "connected",
    tag: "Ingestão",
    tagColor: T.red,
    title: "Base conectada e dados heterogêneos",
    summary:
      "Zero upload manual: fontes oficiais buscadas automaticamente. Texto e estruturado no mesmo retrieval.",
    body: (
      <>
        <p>
          O requisito nº 1 do case: a base <b>não pode depender de upload manual</b>. O sistema tem uma
          camada de ingestão que busca documentos direto das fontes oficiais, de forma{" "}
          <b>reproduzível</b> — sempre que um novo documento é publicado, um processo o baixa, trata,
          indexa e disponibiliza. Isso transforma a base num "sistema vivo".
        </p>
        <p style={{ marginTop: 10 }}>Cinco fontes reais, 100% via API/portal oficial:</p>
        <ul style={ulStyle}>
          <li><b>SEC EDGAR</b> — 10-K/10-Q/8-K/20-F/6-K + exhibits de press release</li>
          <li><b>CVM Dados Abertos (IPE)</b> — press releases, fatos relevantes (guidance!), apresentações</li>
          <li><b>BACEN Olinda (IF.data)</b> — carteira de crédito por instituição → market share</li>
          <li><b>Yahoo Finance</b> — preços diários ajustados para o backtest</li>
          <li><b>RSS Yahoo Finance</b> — notícias por ticker</li>
        </ul>
        <p>
          A parte engenhosa é fazer <b>texto e dados estruturados conversarem no mesmo retrieval</b>. O
          truque: o dado do BACEN é convertido num <i>documento textual</i> ("Market share do grupo
          NUBANK: 2,03% do sistema...") e indexado como qualquer outro chunk. Assim uma pergunta em
          linguagem natural sobre market share recupera a tabela naturalmente, sem uma rota especial.
        </p>
        <p style={{ marginTop: 10 }}>
          <b>Genérico por design:</b> nova empresa = adicionar um ticker na config. Nova fonte = um
          fetcher que retorna <Code>Document</Code>. O resto do pipeline é agnóstico à origem.
        </p>
      </>
    ),
  },
];

// ----------------------------------------------------------------------------
// DADOS — COMPONENTES
// ----------------------------------------------------------------------------
const COMPONENTS = [
  {
    group: "Ingestão",
    color: T.red,
    path: "src/legacy_retrieval/ingestion/",
    intro:
      "Fetchers config-driven, um por fonte. Todos herdam BaseFetcher e retornam objetos Document uniformes — o resto do pipeline não sabe de onde o doc veio.",
    items: [
      { name: "base.py — BaseFetcher", desc: "Classe abstrata. Contrato único: fetch(company, since, until) → list[Document]. Toda fonte nova implementa isto e ganha o pipeline de graça." },
      { name: "sec_edgar.py", desc: "Baixa filings via data.sec.gov. Detalhe difícil: em 8-K/6-K o documento principal é só a capa — o press release real está nos exhibits EX-99, com nomes que variam por empresa. O fetcher os identifica por extensão + tamanho, excluindo artefatos XBRL. Mapa TICKER→CIK validado contra a fonte (o CIK errado da CoreWeave foi um bug real)." },
      { name: "cvm.py", desc: "Portal de Dados Abertos (IPE). Baixa o ZIP anual de documentos entregues, filtra por código CVM + relevância (press-release de resultado, fato relevante com guidance), e busca o PDF/HTML. Encoding latin-1 e filtragem de Demonstrações Financeiras gigantes de baixo valor por página." },
      { name: "bacen.py", desc: "API Olinda (OData), relatório IF.data Resumo. Baixa a carteira de crédito por instituição e monta market share por GRUPO econômico (Nubank = Nu Pagamentos + Nu Financeira, duas entidades reguladas). Vira um Document textual estruturado." },
      { name: "news.py", desc: "RSS do Yahoo Finance por ticker. Parseia o feed e baixa o corpo da notícia (HTML). Fonte do Case A (comentários de demanda)." },
      { name: "ir_scraper.py", desc: "Scraper genérico de sites de RI, dirigido por config/ir_sites.yaml. Faz crawl de páginas-semente e descobre links de PDF/HTML por padrão — sem parser hardcoded por site." },
    ],
  },
  {
    group: "Parsing",
    color: T.amber,
    path: "src/legacy_retrieval/parsing/",
    intro:
      "Normaliza formatos heterogêneos em texto limpo, preservando o que importa para a citação (número de página).",
    items: [
      { name: "pdf.py — pdfplumber", desc: "Extrai texto página a página, inserindo marcadores [Page N]. O chunker depois lê esses marcadores para gravar o número da página em cada chunk — citação com precisão de página." },
      { name: "html.py — BeautifulSoup", desc: "Remove script/style/nav/footer/header e extrai texto com quebras de linha. Usado tanto para exhibits da SEC quanto para documentos da CVM e notícias." },
    ],
  },
  {
    group: "Indexação",
    color: T.green,
    path: "src/legacy_retrieval/indexing/",
    intro:
      "Transforma documentos em uma estrutura de busca dupla: índice léxico BM25 (em memória) + índice vetorial (Qdrant).",
    items: [
      { name: "chunker.py", desc: "Quebra por parágrafo com janela deslizante (~1800 chars, overlap 200). Propaga metadados e página. IDs determinísticos por sha256 — reingestão idempotente." },
      { name: "embeddings.py", desc: "Abstração EmbeddingProvider com duas implementações: local (sentence-transformers, multilingual-e5-small, com prefixos query:/passage:) e OpenAI. Vetores normalizados. Troca de provider via .env." },
      { name: "indexer.py", desc: "O coração da indexação. Mantém BM25Okapi em memória (tokenização regex que preserva acentos PT) e faz upsert em lotes no Qdrant (payload enxuto de 300 chars — texto completo vive no chunks.json). Persiste/carrega estado (chunks.json + bm25.pkl). Expõe bm25_search e vector_search." },
    ],
  },
  {
    group: "Retrieval",
    color: T.accent2,
    path: "src/legacy_retrieval/retrieval/",
    intro: "A cascata que decide QUAIS trechos o LLM vê. Onde mora 25% da nota do case.",
    items: [
      { name: "hybrid.py — RRF", desc: "Roda BM25 e vetorial em paralelo (top-50 cada) e funde por Reciprocal Rank Fusion (k=60). Devolve RetrievedChunks ordenados sem precisar calibrar scores." },
      { name: "reranker.py — cross-encoder", desc: "Recebe os 50 candidatos, monta pares (pergunta, trecho), pontua com mmarco-mMiniLMv2 e devolve o top-10 reordenado. Degrada graciosamente para a ordem do RRF se o modelo não carregar." },
      { name: "evidence.py — EvidenceBuilder", desc: "Converte os chunks vencedores no bloco de contexto [Evidence N] que o LLM recebe, e simultaneamente monta os objetos Citation (doc, empresa, tipo, página, url, trecho). Respeita um teto de caracteres." },
    ],
  },
  {
    group: "Geração",
    color: T.accent,
    path: "src/legacy_retrieval/generation/",
    intro: "Sintetiza a resposta a partir da evidência — ou recusa. Provider-agnóstico.",
    items: [
      { name: "llm.py — GroundedGenerator", desc: "System prompt que proíbe conhecimento externo e exige citações [Evidence N]. Suporta Groq (Llama 3.3 70B, padrão), OpenAI, Ollama e um modo extractivo local (fallback). Implementa a recusa em duas camadas (_should_refuse). Temperatura 0.0. Se a API cair, degrada para extractivo — o retrieval continua íntegro." },
    ],
  },
  {
    group: "Estruturados",
    color: T.amber,
    path: "src/legacy_retrieval/structured/",
    intro: "Onde o retrieval vira ponto de partida para análise quantitativa (Case C) e cruzamento com dados públicos (Case B).",
    items: [
      { name: "rpo.py", desc: "Extração de RPO (Remaining Performance Obligations) de press releases via regex calibrada nas variações reais ('$63B up 11% Y/Y', 'grew 21% to $13.0 billion'). Descarta guidance em faixa. Ranqueia padrões por confiança (rank menor = frase mais inequívoca)." },
      { name: "metrics.py", desc: "Cálculo de YoY growth (pct_change de 4 trimestres) e aceleração (diff do growth). Também extração genérica de métricas RPO/capex com período." },
      { name: "prices.py", desc: "Preços diários ajustados via yfinance (com cache). Regra de timing: divulgação após o fechamento → retorno de D+1; antes da abertura → retorno de D. Usa acceptanceDateTime oficial da SEC." },
      { name: "backtest.py", desc: "Cruza aceleração de RPO com retorno do primeiro pregão pós-earnings. Calcula hit rate e retorno médio quando a aceleração é positiva." },
      { name: "market_share.py", desc: "Market share = carteira do grupo / carteira total do sistema, a partir do IF.data. Agrupa entidades reguladas por grupo econômico." },
      { name: "database.py", desc: "Camada de persistência estruturada (PostgreSQL) para as séries derivadas." },
    ],
  },
  {
    group: "Avaliação",
    color: T.green,
    path: "src/legacy_retrieval/eval/",
    intro: "O harness que mede o retrieval objetivamente. Peso 25% — o mesmo que o retrieval.",
    items: [
      { name: "metrics.py", desc: "Recall@k, Precision@k, MRR e refusal_correct — no NÍVEL DE DOCUMENTO. Inovação: semântica de GRUPOS de documentos alternativos (o 8-K e o 10-Q do mesmo dia contêm o mesmo fato; recuperar qualquer um satisfaz o rótulo). Sem isso, o gold set puniria acertos legítimos." },
      { name: "harness.py", desc: "Roda o gold set pela pipeline completa (híbrido + rerank) e agrega EvalReport com médias por métrica, answer_rate e refusal_rate. Separa perguntas respondíveis das não-respondíveis." },
      { name: "run.py — CLI", desc: "Entry point (Typer + Rich). Carrega o estado indexado, roda o harness, imprime a tabela e grava o JSON. É o comando que fecha o ciclo eval-driven." },
    ],
  },
  {
    group: "API & Núcleo",
    color: T.accent,
    path: "src/legacy_retrieval/",
    intro: "A cola: contratos de dados, configuração central, orquestração e a interface HTTP.",
    items: [
      { name: "models.py", desc: "Contratos Pydantic: Document, Chunk, RetrievedChunk, Citation, QueryResponse, EvalQuestion. O EvalQuestion suporta expected_doc_ids como str OU grupo de alternativas." },
      { name: "config.py — Settings", desc: "Configuração central via pydantic-settings/.env. Todos os hiperparâmetros num só lugar: chunk 1800/200, top_k 50, rerank 10, k RRF, threshold de recusa -2.0, modelos, Qdrant, providers." },
      { name: "pipeline.py — RetrievalPipeline", desc: "Orquestra retrieve → rerank → generate. Expõe query() (resposta completa) e retrieve_only() (top-k documentos deduplicados, que o eval mede)." },
      { name: "cases.py", desc: "Define os 3 cases como CaseConfig (tickers, tipos de filing, empresas CVM, datasets BACEN, perguntas de exemplo). É config, não lógica — a plataforma é genérica." },
      { name: "api/main.py — FastAPI", desc: "Endpoints: POST /query (pergunta → resposta grounded + citações), GET /market-share/{inst}, GET /health. Carrega a pipeline uma vez (singleton)." },
    ],
  },
];

// ----------------------------------------------------------------------------
// DADOS — PIPELINE
// ----------------------------------------------------------------------------
const PIPELINE = [
  { n: 1, title: "Fontes oficiais", color: T.red, detail: "SEC EDGAR · CVM · BACEN · RSS · Yahoo Finance", sub: "Ingestão automática, cache reproduzível, IDs determinísticos" },
  { n: 2, title: "Parsing", color: T.amber, detail: "PDF (pdfplumber) · HTML (BeautifulSoup)", sub: "Texto limpo, marcadores [Page N] preservados" },
  { n: 3, title: "Chunking", color: T.amber, detail: "~1800 chars · overlap 200 · quebra por parágrafo", sub: "Metadados: empresa, tipo, data, página, url" },
  { n: 4, title: "Indexação dupla", color: T.green, detail: "BM25 (léxico) + e5 multilíngue → Qdrant", sub: "822 docs → 63.562 chunks" },
  { n: 5, title: "Busca híbrida", color: T.accent2, detail: "top-50 de cada retriever → fusão RRF (k=60)", sub: "Sem calibração de scores" },
  { n: 6, title: "Reranking", color: T.accent2, detail: "cross-encoder mmarco → top-10", sub: "Logits calibram a recusa" },
  { n: 7, title: "Geração grounded", color: T.accent, detail: "Groq / Llama 3.3 70B · temp 0.0", sub: "Sintetiza SÓ a evidência" },
  { n: 8, title: "Resposta ou recusa", color: T.accent, detail: "Citações [Evidence N] OU 'Não encontrei...'", sub: "Recusa em duas camadas" },
];

// ----------------------------------------------------------------------------
// DADOS — MÉTRICAS
// ----------------------------------------------------------------------------
const METRICS = [
  { label: "Recall@10 (doc)", base: "0.57", final: "0.96", good: true, note: "Fração dos grupos de docs relevantes recuperados no top-10" },
  { label: "MRR", base: "0.52", final: "0.82", good: true, note: "Posição média do 1º doc relevante (1/rank)" },
  { label: "Precision@10", base: "0.11", final: "0.16", good: null, note: "Estruturalmente baixa: 1–4 docs relevantes por pergunta, corte fixo em 10" },
  { label: "Taxa de resposta (70B)", base: "0.67", final: "0.92", good: true, note: "Respondeu quando devia. Cai para 0.58 com Llama 8B" },
  { label: "Recusa correta", base: "1.00", final: "1.00", good: true, note: "Recusou quando devia (Apple, Petrobras fora da base)" },
];

const PER_Q = [
  { id: "q01", cat: "single", recall: 1.0, mrr: 1.0, case: "A", desc: "NVIDIA Data Center revenue Q1 FY27 (+YoY)" },
  { id: "q02", cat: "single", recall: 1.0, mrr: 0.5, case: "A", desc: "Microsoft additions to PP&E FY2025" },
  { id: "q03", cat: "multi-doc", recall: 0.5, mrr: 0.33, case: "A", desc: "Capex Amazon E Meta FY2025 (única falha de recall)" },
  { id: "q04", cat: "single", recall: 1.0, mrr: 1.0, case: "A", desc: "NVIDIA Blackwell demand Q4 FY26" },
  { id: "q05", cat: "single", recall: 1.0, mrr: 1.0, case: "C", desc: "ServiceNow RPO Q1 2026" },
  { id: "q06", cat: "multi-período", recall: 1.0, mrr: 1.0, case: "C", desc: "Evolução do RPO da ServiceNow em 2025" },
  { id: "q07", cat: "single", recall: 1.0, mrr: 1.0, case: "C", desc: "Salesforce cRPO Q4 FY26" },
  { id: "q90", cat: "não-resp.", recall: null, mrr: null, case: "—", desc: "Apple iPhone revenue — deve recusar" },
  { id: "q91", cat: "não-resp.", recall: null, mrr: null, case: "—", desc: "Guidance Petrobras — deve recusar" },
  { id: "q08", cat: "single", recall: 1.0, mrr: 0.5, case: "B", desc: "Guidance Bradesco fev/2025" },
  { id: "q09", cat: "multi-período", recall: 1.0, mrr: 1.0, case: "B", desc: "Revisão do guidance Bradesco 2025" },
  { id: "q10", cat: "estruturado", recall: 1.0, mrr: 1.0, case: "B", desc: "Market share Nubank (BACEN IF.data)" },
  { id: "q11", cat: "single", recall: 1.0, mrr: 1.0, case: "B", desc: "Projeções 2026 do Itaú" },
  { id: "q12", cat: "multi-período", recall: 1.0, mrr: 0.5, case: "B", desc: "Inadimplência Santander ao longo de 2025" },
];

const DIAGNOSES = [
  { problem: "Perguntas em PT recusavam", cause: "Embeddings/reranker só em inglês (all-MiniLM + ms-marco)", fix: "Trocar para multilingual-e5-small + mmarco-mMiniLMv2" },
  { problem: "Fatos afogados em 10-Ks de 500KB", cause: "Pool de candidatos pequeno (top-k 20)", fix: "Aumentar o pool para 50 candidatos antes do rerank" },
  { problem: "Métricas mediam ranking errado", cause: "Avaliação usava o ranking pré-rerank", fix: "Medir o sistema completo (híbrido + rerank)" },
  { problem: "Rótulos gold puniam acertos", cause: "8-K e 10-Q do mesmo dia contêm o mesmo fato", fix: "Grupos de documentos alternativos no gold set" },
  { problem: "1 rótulo gold errado", cause: "Erro de verificação manual", fix: "Corrigido contra o documento real" },
];

const CASES = [
  {
    id: "A",
    color: T.accent,
    title: "Capex hyperscalers vs demanda NVIDIA",
    challenge: "Consolidar informação espalhada entre várias empresas — nenhuma tem a resposta completa.",
    findings: [
      "Capex 2025 reportado por MSFT / AMZN / META / GOOGL, cada um com citação.",
      "Receita Data Center da NVIDIA: US$ 75,2 bi no 1T FY27 (+92% YoY).",
      "Comentário de demanda por Blackwell recuperado dos press releases.",
      "Resolvido só com perguntas à plataforma genérica — zero lógica por empresa.",
    ],
  },
  {
    id: "B",
    color: T.green,
    title: "Bancos brasileiros: promessa, sentimento, market share",
    challenge: "Conectar documentos separados no tempo e cruzar texto com dados estruturados do BACEN.",
    findings: [
      "Promessa vs entrega: guidance Bradesco (fev/2025: carteira 4-8%, margem R$37-41bi) vs revisão (jul/2025: serviços e seguros revisados para cima).",
      "Sentimento: comparação trimestre a trimestre via retrieval multi-período.",
      "Market share real (IF.data, data-base 2026-03): Nubank 2,03% · Itaú 11,6% · Bradesco 10,0% do sistema (R$ 7,26 tri).",
    ],
  },
  {
    id: "C",
    color: T.accent2,
    title: "Backtest: aceleração de RPO vs retorno pós-earnings",
    challenge: "O retrieval vira etapa inicial de uma análise quantitativa: extrair séries e cruzar com preços.",
    findings: [
      "43 eventos trimestrais de 7 empresas, RPO extraído dos press releases reais.",
      "Timing de divulgação via acceptanceDateTime oficial da SEC → retorno do 1º pregão.",
      "Aceleração positiva → 67% de pregões positivos (média +0,75%); desaceleração → 27% (média -0,19%).",
      "Correlação agregada fraca (Pearson -0,08) — amostra pequena, reportado com honestidade.",
    ],
  },
];

// ----------------------------------------------------------------------------
// DADOS — GLOSSÁRIO
// ----------------------------------------------------------------------------
const GLOSSARY = [
  { term: "RAG", def: "Retrieval-Augmented Generation. O LLM responde a partir de documentos recuperados de uma base, não da memória de treino." },
  { term: "Grounded", def: "Resposta 'ancorada' — cada afirmação deriva de uma evidência recuperada e citável, nunca de conhecimento externo." },
  { term: "BM25", def: "Algoritmo de ranking léxico clássico. Pontua documentos por frequência de termos exatos, com saturação e normalização por tamanho. Ótimo para termos raros e precisos." },
  { term: "Embedding", def: "Vetor denso que representa o significado de um texto. Textos semanticamente próximos ficam próximos no espaço vetorial." },
  { term: "Bi-encoder", def: "Modelo que codifica query e documento separadamente. Rápido e pré-computável, base da busca vetorial." },
  { term: "Cross-encoder", def: "Modelo que processa (query, documento) juntos e emite um score de relevância. Preciso, porém caro — usado só no reranking." },
  { term: "RRF", def: "Reciprocal Rank Fusion. Funde múltiplos rankings usando 1/(k+rank), ignorando os scores brutos. Robusto e sem calibração." },
  { term: "Reranking", def: "Segunda passada que reordena um pequeno conjunto de candidatos com um modelo mais preciso (cross-encoder)." },
  { term: "Chunk", def: "Pedaço recuperável de um documento (~1800 chars aqui), com metadados de origem." },
  { term: "Qdrant", def: "Banco de dados vetorial. Armazena embeddings + payload e faz busca por similaridade (cosseno) em escala." },
  { term: "Recall@k", def: "Fração dos itens relevantes que aparecem no top-k recuperado. Mede se o sistema 'achou' o que importa." },
  { term: "Precision@k", def: "Fração do top-k que é de fato relevante. Baixa aqui por construção (poucos docs relevantes por pergunta, corte fixo em 10)." },
  { term: "MRR", def: "Mean Reciprocal Rank. Média de 1/(posição do 1º relevante). Recompensa colocar o certo no topo." },
  { term: "Logit", def: "Saída bruta (pré-sigmoid) do reranker. Aqui usada como score de relevância e para calibrar o threshold de recusa." },
  { term: "RPO", def: "Remaining Performance Obligations. Receita contratada ainda não reconhecida — um indicador antecedente para empresas SaaS." },
  { term: "cRPO", def: "Current RPO: a parcela do RPO a ser reconhecida nos próximos 12 meses." },
  { term: "IF.data", def: "Relatório do BACEN (via API Olinda) com dados por instituição financeira, incluindo carteira de crédito." },
  { term: "8-K / 6-K", def: "Filings da SEC para eventos materiais. O press release real costuma estar nos exhibits (EX-99), não na capa." },
  { term: "Guidance", def: "Projeção que a empresa divulga sobre seu próprio desempenho futuro. No Case B, comparado com a entrega real." },
  { term: "Eval-driven", def: "Desenvolvimento guiado por um harness de avaliação: medir antes de otimizar, validar cada mudança." },
];

// ----------------------------------------------------------------------------
// COMPONENTES DE UI
// ----------------------------------------------------------------------------
function ConceptCard({ c, open, onToggle }) {
  const [hover, setHover] = useState(false);
  return (
    <div
      onClick={onToggle}
      onMouseEnter={() => setHover(true)}
      onMouseLeave={() => setHover(false)}
      style={{
        background: hover ? T.cardHover : T.card,
        border: `1px solid ${open ? c.tagColor + "66" : T.border}`,
        borderRadius: 14,
        padding: "18px 20px",
        cursor: "pointer",
        transition: "all .18s ease",
        boxShadow: open ? `0 0 0 1px ${c.tagColor}22, 0 8px 30px rgba(0,0,0,.35)` : "none",
      }}
    >
      <div style={{ display: "flex", alignItems: "flex-start", gap: 14 }}>
        <div style={{ flex: 1 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 8, flexWrap: "wrap" }}>
            <span style={chip(c.tagColor)}>{c.tag}</span>
            <span style={{ fontSize: 17, fontWeight: 700, color: T.text }}>{c.title}</span>
          </div>
          <p style={{ margin: 0, color: T.textDim, fontSize: 14.5, lineHeight: 1.55 }}>{c.summary}</p>
        </div>
        <div
          style={{
            width: 28, height: 28, borderRadius: 8, flexShrink: 0,
            border: `1px solid ${T.border}`, display: "flex", alignItems: "center",
            justifyContent: "center", color: c.tagColor, fontSize: 16,
            transform: open ? "rotate(45deg)" : "none", transition: "transform .2s ease",
          }}
        >
          +
        </div>
      </div>
      {open && (
        <div
          style={{ marginTop: 16, paddingTop: 16, borderTop: `1px solid ${T.borderSoft}`, color: T.text, fontSize: 14.5, lineHeight: 1.62 }}
          onClick={(e) => e.stopPropagation()}
        >
          {c.body}
        </div>
      )}
    </div>
  );
}

function SectionTitle({ kicker, title, desc }) {
  return (
    <div style={{ marginBottom: 22 }}>
      {kicker && (
        <div style={{ color: T.accent, fontSize: 12.5, fontWeight: 700, letterSpacing: 1.4, textTransform: "uppercase", marginBottom: 8 }}>
          {kicker}
        </div>
      )}
      <h2 style={{ margin: 0, fontSize: 25, fontWeight: 800, color: T.text, letterSpacing: -0.3 }}>{title}</h2>
      {desc && <p style={{ margin: "10px 0 0", color: T.textDim, fontSize: 15, lineHeight: 1.6, maxWidth: 760 }}>{desc}</p>}
    </div>
  );
}

const h3Style = { margin: "0 0 14px", fontSize: 15, fontWeight: 700, color: T.text };

// ----------------------------------------------------------------------------
// VIEWS
// ----------------------------------------------------------------------------
function OverviewView() {
  const stats = [
    { v: "822", l: "documentos reais" },
    { v: "63.562", l: "chunks indexados" },
    { v: "5", l: "fontes oficiais" },
    { v: "0.96", l: "Recall@10 final" },
  ];
  const stack = [
    ["Vector DB", "Qdrant", "Payload com metadados, busca cosseno"],
    ["Léxico", "rank_bm25 + regex", "Termos exatos: capex, RPO, provisões"],
    ["Fusão", "RRF (k=60)", "Combina rankings sem calibração"],
    ["Embeddings", "multilingual-e5-small", "Base bilíngue EN (SEC) + PT (CVM)"],
    ["Reranker", "mmarco-mMiniLMv2", "Multilíngue; logits calibram recusa"],
    ["LLM", "Groq · Llama 3.3 70B", "Síntese grounded, trocável via .env"],
    ["Estruturados", "pandas · yfinance · Olinda", "IF.data, preços, backtest"],
    ["API", "FastAPI", "/query, /market-share/{inst}"],
  ];
  return (
    <div>
      <SectionTitle
        kicker="Legacy Capital · Case de Retrieval"
        title="Uma plataforma de research onde o retrieval é o coração"
        desc="Não é um chatbot. É a fundação de uma plataforma estilo NotebookLM para analistas de equities: ingestão automática de fontes oficiais, respostas grounded com citações e recusa honesta quando a base não tem a informação. O critério de sucesso não é a fluência do texto — é 'encontrou os documentos certos?'."
      />

      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(150px, 1fr))", gap: 12, marginBottom: 28 }}>
        {stats.map((s) => (
          <div key={s.l} style={{ background: T.panel, border: `1px solid ${T.border}`, borderRadius: 12, padding: "16px 18px" }}>
            <div style={{ fontSize: 26, fontWeight: 800, color: T.accent, letterSpacing: -0.5 }}>{s.v}</div>
            <div style={{ fontSize: 13, color: T.textDim, marginTop: 3 }}>{s.l}</div>
          </div>
        ))}
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 18, alignItems: "start" }} className="ov-grid">
        <div style={{ background: T.panel, border: `1px solid ${T.border}`, borderRadius: 14, padding: 20 }}>
          <h3 style={h3Style}>Os três princípios inegociáveis</h3>
          {[
            ["Retrieval é o coração", "O LLM produz texto plausível mesmo com contexto errado. Toda a arquitetura prioriza recuperar o documento certo."],
            ["Zero alucinação", "Toda resposta vem da base indexada e é citável. Sem evidência suficiente → recusa explícita."],
            ["Base conectada e genérica", "Ingestão automática de fontes oficiais, sem upload manual. Nova empresa/fonte = config, não código novo."],
          ].map(([t, d]) => (
            <div key={t} style={{ display: "flex", gap: 12, marginBottom: 14 }}>
              <div style={{ width: 8, height: 8, borderRadius: 999, background: T.accent, marginTop: 7, flexShrink: 0 }} />
              <div>
                <div style={{ fontWeight: 700, color: T.text, fontSize: 14.5 }}>{t}</div>
                <div style={{ color: T.textDim, fontSize: 13.5, lineHeight: 1.5, marginTop: 2 }}>{d}</div>
              </div>
            </div>
          ))}
        </div>

        <div style={{ background: T.panel, border: `1px solid ${T.border}`, borderRadius: 14, padding: 20 }}>
          <h3 style={h3Style}>Stack e o porquê de cada peça</h3>
          <div style={{ display: "flex", flexDirection: "column", gap: 2 }}>
            {stack.map(([k, tech, why]) => (
              <div key={k} style={{ padding: "9px 0", borderBottom: `1px solid ${T.borderSoft}` }}>
                <div style={{ display: "flex", justifyContent: "space-between", gap: 10, alignItems: "baseline" }}>
                  <span style={{ color: T.textFaint, fontSize: 12.5 }}>{k}</span>
                  <span style={{ color: T.text, fontSize: 13.5, fontWeight: 600, fontFamily: T.mono }}>{tech}</span>
                </div>
                <div style={{ color: T.textDim, fontSize: 12.5, marginTop: 3 }}>{why}</div>
              </div>
            ))}
          </div>
        </div>
      </div>

      <div style={{ marginTop: 22, background: `linear-gradient(135deg, ${T.accent}12, ${T.accent2}12)`, border: `1px solid ${T.accent}33`, borderRadius: 14, padding: "18px 22px" }}>
        <div style={{ fontSize: 13, fontWeight: 700, color: T.accent, letterSpacing: 0.5, marginBottom: 6 }}>A TESE, EM UMA FRASE</div>
        <div style={{ fontSize: 16, color: T.text, lineHeight: 1.6 }}>
          A taxa de resposta variou de 58% (Llama 8B) a 92% (Llama 70B) — mas as métricas de <b>retrieval não mudaram com o modelo</b>.
          Um LLM excelente produz respostas ruins com documentos errados. Por isso o retrieval é onde o projeto investe.
        </div>
      </div>
    </div>
  );
}

function ConceptsView() {
  const [open, setOpen] = useState(null);
  return (
    <div>
      <SectionTitle
        kicker="Conceitos"
        title="As oito ideias por trás do sistema"
        desc="Clique em cada card para expandir a explicação completa: o conceito, o trade-off e como ele foi aplicado no código."
      />
      <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
        {CONCEPTS.map((c) => (
          <ConceptCard key={c.id} c={c} open={open === c.id} onToggle={() => setOpen(open === c.id ? null : c.id)} />
        ))}
      </div>
    </div>
  );
}

function PipelineView() {
  return (
    <div>
      <SectionTitle
        kicker="Pipeline"
        title="Da query à resposta, oito etapas"
        desc="O fluxo end-to-end. As duas primeiras metades (ingestão → indexação) rodam offline; a segunda (busca → geração) roda a cada pergunta."
      />
      <div style={{ display: "flex", flexDirection: "column", gap: 0 }}>
        {PIPELINE.map((p, i) => (
          <div key={p.n}>
            <div style={{ display: "flex", gap: 16, alignItems: "stretch" }}>
              <div style={{ display: "flex", flexDirection: "column", alignItems: "center", width: 44 }}>
                <div style={{
                  width: 40, height: 40, borderRadius: 11, background: `${p.color}1a`,
                  border: `1px solid ${p.color}55`, color: p.color, fontWeight: 800, fontSize: 16,
                  display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0,
                }}>
                  {p.n}
                </div>
                {i < PIPELINE.length - 1 && <div style={{ width: 2, flex: 1, background: `linear-gradient(${p.color}55, ${PIPELINE[i + 1].color}55)`, minHeight: 22 }} />}
              </div>
              <div style={{ flex: 1, background: T.card, border: `1px solid ${T.border}`, borderRadius: 12, padding: "13px 18px", marginBottom: 10 }}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", flexWrap: "wrap", gap: 8 }}>
                  <span style={{ fontSize: 15.5, fontWeight: 700, color: T.text }}>{p.title}</span>
                  <span style={{ fontFamily: T.mono, fontSize: 12.5, color: p.color }}>{p.detail}</span>
                </div>
                <div style={{ color: T.textDim, fontSize: 13, marginTop: 4 }}>{p.sub}</div>
              </div>
            </div>
          </div>
        ))}
      </div>
      <div style={{ marginTop: 18, background: T.panel, border: `1px solid ${T.border}`, borderRadius: 12, padding: "16px 20px" }}>
        <div style={{ fontSize: 13, fontWeight: 700, color: T.amber, marginBottom: 6 }}>O FUNIL DE PRECISÃO</div>
        <div style={{ color: T.textDim, fontSize: 14, lineHeight: 1.6 }}>
          Repare como o volume cai a cada etapa de busca: <b style={{ color: T.text }}>63.562 chunks → 50 candidatos → 10 finalistas</b>.
          Métodos baratos e aproximados (BM25, vetorial) fazem o corte grosso; o cross-encoder caro só toca nos 50 sobreviventes.
          É o que torna viável ser preciso <i>e</i> rápido.
        </div>
      </div>
    </div>
  );
}

function ComponentsView() {
  const [active, setActive] = useState(0);
  const g = COMPONENTS[active];
  return (
    <div>
      <SectionTitle
        kicker="Componentes"
        title="Cada peça do projeto, por dentro"
        desc="A arquitetura é modular por design: fetchers uniformes, contratos Pydantic e um pipeline agnóstico à origem dos dados. Escolha um módulo."
      />
      <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginBottom: 20 }}>
        {COMPONENTS.map((c, i) => (
          <button
            key={c.group}
            onClick={() => setActive(i)}
            style={{
              padding: "8px 15px", borderRadius: 999, cursor: "pointer",
              border: `1px solid ${active === i ? c.color + "88" : T.border}`,
              background: active === i ? c.color + "1f" : T.panel,
              color: active === i ? c.color : T.textDim,
              fontSize: 13.5, fontWeight: 600, transition: "all .15s ease",
            }}
          >
            {c.group}
          </button>
        ))}
      </div>

      <div style={{ background: T.panel, border: `1px solid ${T.border}`, borderRadius: 14, padding: "22px 24px" }}>
        <div style={{ display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap", marginBottom: 6 }}>
          <span style={{ width: 10, height: 10, borderRadius: 3, background: g.color }} />
          <h3 style={{ margin: 0, fontSize: 20, fontWeight: 800, color: T.text }}>{g.group}</h3>
          <span style={{ fontFamily: T.mono, fontSize: 12.5, color: T.textFaint }}>{g.path}</span>
        </div>
        <p style={{ color: T.textDim, fontSize: 14, lineHeight: 1.6, margin: "0 0 18px", maxWidth: 780 }}>{g.intro}</p>
        <div style={{ display: "grid", gridTemplateColumns: "1fr", gap: 10 }}>
          {g.items.map((it) => (
            <div key={it.name} style={{ background: T.card, border: `1px solid ${T.borderSoft}`, borderRadius: 10, padding: "14px 16px" }}>
              <div style={{ fontFamily: T.mono, fontSize: 13.5, fontWeight: 700, color: g.color, marginBottom: 5 }}>{it.name}</div>
              <div style={{ color: T.textDim, fontSize: 13.5, lineHeight: 1.55 }}>{it.desc}</div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

function ResultsView() {
  const catColor = (c) =>
    c === "não-resp." ? T.amber : c === "estruturado" ? T.green : c.startsWith("multi") ? T.accent2 : T.accent;
  return (
    <div>
      <SectionTitle
        kicker="Resultados"
        title="O que o eval mediu — e o que ele diagnosticou"
        desc="Base real: 822 documentos, 63.562 chunks, 14 perguntas de gold set verificadas manualmente. Antes de otimizar, medir."
      />

      <div style={{ background: T.panel, border: `1px solid ${T.border}`, borderRadius: 14, padding: "20px 22px", marginBottom: 20 }}>
        <h3 style={h3Style}>Baseline → Final</h3>
        <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
          {METRICS.map((m) => {
            const bn = parseFloat(m.base), fn = parseFloat(m.final);
            const pct = Math.max(0, Math.min(100, fn * 100));
            const pctBase = Math.max(0, Math.min(100, bn * 100));
            return (
              <div key={m.label}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", marginBottom: 5 }}>
                  <span style={{ fontSize: 14, color: T.text, fontWeight: 600 }}>{m.label}</span>
                  <span style={{ fontFamily: T.mono, fontSize: 13.5 }}>
                    <span style={{ color: T.textFaint }}>{m.base}</span>
                    <span style={{ color: T.textFaint, margin: "0 6px" }}>→</span>
                    <span style={{ color: m.good ? T.green : T.textDim, fontWeight: 700 }}>{m.final}</span>
                  </span>
                </div>
                <div style={{ position: "relative", height: 8, background: "#0e1216", borderRadius: 999, overflow: "hidden", border: `1px solid ${T.borderSoft}` }}>
                  <div style={{ position: "absolute", left: 0, top: 0, bottom: 0, width: `${pctBase}%`, background: T.textFaint + "55" }} />
                  <div style={{ position: "absolute", left: 0, top: 0, bottom: 0, width: `${pct}%`, background: m.good ? T.green : T.accent2, borderRadius: 999 }} />
                </div>
                <div style={{ color: T.textFaint, fontSize: 12, marginTop: 4 }}>{m.note}</div>
              </div>
            );
          })}
        </div>
      </div>

      <div style={{ background: T.panel, border: `1px solid ${T.border}`, borderRadius: 14, padding: "20px 22px", marginBottom: 20 }}>
        <h3 style={h3Style}>O ciclo eval-driven: o que o harness revelou</h3>
        <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
          {DIAGNOSES.map((d) => (
            <div key={d.problem} style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 10, alignItems: "stretch" }} className="diag-row">
              <div style={{ background: `${T.red}12`, border: `1px solid ${T.red}33`, borderRadius: 9, padding: "10px 12px" }}>
                <div style={{ fontSize: 11, color: T.red, fontWeight: 700, marginBottom: 3 }}>SINTOMA</div>
                <div style={{ fontSize: 13, color: T.text }}>{d.problem}</div>
              </div>
              <div style={{ background: `${T.amber}12`, border: `1px solid ${T.amber}33`, borderRadius: 9, padding: "10px 12px" }}>
                <div style={{ fontSize: 11, color: T.amber, fontWeight: 700, marginBottom: 3 }}>CAUSA</div>
                <div style={{ fontSize: 13, color: T.text }}>{d.cause}</div>
              </div>
              <div style={{ background: `${T.green}12`, border: `1px solid ${T.green}33`, borderRadius: 9, padding: "10px 12px" }}>
                <div style={{ fontSize: 11, color: T.green, fontWeight: 700, marginBottom: 3 }}>CORREÇÃO</div>
                <div style={{ fontSize: 13, color: T.text }}>{d.fix}</div>
              </div>
            </div>
          ))}
        </div>
      </div>

      <div style={{ background: T.panel, border: `1px solid ${T.border}`, borderRadius: 14, padding: "20px 22px", marginBottom: 20 }}>
        <h3 style={h3Style}>Gold set, pergunta a pergunta</h3>
        <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
          {PER_Q.map((q) => (
            <div key={q.id} style={{ display: "flex", alignItems: "center", gap: 12, padding: "9px 12px", background: T.card, border: `1px solid ${T.borderSoft}`, borderRadius: 9, flexWrap: "wrap" }}>
              <span style={{ fontFamily: T.mono, fontSize: 12.5, color: T.textFaint, width: 34, flexShrink: 0 }}>{q.id}</span>
              <span style={{ ...chip(catColor(q.cat)), flexShrink: 0, minWidth: 92, textAlign: "center" }}>{q.cat}</span>
              <span style={{ flex: 1, minWidth: 160, fontSize: 13.5, color: T.textDim }}>{q.desc}</span>
              <span style={{ fontSize: 12, color: T.textFaint, fontFamily: T.mono, flexShrink: 0 }}>
                {q.recall === null ? "recusa ✓" : `R ${q.recall.toFixed(1)} · MRR ${q.mrr.toFixed(2)}`}
              </span>
              <span style={{ fontSize: 12, color: T.textFaint, width: 18, flexShrink: 0, textAlign: "center" }}>{q.case}</span>
            </div>
          ))}
        </div>
        <div style={{ color: T.textFaint, fontSize: 12.5, marginTop: 12, lineHeight: 1.5 }}>
          A única falha de recall é a <Code>q03</Code> (capex de duas empresas na mesma pergunta — os 10-Ks gigantes competem com dezenas de relatórios trimestrais).
          Query decomposition resolveria; ficou como melhoria futura.
        </div>
      </div>

      <h3 style={{ ...h3Style, fontSize: 17, marginBottom: 14 }}>Os três cases, resolvidos sobre a plataforma genérica</h3>
      <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
        {CASES.map((cs) => (
          <div key={cs.id} style={{ background: T.panel, border: `1px solid ${T.border}`, borderLeft: `3px solid ${cs.color}`, borderRadius: 12, padding: "18px 20px" }}>
            <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 8 }}>
              <span style={{ width: 30, height: 30, borderRadius: 8, background: `${cs.color}1f`, color: cs.color, fontWeight: 800, display: "flex", alignItems: "center", justifyContent: "center", fontSize: 15 }}>{cs.id}</span>
              <span style={{ fontSize: 16.5, fontWeight: 700, color: T.text }}>{cs.title}</span>
            </div>
            <div style={{ color: T.textDim, fontSize: 13.5, fontStyle: "italic", marginBottom: 12 }}>{cs.challenge}</div>
            <div style={{ display: "flex", flexDirection: "column", gap: 7 }}>
              {cs.findings.map((f, i) => (
                <div key={i} style={{ display: "flex", gap: 10 }}>
                  <span style={{ color: cs.color, flexShrink: 0 }}>▸</span>
                  <span style={{ color: T.text, fontSize: 13.5, lineHeight: 1.5 }}>{f}</span>
                </div>
              ))}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

function GlossaryView() {
  const [q, setQ] = useState("");
  const filtered = GLOSSARY.filter(
    (g) => g.term.toLowerCase().includes(q.toLowerCase()) || g.def.toLowerCase().includes(q.toLowerCase())
  );
  return (
    <div>
      <SectionTitle
        kicker="Glossário"
        title="Termos-chave, em uma linha cada"
        desc="Referência rápida para os conceitos que aparecem no projeto."
      />
      <input
        value={q}
        onChange={(e) => setQ(e.target.value)}
        placeholder="Filtrar termos…"
        style={{
          width: "100%", boxSizing: "border-box", padding: "11px 15px", marginBottom: 18,
          background: T.panel, border: `1px solid ${T.border}`, borderRadius: 10,
          color: T.text, fontSize: 14, outline: "none", fontFamily: T.sans,
        }}
      />
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(300px, 1fr))", gap: 12 }}>
        {filtered.map((g) => (
          <div key={g.term} style={{ background: T.card, border: `1px solid ${T.border}`, borderRadius: 11, padding: "14px 16px" }}>
            <div style={{ fontSize: 14.5, fontWeight: 700, color: T.accent, marginBottom: 5, fontFamily: T.mono }}>{g.term}</div>
            <div style={{ color: T.textDim, fontSize: 13.5, lineHeight: 1.55 }}>{g.def}</div>
          </div>
        ))}
        {filtered.length === 0 && <div style={{ color: T.textFaint, fontSize: 14 }}>Nenhum termo encontrado.</div>}
      </div>
    </div>
  );
}

// ----------------------------------------------------------------------------
// APP
// ----------------------------------------------------------------------------
const TABS = [
  { id: "overview", label: "Visão Geral", view: OverviewView },
  { id: "concepts", label: "Conceitos", view: ConceptsView },
  { id: "pipeline", label: "Pipeline", view: PipelineView },
  { id: "components", label: "Componentes", view: ComponentsView },
  { id: "results", label: "Resultados", view: ResultsView },
  { id: "glossary", label: "Glossário", view: GlossaryView },
];

export default function App() {
  const [tab, setTab] = useState("overview");
  const Active = TABS.find((t) => t.id === tab).view;
  return (
    <div style={{ background: T.bg, minHeight: "100vh", color: T.text, fontFamily: T.sans }}>
      <style>{`
        * { box-sizing: border-box; }
        ::-webkit-scrollbar { width: 10px; height: 10px; }
        ::-webkit-scrollbar-track { background: ${T.bg}; }
        ::-webkit-scrollbar-thumb { background: ${T.border}; border-radius: 5px; }
        ::-webkit-scrollbar-thumb:hover { background: ${T.textFaint}; }
        p { margin: 0 0 10px; }
        @media (max-width: 760px) {
          .ov-grid { grid-template-columns: 1fr !important; }
          .diag-row { grid-template-columns: 1fr !important; }
        }
      `}</style>

      <div style={{ position: "sticky", top: 0, zIndex: 10, background: `${T.bg}f2`, backdropFilter: "blur(10px)", borderBottom: `1px solid ${T.border}` }}>
        <div style={{ maxWidth: 940, margin: "0 auto", padding: "16px 24px 0" }}>
          <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 14 }}>
            <div style={{ width: 34, height: 34, borderRadius: 9, background: `linear-gradient(135deg, ${T.accent}, ${T.accent2})`, display: "flex", alignItems: "center", justifyContent: "center", fontWeight: 800, fontSize: 15, color: "#fff" }}>L</div>
            <div>
              <div style={{ fontSize: 15.5, fontWeight: 800, letterSpacing: -0.2 }}>Legacy Capital · AI Retrieval System</div>
              <div style={{ fontSize: 12.5, color: T.textFaint }}>Guia de estudo interativo — conceitos, arquitetura e resultados</div>
            </div>
          </div>
          <div style={{ display: "flex", gap: 4, overflowX: "auto" }}>
            {TABS.map((t) => (
              <button
                key={t.id}
                onClick={() => setTab(t.id)}
                style={{
                  padding: "10px 16px", border: "none", background: "none", cursor: "pointer",
                  color: tab === t.id ? T.text : T.textFaint, fontSize: 14,
                  fontWeight: tab === t.id ? 700 : 500, whiteSpace: "nowrap",
                  borderBottom: `2px solid ${tab === t.id ? T.accent : "transparent"}`,
                  transition: "color .15s ease", fontFamily: T.sans,
                }}
              >
                {t.label}
              </button>
            ))}
          </div>
        </div>
      </div>

      <div style={{ maxWidth: 940, margin: "0 auto", padding: "34px 24px 80px" }}>
        <Active />
      </div>

      <div style={{ maxWidth: 940, margin: "0 auto", padding: "0 24px 40px", color: T.textFaint, fontSize: 12.5, borderTop: `1px solid ${T.borderSoft}`, paddingTop: 20 }}>
        Guia gerado a partir do repositório <span style={{ fontFamily: T.mono }}>legacy_case</span>. Todos os números
        (822 docs · 63.562 chunks · Recall@10 0.96 · MRR 0.82) vêm do <span style={{ fontFamily: T.mono }}>README.md</span> e de{" "}
        <span style={{ fontFamily: T.mono }}>eval/results.json</span>.
      </div>
    </div>
  );
}
