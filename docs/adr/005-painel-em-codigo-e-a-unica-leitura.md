# ADR 005 — O painel em código é a única interface de leitura

> **Nota de 14/11/2026, sem alterar o texto abaixo.** O painel deixou de ser o
> arquivo único `relatorios/painel.html` e virou o site estático
> `relatorios/painel/`, com gráficos em ECharts (ADR 006). A decisão daqui vale
> igual.

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

- `marts/` continua sendo o contrato, e as regras dele (datas como `date32`,
  grão fino sem pré-agregação, escrita atômica) valem porque o painel lê esses
  arquivos.
- Agregações e ordenações que antes ficariam para a ferramenta de BI são papel
  do código do painel.
- Hoje o painel lê só `dim_paper`, `fato_triagem`, `dim_ficha`,
  `ponte_paper_area`, `ponte_paper_vertente`, `fato_metrica`, `dim_area`,
  `dim_vertente` e `dim_natureza`. `ponte_paper_autor`, `ponte_paper_keyword`
  e `fato_execucao` também não têm leitor no painel, mas ficaram fora desta
  decisão e seguem no export.
- **Deixam de ser exportados**, por não terem leitor: `dim_calendario`,
  `dim_prerequisito`, `dim_perfil`, `ponte_perfil_prerequisito` e
  `ponte_paper_perfil`. O painel nunca leu o calendário, e o pré-requisito e os
  perfis saíram dele em 21/10/2026 (adendo do ADR 004). Os cinco entram em
  `ARQUIVOS_MORTOS`, e o export apaga o Parquet antigo de `marts/`.
- As tabelas continuam **no banco**: `vw_paper_perfil` depende dos perfis e dos
  degraus, o Estágio B grava `prerequisito`, e `fato_triagem.prerequisito`
  segue no Parquet como coluna. Só o arquivo de cada uma sai.
- `_manifest.versao_schema` passa a 3.
- Os comentários, testes e docs que citavam a ferramenta externa foram
  reescritos para citar o painel ou os Parquet.
