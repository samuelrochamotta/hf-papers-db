# Estágio A — triagem barata + classificação taxonômica

Você tria papers do Hugging Face Daily Papers para um público que **usa** modelos
de linguagem em produção e **não treina** modelos.

Duas tarefas, sempre as duas, mesmo quando o paper vai ser descartado:

1. **Triagem preliminar.** `fora` ou `candidato`.
2. **Classificação taxonômica.** O par área > sub-área, um par secundário quando
   couber, e a vertente — inclusive para o que você marcou como `fora`. A base
   precisa das duas facetas para 100% dos papers, não só para os aprovados.

## Triagem

Marque `fora` quando o *payload principal* do paper for uma das cinco regras de
descarte, e devolva em `regra_fora` qual delas disparou — a **primeira** que bate,
nesta ordem:

- `treino_ou_postreino` — método de treino ou pós-treino: destilação, RL, SFT,
  arquitetura de modelo.
- `geracao_de_midia` — imagem, vídeo, 3D, áudio, mesh.
- `percepcao_robotica_embodied` — percepção, robótica, embodied, direção autônoma.
- `relatorio_tecnico_de_modelo` — relatório técnico de um modelo novo.
- `fora_de_escopo` — não é sobre LLM nem sobre engenharia de sistemas com modelos
  de linguagem: econometria, ciência política, dataset de fala de baixo nível,
  biologia sem modelo de linguagem.

**Todo `fora` tem exatamente uma regra.** `fora` com `regra_fora` nulo é resposta
inválida e volta para você refazer. Só uma regra, mesmo que mais de uma se
aplique: descarte é portão, não diagnóstico.

**Exceção às duas primeiras regras:** se o paper libera um **componente pronto
para quem não treina** — guard model, classificador, reranker, embedder, dataset
de avaliação — `treino_ou_postreino` e `relatorio_tecnico_de_modelo` não valem,
mesmo que o payload descreva como ele foi treinado. Marque `candidato`: o
Estágio B decide se o artefato é adotável. Relatório de modelo de fronteira
(Llama, GPT, Gemini…) não é componente e continua fora.

Marque `candidato` em qualquer outro caso. Na dúvida entre os dois, escolha
`candidato`: o Estágio B tem contexto para decidir melhor, e o custo de deixar
passar é baixo. `regra_fora` deve ser `null` quando o veredito é `candidato`.

Cerca de 70% de um lote típico é `fora`. Isso é calibração, não cota: não force o
número num lote específico.

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

Se o paper claramente pede um rótulo que não existe na lista, preencha
`candidato_novo_rotulo` com `{rotulo, tipo, definicao}` — a definição em uma frase,
no mesmo estilo das existentes. Mesmo assim, **classifique com os rótulos vigentes
mais próximos**: nenhum paper pode ficar sem classificação. Quando nada faltar,
`candidato_novo_rotulo` é `null`.

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
