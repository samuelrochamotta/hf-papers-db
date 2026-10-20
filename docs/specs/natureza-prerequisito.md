# Natureza × pré-requisito, perfil fora do paper

Status: aprovada em 20/10/2026 após 2 rodadas de crítica (12 agentes).
Decisão registrada em `docs/adr/004-natureza-e-prerequisito.md`.

## Decisões do dono (fixas)

1. Vários perfis de leitor (produto com LLM; treino/pesquisa).
2. `geracao_de_midia` e `percepcao_robotica_embodied` continuam fora.
3. A consulta filtra por "dá para agir nisso".
4. Esquema v1/v2 (substituir), não a alternativa mínima.
5. Relatório técnico de modelo de fundação **entra**.
6. Implementação **direto na main**, sem branch, sem backup do banco.
7. **Piloto de 150 papers**, depois **uma única** reclassificação total.
8. Exporta-se `.scratch/regime_v1.csv` como régua do piloto (não é backup).
9. Sem gabarito humano: o aceite do piloto é só por métricas.
10. Implementação **completa**, painel incluído; nada fica para depois.

## Princípio

Substituir, não somar. Saem: `veredito` estrito/amplo, os 10
`criterios_veredito` (`ponte_paper_criterio`), `decisao_fronteira`,
`fronteira_contraparte`, o teste de portabilidade como descarte,
`tem_artefato_nomeado`, `tem_codigo_aberto` e as regras `treino_ou_postreino`,
`relatorio_tecnico_de_modelo` e `portabilidade_reprovada`. Entram dois campos
classificatórios, dois textos anuláveis e um artefato com evidência externa.
Uma fonte de verdade por fato (ADR 001).

## 1. Escopo — Estágio A

O Estágio A continua: classifica área × vertente de 100% da base e aplica três
descartes baratos, **nesta ordem**:

1. `geracao_de_midia` — imagem, vídeo, 3D, áudio, mesh; **TTS/ASR quando a fala
   é o objeto do paper**. Modelo omni com núcleo LLM que também fala **entra**.
2. `percepcao_robotica_embodied` — percepção, robótica, embodied, direção
   autônoma, **visão discriminativa sem saída em linguagem** (classificação,
   detecção, CLIP, aprendizado contínuo visual). MLLM que responde em texto
   sobre imagem/vídeo **entra**; agente em jogo/simulação só cai aqui se a ação
   for motora contínua.
3. `fora_de_escopo` — o modelo central não recebe nem produz linguagem natural
   e não é componente de pipeline com LLM (embedder, reranker, parser de RAG).

Sai do prompt A: "o leitor não treina", a exceção "componente adotável", a meta
"~70% fora". Guardrail de coerência (aviso, não decisão): regra de mídia sem
área Geração de mídia, e vice-versa; idem percepção.

A grade (áreas, sub-áreas, vertentes) **não muda** nesta entrega; a total roda
com ela congelada.

## 2. Classificação — Estágio B

Ordem normativa dos campos do JSON:

1. `regra_fora` — rede de segurança, só as 3 regras do A. Não nula ⇒ todo o
   resto nulo.
2. `natureza` — `proposta` | `achado_empirico` | `teoria` | `panorama`.
3. `padrao_extraido` `{nome, mecanismo}` — obrigatório se `proposta`, nulo
   senão.
4. `prerequisito` — `nenhum` | `implementar` | `acesso_interno` | `treino` |
   `sem_acao`.
5. `pratica_contradita` — texto ou NULL (deriva `contradiz_pratica`).
6. `falta_o_como` — texto ou NULL (deriva `como_incompleto`).
7. `artefato_status` — `liberado` | `prometido` | NULL; só perguntado quando há
   evidência de artefato (§3).
8. `justificativa`
9. `ficha`

### Definições e réguas de desempate

**natureza** — a contribuição que o abstract anuncia.
- "Propomos X", X adotável (método, sistema, ferramenta, **benchmark**) →
  `proposta`. "Mostramos/medimos que…", o método é veículo → `achado_empirico`.
- Desempate: o título nomeia um instrumento → `proposta`; nomeia uma pergunta
  ou fenômeno → `achado_empirico`.
- Relatório técnico de modelo de fundação geral de família nomeada →
  `achado_empirico`.
- `teoria`: modelo formal ou conceitual sem instrumento. `panorama`: survey,
  taxonomia.

**prerequisito** — o caminho mais barato até o ganho principal.
- `nenhum` — muda decisão, prompt ou configuração **sem escrever código**.
- `implementar` — escrever componente a partir da descrição, **ou rodar
  ferramenta/benchmark/checkpoint de terceiros**. Servir pesos abertos (vLLM,
  ollama) é `implementar`, não acesso interno.
- `acesso_interno` — ativações, pesos internos, KV cache, decodificação
  própria, engine ou kernel modificados.
- `treino` — atualização de gradiente (FT, LoRA, RL, destilação).
- `sem_acao` — nada a adotar (teoria, panorama, achado sem ação). É valor
  explícito, não NULL: a view, o Power BI e o filtro não precisam tratar nulo.
- Desempates: "exige código novo além de cola?" → `implementar`. "Roda só via
  API de chat com logprobs?" → no máximo `implementar`. Pesos liberados: ganho
  é **usar** o checkpoint → `implementar`; ganho é a **receita** → `treino`.
  Relatório de fundação: `sem_acao`, ou `implementar` com pesos abertos.
- **Achado que contradiz prática recebe o degrau necessário para aplicar a
  correção** (não `sem_acao`). Assim a contradição de uma prática de treino fica em
  `treino` e não vaza para o perfil produto.

**pratica_contradita** — o que o leitor plausivelmente já faz hoje, nomeado.
**falta_o_como** — o princípio é portável, mas o paper não diz como fazer.

### Validações em código (resposta volta para o modelo refazer)

- `regra_fora` não nula ⇒ natureza, prerequisito, padrão, textos e ficha nulos.
  Aprovado ⇒ natureza e ficha completa.
- `proposta` ⇒ `prerequisito` ≠ `sem_acao` e `padrao_extraido` preenchido;
  não `proposta` ⇒ padrão nulo.
- `teoria`/`panorama` ⇒ `prerequisito` = `sem_acao`.
- Mecanismo do padrão: mantém o regex de 2ª pessoa/imperativo; **novo**: proíbe
  o nome próprio extraído do título (acrônimo/CamelCase antes de ":"). Substitui
  o teste de portabilidade autoavaliado (7 reprovações em 4477).
- `artefato_status` sem evidência de artefato: o código **sobrescreve** para
  NULL, sem retentativa (o schema JSON é fixo; o prompt diz por paper se há
  evidência).
- Avisos sem retentativa: `achado_empirico` + `sem_acao` com prática contradita;
  vertente Treinar + `nenhum` sem artefato; `artefato_status=liberado` sem link.
- Morre o validador de fronteira e o de coerência critérios↔veredito.

### Prompts

Saem de `estagio_b.md` e `regras_classificacao.md`: "o leitor não treina", §3
inteira (critérios, estrito/amplo, fronteira), portabilidade como descarte,
faixas 60–80% e 4–9 aprovados. **Todos os exemplos "AMPLO porque…/ESTRITO
por…" são reescritos** com os rótulos novos — em modelo barato exemplo
sobrevivente vira few-shot. Ficam: regra do upvote, teste de separação da
ficha.

## 3. Artefato aberto — evidência externa + uma pergunta

- Evidência (código, recalculada a cada export): `github_repo` não nulo, **ou**
  link `github.com`/`huggingface.co` no abstract (89 papers hoje sem
  `github_repo`), **ou** `MAX(qtd_modelos, qtd_datasets) > 0` sobre todos os
  snapshots (o mais recente costuma ter NULL).
- Com evidência, o B responde `artefato_status`: `liberado` ou `prometido`
  ("código será liberado", repo vazio). Sem evidência, NULL e não pergunta.
- `artefato_aberto = evidencia AND artefato_status = 'liberado'`, calculado
  **só na view**. NULL para `teoria`/`panorama` (listas "awesome").
- Sai `dim_paper.tem_codigo_aberto` (já diverge de `github_repo` em 11 linhas).

## 4. Perfis — fora do paper, por conjunto de degraus

`degrau_max` não serve: o perfil treino com teto em `treino` deixa passar tudo.
Perfil é um **conjunto** de degraus:

| perfil | degraus |
|---|---|
| `produto` | `nenhum`, `implementar` |
| `pesquisa_treino` | `acesso_interno`, `treino`, `sem_acao` |

Em linguagem simples: **produto** é o que se aplica usando o modelo como ele
vem; **treino/pesquisa** é o que exige abrir o modelo, treiná-lo, ou só amplia
o entendimento. Configurável em `config.yaml`, sincronizado no banco a cada
conexão (quem hospeda modelo pode pôr `acesso_interno` em produto). "Tudo" é
ausência de filtro. Nada é gravado por paper; a LLM não escolhe perfil, e mudar
a divisão não exige reclassificar.

## 5. Modelo de dados

```sql
fato_triagem(
  paper_id PK, veredito CHECK IN ('fora','aprovado'),
  regra_fora CHECK IN ('geracao_de_midia','percepcao_robotica_embodied','fora_de_escopo'),
  natureza REFERENCES dim_natureza, prerequisito REFERENCES dim_prerequisito,
  pratica_contradita TEXT, falta_o_como TEXT,
  artefato_status CHECK IN ('liberado','prometido'),
  justificativa, classificado_em, run_id, revisao,
  CHECK ((veredito='fora') = (regra_fora IS NOT NULL))
)
dim_natureza(natureza, rotulo, definicao, ordem)       -- fixa, schema.sql
dim_prerequisito(prerequisito, rotulo, definicao, ordem) -- fixa; sem_acao = 5
dim_perfil(perfil, rotulo); ponte_perfil_prerequisito(perfil, prerequisito)
                                                        -- config.yaml, sincronizada em migrar
vw_paper_perfil   -- paper aprovado × perfil (join simples, sem NULL)
vw_artefato       -- paper: evidencia, artefato_aberto
```

- Só os invariantes sempre verdadeiros ficam em CHECK/FK. A coerência
  natureza↔prerequisito (§2) vive no validador pydantic, que é o portão de
  escrita, e numa consulta do `doutor`. Não há rebuild posterior à total.
- `dim_natureza`/`dim_prerequisito` com `INSERT OR IGNORE` no `schema.sql` +
  teste que confere contra os Enums de `llm/schemas.py`.
- A ordem do degrau vive só em `dim_prerequisito` (Power BI: "classificar por
  coluna").
- `log_execucao`: `qtd_aprovados` + contagem por degrau (`qtd_pr_*`); é o único
  histórico de distribuição. Linhas antigas: `qtd_aprovados = amplo + estrito`.
- `ponte_paper_criterio`: DROP. Apagar `marts/ponte_paper_criterio.parquet` à
  mão (o export não apaga). Export: sai a ponte, entram `dim_natureza`,
  `dim_prerequisito`, `dim_perfil`, `ponte_paper_perfil` (da view) e as colunas
  de artefato; `_manifest.versao_schema = 2`.
- Migração `_migrar_triagem_v2`, uma vez, presa à existência de
  `decisao_fronteira`: CREATE nova → `INSERT…SELECT` (estrito/amplo →
  `aprovado`, campos novos NULL até a total) → DROP → RENAME. Tirar
  `fronteira_contraparte` de `COLUNAS_MIGRADAS` (senão volta por ALTER).

## 6. Ficha

Única. `implicacao_pratica` vira "O que muda para você", abrindo pelo perfil
quando couber ("Se você treina…", "Se você usa via API…"). Quando
`prerequisito` ≥ `acesso_interno`, a **Ressalva abre com o pré-requisito**
(sem campo novo). `exemplo_concreto` vale para treino (run nomeada, falha
observada).

## 7. Painel

- **Aprovados**: seletor Produto / Treino-pesquisa / Tudo (padrão: último
  usado, inicial Produto; localStorage) que marca pílulas de degrau visíveis
  — `nenhum · implementar · acesso interno · treino · sem ação` — com contador
  e cor ordinal. Pílulas de natureza e dos três booleanos; área e vertente
  ficam. Saem filtros de veredito e critério.
- Paginação **por dia** (todos os aprovados do dia, "dia anterior" no fim).
  Ordem dentro do dia: degrau, depois votos (upvote ordena exibição, nunca
  classifica nem corta).
- Card recolhido: selo do degrau · letra da natureza · título · 1ª frase de
  "O que muda para você" · marcas de contradiz e de artefato (com link) ·
  área · votos.
- **Busca** em título, organização e texto da ficha, com índice em
  minúsculas montado no carregamento e debounce.
- **Panorama**: lote diário empilhado por degrau; matriz natureza ×
  pré-requisito; área por degrau; onde o pipeline corta (3 regras); upvotes ×
  estrelas; e os gráficos de votos que não dependem de veredito.
- **Registro histórico**: por trimestre fora da janela, 15 aprovados mais
  votados seguindo o perfil selecionado + 5 descartados de auditoria.
- Peso estimado: 3,6 → 5,5–7 MB (1,3–1,7 MB gzip). Aceitável; renderizar só a
  página visível.

## 8. Guardrails

- Faixas de fora e de aprovados/dia: **neutras** até a total; recalibradas com
  a distribuição dela.
- Distribuição por degrau por dia: aviso se `nenhum` > 40% dos aprovados.
- Coerência regra de descarte × área (§1); Treinar + `nenhum` sem artefato.

## 9. Operação e piloto

**Custo/tempo** (preço atual do GLM 5.3 flash via Together):

| | Papers A / B | US$ | Tempo (conc. 4) |
|---|---|---|---|
| Piloto 150 + reteste de 30 | 150 / ~130 (+30) | ~0,3 | ~10 min |
| Reclassificação total | 4477 / ~3100 | ~6,5 | 2,5–3,5 h |
| Rodada diária nova | — | ~1,6/mês (hoje 1,1) | — |

**Passos** (cada um com testes verdes):

0. Pausar **os dois** agentes do launchd antes da primeira edição
   (`launchctl bootout` em `-db` e `-painel`): o run diário roda a árvore de
   trabalho, e `gerar_painel.sh` dá push de qualquer commit pendente. Exportar
   `.scratch/regime_v1.csv` (veredito, regra, critérios agregados; ~1 MB):
   não é backup, é a régua do piloto — qualquer comando com o código novo
   migra o banco e apaga o regime antigo.
1. CLI: `reclassificar --ids-arquivo` e `--retomar <run_id>` (reaproveita o
   `run_id`; `conferir` fecha 0/0).
2. `llm/schemas.py`, validações, prompts A e B.
3. `schema.sql` + migração, testada contra banco v1 de fixture.
4. Gravação em `classificacao`, contadores em `execucao`, `doutor`, guardrails.
5. Export, views, `gerar_painel.py`, `painel_app.js`; prévia `--destino /tmp`.
6. **Piloto** em `/tmp/piloto.db` via `HFPAPERS_CONFIG` (já existe).
7. **Total** no banco real com `nohup`; `--retomar` se cair; `--paper` nas
   falhas do B; `conferir` 0/0.
8. Recalibrar guardrails, `doutor --sem-rede`, `export`, apagar parquet da
   ponte, `gerar_painel.py --force` (o push fica com o agente `-painel`
   religado).
9. Religar os agentes; `kickstart` do `-db` recupera os dias parados (até 30;
   perdem-se só os snapshots de upvote desses dias).
10. README, CONTEXT.md (glossário: sai Veredito estrito/amplo, Critério,
    Fronteira, Teste de portabilidade como descarte; entram Natureza,
    Pré-requisito, Perfil, Evidência de artefato; "treino" desambiguado entre
    vertente, área, degrau e perfil), ADR 004.

**Amostra do piloto (150, estratificada pelo regime antigo):**

| estrato | n |
|---|---|
| fora por treino (metade sem "LLM" no título/abstract) | 40 |
| estrito (10 com fronteira) | 25 |
| amplo (12 `exige_acesso_interno`) | 25 |
| relatório técnico | 12 |
| `invalida_pratica` | 10 |
| teoria/panorama (`framework_conceitual`, `panorama`) | 8 |
| mídia + percepção, com TTS/ASR, CLIP, MLLM de vídeo | 16 |
| `fora_de_escopo` | 7 |
| `portabilidade_reprovada` | 7 |

**Critérios de aceite — fixados antes de rodar:**

- Retentativa do B ≤ 10%; zero falha definitiva sem explicação.
- Estrito antigo → `nenhum`/`implementar` em ≥ 80%.
- Amplo `exige_acesso_interno` → `acesso_interno` em ≥ 70%.
- Mídia/percepção antigos continuam fora em ≥ 90%.
- `nenhum` ≤ 40% dos aprovados.
- Reteste de 30 papers: ≥ 90% de concordância em fora/aprovado, ≥ 85% em
  `prerequisito` e em `natureza`.
- Falhou: ajustar prompt e repetir o piloto (US$ 0,3). Falhou duas vezes no
  reteste: trocar o modelo do B.

## Riscos aceitos

- `nenhum`×`implementar` continua sendo a fronteira mais instável (17% de
  ambiguidade estimada após os ajustes).
- `proposta`×`achado_empirico` em benchmark com resultados (~14%).
- Vertente Treinar ≈ área Modelo & treino ≈ degrau `treino` em boa parte dos
  aprovados: redundância parcial aceita, porque cada um responde a uma pergunta
  diferente e o guardrail mede a divergência.
- Volume: ~38 aprovados/dia; o perfil é o filtro padrão, nunca "Tudo".

## Histórico de revisões

- v0 → v1: 7 naturezas → 4; `adocao` com `so_informa` → escada de
  pré-requisito com NULL; 10 critérios → booleanos; perfil fora do paper.
- v1 → v2: booleanos viram textos anuláveis; teste de portabilidade sai do
  schema; `artefato_aberto` vira evidência + `liberado/prometido`; perfil por
  conjunto de degraus (não teto); contradição recebe o degrau da correção (sai o
  `OR` do filtro); `pre_requisito_texto` cortado (Ressalva abre com ele); regras
  de mídia e percepção redigidas para não engolir MLLM/omni; "fronteira" →
  "modelo de fundação geral"; plano operacional sem branch e sem backup; piloto
  de 150 estratificado com aceite numérico.
