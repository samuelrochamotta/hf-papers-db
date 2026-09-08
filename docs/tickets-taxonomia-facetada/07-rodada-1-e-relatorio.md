# 07: Rodada 1 e relatório de massa

**O que construir:** a base inteira — cerca de 2.600 papers — classificada na grade v1,
**só no Estágio A**, e um relatório que diz se a grade se sustenta. É o ponto em que as
sub-áreas deixam de ser hipótese e viram medida.

O relatório responde às duas checagens objetivas da spec:

- nenhuma sub-área acima de ~25% da sua área — acima disso, falta ramificar;
- nenhuma vertente abaixo de ~2% — abaixo disso, o rótulo deve ser absorvido.

*Adaptar* e *Explicar* são as candidatas conhecidas a sumir: na classificação manual dos
127 aprovados, *Medir* ficaria com cerca de 40 e *Adaptar* com 3.

A rodada usa concorrência 4, conforme o ADR 001 — é espera de rede, e divide por N.
Vale também a consequência que o ADR registra: rodada interrompida no meio deixa papers
já pagos sem triagem, com o gasto visível no log de custos mas fora do custo da
execução.

**Bloqueado por:** 05, 06.

**Status:** ready-for-agent

- [ ] Backup do banco tomado antes da rodada
- [ ] Custo estimado apresentado antes de disparar
- [ ] Todos os papers da base com área, sub-área e vertente, incluindo os `fora`
- [ ] Uma única rodada, com `run_id` único em toda a triagem
- [ ] Nenhuma ficha nova gerada nesta etapa
- [ ] Relatório com a distribuição por sub-área e por vertente, e o resultado das duas
      checagens
- [ ] Relatório com a contagem de não-encaixes por eixo
- [ ] Custo real conferido contra a estimativa de US$ 0,54
