# 03: Vertente substitui tópico ponta a ponta

**O que construir:** o mesmo dia real passa a gravar **que movimento o paper faz** com
a peça em que mexe: de uma a duas vertentes, ordenadas, com a dominante em primeiro.
O campo de tópicos desaparece do contrato. O prompt ganha a frase que faltava — a
vertente responde *o quê*, a área responde *onde* — e o teste de decisão que separa os
dois: *"o paper mede isso, ou faz isso?"*.

É o ticket que resolve a confusão de origem: um benchmark de memória e um sistema de
memória deixam de ser indistinguíveis.

A ordem é o que distingue a vertente dominante da secundária, e mora na ponte:

```sql
CREATE TABLE ponte_paper_vertente (
    paper_id  TEXT NOT NULL REFERENCES dim_paper(paper_id),
    vertente  TEXT NOT NULL REFERENCES dim_vertente(vertente),
    ordem     INTEGER NOT NULL,   -- 1 = dominante
    PRIMARY KEY (paper_id, vertente)
);
```

**Bloqueado por:** 02 — não por dependência técnica, mas para que o contrato de saída e
o prompt sejam tocados uma vez de cada vez.

**Status:** done

- [x] O contrato de saída do Estágio A pede de uma a duas vertentes, ordenadas
- [x] O prompt declara em uma frase que a vertente responde *que movimento o paper faz*
- [x] O prompt traz as nove vertentes com o complemento que fixa o sentido de cada uma
- [x] O prompt traz o teste de decisão que separa medir de fazer
- [x] O teto de duas vertentes é aplicado na persistência, não só pedido no prompt
- [x] Paper com uma vertente só é o caminho comum e não exige a segunda
- [x] A vertente de ordem 1 é recuperável como dominante em consulta e nos Parquet
- [x] Rodar um dia real grava vertente para 100% dos papers classificados, inclusive
      os `fora`
- [x] O painel exibe a vertente no lugar do tópico
