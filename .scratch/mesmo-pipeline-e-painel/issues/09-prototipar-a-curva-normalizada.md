# Prototipar a curva normalizada

Type: prototype
Status: resolved
Blocked by: —

## Question

A curva "% do voto final × dias desde o HF Daily" (ticket 05) diz alguma coisa
com os dados reais? Gerar o painel no scratch com o card substituído e reagir.
Decidir no protótipo: o que é "voto final" (último snapshot de papers com idade
≥ N dias — N=14 é o ponto em que o README mede movimento residual zero); se a
faixa P25–P75 entra; onde marcar o dia dos 90%; e se a lista "maior velocidade
recente" continua ao lado.

Consultar `dataviz` antes de desenhar. Gerar sempre com
`scripts/gerar_painel.sh --force --destino <scratch>/previa.html`.

Resolvido quando: o usuário olha o protótipo e aprova a forma, ou decide que
o card sai (opção (c) da cartografia).

## Answer

(2026-09-04) **Protótipo pulado a pedido do usuário**; decidido em conversa.
Preferências para a implementação:

- **Voto final** = último snapshot do paper; só entram na curva papers com
  idade ≥ 14 dias (hoje 185; cresce sozinho). Paper mais novo não tem "final".
- **Uma faixa P25–P75** atrás da mediana, escala **linear 0–100%**. Nada de
  log nem de faixas por veredito.
- **Marca dos 90%**: linha vertical tracejada no primeiro dia em que a mediana
  cruza 90%, rótulo "estabiliza por volta do dia +N".
- A lista lateral "maior velocidade recente" **continua**.
- Idade = dias desde `data_hf_daily`, como hoje.
