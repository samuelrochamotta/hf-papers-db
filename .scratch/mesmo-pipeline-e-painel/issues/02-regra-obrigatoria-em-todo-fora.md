# Regra obrigatória em todo `fora`

Type: grilling
Status: resolved
Blocked by: —

## Question

"Todo paper `fora` tem regra registrada" é falso hoje por desenho: o prompt
manda descartar por reprovação no teste de portabilidade e por assunto fora de
escopo, mas o enum de `regra_fora` só tem os quatro rótulos de conteúdo. Como
corrigir na origem?

## Answer

(Decidido na cartografia, 2026-09-04.)

- Dois rótulos novos no enum: **`portabilidade_reprovada`** (o Estágio B
  reprovou o padrão — nome próprio ou generalidade) e **`fora_de_escopo`** (não
  é sobre LLM / engenharia de sistemas: econometria, ciência política, dataset
  de fala…). Os seis rótulos, na ordem de teste: `treino_ou_postreino`,
  `geracao_de_midia`, `percepcao_robotica_embodied`,
  `relatorio_tecnico_de_modelo`, `fora_de_escopo`, `portabilidade_reprovada`.
- O schema **exige** `regra_fora` não nula quando `veredito = fora`. Resposta
  sem regra é rejeitada e o paper volta à fila — mesmo tratamento da
  justificativa vazia (`validar_justificativa`).
- `regra_fora` continua **única**: descarte é portão, não diagnóstico; a
  primeira regra que bate na ordem basta. Isso mantém o Pareto somando 100%.

Evidência dos 6 casos de rodadas normais sem regra: `2608.22071` (dataset de
fala), `2608.28695` (generalidade + percepção), `2608.27509` (ciência
política), `2608.29669` (econometria), `2609.01507` (treino, mas o modelo
deixou nulo), `2609.04034` (mídia, idem) — os dois últimos mostram que sem a
exigência no schema o modelo às vezes nem preenche a regra que existe.

### Adendo (2026-09-04)

**Exceção do componente adotável**, no Estágio A: `treino_ou_postreino` e
`relatorio_tecnico_de_modelo` não valem quando o paper libera componente pronto
para quem não treina (guard model, classificador, reranker, embedder, dataset
de avaliação) — passa como candidato e o B decide entre `artefato_aberto` e
fora. Relatório de modelo de fronteira continua fora. Caso: *SafeAtlas-VL*
morria no portão por treino; com a exceção, estrito · `artefato_aberto` +
`benchmark`, sem fronteira.
