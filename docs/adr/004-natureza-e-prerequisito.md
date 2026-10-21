# ADR 004 — Natureza e pré-requisito no lugar de estrito/amplo

- **Data**: 2026-10-20
- **Estado**: aceito
- **Contexto**: `docs/specs/natureza-prerequisito.md`
- **Supera**: a decisão 1 do ADR 001 ("o veredito já decorre da lista de
  critérios") e o §3 de `prompts/regras_classificacao.md` até esta data.

## Contexto

O pipeline inteiro respondia a uma pergunta só: *isto serve para quem usa LLM
em produção e não treina?* Ela estava no prompt do Estágio B ("o leitor… não
treina modelos"), nas regras de descarte e no par estrito/amplo. O dono passou
a se interessar também por treino e por papers teóricos, e a pergunta deixou
de servir:

- `treino_ou_postreino` respondia por 1544 dos 2968 descartes (52%); a área
  *Modelo & treino* tinha 1250 papers e 13 aprovados.
- O próprio descarte por treino escondia ruído: era a primeira regra testada,
  e 641 dos 1544 nem citavam LLM no título ou abstract (mídia, robótica, visão
  que nunca chegavam às regras certas).
- Três campos do regime antigo quase não discriminavam: `portabilidade_reprovada`
  pegou 7 papers em 4477; `decisao_fronteira` marcava 57% dos amplos; o teste de
  portabilidade era autoavaliado pelo modelo.

## Decisão

1. **Escopo.** Saem `treino_ou_postreino`, `relatorio_tecnico_de_modelo` e
   `portabilidade_reprovada`. Ficam três descartes, testados nesta ordem:
   `geracao_de_midia`, `percepcao_robotica_embodied`, `fora_de_escopo`, com
   redação que deixa entrar MLLM que responde em texto e modelo omni com núcleo
   LLM.
2. **O veredito vira `aprovado`/`fora`.** Estrito/amplo, os dez critérios
   (`ponte_paper_criterio`), a fronteira e a contraparte saem.
3. **Dois campos classificam um aprovado.** `natureza` (proposta, achado
   empírico, teoria, panorama) diz que tipo de afirmação o paper faz;
   `prerequisito` (nenhum < implementar < acesso interno < treino; e `sem_acao`)
   diz o que é preciso ter para usá-lo. Dois textos anuláveis
   (`pratica_contradita`, `falta_o_como`) substituem os critérios que
   sobreviviam como fato.
4. **Perfil fica fora do paper.** É um conjunto de degraus em `config.yaml`
   (produto: nenhum, implementar; treino/pesquisa: acesso interno, treino, sem
   ação). A LLM não escolhe perfil; mudar a divisão não reclassifica nada.
5. **Artefato aberto tem evidência externa.** O código junta repositório do HF,
   link no abstract e modelos/datasets vinculados; a LLM só distingue
   `liberado` de `prometido` quando há evidência. O booleano final existe só
   na view.
6. **Uma reclassificação total**, depois de um piloto de 150 papers com aceite
   por métricas fixadas antes de rodar. Sem backup do regime antigo: o
   `.scratch/regime_v1.csv` é a régua do piloto.

## Consequências

- Volume de aprovados sobe de ~15 para ~38 por dia; o painel abre filtrado
  pelo perfil, nunca em "Tudo".
- Guardrails de taxa de fora (60–80%) e de aprovados/dia (4–9) perdem a
  calibração e ficam neutros até serem medidos de novo na distribuição da
  reclassificação total.
- A redundância parcial entre vertente *Treinar*, área *Modelo & treino* e
  degrau `treino` é aceita: cada um responde a uma pergunta diferente, e um
  guardrail mede a divergência.
- A fronteira mais instável passa a ser `nenhum`×`implementar` (a mesma
  hesitação que existia em estrito×amplo); o piloto mede a estabilidade por
  reteste.

## O que foi considerado e recusado

- **Alternativa mínima** (manter estrito/amplo e criar `exige_treino`): mais
  barata, mas deixava o leitor de treino como caso de exceção de um eixo
  pensado para outro leitor.
- **Escala de adoção com "só informa" como quinto degrau**: não era ordinal.
- **Perfil gravado por paper pela LLM**: um terceiro rótulo para calibrar, e
  derivável dos degraus.
- **Valer só daqui para frente**: dois regimes para sempre no banco, no painel
  e no Power BI, por uma economia de ~US$ 6,5.

## Adendo (21/10/2026): o painel HTML deixa o pré-requisito de fora

Depois da reclassificação total, a coluna de pré-requisito no painel, os perfis
de leitura e o Padrão Extraído se mostraram mais confusos do que úteis: os
rótulos dos degraus não se liam como uma escada, e o padrão repetia o achado e
"o que muda para você". O painel passa a categorizar por **natureza**, **área ›
sub-área** e **vertente**; a matriz do Panorama vira natureza × vertente; a marca
`falta_o_como` se chama "somente princípio". Nada muda no pipeline, no banco nem
no Power BI: `prerequisito`, os perfis (`vw_paper_perfil`) e o padrão continuam
gravados e exportados, e o padrão segue como passo de raciocínio do Estágio B.
