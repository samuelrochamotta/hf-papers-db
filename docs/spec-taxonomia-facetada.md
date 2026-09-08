# Spec — Taxonomia facetada: Área > Sub-área × Vertente

- **Data**: 2026-09-07
- **Estado**: **implementada** em 2026-09-08 (tickets 01 a 10)
- **Precede**: reescrita da classificação do Estágio A
- **Respeita**: `adr-001-fora-de-escopo-do-mapa.md` (uma fonte de verdade por decisão)
- **Corrigida por**: `adr-002-a-lista-de-vertentes.md` (a lista de nove verbos virou dez)

> **Leitura desta spec, agora que ela foi executada.** O texto abaixo está como
> foi escrito em 07/09, e o *Problem Statement* descreve a grade de tópicos que
> deixou de existir — é a causa registrada, não uma descrição do sistema atual.
> Onde o desenho foi derrubado pela medição, a nota está no ponto. O estado
> atual do sistema está no README (seção *A taxonomia facetada*); a medição
> vigente, em `relatorio-massa-grade-v2.md`.
>
> **O que a execução mudou em relação ao que esta spec previa:**
>
> | | previsto aqui | medido |
> |---|---|---|
> | base a classificar | ~2.600 papers | **3.166** (a coleta retroativa trouxe 2.641, +26% sobre a estimativa) |
> | sub-áreas | ~45 | 47 na v1, **64** na v2 |
> | vertentes | 9, com *Adaptar* e *Explicar* a sumir | **10**: nenhuma sumiu e `Treinar` entrou — ver ADR 002 |
> | custo total | ~US$ 1,35 | **US$ 3,30** de fatura (`log_llm`: rodada 1 US$ 1,2326, rodada 2 US$ 2,0675). O que virou triagem (`log_execucao`) foi US$ 3,27 |
> | tempo de máquina | ~3 h | **1,54 h** (31 min + 61,5 min, concorrência 4) |
> | par secundário | ~20% dos aprovados | **18,5% da base inteira** |
>
> As duas checagens objetivas do passo 5 da *Operação* **falham na v2**, e isso
> está registrado, não esquecido: 7 sub-áreas acima de 25% (eram 15) e 2
> vertentes abaixo de 2% (*Adaptar* 1,2%, *Especificar* 1,1%). A pendência é do
> ADR 002.

## Problem Statement

Os dois campos de classificação do Estágio A — `area_primaria` e `topicos` — comunicam
a mesma informação em resoluções diferentes, e por isso um deles não comunica nada.
Quem lê o painel não consegue perguntar "o que este trabalho **faz**", só "sobre o que
ele é" — duas vezes.

Quatro medições sobre os 516 papers da base sustentam o diagnóstico:

1. **Metade dos tópicos é área mais fina.** Áudio & fala está 96% dentro de Multimodal
   & percepção; Ataque adversarial, 77% dentro de Segurança; Descoberta científica,
   75% dentro de Dados & previsão. Saber o tópico não acrescenta nada a quem já sabe
   a área.
2. **O tópico mais frequente duplica outro campo.** "Validado em benchmark" (288
   papers, o mais atribuído de todos) coincide com o critério `benchmark` de
   `ponte_paper_criterio` em 88 de 89 casos.
3. **A área virou proxy da regra de descarte.** Duas das nove áreas concentram 57% da
   base e quase não têm aprovados: Multimodal & percepção (162 papers, 98% `fora`) e
   Treino & pós-treino (131 papers, 100% `fora`, zero aprovados). Elas não classificam
   assunto — marcam descarte, informação que `regra_fora` já dá com precisão maior.
4. **A pressão por vocabulário novo vem do que o produto recusa.** 140 dos 168
   candidatos acumulados (83%) nasceram de papers descartados — robótica, world
   models, geração 3D, difusão —, com famílias duplicadas (seis variantes de robótica;
   `World models` / `Modelos de mundo` / `World models & geração de vídeo`).

A causa é estrutural e está no prompt do Estágio A: ele pede "a área que melhor
descreve o payload principal" e "de 1 a 5 tópicos", **sem nunca dizer em que eixo os
dois campos diferem**. Sob essa instrução, o modelo só pode produzir duas listas de
assuntos, uma mais grossa que a outra — e joga no campo aberto tudo que não coube.

## Solution

Substituir os dois campos por **um sistema facetado de dois eixos ortogonais**, em que
cada campo responde a uma pergunta de tipo diferente:

- **ÁREA — *em que peça do sistema o trabalho mexe*.** Hierárquica: uma área raiz e
  uma sub-área sob ela. Dez áreas, cerca de 45 sub-áreas.
- **VERTENTE — *que movimento o paper faz com essa peça*.** Nove verbos que atravessam
  todas as áreas. É o único eixo transversal, e o teste de que é ortogonal: qualquer
  peça pode ser medida, barateada, endurecida ou explicada.

O teste que a grade atual falha e esta passa: **nenhuma coordenada é dedutível da
outra**. `MemUse` e `LycheeMemory V2` vivem na mesma sub-área (Contexto & recuperação >
Memória de longo prazo) e hoje são indistinguíveis; com a vertente, um **mede** e o
outro **barateia**.

Três áreas passam a nomear o descarte com honestidade — Modelo & treino, Geração de
mídia, Percepção & robótica — em vez de espremê-lo em rótulos que fingem discriminar.

### A grade

| Área | Sub-áreas |
|---|---|
| **Harness & orquestração** — o laço que chama o modelo: o que executar, em que ordem, com quais ferramentas | Auto-evolução do harness · Laço de execução & trajetória · Engenharia de código com agente · Sistemas multiagente · Pesquisa autônoma · Elicitação & requisito |
| **Contexto & recuperação** — o que entra na janela e de onde vem | RAG & recuperação · Memória de longo prazo · Compressão & alocação de contexto · Skills & conhecimento compilado · Verificação de fonte & citação |
| **Avaliação & instrumentação** — como o comportamento é medido | Benchmark de agente · Protocolo & metodologia · LLM como avaliador · Benchmark de domínio · Diagnóstico de falha · Custo da avaliação |
| **Serving & inferência** — como o token sai, da requisição ao hardware | Atenção, kernel & cache · Escala em tempo de inferência · Infraestrutura & deployment · Roteamento de modelos · Orçamento de token visual |
| **Guardrails & controle** — o que é barrado antes de acontecer | Política & conformidade · Injeção & delegação · Detecção de alucinação · Guard models · Risco & dano |
| **Internos do modelo** — o que acontece dentro dos pesos, como objeto de estudo | Interpretabilidade & sondas · Fidelidade do raciocínio · Atalhos & espúrios |
| **Interface & modalidade** — como humano e sistema trocam sinal | Fala & áudio · GUI & visão de tela · Vídeo & streaming · Documento & extração |
| **Modelo & treino** — como os pesos ficaram do jeito que estão | Pré-treino & arquitetura · Pós-treino & RL · Destilação & quantização · Dados de treino & sintéticos |
| **Geração de mídia** | Imagem & difusão · Vídeo & animação · 3D & cena · Áudio & música · World models generativos |
| **Percepção & robótica** | VLA & manipulação · Navegação & mundo físico · Sensores & percepção 3D · Rastreamento & detecção |

As nove vertentes, com o complemento que fixa o sentido e impede a leitura como tema:

```
Medir ......... cria o instrumento: benchmark, protocolo, métrica, auditoria
Baratear ...... reduz custo, latência, memória ou tokens
Endurecer ..... sustenta o comportamento sob ataque, ruído ou entrada fora da distribuição
Confiabilizar . reduz o erro silencioso: alucinação, calibração, atribuição
Automatizar ... tira o humano do laço: auto-evolução, síntese, busca automática
Explicar ...... torna legível o que já acontece: interpretabilidade, sondas, causalidade
Especificar ... formaliza o que se quer antes de executar: contrato, verificação, política
Adaptar ....... ajusta a um contexto, usuário ou domínio sem retreinar
Escalar ....... faz funcionar maior: horizonte, contexto, número de agentes
```

## User Stories

1. Como curador do acervo, quero que área e vertente respondam perguntas de tipos
   diferentes, para que os dois campos juntos digam mais do que cada um sozinho.
2. Como curador, quero saber em que peça do sistema um paper mexe, para localizá-lo na
   arquitetura que estou construindo.
3. Como curador, quero saber que movimento o paper faz, para distinguir quem mede um
   problema de quem o resolve.
4. Como curador, quero que um benchmark de memória e um sistema de memória caiam em
   células diferentes, para não confundir instrumento com solução.
5. Como curador, quero uma sub-área sob cada área, para navegar do geral ao específico
   sem perder o agrupamento.
6. Como curador, quero que a sub-área seja sempre filha de exatamente uma área, para
   que a hierarquia não tenha ambiguidade.
7. Como curador, quero um par secundário opcional (área > sub-área), porque 20% dos
   papers aprovados vivem legitimamente em duas peças do sistema.
8. Como curador, quero que o par secundário aceite a mesma área com sub-área diferente,
   para cobrir também o caso raro de um paper que atravessa duas sub-áreas irmãs.
9. Como curador, quero no máximo duas vertentes por paper, e ordenadas, para reconhecer
   o trabalho que genuinamente barateia e confiabiliza sem convidar ao preenchimento
   por inércia.
10. Como curador, quero que a primeira vertente seja a dominante, para que rankings e
    agregações tenham uma resposta única quando precisarem de uma.
11. Como curador, quero que os papers descartados também recebam área, sub-área e
    vertente, para que as regras de descarte fiquem revisáveis com dado, não com
    memória.
12. Como curador, quero que "Geração de mídia > World models generativos, descartado 95
    vezes" seja uma frase que a base sabe dizer, para poder contestar minha própria
    regra de descarte.
13. Como curador, quero que o modelo declare quando nenhuma célula serve, em vez de
    inventar um rótulo, para que o vocabulário pare de acumular sinônimos.
14. Como curador, quero que essa declaração diga em qual dos três eixos o encaixe
    falhou, para saber se a grade precisa de uma área nova, uma sub-área nova, ou se o
    problema é meu desenho das vertentes.
15. Como curador, quero que a vertente também aceite a declaração de não-encaixe,
    porque a lista de nove verbos é a hipótese mais frágil do sistema e precisa do seu
    próprio detector de erro.
16. Como curador, quero medir quantos papers cada sub-área recebeu, para decidir com
    dado se ela é real ou é ruído de um mês.
17. Como curador, quero uma amostra grande o bastante para essa medição, porque 127
    papers aprovados não dimensionam 45 sub-áreas.
18. Como curador, quero coletar três meses de papers anteriores ao início do pipeline,
    para levar a mediana da sub-área de cerca de 4 para cerca de 15 papers.
19. Como curador, quero que esses papers retroativos entrem na base de produção, para
    que a grade seja calibrada contra o que o painel realmente mostra.
20. Como leitor do painel, quero que o hall ganhe os trimestres anteriores, para ter
    acervo histórico onde hoje há 25 dias.
21. Como leitor do painel, quero que os aprovados retroativos tenham ficha, para que o
    hall não exiba aprovado sem conteúdo.
22. Como operador do pipeline, quero classificar os papers retroativos apenas com o
    Estágio A na primeira passada, para medir a grade antes de gastar com fichas.
23. Como operador, quero rodar a classificação em massa com concorrência, porque o ADR
    001 já estabeleceu que a rodada total é espera de rede e divide por N.
24. Como operador, quero saber o custo estimado antes de disparar, para não descobrir o
    gasto depois.
25. Como operador, quero que a segunda rodada corrija apenas o nível da sub-área, para
    que área e vertente validadas na primeira não sejam refeitas.
26. Como analista no Power BI, quero a sub-área e a vertente como colunas nos Parquet,
    para cortar o acervo pelos dois eixos.
27. Como analista, quero a ordem da vertente nos Parquet, para separar a dominante da
    secundária nas medidas.
28. Como desenvolvedor, quero que rótulo desconhecido continue sendo ignorado em vez de
    derrubar a classificação, preservando o comportamento atual.
29. Como desenvolvedor, quero que o teto de vertentes por paper seja aplicado na
    persistência, não só pedido no prompt, para que o contrato valha mesmo quando o
    modelo desobedecer.
30. Como desenvolvedor, quero que a taxonomia antiga saia da base inteira em vez de
    conviver versionada, para não carregar um filtro permanente em toda consulta por
    causa de dado que ninguém vai querer.
31. Como desenvolvedor, quero que os candidatos acumulados sejam descartados, porque a
    informação que carregavam já foi extraída e usada no desenho desta grade.
32. Como desenvolvedor, quero que o prompt declare explicitamente o eixo de cada campo,
    porque a ausência dessa frase é a causa raiz de todo o problema.
33. Como desenvolvedor, quero um teste que falhe se o par secundário de mesma área for
    rejeitado, porque a chave primária atual da ponte de área o proíbe.
34. Como desenvolvedor, quero que o diagnóstico do projeto continue saindo com código 0
    após a migração, para que a regressão apareça no dia em que aparecer.

## Implementation Decisions

### Eixos e cardinalidade

- Dois eixos ortogonais. **Área** é hierárquica em dois níveis (área raiz > sub-área);
  **vertente** é plana e transversal a todas as áreas.
- Um paper recebe: exatamente um par primário (área > sub-área), no máximo um par
  secundário (área > sub-área, podendo repetir a área do primário desde que a sub-área
  difira), e de uma a duas vertentes ordenadas — a de ordem 1 é a dominante.
- Toda a base recebe as três facetas, inclusive os papers `fora`. A faceta não depende
  do veredito.
- A grade nasce com 10 áreas e cerca de 45 sub-áreas. As áreas e as vertentes são
  tratadas como decisões firmes; **as sub-áreas são hipóteses** a serem confirmadas pela
  medição.

### Schema

`dim_area` passa a comportar os dois níveis pela auto-referência, em vez de ganhar uma
tabela irmã — a hierarquia é do mesmo tipo de coisa, e uma tabela só evita divergência
entre definições de área e de sub-área:

```sql
-- area raiz tem area_pai NULL; sub-area aponta para o pai
ALTER TABLE dim_area ADD COLUMN area_pai TEXT NULL REFERENCES dim_area(area);
```

A ponte de área ganha a sub-área **na chave primária**. A chave atual é
`(paper_id, area)` e proibiria o par secundário de mesma área — é a mudança que o teste
33 protege:

```sql
CREATE TABLE ponte_paper_area (
    paper_id    TEXT NOT NULL REFERENCES dim_paper(paper_id),
    area        TEXT NOT NULL REFERENCES dim_area(area),
    subarea     TEXT NOT NULL REFERENCES dim_area(area),
    is_primaria INTEGER NOT NULL,
    PRIMARY KEY (paper_id, area, subarea)
);
```

`dim_topico` e `ponte_paper_topico` são substituídas por `dim_vertente` e
`ponte_paper_vertente`. A ponte carrega a ordem, que é o que distingue dominante de
secundária:

```sql
CREATE TABLE ponte_paper_vertente (
    paper_id  TEXT NOT NULL REFERENCES dim_paper(paper_id),
    vertente  TEXT NOT NULL REFERENCES dim_vertente(vertente),
    ordem     INTEGER NOT NULL,   -- 1 = dominante
    PRIMARY KEY (paper_id, vertente)
);
```

`tax_candidato` muda de propósito: deixa de guardar rótulo sugerido e passa a registrar
o não-encaixe. O `tipo` aceita `area`, `subarea` e `vertente`; o registro carrega a
justificativa do modelo. A tabela é truncada na migração — os 168 candidatos existentes
descrevem uma grade que deixou de existir.

> **Implementado diferente, e melhor (ticket 04).** A tabela não mudou de propósito:
> foi **derrubada** e substituída por `tax_nao_encaixe`, com a coluna chamada `eixo`
> (não `tipo`) e chave primária em `paper_id`, não em `(paper_id, eixo)`. A razão da
> chave: o contrato do Estágio A traz no máximo uma declaração por paper, então
> reclassificar substitui a anterior em vez de deixar a de ontem pendurada num eixo
> que o modelo abandonou. Mudar de propósito uma tabela que guardava rótulo proposto
> teria deixado o nome mentindo sobre o conteúdo.

A migração **trunca e repovoa** as quatro tabelas de taxonomia. Não há coluna de versão
e não há convivência entre as duas grades: pelo princípio do ADR 001, uma fonte de
verdade por decisão. A rastreabilidade vem do `run_id` em `fato_triagem` e do histórico
do arquivo de taxonomia no git.

### Contrato do Estágio A

O JSON de saída da classificação passa a ter a forma abaixo. A mudança central é que
`topicos` desaparece e `candidato_novo_rotulo` — que pedia um rótulo inventado — dá
lugar a `nao_coube`, que pede uma constatação:

```json
{
  "area_primaria": "Contexto & recuperação",
  "subarea_primaria": "Memória de longo prazo",
  "area_secundaria": "Interface & modalidade",
  "subarea_secundaria": "Fala & áudio",
  "vertentes": ["Baratear", "Escalar"],
  "nao_coube": { "eixo": "subarea", "justificativa": "..." }
}
```

`area_secundaria`/`subarea_secundaria` e `nao_coube` são nulos na maioria dos papers, e
o prompt precisa dizer isso — hoje ele não diz para `areas_secundarias`, e a lista vazia
acabou virando exceção em vez de resposta comum.

### Prompt

A seção de classificação do prompt do Estágio A é reescrita para: declarar o eixo de
cada campo em uma frase cada ("área é *onde*, vertente é *o quê*"); apresentar a grade
aninhada, com as sub-áreas sob a área a que pertencem; dar o teste de decisão da
vertente — *"o paper mede isso, ou faz isso?"*; e afirmar que campo nulo é resposta
esperada, não falha.

Esta é a mudança que ataca a causa raiz. As demais são consequência dela.

### Módulos afetados

- **Taxonomia**: carga hierárquica do arquivo de vocabulário, validação dos três eixos,
  aplicação da classificação nas pontes, registro de não-encaixe, governança (listar,
  fundir, exportar, carregar).
- **Classificação (Estágio A)**: persistência das facetas novas; validação do JSON.
- **Export**: colunas de sub-área, vertente e ordem nos Parquet.
- **Painel**: passa a ler os campos novos sem introduzir corte por vertente nesta spec.
- **Testes**: os dublês de LLM compartilhados carregam `area_primaria` e `topicos`, e
  precisam acompanhar o contrato novo.

### Operação

Sequência contínua, sem intervenção humana — a correção da grade no passo 5 é
automática, governada por regras determinísticas:

1. Backup do banco antes de qualquer escrita.
2. Grade, schema, prompt, código e testes verdes.
3. Coleta retroativa de três meses (maio a agosto de 2026), forçando a data por dia, só
   os estágios de coleta e enriquecimento. Cerca de 2.100 papers a 5 requisições por
   segundo.
4. Primeira rodada, só Estágio A, sobre a base inteira (~2.600 papers), com
   concorrência 4.
5. **Correção automática**: medir a massa por sub-área e por vertente, e aplicar as
   regras em uma passada única — ramificar sub-área acima de ~25% da sua área (cada
   irmã com ao menos 5%), fundir sub-área abaixo de 3% da área ou de 10 papers,
   absorver vertente abaixo de ~2%, promover família de não-encaixe com oito papers de
   quórum. *Adaptar* e *Explicar* são as candidatas conhecidas a sumir. Travas: as dez
   áreas raiz, os dois eixos, a cardinalidade e o piso de seis vertentes não se mexem,
   e toda alteração cita o número que a motivou.
6. Segunda rodada com a grade v2, mais o Estágio B nos aprovados retroativos.
7. Export, diagnóstico, geração do painel.

Custos derivados do log de LLM da última rodada real (Estágio A: US$ 0,000256 e 9,7 s
por paper; Estágio B: US$ 0,000483 e 34 s): cerca de **US$ 1,35 e 3 h de máquina** no
total. A concorrência 4 segue o ADR 001, inclusive sua consequência conhecida — rodada
interrompida no meio deixa papers pagos sem triagem.

## Testing Decisions

Um bom teste aqui afirma **o que sai no banco e nos Parquet**, não como a função chegou
lá: nenhum teste deve conhecer a ordem das escritas, o nome de uma variável interna, ou
o texto do prompt. O contrato observável é o conteúdo das pontes e das dimensões.

**Nenhuma seam nova é introduzida.** Todo o comportamento desta spec é observável em
duas seams que já existem e já têm testes:

- **Aplicação da classificação na taxonomia** — a seam mais alta específica do
  vocabulário. Recebe as facetas e escreve as pontes. É onde ficam os testes de
  hierarquia (sub-área é filha da área declarada), cardinalidade (teto de duas
  vertentes aplicado na persistência, não só pedido no prompt), par secundário de mesma
  área com sub-área diferente, ordem das vertentes, e rejeição silenciosa de rótulo
  desconhecido. Prior art: os testes de teto de tópicos por paper e de rótulo
  desconhecido ignorado, que já existem e mudam de forma sem mudar de intenção.
- **Execução da classificação com o dublê de LLM** — a seam de ponta a ponta já usada
  pelos testes de concorrência e de critérios. Garante que o contrato JSON novo do
  Estágio A atravessa validação e persistência até o banco. Cobre a validação do
  schema sem criar seam própria para ela.

Os marts continuam cobertos pelos testes de export existentes, estendidos para as
colunas novas. O diagnóstico do projeto continua cobrindo a integridade do banco após a
migração.

Casos que merecem teste explícito por serem regressões plausíveis: par secundário com a
mesma área do primário (a chave primária atual o proibiria); paper com uma vertente só
(o caminho comum, que não pode exigir a segunda); paper `fora` com as três facetas
preenchidas; e não-encaixe registrado nos três eixos.

## Out of Scope

> **Depois da execução, as três exclusões que o ticket 10 nomeia — corte por
> vertente no painel, versionamento da taxonomia antiga e terceira faceta de
> domínio de aplicação — continuam de pé.** A razão de cada uma, com o que a
> medição acrescentou, está em `README.md`, seção *O que ficou de fora, e por
> quê*: é lá que o leitor vai procurar, e uma razão só tem uma casa.

- **Corte por vertente no painel.** A vertente é o único eixo transversal e é candidata
  natural a filtro, mas o painel é a última peça a mexer justamente porque depende de
  ver a distribuição real — e a grade ainda passa por uma segunda versão.
- **Versionamento da taxonomia antiga.** Decidido contra: uma fonte de verdade por
  decisão.
- **Promoção de qualquer um dos 168 candidatos acumulados.**
- **Regras de descarte e critérios de veredito.** Nenhuma muda. A taxonomia nova torna
  as regras revisáveis; revisá-las é outro trabalho.
- **Estágio B** além de rodá-lo nos aprovados retroativos. A ficha e os critérios não
  mudam.
- **Coleta retroativa além de três meses.** Extensível depois, ao mesmo custo por mês.
- **Terceira faceta de domínio de aplicação.** Avaliada e recusada: o único domínio
  recorrente na base é código, e ele já cai em Harness & orquestração.

## Further Notes

O desenho foi validado contra um caso que ele próprio previu. Ao classificar os 127
aprovados à mão, oito papers pareciam exigir duas sub-áreas da mesma área — e quatro
deles eram o mesmo par, `Harness > geração de código` com `Harness > especificação`.
Mas "especificação" não é irmã de "código": é a vertente **Especificar**. Com o eixo
transversal fazendo seu trabalho, a demanda por segunda sub-área cai de 6% para perto
de zero. A pressão sobre a hierarquia era pressão por um eixo que faltava — a mesma
patologia da grade atual, em escala menor, e a evidência mais forte de que separar os
eixos resolve o problema em vez de renomeá-lo.

A hipótese mais frágil é a lista de nove vertentes. Na classificação manual, *Medir*
ficaria com cerca de 40 dos 127 e *Adaptar* com 3. Se a distribuição se confirmar em
2.600 papers, *Adaptar* e *Explicar* devem ser absorvidas. É por isso que a vertente
aceita o registro de não-encaixe: é o instrumento que mede o erro do próprio desenho.

> **O parágrafo acima acertou a fragilidade e errou a previsão — `adr-002`.** O
> instrumento funcionou: 12 dos 13 não-encaixes de eixo `vertente` pediram
> literalmente o mesmo verbo, e a grade **ganhou** `Treinar` em vez de perder duas
> vertentes. *Explicar* ficou em 6,3% na v1, com folga de três vezes o piso; quem
> reprovou foi *Especificar* (1,5%), que esta spec não cita uma única vez. A régua
> dos 127 aprovados mede o que o produto **aprova**, e a grade classifica o que a
> base **tem** — 65% da qual é descartada.

A sub-área foi considerada como **substituta** da vertente, e os dados a recusaram
nesse papel: ela é 100% dedutível da área por construção, então não comunica informação
diferente — comunica a mesma em resolução mais fina. Como complemento, porém, ela se
sustenta, e é o que esta spec adota.
