# Como o voto amadurece

Type: grilling
Status: resolved
Blocked by: —

## Question

O usuário não conseguiu interpretar o gráfico. É problema de leitura ou do
gráfico?

## Answer

(Decidido na cartografia, 2026-09-04.) **É o gráfico.** Ele sobrepõe três
faixas P25–P75 em escala log e as amostras por idade não são comparáveis: só
papers antigos chegam ao dia 20, então a curva mostra sobrevivência, não
maturação.

Vira **uma curva única, normalizada**: % do voto final × dias desde o HF
Daily, sem separação por veredito, com o dia em que a mediana cruza 90%
marcado. A pergunta que responde: *em quantos dias o voto estabiliza?* (o
README já sabe: dia +6). A lista lateral "maior velocidade recente" fica.

O que "voto final" significa (último snapshot? só papers com idade ≥ 14 dias?)
e se a faixa P25–P75 volta numa curva só é assunto do ticket
[Prototipar a curva normalizada](09-prototipar-a-curva-normalizada.md).
