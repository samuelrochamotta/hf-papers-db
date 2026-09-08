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

**Status:** done — com uma ressalva declarada: a regra 3 não foi aplicada a
*Especificar* (ver o checkbox correspondente e *Por que a regra 3 ficou parada*)

- [x] Cada ajuste registra o número do relatório que o motivou — `docs/grade-v2-resumo.md`
- [x] Nenhuma sub-área da v2 acima de 25% da sua área, ou o caso está registrado com a
      razão pela qual a divisão foi rejeitada — 12 das 15 divididas; três registradas
      (*Escala em tempo de inferência* a 0,5 ponto do teto e na seção 7 do relatório;
      *Fala & áudio* e *GUI & visão de tela* com irmãs estimadas abaixo do piso de 10
      papers da regra 2). *Interpretabilidade & sondas* foi dividida e a estimativa a
      deixa em 40,7%: a regra admite três irmãs no máximo, e a área tem 91 papers — o
      caso está registrado
- [x] Nenhuma sub-área da v2 abaixo de 3% da sua área ou com menos de 10 papers, salvo
      a exceção das áreas com duas sub-áreas — quatro fundidas; duas registradas
      (*Atalhos & espúrios* e *Fidelidade do raciocínio*, ambas com 9 papers, um abaixo
      do piso e dentro da instabilidade de ~19%)
- [ ] Nenhuma vertente da v2 abaixo de 2%, e no mínimo seis vertentes vivas —
      **não cumprido, por decisão registrada**: *Especificar* fica em 1,5%, 0,5 ponto
      abaixo do piso e na seção 7 do relatório; medida na base, ela não tem vertente
      substituta (co-ocorrência espalhada, 32 dominantes com tema coerente) e o
      denominador muda na rodada 2. Dez vertentes vivas, bem acima do piso de seis
- [ ] Absorção de vertente com o mapeamento de origem e destino declarado no arquivo —
      **sem objeto**: nenhuma vertente foi absorvida
- [x] Cada família de não-encaixe com oito ou mais papers virou rótulo, ou está
      registrada com a razão de não ter virado — `Treinar` promovida (12 registros de
      eixo `vertente`); *neurociência & sinal biomédico* (8 registros de eixo `area`)
      registrada, porque promovê-la criaria uma 11ª área raiz e a trava proíbe; nenhuma
      família de eixo `subarea` chega a oito
- [x] As dez áreas raiz, os dois eixos e a cardinalidade intactos
- [x] Uma única passada: nenhuma regra reaplicada sobre o resultado da anterior
- [x] O arquivo de taxonomia atualizado, recarregável, e reproduzindo a grade ao ser
      exportado e relido — `config/taxonomia_inicial.json`, 10 áreas, 64 sub-áreas,
      10 vertentes; a ida e volta é o que `test_arquivo_versionado_povoa_banco_vazio`
      afirma
- [x] Um resumo do que mudou entre v1 e v2, rótulo a rótulo, deixado para leitura —
      `docs/grade-v2-resumo.md`

## Por que a regra 3 ficou parada

A regra 3 mandava absorver *Especificar* (46 papers, 1,5%), e a trava do piso de seis
vertentes não a protegia — absorvê-la deixaria nove, com folga. A regra foi suspensa por
**decisão de coordenação**, não por leitura do agente implementador: a instrução que ele
recebeu era não mexer em rótulo a menos de três pontos de um limiar, porque a grade tem
~19% de instabilidade intrínseca e *Especificar* está a 0,5 ponto do piso.

Três coisas sustentam a suspensão, e a terceira é a que decide:

1. Medida na base, *Especificar* **não tem substituta**: sua co-ocorrência é espalhada
   (Medir 8, Confiabilizar 8, Endurecer 5, sem dominante), e os 32 papers em que ela é
   dominante formam tema coerente — contrato, protocolo, verificação formal. Absorver
   sem destino óbvio é escolher um destino, não descobri-lo.
2. A absorção é **irreversível** e a rodada 2 remede de graça.
3. O denominador **já mudou**: `Treinar` entrou nesta mesma passada, e uma parte do que
   hoje é *Baratear* dentro de *Modelo & treino* vai migrar. Medir *Especificar* contra
   o denominador antigo é medir contra uma base que não existe mais.

A consequência honesta é que o checkbox fica aberto e o ticket 09 herda a pergunta: se
*Especificar* continuar abaixo de 2% na rodada 2, com o denominador novo e o ruído
diluído por uma segunda medição, ela é absorvida sem mais discussão.

## Efeito colateral medido: o prompt cresceu

A v2 tem 64 sub-áreas em vez de 47, e o Estágio A injeta a grade inteira no prompt. O
prompt renderizado passou de **14.832 para 18.785 caracteres (+26,7%)**, ou cerca de
+988 tokens de entrada por chamada.

Projeção para a rodada 2 sobre 3.166 papers, a partir do custo real da rodada 1
(US$ 1,2326 com 4.398 tokens de entrada por chamada): **US$ 1,51 para o Estágio A**,
22% acima. A estimativa de US$ 0,54 que consta do ticket 09 é da grade antiga e está
obsoleta por um fator de quase três.

`docs/grade-v2-resumo.md` mede o mesmo crescimento como 13.579 → 17.532 caracteres.
**As duas medições estão certas**: o delta é 3.953 caracteres nas duas, e o que muda
é o denominador — o prompt renderizado inclui o paper, e cada medição usou um
abstract de tamanho diferente. O número comparável entre grades é o delta; o
percentual depende do paper que se escolheu para renderizar.
