# 10: Documentação

**O que construir:** o repositório passa a descrever o sistema que ele de fato tem. O
modelo de dados documenta as facetas novas e a hierarquia; a spec sai de *proposta* para
*implementada*, com os números reais no lugar das estimativas; e o registro de como o
diagnóstico deve se comportar acompanha a grade nova.

Vale documentar também o que **não** foi feito e por quê, porque essas ausências são
decisões: o corte por vertente no painel, o versionamento da taxonomia, e a terceira
faceta de domínio de aplicação — avaliada e recusada porque o único domínio recorrente
na base é código, e ele já cai em Harness & orquestração.

Se a rodada 1 tiver derrubado alguma decisão do desenho — a lista de nove vertentes é a
candidata —, o registro dessa mudança de rumo vale um ADR próprio.

**Bloqueado por:** 09.

**Status:** ready-for-agent

- [ ] O modelo de dados documenta área hierárquica, sub-área, vertente e ordem
- [ ] A spec marcada como implementada, com custo e tempo reais medidos
- [ ] A distribuição final por área, sub-área e vertente registrada
- [ ] As três exclusões de escopo documentadas com a razão de cada uma
- [ ] Nenhuma referência ao vocabulário de tópicos permanece na documentação
