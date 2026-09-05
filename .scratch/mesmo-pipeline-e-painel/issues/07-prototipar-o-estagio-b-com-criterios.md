# Prototipar o Estágio B com critérios

Type: prototype
Status: resolved
Blocked by: 06

## Question

O enum decidido no ticket 06 produz, na LLM real, vereditos e justificativas
que o usuário aceita? Rodar o prompt do Estágio B alterado (`criterios_veredito`
como lista, justificativa que aplica o critério, `regra_fora` obrigatória com
os seis rótulos do ticket 02) numa amostra de ~20 papers — HarnessDev, os 6
`fora` sem regra do ticket 02, e estritos/amplos de setembro — **sem gravar em
`fato_triagem`**: saída em arquivo no scratch, lado a lado com o veredito e a
justificativa atuais.

O usuário reage à tabela: critérios errados, justificativas que ainda
descrevem em vez de aplicar, `fora_de_escopo` engolindo demais.

Resolvido quando: o usuário aprova a amostra ou devolve ajustes ao enum (reabre
06). O prompt e o schema do protótipo ficam linkados como asset — são o
rascunho da implementação.

## Answer

(2026-09-04) **Pulado a pedido do usuário** — "acho menos relevante": em vez
de protótipo descartável, a implementação real foi despachada a um subagente,
com quatro decisões tomadas antes:

- critérios persistem em **`ponte_paper_criterio (paper_id, criterio)`**,
  esquema estrela como as outras pontes;
- fronteira fundamentada por **`fronteira_contraparte`** (ver ticket 06,
  revisado); incoerência ⇒ refazer uma vez, depois gravar com aviso;
- validação com **chamadas reais** em 6 papers via `reclassificar --paper`
  (HarnessDev, Ask or Answer, Control Their Own Attention, Verification-Aware
  Training, SafeAtlas-VL, 2608.29669) — gravam no banco, inócuo porque todos
  serão reclassificados na rodada total;
- **só backend** agora (schema, prompts, Estágios A/B, export, testes); o
  painel recebe os critérios no trilho dele.

O resultado da validação e o commit ficam registrados aqui quando o subagente
terminar.

### Resultado da implementação (2026-09-04, modelo `qwen/qwen3.8-flash` nos dois estágios)

Testes: 207 → 247 passando. Export com `ponte_paper_criterio.parquet` no
manifest; prévia do painel gerada sem erro (coluna nova não quebra nada).

| paper | antes | depois | critérios / regra | fronteira → contraparte | esperado? |
|---|---|---|---|---|---|
| HarnessDev `2609.01437` | amplo | **amplo** | `benchmark` | não | ✔ |
| Ask or Answer `2608.21721` | amplo | **estrito** | `padrao_arquitetural` | não | ✔ (padrão sem código é estrito) |
| Verification-Aware Training `2608.30135` | amplo | **fora** | `treino_ou_postreino` | não | ✔ |
| Wasserstein… (econometria) `2608.29669` | fora sem regra | **fora** | `fora_de_escopo` | não | ✔ |
| Control Their Own Attention `2609.02737` | amplo | **estrito** | `exige_acesso_interno` + `padrao_arquitetural` | sim → `exige_acesso_interno` | ✘ esperado amplo |
| SafeAtlas-VL `2608.29098` | estrito | **fora** | `treino_ou_postreino` (Estágio A) | — | ✘ esperado estrito · `artefato_aberto` |

Justificativas passaram a aplicar o critério ("AMPLO porque é benchmark: mede…;
não entrega…"; "ESTRITO por padrão arquitetural: …reproduzível pela descrição").

**Divergência 1 — *Control Their Own Attention*.** O modelo listou
`exige_acesso_interno` **e** `padrao_arquitetural`; estrito prevaleceu, e a
contraparte da fronteira é um critério que está na própria lista. A
justificativa se contradiz ("reproduzível pela descrição, mas exige modificação
no motor de inferência"). Expõe duas lacunas de regra: (a) `exige_acesso_interno`
deveria ser **excludente** — se a adoção exige acesso interno, nenhum critério
de estrito vale, porque estrito é "adota sem treinar/sem acesso interno";
(b) a contraparte não pode estar na lista do que vale. Decisão pendente do
usuário.

**Divergência 2 — *SafeAtlas-VL*.** O Estágio A cortou por
`treino_ou_postreino` ("payload é criar dataset de 1,5M e treinar guard
models"). Pela letra da regra 1 está certo; antes era estrito porque o B viu os
artefatos abertos (dataset, benchmark, modelo de 8B prontos). A tensão é real:
paper cujo payload é treino, mas que libera artefato pronto para uso. Decisão
pendente do usuário: artefato aberto pronto para uso sobrepõe a regra de treino
no Estágio A?

**Operacional.** O `qwen3.8-flash` raciocina antes de responder: o Estágio A
truncou em 1200 tokens em **todos** os 6 papers (8 retentativas). O teto de
`estagio_a.max_tokens` deveria subir para 2400.
