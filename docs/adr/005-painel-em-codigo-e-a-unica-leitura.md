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
  do código do painel, que lê os booleanos e as colunas de ordem prontos.
- Os comentários, testes e docs que citavam a ferramenta externa foram
  reescritos para citar o painel ou os Parquet.
