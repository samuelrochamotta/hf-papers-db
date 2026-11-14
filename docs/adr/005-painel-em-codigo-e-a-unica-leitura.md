# ADR 005 — O painel em código é a única interface de leitura

- **Data**: 2026-11-14
- **Estado**: aceito
- **Supera**: a frase do README e de `scripts/gerar_painel.py` que tratava o
  painel HTML como vitrine de distribuição e uma ferramenta de BI externa como
  a interface de leitura.

## Decisão

O único dashboard do projeto é o painel feito por código neste repositório:
`scripts/gerar_painel.py` + `scripts/painel_app.js`, gerando
`relatorios/painel.html` a partir dos Parquet de `marts/`. Não há ferramenta de
BI externa lendo os Parquet, e nenhuma decisão de modelagem deve ser tomada
pensando numa.

## Consequências

- `marts/` continua sendo o contrato: o export não muda, e as regras dele
  (datas como `date32`, grão fino sem pré-agregação, escrita atômica) valem
  porque o painel lê esses arquivos.
- Agregações e ordenações que antes ficariam para a ferramenta de BI são papel
  do código do painel.
- Hoje o painel lê só `dim_paper`, `fato_triagem`, `dim_ficha`,
  `ponte_paper_area`, `ponte_paper_vertente`, `fato_metrica`, `dim_area`,
  `dim_vertente` e `dim_natureza`. Ficam **sem leitor no repositório**:
  `dim_calendario`, `dim_prerequisito`, `dim_perfil`,
  `ponte_perfil_prerequisito` e `ponte_paper_perfil` (o pré-requisito e os
  perfis saíram do painel em 21/10/2026, ADR 004). Por ora continuam sendo
  exportados, para análise ad hoc dos Parquet. Se vão para `ARQUIVOS_MORTOS`
  é decisão de um PR seguinte; até lá, nenhum comentário deve citar o painel
  como motivo para mantê-los.
- Os comentários, testes e docs que citavam a ferramenta externa foram
  reescritos para citar o painel ou os Parquet.
