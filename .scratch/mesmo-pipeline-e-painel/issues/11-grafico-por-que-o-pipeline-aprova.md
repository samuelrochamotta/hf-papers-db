# Gráfico "por que o pipeline aprova"

Type: prototype
Status: resolved
Blocked by: 07

## Question

O espelho do Pareto para os aprovados: uma barra por critério de veredito,
dividida entre estrito e amplo, com filtro cruzado por clique. Prototipar no
scratch com os dados da amostra do ticket 07 (o banco ainda não tem critério).
Decidir: barras empilhadas ou lado a lado; se um paper com dois critérios conta
em dois (ocorrências) ou entra num "combinado"; onde o card fica na seção
"Regras do corte"; como a ficha mostra os critérios.

Consultar `dataviz`. Verde = aprovado (ticket 04) vale aqui.

Resolvido quando: o usuário aprova a forma no protótipo.

## Answer

(2026-09-04) **Protótipo pulado a pedido do usuário**; decidido em conversa.
Preferências para a implementação:

- **Barras horizontais, uma por critério**, ordenadas por total, **empilhadas**
  por veredito do paper: estrito em verde escuro, amplo em verde claro (verde
  = aprovado, ticket 04). Separador fino entre o bloco dos critérios de estrito
  e o dos de amplo. A divisão só carrega informação nos critérios de amplo
  (ex.: `benchmark` que acompanhou `artefato_aberto`); nos de estrito a barra
  é de uma cor só, e está certo.
- **Contagem por ocorrência**: paper com dois critérios conta em dois; o
  subtítulo mostra o total de aprovados para o leitor não somar barras. Sem
  barras de combinação.
- **Posição**: seção "Regras do corte", logo depois do Pareto, mesmo tamanho;
  clique na barra filtra o painel como no Pareto.
- **Ficha**: linha "ESTRITO · artefato aberto + benchmark" com rótulos em
  português legível (mapa enum → rótulo no `painel_app.js`); quando há
  fronteira, "fronteira: quase <contraparte>" ao lado.
- Fonte: `ponte_paper_criterio.parquet` + `fato_triagem.fronteira_contraparte`,
  já exportados.
