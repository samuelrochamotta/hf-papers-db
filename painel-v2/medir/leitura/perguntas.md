# Teste de leitura

Você é uma pessoa que constrói produtos com IA e olha, pela primeira vez, telas de um painel sobre papers de IA. Responda **só com o que cada imagem mostra**. Não é um teste de programação.

## Regras

- Sua pasta de imagens vem na tarefa. Leia as sete imagens com a ferramenta Read, uma por vez, na ordem dos nomes (1-indice.png ... 7-comparar-celular.png).
- É proibido ler qualquer outro arquivo ou pasta, rodar comandos ou usar subagentes. Isso invalida o teste.
- Responda cada pergunta olhando só a imagem indicada. Se a imagem não permitir saber, responda exatamente `não dá para saber`. Não chute.
- Seja curto: nomes, números, poucas palavras.
- No fim, grave as respostas no arquivo JSON indicado na tarefa (use a ferramenta Write), neste formato:
  `{"Q1": "...", "Q2": "...", ..., "Q21": "...", "confianca": {"1": 4, "2": 5, "3": 3, "4": 4, "5": 4, "6": 4, "7": 3}, "dificuldades": {"1": "...", "3": "..."}}`
  - `confianca`: de 1 (chutei) a 5 (li direto), uma nota por imagem.
  - `dificuldades`: por imagem, uma frase sobre o que atrapalhou a leitura (deixe de fora as imagens sem dificuldade). Sem sugestões de solução.

## Perguntas

Imagem 1 (1-indice.png): a primeira tela do painel.
- Q1. Qual é o esforço de adoção do paper CoworkOS e o que ele liberou (código, pesos, dados)?
- Q2. Qual é o ganho do paper Confucius4-R2T2 contra o rival?
- Q3. Entre os papers que aparecem nesta tela, qual é o mais votado com prova forte?
- Q4. Quantos papers aparecem por inteiro nesta tela?

Imagem 2 (2-filtro.png): a mesma tela em outro estado.
- Q5. A tela mostra todos os papers ou só uma parte? Que parte, e quantos papers são?
- Q6. Onde você clicaria para voltar a ver todos os papers? Diga o texto do elemento.

Imagem 3 (3-prova.png): um gráfico.
- Q7. Quantos papers têm prova forte?
- Q8. Quais papers têm votos acima da mediana e prova frágil ou básica? Dê os nomes.
- Q9. Qual é, aproximadamente, a mediana de votos?

Imagem 4 (4-ganho.png): um gráfico.
- Q10. Qual paper tem o maior ganho contra o rival, e de quanto?
- Q11. Quantos papers perdem do rival (ganho negativo)?
- Q12. Qual é o ganho do paper Sage-Taiyi?

Imagem 5 (5-adocao.png): um gráfico.
- Q13. Quantos papers pedem só integrar?
- Q14. Em qual nível de esforço há mais papers?
- Q15. Entre os papers que pedem só integrar, quantos têm prova firme ou forte?

Imagem 6 (6-comparar.png): comparação de três papers (SLA, Harness-S e Confucius4-R2T2).
- Q16. Qual dos três tem a prova mais sólida?
- Q17. Qual dos três é o mais difícil de adotar?
- Q18. Em quais eixos o Harness-S fica abaixo da mediana do recorte?
- Q19. Qual dos três tem mais votos, e quantos votos?

Imagem 7 (7-comparar-celular.png): a mesma comparação numa tela de celular.
- Q20. Qual dos três tem o maior ganho, e de quanto?
- Q21. Em amplitude, o Confucius4-R2T2 está acima ou abaixo da mediana do recorte?
