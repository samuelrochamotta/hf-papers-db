# Natureza × pré-requisito — piloto e reclassificação total (ADR 004)

- **Spec**: `docs/specs/natureza-prerequisito.md` · **ADR**: `docs/adr/004-natureza-e-prerequisito.md`
- **Modelo**: `z-ai/glm-5.3-flash` nos dois estágios, via OpenRouter
- **Rodada total**: `run-20261020-195152` (4.477 papers, concorrência 4, 19:51 → 22:51)
- **Repasse dirigido**: `run-20261020-225228` (930 papers com `pratica_contradita` preenchida, 22:52 → 23:21)
- **Custo**: piloto ~US$ 0,26 · rodada total US$ 2,12 · teste do ajuste US$ 0,02 · repasse US$ 0,86 → **~US$ 3,26**
- **Medição**: `.scratch/medir_total.py data/hfpapers.db run-20261020-195152,run-20261020-225228 2026-10-20`

Sem gabarito humano (decisão 9 da spec): todo aceite abaixo é por métrica contra o
regime v1 (`.scratch/regime_v1.csv`, exportado antes da migração) e por reteste.

## 1. Piloto (150 papers, estratificados pelo regime v1)

Critérios fixados na spec antes de rodar. Três rodadas mais um reteste:

| critério | limite | rodada 1 | rodada 2 | rodada 3 |
|---|---|---|---|---|
| Retentativa do B | ≤ 10% | passa | passa | 3% |
| Estrito v1 → `nenhum`/`implementar` ou contradiz | ≥ 80% | passa | passa | 94% |
| Amplo v1 com acesso interno → `acesso_interno` | ≥ 70% | **67% (falha)** | passa | 92% |
| Mídia/percepção v1 continuam fora | ≥ 90% | passa | passa | 100% |
| `nenhum` entre os aprovados | ≤ 40% | passa | passa | 2% |
| *(não era critério)* contradiz prática | — | 58% | 40% | 34% |

- **Rodada 1 → 2**: `acesso_interno` passou a valer mesmo quando o leitor escreve o
  código (interpretabilidade, atenção esparsa); contradição de PPO/destilação recebe
  `treino`; `pratica_contradita` só quando a prática é o objeto do achado central;
  OCR e texto em cena vão para percepção; encoders tabulares e de séries temporais
  para `fora_de_escopo`.
- **Reteste** (30 papers da rodada 3, mesma entrada): veredito 97%, pré-requisito 87%,
  natureza 93% — todos acima dos limites (90/85/85).
- **Rodada 3 × base final** (os 150 do piloto, reclassificados na rodada total):
  veredito 147/150 (98%), pré-requisito 141/150 (94%), natureza 139/150 (93%) —
  um segundo reteste, de graça.

## 2. Correção depois do piloto: "contradiz prática"

O piloto passou em todos os critérios, mas nenhum deles media `pratica_contradita`,
que ficou em 34% dos aprovados (o `invalida_pratica` do regime antigo marcava ~6,5%).
A rodada total confirmou a taxa: **32%** (712 de 2.235 aprovados quando foi medida no
meio da rodada), com **530 dos 712 em `proposta`**. Lendo uma amostra de 30: em
propostas de método, cerca de metade nomeava só o baseline que o método supera
("aplicar a supervisão do professor uniformemente na destilação on-policy"); as
propostas de benchmark ou protocolo de avaliação ("tratar a nota do SWE-bench como
raciocínio de repositório") e os achados empíricos eram, em geral, legítimos.

- **Ajuste** (`prompts/estagio_b.md` §5 e `prompts/regras_classificacao.md`): em
  `proposta` de método, `pratica_contradita` é `null`; a exceção é o instrumento que
  mede a prática falhando — benchmark que mostra a avaliação corrente enganando, ou
  análise separada de dano.
- **Teste** (40 papers marcados, banco do piloto): propostas 24 → 7 marcadas,
  achados 16 → 13; pré-requisito mudou em 3 de 40 (entre `nenhum` e `implementar`).
- **Repasse**: Estágio B inteiro (não só o campo, porque o degrau deriva da
  contradição) nos **930 papers** marcados ao fim da rodada total. Os não marcados
  não foram refeitos: o ajuste só aperta, então `null` continua `null`.
- **Resultado**: **381 de 2.893 aprovados (13%)**.

Não é uma segunda reclassificação total: é uma correção dirigida da mesma rodada,
em 21% da base.

**Efeito no critério do piloto.** "Estrito v1 → baixo *ou contradiz*" usava o campo
como alternativa, então os 94% estavam inflados. Sem a alternativa, na base inteira:
**873 de 1.005 estritos (87%)** viram `nenhum`/`implementar` — passa sozinho. No
recorte do piloto, já com a base final, são 24 de 35 (69%); o piloto puxou de
propósito os estritos de fronteira, e a base inteira é a medida que vale.

## 3. Base final

**Veredito**: 2.893 aprovados (65%), 1.584 fora (35%).

| regra de descarte | papers |
|---|---|
| `geracao_de_midia` | 812 |
| `percepcao_robotica_embodied` | 623 |
| `fora_de_escopo` | 149 |

| pré-requisito | aprovados |
|---|---|
| `nenhum` | 47 |
| `implementar` | 1.404 |
| `acesso_interno` | 210 |
| `treino` | 1.135 |
| `sem_acao` | 97 |

- **Natureza**: `proposta` 2.508, `achado_empirico` 314, `panorama` 44, `teoria` 27.
- **Textos**: contradiz prática 381 (13%), falta o como 195; artefato aberto 1.971.
- **Perfis**: Produto 1.451, Treino/pesquisa 1.442.

| natureza | nenhum | implementar | acesso_interno | treino | sem_acao |
|---|---|---|---|---|---|
| proposta | 4 | 1.299 | 164 | 1.041 | 0 |
| achado_empirico | 43 | 105 | 46 | 94 | 26 |
| teoria | 0 | 0 | 0 | 0 | 27 |
| panorama | 0 | 0 | 0 | 0 | 44 |

`nenhum` é raro (1,6%): quase toda proposta pede ao menos código. Os 43 achados
empíricos em `nenhum` são o que muda decisão de prompt ou de avaliação sem código —
é o filtro mais curto do perfil Produto.

## 4. Regime v1 × regime v2

| v1 | n | fora mídia | fora percepção | fora escopo | nenhum | implementar | acesso_interno | treino | sem_acao |
|---|---|---|---|---|---|---|---|---|---|
| fora `treino_ou_postreino` | 1.544 | 139 | 97 | 24 | 3 | 162 | 27 | 1.070 | 22 |
| estrito | 1.005 | 8 | 4 | 1 | 40 | 833 | 73 | 40 | 6 |
| fora `geracao_de_midia` | 678 | 636 | 13 | 9 | 0 | 11 | 3 | 6 | 0 |
| amplo | 494 | 2 | 4 | 2 | 4 | 317 | 104 | 13 | 48 |
| fora `percepcao_robotica_embodied` | 492 | 8 | 458 | 3 | 0 | 18 | 0 | 2 | 3 |
| fora `fora_de_escopo` | 195 | 10 | 42 | 109 | 0 | 22 | 3 | 2 | 7 |
| fora `relatorio_tecnico_de_modelo` | 52 | 5 | 4 | 0 | 0 | 32 | 0 | 1 | 10 |
| fora `portabilidade_reprovada` | 7 | 0 | 0 | 1 | 0 | 5 | 0 | 0 | 1 |
| (sem v1) | 10 | 4 | 1 | 0 | 0 | 4 | 0 | 1 | 0 |

- O ganho da mudança está na primeira linha: **1.284 papers de treino** que o regime
  v1 descartava agora entram, 1.070 deles em `treino`. Os 236 que caem em mídia ou
  percepção eram descartes por treino que escondiam a regra de domínio (a regra de
  treino vinha antes na ordem v1).
- Mídia e percepção v1 continuam fora em 94% e 93%.
- `relatorio_tecnico_de_modelo`: 32 de 52 viram `implementar` (pesos abertos).

**Área × regra.** 175 descartes por mídia/percepção (12%) têm área primária de outro
nome — "Internos do modelo" para interpretabilidade de um modelo de TTS,
"Avaliação & instrumentação" para benchmark de robótica. É o esperado: a área diz o
que o paper faz, a regra diz o domínio. Numa amostra de 15, três descartes são
discutíveis (relatório técnico de agente de GUI, benchmark de vídeo com resposta em
texto, método de incerteza genérico) — ~1% da base, abaixo do ruído do reteste. O
`doutor` passou a reportar esse número como dado, não como aviso.

## 5. Recalibração dos guardrails

Dias dos últimos 90 com ≥ 15 classificados (64 dias), distribuição da base final:

| medida | p5 | p10 | mediana | p90 | p97 | máx |
|---|---|---|---|---|---|---|
| taxa de fora | 23% | 27% | 35% | 45% | 48% | 48% |
| aprovados/dia | 12 | 14 | 22 | 38 | 41 | 48 |
| fração `nenhum` (dias ≥ 10 aprovados) | 0% | 0% | 0% | 7% | 10% | 12% |

| guardrail | provisório | calibrado | regra |
|---|---|---|---|
| `taxa_fora_min` | 0,15 | **0,20** | abaixo do p5 |
| `taxa_fora_faixa_normal` | 0,20–0,60 | **0,25–0,47** | p10–p90, arredondado para fora |
| `aprovados_faixa_normal` | 8–60 | **13–40** | p10–p90, arredondado para fora |
| `aprovados_volume_alto` | 70 | **45** | acima do p97 |
| `prerequisito_nenhum_max` | 0,40 | **0,15** | acima do máximo observado |
| `prerequisito_min_aprovados` | 10 | 10 | sem mudança |

A faixa normal p10–p90 avisa, por construção, em cerca de 1 dia útil a cada 5 —
`volume_atipico` é aviso, não erro. A estimativa de custo de `classificacao.estimar`
continua com 70% de candidatos ao Estágio B: na rodada total foram 68%.
