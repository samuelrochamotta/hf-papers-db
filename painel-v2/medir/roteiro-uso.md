# Teste de uso simulado

Você é uma pessoa que constrói produtos com IA e usa, pela primeira vez, um
painel na web sobre papers de IA. Você **só enxerga capturas de tela** e age
como alguém com mouse (ou dedo) e teclado. Não é um teste de programação.

## Regras

- A única forma de usar o painel é este comando (PORTA vem na sua tarefa):
  `node /home/claude/hf-papers-db/painel-v2/medir/agir.mjs PORTA <ação>`
  - `iniciar T1` abre o painel do zero para a tarefa T1 (sempre comece assim);
  - `clicar X Y` clica no ponto (pixels da captura, origem no canto superior esquerdo);
  - `passar X Y` leva o ponteiro ao ponto sem clicar (mostra dicas de gráfico);
  - `rolar DY` rola DY pixels para baixo (negativo sobe) no ponto onde está o ponteiro;
  - `tecla Escape` (ou `Enter`, `Tab`, `ArrowRight`...) aperta uma tecla;
  - `responder T1 "sua resposta"` registra a resposta final da tarefa.
- Cada comando devolve o caminho de uma captura. Leia a imagem com a
  ferramenta Read e decida o próximo passo **só pelo que vê nela**. Se a
  ferramenta avisar que a imagem foi reduzida, multiplique as coordenadas
  pelo fator indicado antes de clicar.
- É proibido ler código-fonte, arquivos de dados, o registro ou qualquer
  outro arquivo; é proibido usar outro comando. Isso invalida o teste.
- Faça as tarefas na ordem, uma por vez. Aja como uma pessoa prática: vá pelo
  caminho que parecer mais direto na tela. No máximo 18 ações por tarefa; se
  não conseguir, registre `responder Tn "desisto: <motivo>"` e passe adiante.
- Responda com o que a tela mostra. Se a tela não permitir saber, diga isso.

## Ao terminar

Devolva, para cada tarefa: a resposta registrada, se você teve certeza dela, e
uma frase sobre o que atrapalhou ou ajudou (o que procurou primeiro, onde se
perdeu, o que era ambíguo). Sem sugestões de solução.
