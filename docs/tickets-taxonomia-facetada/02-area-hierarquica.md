# 02: Área hierárquica ponta a ponta

**O que construir:** um dia real classificado passa a gravar **em que peça do sistema**
o paper mexe e em que sub-área dela — e, quando o paper vive genuinamente em duas
peças, um segundo par. O prompt passa a declarar que a área responde *onde*, e a
apresentar a grade aninhada em vez de uma lista plana. Quem lê o painel e os Parquet
enxerga a sub-área.

O par secundário pode repetir a área do primário desde que a sub-área difira. A chave
primária atual da ponte de área proíbe isso, e é a mudança de maior risco do ticket:

```sql
CREATE TABLE ponte_paper_area (
    paper_id    TEXT NOT NULL REFERENCES dim_paper(paper_id),
    area        TEXT NOT NULL REFERENCES dim_area(area),
    subarea     TEXT NOT NULL REFERENCES dim_area(area),
    is_primaria INTEGER NOT NULL,
    PRIMARY KEY (paper_id, area, subarea)
);
```

**Decisão apurada na exploração do código:** o schema JSON do Estágio A injeta os
`enum` de vocabulário em tempo de execução, e JSON Schema não expressa "sub-área
válida *dado* que a área é X" sem um `oneOf` de dez ramos que nem todo provider trata
bem. A saída é **enum plano de todas as sub-áreas, com a validação de parentesco na
persistência** — que é o comportamento que já existe hoje para rótulo desconhecido:
ignora-se a atribuição, não se derruba a classificação.

**Bloqueado por:** 01.

**Status:** done

- [x] O contrato de saída do Estágio A pede área e sub-área primárias, e área e
      sub-área secundárias opcionais
- [x] O prompt declara em uma frase que a área responde *onde o trabalho mexe*
- [x] O prompt apresenta as sub-áreas aninhadas sob a área a que pertencem
- [x] O prompt afirma que o par secundário nulo é resposta esperada, não falha
- [x] Sub-área que não é filha da área declarada é ignorada, sem derrubar o paper
- [x] Par secundário com a mesma área do primário e sub-área diferente é gravado
- [x] Rodar um dia real grava o par primário para 100% dos papers classificados,
      inclusive os `fora`
- [x] Os Parquet e o painel expõem a sub-área
