# ADR 008: o export é o contrato do painel

- **Data**: 2026-11-18
- **Estado**: aceito
- **Contexto**: `src/hfpapers/estagios/export.py`, `paineis/v1/gerar_painel.py`
- **Completa**: o ADR 005, que tirou do export as tabelas de calendário,
  pré-requisito e perfis, mas deixou `ponte_paper_autor`, `ponte_paper_keyword`
  e `fato_execucao` "fora desta decisão".

## Contexto

O ADR 005 fez de `marts/` o contrato do painel. Mesmo assim, o export continuou
gravando o que o esquema estrela do Power BI pedia:
- três tabelas sem leitor;
- dentro das 9 tabelas que o painel lê, colunas que ele não lê. No `dim_paper`
  eram 19 das 32, entre elas `abstract`, `ai_summary`, as datas do arXiv e
  `faixa_upvotes_atual`.

O painel v2 (ADR 007) não muda isso, porque lê o SQLite direto. O único leitor
de `marts/` é `paineis/v1/gerar_painel.py`, e nenhuma rotina fora do repositório
lê esses arquivos.

## Decisão

O export grava a tabela e a coluna que `paineis/v1/gerar_painel.py` lê, e só elas.
Dado que o painel não mostra fica no banco, que é a fonte.

**Saem do export:**
- 3 tabelas: `fato_execucao`, `ponte_paper_keyword` e `ponte_paper_autor`.
  Entram em `ARQUIVOS_MORTOS`, e o export apaga os arquivos antigos de
  `marts/`.
- As colunas sem leitor:
  - **`dim_paper`:** tudo que não é título, data, links, organização, contagem
    de autores e as três métricas atuais.
  - **`fato_triagem`:** `aprovado`, `prerequisito`, `contradiz_pratica`,
    `como_incompleto`, `artefato_status`, `evidencia_artefato`,
    `classificado_em`, `run_id` e `revisao`. O painel usa os textos
    `pratica_contradita` e `falta_o_como` e o booleano `artefato_aberto`.
  - **`fato_metrica`:** tudo menos `paper_id`, `data_snapshot` e `upvotes`. Com
    isso sai também o preenchimento para frente de `qtd_modelos`,
    `qtd_datasets` e `qtd_spaces`, além do `upvotes_delta_dia`.
  - **`dim_ficha`:** o Padrão Extraído, `gerada_em`, `modelo_usado` e `run_id`.
  - **`dim_area` e `dim_vertente`:** `desde`.
- `faixa_upvotes_atual`, a função que a calculava e a chave
  `export.faixas_upvotes` do `config.yaml`.

**Ficam:** as regras do ADR 005 (`date32`, grão fino, escrita atômica) e o
`_manifest.json`, que dispara o launchd do painel. `VERSAO_SCHEMA` sobe para 4.

## Como a equivalência foi medida

O site do painel foi gerado duas vezes a partir de uma cópia do banco de
18/11/2026, uma com o export do ADR 005 e outra com este. Os arquivos foram
comparados um a um:

- **`dados.json`:** só muda o carimbo `gerado`.
- **`index.html`:** só muda o hash de cache do `dados.json`, que acompanha o
  carimbo.
- **`fichas.json` e o ECharts:** idênticos.
- **Tamanho:** o `marts/` caiu de 11 MB para 4,0 MB.

`test_o_painel_monta_a_partir_do_export` mantém o contrato coberto. É o único
teste que roda o export e o painel em sequência.

## Consequências

- **Coluna nova no painel começa no schema de `export.py`.** Ela também entra
  no teste de ponta a ponta, com um valor diferente do padrão do
  `.get(...) or` do painel. Sem isso, um corte futuro da coluna passa em
  silêncio.
- **Análise ad hoc lê o banco**, não `marts/`.
- **Pendências no SQLite, sem migração agora:** `dim_calendario` e as tabelas
  e a view de perfis continuam sendo preenchidas, mas nada lê essas tabelas.
