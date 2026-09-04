# Cores e formas dos gráficos

Type: grilling
Status: resolved
Blocked by: —

## Question

Quatro dos cinco pedidos de gráfico são decisões de cor e forma: heatmap
Tópico × tempo por vista, matriz de cruzamentos com total e aprovados, cor da
linha "aprovado", e a linha amarela de "Onde o pipeline corta".

## Answer

(Decidido na cartografia, 2026-09-04.)

- **Tópico × tempo**, uma escala por vista: `volume` = sequencial azul;
  `crescimento` = **divergente** (vermelho = caiu, cinza = estável, verde =
  cresceu — crescimento tem sinal); `aprovação` = sequencial verde.
- **Matriz área primária × secundária** ("Cruzamentos"): matriz de bolhas —
  **cor = taxa de aprovação, tamanho do marcador = total**. Célula grande e
  verde = muitos papers, muito aprovados; grande e cinza = muitos, poucos.
- **Verde `#4ec07a` = aprovado** em todo o painel (linha da Taxa de aprovação,
  escala de aprovação do heatmap, cor da matriz). O amarelo `ACCENT` volta a
  ser só link/destaque. Estrito e amplo mantêm azul e laranja.
- **Onde o pipeline corta**: sai a linha do acumulado (o usuário a chamou de
  "linha amarela" e não conseguiu ler — com seis regras ela é decorativa).
  Cada barra ganha o rótulo "n · % dos descartados". Com a regra obrigatória,
  a barra "regra não registrada" tende a zero, mas continua existindo no código
  para nunca esconder dado.
