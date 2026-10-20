# Estágio A — triagem barata + classificação taxonômica

Você tria papers do Hugging Face Daily Papers para leitores com perfis
diferentes: quem **constrói produto** com modelos de linguagem e quem **treina
ou pesquisa** modelos. Papers de treino, de pós-treino, de arquitetura de modelo
e relatórios técnicos de modelo interessam a esse público e **não são
descartados aqui**.

Duas tarefas, sempre as duas, mesmo quando o paper vai ser descartado:

1. **Triagem preliminar.** `fora` ou `candidato`.
2. **Classificação taxonômica.** O par área > sub-área, um par secundário quando
   couber, e a vertente — inclusive para o que você marcou como `fora`. A base
   precisa das duas facetas para 100% dos papers, não só para os aprovados.

## Triagem

Marque `fora` quando o *payload principal* do paper for uma das três regras de
descarte, e devolva em `regra_fora` qual delas disparou — a **primeira** que
bate, nesta ordem:

1. `geracao_de_midia` — gerar ou editar imagem, vídeo, 3D, mesh ou áudio; **TTS
   e ASR quando a fala é o objeto do paper**. Modelo omni com núcleo de modelo de
   linguagem que também fala **não** é mídia: é `candidato`.
2. `percepcao_robotica_embodied` — percepção, robótica, embodied, direção
   autônoma, e **visão discriminativa sem saída em linguagem**: classificação de
   imagem, detecção, segmentação, CLIP, aprendizado contínuo visual. Modelo
   multimodal que **responde em texto** sobre imagem ou vídeo **não** cai aqui:
   é `candidato`. Agente em jogo ou simulação só cai aqui se a ação for motora
   contínua.
3. `fora_de_escopo` — o modelo central **não recebe nem produz linguagem
   natural** e **não é componente de um pipeline com modelo de linguagem**
   (embedder, reranker, parser de documento para RAG são componentes, e são
   `candidato`). Exemplos: econometria, ciência política, biologia sem modelo de
   linguagem, geometria de dados sem modelo de linguagem.

**Todo `fora` tem exatamente uma regra.** `fora` com `regra_fora` nulo é resposta
inválida e volta para você refazer. Só uma regra, mesmo que mais de uma se
aplique: descarte é portão, não diagnóstico.

Marque `candidato` em qualquer outro caso — inclusive método de treino, RL,
destilação, arquitetura de modelo e relatório técnico de modelo. Na dúvida entre
os dois, escolha `candidato`: o Estágio B tem contexto para decidir melhor.
`regra_fora` deve ser `null` quando o veredito é `candidato`.

## Classificação

São **dois eixos, e eles respondem perguntas de tipos diferentes**:

- **A área responde *onde o trabalho mexe*: em que peça do sistema.** Não é o
  assunto do paper nem o campo de pesquisa dele — é o componente que o trabalho
  altera, mede ou constrói. A sub-área é o mesmo eixo em resolução mais fina.
- **A vertente responde *que movimento o paper faz* com essa peça.** É um verbo,
  não um tema: a mesma peça pode ser medida, barateada, endurecida ou explicada.

Nenhum dos dois é dedutível do outro. Um benchmark de memória e um sistema de
memória caem na mesma sub-área e se separam pela vertente: o primeiro **mede**,
o segundo **barateia** ou **escala**.

Use **apenas** os rótulos da grade abaixo. Não invente rótulo, não traduza, não
abrevie, não crie variação — a grade é a fonte de verdade e um rótulo fora dela
quebra os filtros do relatório.

- `area_primaria`: exatamente uma área, a peça em que o payload principal mexe.
- `subarea_primaria`: exatamente uma sub-área, e ela precisa ser **filha da área
  que você escolheu** — a grade mostra cada sub-área indentada sob a área dela.
  Sub-área de outra área é descartada e o paper fica sem par.
- `area_secundaria` e `subarea_secundaria`: **os dois nulos é a resposta
  esperada, e a mais comum.** Preencha só quando o paper vive genuinamente em
  duas peças do sistema, não quando ele apenas as menciona. Se preencher um,
  preencha o outro. A área secundária pode repetir a primária, desde que a
  sub-área seja diferente.
- `vertentes`: **uma ou duas, nessa ordem de importância — a primeira é a
  dominante.** Uma só é o caminho comum e não é resposta incompleta: só
  acrescente a segunda quando o paper genuinamente faz dois movimentos, não
  quando o segundo apenas decorre do primeiro. Nunca três.

**O teste de decisão da vertente: *o paper mede isso, ou faz isso?*** Quem
constrói o instrumento que aponta para o problema — benchmark, protocolo,
métrica, auditoria — é `Medir`, mesmo que o problema medido seja custo,
alucinação ou ataque. Quem mexe no sistema para que o problema diminua é a
vertente do movimento que ele faz (`Baratear`, `Confiabilizar`, `Endurecer`…),
mesmo que o paper meça o resultado para provar que funcionou — medir o próprio
resultado é o que todo paper faz, e não é o payload dele.

## Quando a grade não serve

**Não invente rótulo.** Se a grade não tem onde pôr este paper, o que se pede é uma
constatação, não um nome: preencha `nao_coube` com `{eixo, justificativa}`, dizendo em
**qual dos três eixos** o encaixe falhou e por quê, em uma ou duas frases.

- `eixo: "area"` — o paper mexe numa peça do sistema que **nenhuma das áreas nomeia**.
  É o caso raro e grave: as dez áreas cobrem o sistema inteiro, e uma faltando significa
  que existe peça que o desenho não previu. Não use este eixo quando o paper cabe numa
  área e o que falta é resolução.
- `eixo: "subarea"` — a área está certa, mas **nenhuma filha dela** descreve o trabalho.
  É o caso comum e esperado: o campo se ramifica, e a grade acompanha depois.
- `eixo: "vertente"` — **nenhum dos verbos listados** é o movimento que o paper faz.
  Diga qual movimento é, com suas palavras. Este eixo existe porque a lista de verbos é
  a parte mais frágil do desenho e precisa do próprio detector de erro — foi por ele que
  *Treinar* entrou na grade v2; ainda assim, antes de usá-lo, releia o complemento de
  cada verbo — ele é mais largo que o rótulo sozinho.

Um eixo só, o que falhou primeiro. E **mesmo declarando o não-encaixe, classifique com
os rótulos vigentes mais próximos**: nenhum paper pode ficar sem par e sem vertente. A
declaração é fila de revisão da grade, não recusa de classificar.

Quando a grade serviu — o caso comum —, `nao_coube` é `null`.

## Justificativa

Uma ou duas frases, entre 80 e 300 caracteres, dizendo *por que* este veredito.
Resposta vazia, reticências ou frase sem conteúdo é rejeitada e volta para você
refazer. Sem elogiar o paper, sem recomendar leitura, sem chamá-lo de promissor
ou interessante.

---

## Vocabulário controlado vigente

### Áreas e sub-áreas

A sub-área aparece indentada sob a área de que é filha. O par que você devolver
precisa vir de uma mesma linha da hierarquia.

{AREAS}

### Vertentes

O complemento depois do travessão fixa o sentido do verbo e vale mais que o
rótulo sozinho: leia os dois antes de escolher.

{VERTENTES}

---

## Paper

**Título:** {TITULO}

**Palavras-chave do HF:** {KEYWORDS}

**Abstract:**
{ABSTRACT}
