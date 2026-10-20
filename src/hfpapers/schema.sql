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
    data_arxiv              DATE,        -- legado: paper.publishedAt do HF, nao v1
    data_arxiv_informada_hf  DATE,
    data_arxiv_v1            DATE,        -- submissao inicial verificada no arXiv
    arxiv_v1_verificado_em   TEXT,
    data_hf_daily           DATE,        -- paper.submittedOnDailyAt  (organiza a operação)
    url_arxiv               TEXT,        -- derivado: https://arxiv.org/abs/{id}
    url_hf                  TEXT,        -- derivado: https://huggingface.co/papers/{id}
    project_page            TEXT,
    github_repo             TEXT,
    github_repo_added_by    TEXT,
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
    origem          TEXT NOT NULL,   -- 'daily' | 'por_paper' (linhas antigas trazem 'backfill', que nada mais escreve)
    PRIMARY KEY (paper_id, data_snapshot)
);
CREATE INDEX IF NOT EXISTS ix_metrica_data ON fato_metrica(data_snapshot);

-- ══════════════ FATO: TRIAGEM ══════════════
-- Regime do ADR 004: `aprovado`/`fora`, e o aprovado localizado por natureza ×
-- pré-requisito. Só os invariantes sempre verdadeiros ficam em SQL; a coerência
-- natureza↔pré-requisito é do validador do Estágio B e do `doutor`. O CHECK de
-- `regra_fora` não lista os rótulos de propósito: as linhas anteriores à
-- reclassificação total trazem regras que saíram, e quem as acusa é o `doutor`.
-- Tabela reconstruída por migração em db.migrar nos bancos do regime anterior.
CREATE TABLE IF NOT EXISTS fato_triagem (
    paper_id                TEXT PRIMARY KEY REFERENCES dim_paper(paper_id),
    veredito                TEXT NOT NULL CHECK (veredito IN ('fora','aprovado')),
    regra_fora              TEXT,     -- regra de descarte; obrigatória em todo 'fora', NULL se aprovado
    justificativa           TEXT,
    natureza                TEXT REFERENCES dim_natureza(natureza),          -- NULL se 'fora'
    prerequisito            TEXT REFERENCES dim_prerequisito(prerequisito),  -- NULL se 'fora'
    pratica_contradita      TEXT,     -- a prática que o achado contradiz, nomeada; NULL se não contradiz
    falta_o_como            TEXT,     -- o que falta para implementar; NULL se o paper diz como
    artefato_status         TEXT CHECK (artefato_status IN ('liberado','prometido')),  -- só com evidência (vw_artefato)
    classificado_em         TIMESTAMP NOT NULL,
    run_id                  TEXT NOT NULL,
    revisao                 INTEGER NOT NULL DEFAULT 1,
    CHECK ((veredito = 'fora') = (regra_fora IS NOT NULL))
);
CREATE INDEX IF NOT EXISTS ix_triagem_veredito ON fato_triagem(veredito);

-- Os dois eixos de um aprovado. Vocabulário fixo, que só muda junto com o
-- código (Enums em llm/schemas.py; um teste confere que batem). Por isso mora
-- aqui, e não no JSON da grade, que é vocabulário que evolui por medição.
CREATE TABLE IF NOT EXISTS dim_natureza (
    natureza    TEXT PRIMARY KEY,
    rotulo      TEXT NOT NULL,
    definicao   TEXT NOT NULL,
    ordem       INTEGER NOT NULL
);
INSERT OR IGNORE INTO dim_natureza VALUES
    ('proposta',        'Proposta',        'Propõe algo adotável: método, sistema, ferramenta, benchmark.', 1),
    ('achado_empirico', 'Achado empírico', 'Mostra ou mede algo; o método é veículo.', 2),
    ('teoria',          'Teoria',          'Modelo formal ou conceitual, sem instrumento.', 3),
    ('panorama',        'Panorama',        'Sistematiza o que existe: survey, taxonomia.', 4);

-- A escada de capacidade: cada degrau implica os anteriores. `ordem` é a única
-- cópia da ordenação (o Power BI classifica por ela; o painel também).
CREATE TABLE IF NOT EXISTS dim_prerequisito (
    prerequisito TEXT PRIMARY KEY,
    rotulo       TEXT NOT NULL,
    definicao    TEXT NOT NULL,
    ordem        INTEGER NOT NULL
);
INSERT OR IGNORE INTO dim_prerequisito VALUES
    ('nenhum',         'Nenhum',         'Muda decisão, prompt ou configuração, sem escrever código.', 1),
    ('implementar',    'Implementar',    'Escrever um componente pela descrição, ou rodar ferramenta, benchmark ou checkpoint de terceiros.', 2),
    ('acesso_interno', 'Acesso interno', 'Ativações, pesos internos, KV cache, decodificação própria, engine ou kernel modificados.', 3),
    ('treino',         'Treino',         'Atualização de gradiente: fine-tune, LoRA, RL, destilação.', 4),
    ('sem_acao',       'Sem ação',       'Nada a adotar: muda o entendimento, não a prática.', 5);

-- Perfil de leitura: um conjunto de degraus. Fica fora do paper - nada é
-- gravado por paper, e mudar a divisão não reclassifica nada. A fonte é
-- `perfis` no config.yaml; db.sincronizar_perfis reescreve as duas tabelas.
CREATE TABLE IF NOT EXISTS dim_perfil (
    perfil      TEXT PRIMARY KEY,
    rotulo      TEXT NOT NULL,
    ordem       INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS ponte_perfil_prerequisito (
    perfil       TEXT NOT NULL REFERENCES dim_perfil(perfil),
    prerequisito TEXT NOT NULL REFERENCES dim_prerequisito(prerequisito),
    PRIMARY KEY (perfil, prerequisito)
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
-- Área e sub-área são a mesma coisa em dois níveis, e por isso moram na mesma
-- tabela: área raiz tem `area_pai` NULL, sub-área aponta para o pai. Uma tabela
-- irmã só deixaria as duas definições de área divergirem.
CREATE TABLE IF NOT EXISTS dim_area (
    area        TEXT PRIMARY KEY,
    definicao   TEXT NOT NULL,
    desde       DATE,
    area_pai    TEXT NULL REFERENCES dim_area(area)   -- coluna adicionada por migração em db.migrar
);
-- O eixo transversal: que movimento o paper faz com a peça em que mexe.
CREATE TABLE IF NOT EXISTS dim_vertente (
    vertente    TEXT PRIMARY KEY,
    definicao   TEXT NOT NULL,
    desde       DATE
);
-- O par (área > sub-área) que localiza o paper na grade. A sub-área entra na
-- chave primária porque o par secundário pode repetir a área do primário desde
-- que a sub-área difira: com a chave `(paper_id, area)` esse par era proibido.
-- Tabela reconstruída por migração em db.migrar nos bancos que já existiam.
CREATE TABLE IF NOT EXISTS ponte_paper_area (
    paper_id    TEXT NOT NULL REFERENCES dim_paper(paper_id),
    area        TEXT NOT NULL REFERENCES dim_area(area),
    subarea     TEXT NOT NULL REFERENCES dim_area(area),
    is_primaria INTEGER NOT NULL,   -- 1 = par primário, 0 = secundário
    PRIMARY KEY (paper_id, area, subarea)
);
-- De uma a duas vertentes por paper. A `ordem` é o que distingue a dominante
-- (1) da secundária (2): sem ela as duas seriam intercambiáveis e nenhuma
-- agregação teria resposta única. Tabela nova, então `CREATE TABLE IF NOT
-- EXISTS` basta - não há linha antiga para migrar.
CREATE TABLE IF NOT EXISTS ponte_paper_vertente (
    paper_id    TEXT NOT NULL REFERENCES dim_paper(paper_id),
    vertente    TEXT NOT NULL REFERENCES dim_vertente(vertente),
    ordem       INTEGER NOT NULL,   -- 1 = dominante
    PRIMARY KEY (paper_id, vertente)
);
-- A fila de revisão da grade: onde ela não serviu, e por quê. Substitui
-- `tax_candidato`, que guardava o rótulo que o modelo inventava — daí vinham
-- as seis variantes de robótica e as três de world models. Aqui o modelo não
-- propõe nome nenhum: constata em qual dos três eixos o encaixe falhou. Quem
-- promove é a revisão da grade, por quórum, e não o ato de classificar.
-- Chave por paper, e não por (paper, eixo): o contrato do Estágio A traz no
-- máximo uma declaração por paper, então reclassificar substitui a anterior
-- em vez de deixar a de ontem pendurada num eixo que o modelo abandonou.
CREATE TABLE IF NOT EXISTS tax_nao_encaixe (
    paper_id        TEXT PRIMARY KEY REFERENCES dim_paper(paper_id),
    eixo            TEXT NOT NULL CHECK (eixo IN ('area','subarea','vertente')),
    justificativa   TEXT NOT NULL,
    registrado_em   TIMESTAMP NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_nao_encaixe_eixo ON tax_nao_encaixe(eixo);

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
    qtd_amplo           INTEGER,         -- regime anterior ao ADR 004; NULL desde então
    qtd_estrito         INTEGER,         -- idem
    qtd_aprovados       INTEGER,
    qtd_pr_nenhum       INTEGER,         -- aprovados por degrau de pré-requisito: o
    qtd_pr_implementar  INTEGER,         -- único histórico da distribuição, porque
    qtd_pr_acesso_interno INTEGER,       -- fato_triagem é sobrescrita a cada
    qtd_pr_treino       INTEGER,         -- reclassificação
    qtd_pr_sem_acao     INTEGER,
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
    -- Quem do outro lado atendeu. O OpenRouter roteia entre dezenas de
    -- endpoints do mesmo modelo, e eles nao se comportam igual: sem esta
    -- coluna, "a rodada ficou 9x mais lenta" nao tem a quem ser atribuido.
    provedor        TEXT,
    -- `prompt_tokens_details.cached_tokens` da resposta: quanto do
    -- `tokens_entrada` veio do cache do provedor (mais barato). NULL quando o
    -- provedor nao devolve o campo - nao e o mesmo que zero.
    tokens_cache_leitura INTEGER,
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
