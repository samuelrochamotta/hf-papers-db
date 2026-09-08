# 01: Grade v1 como dado carregável

**O que construir:** o vocabulário novo passa a existir como dado — no arquivo de
taxonomia e no banco — **ao lado** do vocabulário antigo, sem que nada mude na
classificação. Quem inspeciona a taxonomia vê as dez áreas com suas sub-áreas
aninhadas sob elas e as nove vertentes com a definição que fixa o sentido de cada
verbo. A rodada diária continua funcionando exatamente como antes, na grade antiga.

Este é o passo de *expand*: nada quebra porque nada foi substituído ainda.

A hierarquia mora na própria dimensão de área, por auto-referência, e não numa tabela
irmã — área e sub-área são o mesmo tipo de coisa, e uma tabela só evita que as duas
definições divirjam:

```sql
-- area raiz tem area_pai NULL; sub-area aponta para o pai
ALTER TABLE dim_area ADD COLUMN area_pai TEXT NULL REFERENCES dim_area(area);
```

**Bloqueado por:** nenhum (pode começar imediatamente).

**Status:** done

- [x] O arquivo de taxonomia traz as 10 áreas, cada uma com suas sub-áreas, e as 9
      vertentes com a definição-complemento
- [x] A migração de schema roda sobre o banco existente sem perder nenhuma linha
- [x] Toda área raiz tem pai nulo e toda sub-área aponta para exatamente uma área
- [x] O comando de listar a taxonomia mostra a hierarquia aninhada e as vertentes
- [x] Exportar a taxonomia e recarregá-la num banco vazio reproduz a grade idêntica
- [x] A rodada diária continua gravando área e tópico na grade antiga, sem erro
- [x] Os testes de taxonomia existentes seguem verdes
