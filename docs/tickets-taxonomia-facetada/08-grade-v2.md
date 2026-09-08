# 08: Grade v2 a partir da medição

**O que construir:** a grade corrigida pelo que o relatório do ticket 07 mostrou, **sem
intervenção humana**. Sub-área inchada é ramificada; sub-área raquítica é fundida na
irmã; vertente sem massa é absorvida. Os não-encaixes registrados pelo ticket 04 são
lidos como fila e viram rótulo quando têm quórum.

A v1 foi desenhada sobre 127 títulos lidos à mão e é esperado que erre — foi para isso
que ela foi medida. Este ticket é o conserto, e ele é automático: as regras abaixo são
determinísticas o bastante para serem aplicadas a partir do relatório, sem julgamento
de fora.

## Regras de correção

Aplicadas em **uma única passada**, na ordem, nunca recursivamente:

1. **Ramificar** — sub-área acima de 25% da sua área é dividida em duas ou três irmãs,
   derivadas da leitura dos títulos daquele conjunto. A divisão só vale se **cada
   irmã ficar com pelo menos 5% da área**; se não ficar, a sub-área permanece como está
   e o caso é registrado.
2. **Fundir** — sub-área abaixo de 3% da sua área ou com menos de 10 papers é fundida
   na irmã de maior afinidade temática. **Exceção:** área com apenas duas sub-áreas não
   funde, para não ficar sem ramificação alguma.
3. **Absorver vertente** — vertente abaixo de 2% da base é absorvida pela vertente mais
   próxima, com o mapeamento declarado explicitamente no arquivo de taxonomia.
   *Adaptar* e *Explicar* são as candidatas conhecidas.
4. **Promover não-encaixe** — família de não-encaixes com **oito ou mais papers no mesmo
   eixo** vira rótulo novo. Abaixo desse quórum, fica registrada para a próxima medição.

## Travas

Nada aqui reabre o desenho, só o afina. O agente **não** altera: as dez áreas raiz, a
estrutura de dois eixos, a cardinalidade dos campos, nem o piso de seis vertentes — se
a regra 3 fosse derrubar a sétima vertente, ela para e registra em vez de aplicar.

Toda alteração precisa citar o número do relatório que a motivou. Alteração sem número
é alteração sem causa, e é o modo de falha que produziu a grade que estamos
substituindo.

**Bloqueado por:** 07.

**Status:** ready-for-agent

- [ ] Cada ajuste registra o número do relatório que o motivou
- [ ] Nenhuma sub-área da v2 acima de 25% da sua área, ou o caso está registrado com a
      razão pela qual a divisão foi rejeitada
- [ ] Nenhuma sub-área da v2 abaixo de 3% da sua área ou com menos de 10 papers, salvo
      a exceção das áreas com duas sub-áreas
- [ ] Nenhuma vertente da v2 abaixo de 2%, e no mínimo seis vertentes vivas
- [ ] Absorção de vertente com o mapeamento de origem e destino declarado no arquivo
- [ ] Cada família de não-encaixe com oito ou mais papers virou rótulo, ou está
      registrada com a razão de não ter virado
- [ ] As dez áreas raiz, os dois eixos e a cardinalidade intactos
- [ ] Uma única passada: nenhuma regra reaplicada sobre o resultado da anterior
- [ ] O arquivo de taxonomia atualizado, recarregável, e reproduzindo a grade ao ser
      exportado e relido
- [ ] Um resumo do que mudou entre v1 e v2, rótulo a rótulo, deixado para leitura
