# Enum de critérios estrito/amplo

Type: grilling
Status: resolved
Blocked by: —

## Question

Quais critérios entram no enum de `criterios_veredito`, com que definição de
uma frase cada, e que teste separa dois critérios vizinhos?

Ponto de partida: os cinco de estrito que já estão em
`prompts/regras_classificacao.md` §3 (padrão arquitetural reproduzível,
biblioteca/infra aberta, achado que invalida prática corrente, vulnerabilidade
explorável, técnica de avaliação transferível) e os quatro de amplo (benchmark,
survey, relato de sistema em escala não reproduzível, framework conceitual sem
instrumento) mais o "princípio passou mas falta o como".

A suspeita a testar: a régua real virou "usável em produção hoje ⇒ estrito,
senão amplo". Se for isso, ou os critérios de estrito estão frouxos demais
para o que o usuário quer, ou faltam critérios de amplo que capturem "informa
decisão sem entregar artefato" de forma mais fina.

Grelhar com papers reais nas mãos: HarnessDev (`2609.01437`, amplo — benchmark
+ achado), e uma amostra de estritos e amplos das rodadas de setembro
(`SELECT paper_id, veredito, justificativa FROM fato_triagem WHERE run_id LIKE
'run-202609%'`). Para cada um: com o enum proposto, qual(is) critério(s) ele
receberia — e o usuário concorda?

Resolvido quando: enum fechado (nome, lado, definição de uma frase), regra de
precedência confirmada (estrito prevalece — ticket 03) e o texto novo de §3
das regras rascunhado no ticket.

## Answer

(Resolvido em 2026-09-04, com os 52 aprovados de setembro como prova.)

### O diagnóstico

A régua real do modelo virou **"tem código adotável sem treinar ⇒ estrito;
senão ⇒ amplo"**: 19 dos 31 amplos de setembro justificam com "não entrega
biblioteca/ferramenta pronta para produção", inclusive um padrão arquitetural
(*Ask or Answer*, 2608.21721) — o que contradiz §3, que faz de "padrão
reproduzível" um critério pleno. E 7 amplos caem num balde sem nome: técnica
válida que **exige treino ou acesso interno** (ativações, engine, kernel).

### As três réguas que o prompt passa a dizer com todas as letras

1. **Código aberto é um critério, não a régua.** Padrão arquitetural
   reproduzível pela descrição é estrito mesmo sem código dos autores — o
   leitor escreve o código dele; o que precisa é o desenho.
2. **"Prática corrente" = o que o leitor plausivelmente faz hoje.** Só isso faz
   um achado empírico virar `invalida_pratica`. "Deixar o agente evoluir o
   próprio harness" não é prática de ninguém ⇒ o achado do HarnessDev é
   contexto, e ele fica `benchmark`, amplo. "Monitorar o raciocínio para
   detectar desvio" é prática ⇒ *CoT Faithfulness* é estrito. A justificativa
   **nomeia a prática invalidada** quando usa o critério 3.
3. **Treino como payload ⇒ fora (regra 1); acesso interno como pré-requisito
   de adoção ⇒ amplo (`exige_acesso_interno`).** *Verification-Aware Training*
   é sobre treinar: fora. *Language Models Can Control Their Own Attention* é
   achado sobre inferência que só roda controlando a engine: amplo.

### O enum — 10 critérios

**Estrito** — entrega algo que o leitor adota sem treinar:

| critério | definição | exemplo (set/2026) |
|---|---|---|
| `padrao_arquitetural` | desenho reproduzível pela descrição, sem depender do código dos autores | *Control-Data Flow Separation*, *PaperCompiler*, *StepGuard* |
| `artefato_aberto` | biblioteca, modelo, dataset, checkpoint ou kernel aberto e usável | *SafeAtlas-VL*, *Random Attention*, *Gated DeltaNet* |
| `invalida_pratica` | achado empírico que contradiz algo que o leitor faz hoje | *Lost in Compression*, *Sliding-window beats linear attention*, *CoT Faithfulness* |
| `vulnerabilidade` | falha explorável com mecanismo descrito | *Agent Memory Is a Surface for Authorization Laundering* |
| `tecnica_de_avaliacao` | método de avaliação ou diagnóstico transferível para outro domínio | *Grounded Theory for Agent Behavior*, *EarlyEval*, *Knowledge-Gated Tasks* |

**Amplo** — informa a decisão, não entrega o que adotar:

| critério | definição | exemplo (set/2026) |
|---|---|---|
| `benchmark` | mede capacidade; o artefato é o instrumento de medida | *HarnessDev*, *RealSWE*, *AgentJudgeBench* |
| `panorama` | sistematiza o que já existe (survey, taxonomia), sem propor nem medir nada novo | *MMMMM* |
| `framework_conceitual` | modelo mental sem instrumento | *Agents in the Large*, *Recursive Criticality*, *The Safeguard Worked* |
| `principio_sem_o_como` | o padrão passou no teste de portabilidade, mas o paper não diz como implementar | *PaperBanana-Interact*, *EM²Mem* |
| `exige_acesso_interno` | técnica válida que pede ativações, engine de inferência, kernel ou retreino para ser adotada | *CRISP*, *Cross-lingual Functional Vectors*, *Control Their Own Attention* |

`relato_em_escala` foi cortado (1 paper em 52; o "X fez Y com 10 mil GPUs" cai
em `framework_conceitual` ou `principio_sem_o_como`, conforme o que sobra do
paper). Nomes rejeitados para `panorama`: `survey_ou_taxonomia`,
`estado_da_arte` (soa elogio), `sistematizacao` (abstrato demais no painel).

### Precedência e fronteira

- `criterios_veredito` é lista com ≥1 item. **Estrito prevalece**: um critério
  de estrito basta (ticket 03).
- `decisao_fronteira` continua **declarada pelo modelo, mas fundamentada** por
  um campo próprio, **`fronteira_contraparte`** — *o que quase venceu* —
  obrigatório quando a flag é `true`, nulo caso contrário. O valor vem de um
  enum unificado: as 6 regras de descarte ∪ os 10 critérios. Cobre as três
  fronteiras: estrito↔amplo (contraparte é critério do outro lado),
  aprovado→fora (contraparte é regra de descarte) e fora→aprovado (contraparte
  é critério). *(Revisado em 2026-09-04: a versão anterior fundamentava só
  com "critério do outro lado na lista", e isso deixava `fora` sem fronteira
  possível.)*
- A lista `criterios_veredito` é só **o que vale**; o "quase" mora na
  contraparte. Dois lados na lista **não** obrigam fronteira (*SafeAtlas-VL* é
  artefato aberto + benchmark e não é fronteira de nada).
- Coerência cobrada em código: a contraparte tem que ser de lado **diferente**
  do veredito. Se violar, refazer uma vez; se insistir, gravar como veio com
  aviso `fronteira_incoerente:<paper_id>`. A flag **nunca** vira `false` pela
  nossa mão.
- O Estágio A continua sem fronteira: é "descarte primeiro, sem análise"; se
  tem dúvida, deixa passar como `candidato`.
- Hoje 36% dos aprovados são fronteira sem fundamento; isso deve cair.

### Rascunho do §3 novo de `prompts/regras_classificacao.md`

> ## 3. ESTRITO vs AMPLO — por critério, não por impressão
>
> O veredito de um aprovado é a consequência dos **critérios** que ele
> satisfaz. Liste todos que valem (um ou mais); o veredito segue a lista:
> **qualquer critério de estrito ⇒ estrito**; só critérios de amplo ⇒ amplo.
>
> **ESTRITO** — entrega algo que o leitor adota sem treinar modelo:
> `padrao_arquitetural`, `artefato_aberto`, `invalida_pratica`,
> `vulnerabilidade`, `tecnica_de_avaliacao`. *(definições da tabela acima)*
>
> **AMPLO** — informa a decisão, não entrega o que adotar: `benchmark`,
> `panorama`, `framework_conceitual`, `principio_sem_o_como`,
> `exige_acesso_interno`.
>
> Três réguas que decidem os casos difíceis:
> - **Código aberto é um critério, não a régua.** Padrão reproduzível pela
>   descrição é estrito sem código dos autores.
> - **Prática corrente é o que o leitor faz hoje.** Só um achado que contradiz
>   isso é `invalida_pratica`; conclusão de benchmark sobre prática que ainda
>   não existe é contexto, e o paper fica `benchmark`. Nomeie a prática.
> - **Treino como payload é FORA (regra 1). Acesso interno como pré-requisito
>   de adoção é AMPLO** (`exige_acesso_interno`).
>
> `decisao_fronteira` verdadeira exige `fronteira_contraparte`: a regra de
> descarte ou o critério do outro lado que quase venceu. A **justificativa
> aplica o critério ao paper** ("AMPLO porque é benchmark: mede X, não entrega
> Y"); não descreve o paper.

Próximo passo: [Prototipar o Estágio B com critérios](07-prototipar-o-estagio-b-com-criterios.md) — pulado a pedido do usuário; a implementação foi direto (ver o ticket).
