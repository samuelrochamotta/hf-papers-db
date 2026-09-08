# 05: Contração — a grade antiga sai

**O que construir:** o vocabulário anterior deixa de existir. A dimensão de tópicos e
sua ponte são removidas; as nove áreas e os vinte e três tópicos antigos saem do banco;
o código que só existia para servi-los é apagado. O diagnóstico do projeto passa a
validar a grade nova e volta a sair com código 0.

Não há versionamento e não há convivência entre as duas grades. É o mesmo princípio que
o ADR 001 já aplicou ao veredito: **uma fonte de verdade por decisão**. A
rastreabilidade vem do `run_id` da rodada e do histórico do arquivo de taxonomia no
git, não de uma coluna de versão que toda consulta teria de filtrar para sempre.

Este é o passo irreversível do conjunto, e por isso está isolado: pode ser adiado sem
travar nada.

**Bloqueado por:** 03, 04.

**Status:** done

- [x] Backup do banco tomado antes da primeira escrita destrutiva
- [x] A dimensão de tópicos e sua ponte não existem mais no schema
- [x] Nenhuma área ou tópico do vocabulário anterior permanece no banco
- [x] Nenhum caminho de código ainda lê ou escreve o vocabulário antigo
- [x] O diagnóstico sem rede sai com código 0
- [x] A suíte de testes está verde, incluindo os dublês de LLM atualizados
