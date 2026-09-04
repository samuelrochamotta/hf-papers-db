# Critério de veredito

Type: grilling
Status: resolved
Blocked by: —

## Question

A justificativa do veredito é texto livre e por isso às vezes descreve o paper
em vez de dizer por que ele é estrito ou amplo (caso HarnessDev, `2609.01437`).
E o usuário suspeita que a régua real virou "usável em produção hoje ⇒ estrito".
Que forma dá objetividade ao veredito?

## Answer

(Decidido na cartografia, 2026-09-04.)

- O Estágio B ganha **`criterios_veredito`: lista com pelo menos um item** de um
  enum. Um paper pode se qualificar por dois critérios (biblioteca aberta +
  benchmark). **Quais** critérios entram no enum é o ticket
  [Enum de critérios estrito/amplo](06-enum-de-criterios-estrito-amplo.md).
- **Estrito prevalece**: basta um critério de estrito para o veredito ser
  estrito, porque a definição é "entrega artefato adotável" — se entrega,
  entrega; o benchmark é contexto. Mistura de lados é permitida e é o sinal
  natural para `decisao_fronteira`.
- A **justificativa aplica o critério** ao paper ("AMPLO porque é benchmark: mede
  X, não entrega Y"), em vez de descrever o paper.
- No painel: a ficha mostra "AMPLO · benchmark + achado empírico", e entra o
  gráfico **"por que o pipeline aprova"** (espelho do Pareto, uma barra por
  critério, dividida entre estrito e amplo) — último ticket do trilho do painel.
- Rubrica com pontuação foi descartada (ver *Out of scope* no mapa).
