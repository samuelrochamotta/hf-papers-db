# ADR 005 — O painel em código é a única interface de leitura

- **Data**: 2026-11-14
- **Estado**: aceito
- **Supera**: a frase do README e de `paineis/v1/gerar_painel.py` que tratava o
  painel HTML como vitrine de distribuição e uma ferramenta de BI externa como
  a interface de leitura.

## Decisão

A leitura do projeto é feita só pelos painéis em código deste repositório. O
v1 (`paineis/v1/gerar_painel.py` + `paineis/v1/painel_app.js`) gera
`relatorios/painel/` a partir dos Parquet de `marts/`. O v2 (ADR 007) lê o
SQLite direto. Não há ferramenta de BI externa lendo os Parquet, e nenhuma
decisão de modelagem deve ser tomada pensando numa.

## Consequências

- `marts/` é o contrato do painel, e as regras dele (datas como `date32`, grão
  fino sem pré-agregação, escrita atômica) valem porque o painel lê esses
  arquivos.
- Agregações e ordenações que antes ficariam para a ferramenta de BI são papel
  do código do painel.
- Deixaram de ser exportados, por não terem leitor: `dim_calendario`,
  `dim_prerequisito`, `dim_perfil`, `ponte_perfil_prerequisito` e
  `ponte_paper_perfil`. Estão em `ARQUIVOS_MORTOS`, e o export apaga o Parquet
  antigo de `marts/`. As tabelas continuam no banco.
- `_manifest.versao_schema` passou a 3.
- O ADR 008 levou a regra até o fim: o export grava só a tabela e a coluna que o
  painel lê, e a versão do schema subiu para 4.
