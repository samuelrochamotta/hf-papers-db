-- Esquema estrela do hf-papers-db.
-- Executado com executescript() em toda abertura de banco: tudo eh IF NOT EXISTS.
-- PRAGMA foreign_keys eh por conexao e fica em db.py, nao aqui.

PRAGMA journal_mode = WAL;

-- ══════════════ DIMENSÃO PRINCIPAL ══════════════
CREATE TABLE IF NOT EXISTS dim_paper (
    paper_id                TEXT PRIMARY KEY,          -- id base, sem versão
    titulo                  TEXT NOT NULL,
    abstract                TEXT,
    ai_summary              TEXT,
    ai_summary_model        TEXT,
    data_arxiv              DATE,        -- paper.publishedAt
    data_hf_daily           DATE,        -- paper.submittedOnDailyAt  (organiza a operação)
    url_arxiv               TEXT,        -- derivado: https://arxiv.org/abs/{id}
    url_hf                  TEXT,        -- derivado: https://huggingface.co/papers/{id}
    project_page            TEXT,
    github_repo             TEXT,
    github_repo_added_by    TEXT,
    tem_codigo_aberto       INTEGER,     -- 0/1, derivado de github_repo IS NOT NULL
    discussion_id           TEXT,
    thumbnail_url           TEXT,
    organizacao             TEXT,        -- organization.name
    organizacao_nome_longo  TEXT,        -- organization.fullname
    submetido_por           TEXT,        -- submittedOnDailyBy.user
    submetido_por_nome      TEXT,
    autor_participa         INTEGER,     -- isAuthorParticipating
    qtd_autores             INTEGER,
    qtd_autores_verificados INTEGER,     -- authors[].status == 'claimed_verified'
    primeiro_visto_em       TIMESTAMP NOT NULL,
    enriquecido_em          TIMESTAMP
);
CREATE INDEX IF NOT EXISTS ix_paper_data_hf ON dim_paper(data_hf_daily);

-- ══════════════ FATO: MÉTRICAS VIVAS (série temporal) ══════════════
CREATE TABLE IF NOT EXISTS fato_metrica (
    paper_id        TEXT NOT NULL REFERENCES dim_paper(paper_id),
    data_snapshot   DATE NOT NULL,
    upvotes         INTEGER,
    comentarios     INTEGER,
    github_stars    INTEGER,
    qtd_modelos     INTEGER,   -- numTotalModels    (só atualizado no enriquecimento)
    qtd_datasets    INTEGER,   -- numTotalDatasets
    qtd_spaces      INTEGER,   -- numTotalSpaces
    origem          TEXT NOT NULL,   -- 'daily' | 'por_paper' | 'backfill'
    PRIMARY KEY (paper_id, data_snapshot)
);
CREATE INDEX IF NOT EXISTS ix_metrica_data ON fato_metrica(data_snapshot);

-- ══════════════ FATO: TRIAGEM ══════════════
CREATE TABLE IF NOT EXISTS fato_triagem (
    paper_id                TEXT PRIMARY KEY REFERENCES dim_paper(paper_id),
    veredito                TEXT NOT NULL CHECK (veredito IN ('fora','amplo','estrito')),
    regra_fora              TEXT,     -- regra de descarte (§1 das regras, 6 rótulos); obrigatória em todo 'fora', NULL se aprovado
    justificativa           TEXT,
    tem_artefato_nomeado    INTEGER,  -- 0/1
    portabilidade_aprovada  INTEGER,  -- 0/1/NULL (NULL = não chegou a ser testada)
    portab_depende_nome     INTEGER,  -- 0/1/NULL — falha tipo 1
    portab_generalidade     INTEGER,  -- 0/1/NULL — falha tipo 2
    decisao_fronteira       INTEGER DEFAULT 0,  -- 1 se o modelo marcou como poderia ter ido para o outro lado
    fronteira_contraparte   TEXT,     -- o que quase venceu (regra de descarte ou critério); NULL sem fronteira. Coluna adicionada por migração em db.migrar
    classificado_em         TIMESTAMP NOT NULL,
    run_id                  TEXT NOT NULL,
    revisao                 INTEGER NOT NULL DEFAULT 1
);
CREATE INDEX IF NOT EXISTS ix_triagem_veredito ON fato_triagem(veredito);

-- Critérios de veredito (§3 das regras): por que um aprovado é estrito ou amplo.
-- Um paper pode ter vários; 'fora' não tem nenhum. Enum vive em llm/schemas.py.
CREATE TABLE IF NOT EXISTS ponte_paper_criterio (
    paper_id    TEXT NOT NULL REFERENCES dim_paper(paper_id),
    criterio    TEXT NOT NULL,
    PRIMARY KEY (paper_id, criterio)
);

-- ══════════════ DIMENSÃO: FICHA (só aprovados) ══════════════
CREATE TABLE IF NOT EXISTS dim_ficha (
    paper_id            TEXT PRIMARY KEY REFERENCES dim_paper(paper_id),
    achado              TEXT NOT NULL,
    padrao_nome         TEXT,     -- NULL quando o achado é puramente empírico
    padrao_mecanismo    TEXT,
    implicacao_pratica  TEXT NOT NULL,
    exemplo_concreto    TEXT NOT NULL,
    ressalva            TEXT NOT NULL,
    gerada_em           TIMESTAMP NOT NULL,
    modelo_usado        TEXT NOT NULL,
    run_id              TEXT NOT NULL
);

-- ══════════════ VOCABULÁRIO CONTROLADO ══════════════
CREATE TABLE IF NOT EXISTS dim_area (
    area        TEXT PRIMARY KEY,
    definicao   TEXT NOT NULL,
    desde       DATE
);
CREATE TABLE IF NOT EXISTS dim_topico (
    topico      TEXT PRIMARY KEY,
    definicao   TEXT NOT NULL,
    desde       DATE
);
CREATE TABLE IF NOT EXISTS ponte_paper_area (
    paper_id    TEXT NOT NULL REFERENCES dim_paper(paper_id),
    area        TEXT NOT NULL REFERENCES dim_area(area),
    is_primaria INTEGER NOT NULL,   -- 1 = área primária, 0 = secundária
    PRIMARY KEY (paper_id, area)
);
CREATE TABLE IF NOT EXISTS ponte_paper_topico (
    paper_id    TEXT NOT NULL REFERENCES dim_paper(paper_id),
    topico      TEXT NOT NULL REFERENCES dim_topico(topico),
    PRIMARY KEY (paper_id, topico)
);
CREATE TABLE IF NOT EXISTS tax_candidato (
    rotulo      TEXT NOT NULL,
    tipo        TEXT NOT NULL CHECK (tipo IN ('area','topico')),
    definicao   TEXT NOT NULL,
    papers      TEXT NOT NULL,   -- JSON array de paper_id
    promovido   INTEGER NOT NULL DEFAULT 0,
    criado_em   TIMESTAMP NOT NULL,
    PRIMARY KEY (rotulo, tipo)
);

-- ══════════════ FACETA NÃO CONTROLADA (keywords do HF) ══════════════
CREATE TABLE IF NOT EXISTS ponte_paper_keyword (
    paper_id    TEXT NOT NULL REFERENCES dim_paper(paper_id),
    keyword     TEXT NOT NULL,
    PRIMARY KEY (paper_id, keyword)
);

-- ══════════════ AUTORES ══════════════
CREATE TABLE IF NOT EXISTS ponte_paper_autor (
    paper_id    TEXT NOT NULL REFERENCES dim_paper(paper_id),
    ordem       INTEGER NOT NULL,
    autor       TEXT NOT NULL,
    hf_user     TEXT,
    verificado  INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (paper_id, ordem)
);

-- ══════════════ OPERAÇÃO ══════════════
CREATE TABLE IF NOT EXISTS log_execucao (
    run_id              TEXT PRIMARY KEY,
    iniciado_em         TIMESTAMP NOT NULL,
    finalizado_em       TIMESTAMP,
    status              TEXT NOT NULL,   -- 'ok' | 'parcial' | 'erro'
    dias_cobertos       TEXT,            -- JSON array de datas
    qtd_coletados       INTEGER,
    qtd_novos           INTEGER,
    qtd_ja_vistos       INTEGER,
    qtd_fora            INTEGER,
    qtd_amplo           INTEGER,
    qtd_estrito         INTEGER,
    taxa_fora           REAL,
    qtd_refresh         INTEGER,
    tokens_entrada      INTEGER,
    tokens_saida        INTEGER,
    custo_usd           REAL,
    avisos              TEXT             -- JSON array de strings
);

CREATE TABLE IF NOT EXISTS log_llm (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id          TEXT NOT NULL,
    paper_id        TEXT,
    etapa           TEXT NOT NULL,       -- 'estagio_a' | 'estagio_b'
    modelo          TEXT NOT NULL,
    tokens_entrada  INTEGER,
    tokens_saida    INTEGER,
    custo_usd       REAL,
    latencia_ms     INTEGER,
    tentativas      INTEGER NOT NULL DEFAULT 1,
    erro            TEXT,
    criado_em       TIMESTAMP NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_llm_run ON log_llm(run_id);

-- ══════════════ CALENDÁRIO (o Power BI precisa) ══════════════
CREATE TABLE IF NOT EXISTS dim_calendario (
    data            DATE PRIMARY KEY,
    ano             INTEGER, mes INTEGER, dia INTEGER,
    nome_mes        TEXT,
    trimestre       INTEGER,
    semana_iso      INTEGER,
    ano_semana_iso  TEXT,      -- '2026-W34'
    dia_semana      INTEGER,   -- 1=segunda
    nome_dia_semana TEXT,
    eh_dia_util     INTEGER
);
