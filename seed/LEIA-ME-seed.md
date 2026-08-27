# Arquivos-semente do backfill

Tudo o que o `python -m hfpapers backfill --seed ./seed` precisa já está aqui.
Copie esta pasta inteira para `<raiz-do-projeto>/seed/`. **Nada a baixar à parte.**

```
seed/
├── hf-digest-estado.json          241 ids com veredito e upvotes do dia 1
├── taxonomia.json                 vocabulário controlado + 83 classificações curadas
└── digests/                       8 digests diários, 83 fichas ao todo
    ├── hf-digest-2026-08-14.md         9 fichas
    ├── hf-digest-2026-08-17.md        11
    ├── hf-digest-2026-08-18.md        12
    ├── hf-digest-2026-08-19.md        12
    ├── hf-digest-2026-08-20.md         6
    ├── hf-digest-2026-08-21.md        10
    ├── hf-digest-2026-08-24.md         9
    └── hf-digest-2026-08-25.md        14
```

O `hf-digest-2026-W34.md` (consolidação semanal) foi deixado de fora de propósito:
é índice derivado, sem informação que os diários não tenham.

## Papel de cada arquivo

**`taxonomia.json` é autoritativo.** 8 áreas, 23 tópicos, os tetos de vocabulário,
a regra de promoção de candidato a rótulo, 5 candidatos pendentes e 83 papers já
classificados à mão. O backfill importa essas classificações **como estão**; não as
regenera com LLM. Verificado: nenhum rótulo órfão, nenhum paper acima do teto de
5 tópicos, tetos respeitados.

**`hf-digest-estado.json` é registro histórico — mantenha verbatim.** 241 ids
(159 fora, 28 amplo, 54 estrito). Tem um furo conhecido, descrito abaixo. Não o
corrija: o backfill contorna pela união das fontes.

**Os digests diários são conjunto de validação, não fonte de verdade.** As 83
fichas neles foram escritas pelo pipeline antigo e revisadas. O backfill regenera
as fichas pelo pipeline novo e depois compara, para você medir se o prompt novo
reproduz a qualidade do antigo. Se a comparação for ruim, o prompt do Estágio B
precisa de ajuste — não as fichas antigas.

## Furo conhecido: `2608.14577`

O paper **`2608.14577`** ("HarmProfile: Characterizing Harmful Distributions in
Frontier LLMs") aparece com ficha completa no digest de 18/08 e tem classificação
no `taxonomia.json`, mas **está ausente do `estado.json`**. A rodada daquele dia
gravou o digest e perdeu o id ao atualizar o estado.

Por isso a lista de trabalho do backfill é a **união** das três fontes:

| Fonte | ids |
|---|---|
| `hf-digest-estado.json` | 241 |
| `taxonomia.json` | 83 |
| fichas nos digests | 83 |
| **união** | **242** |

Um backfill que use só o `estado.json` produz 241 papers e 82 fichas — e está
errado. O número correto é **242 papers, 83 fichas** (55 estrito + 28 amplo).

## Integridade verificada

- `taxonomia.json` parseia; nenhum rótulo de área ou tópico órfão nas 83 classificações.
- Cada digest tem as 5 seções numeradas (`## 1.` a `## 5.`) e o número de fichas
  bate com `Amplo + Estrito` da sua própria tabela de Operação — os 8, sem exceção.
  Use isso como teste do parser.
- Sem mojibake, sem truncamento; acentuação e travessões preservados.
