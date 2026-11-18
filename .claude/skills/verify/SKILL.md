---
name: verify
description: Como verificar mudanças neste repo rodando a CLI `hfpapers` e os painéis, sem gastar com o OpenRouter.
---

# Verificar mudanças em digest-hf-papers

## Python

Use `/opt/miniconda3/envs/digest-hf/bin/python`. O pacote `hfpapers` é uma
instalação editável que aponta para o checkout principal.

**Em worktree**, exporte `PYTHONPATH=$PWD/src`. Sem isso você roda o código do
checkout principal e a mudança não é exercitada. O worktree não tem `.env` nem
`data/`: a chave some e o banco nasce vazio.

## Comandos sem custo

- `python -m hfpapers doutor --sem-rede`: diagnóstico de config, chave, banco e
  triagem. Só lê, não chama rede. É o teste de fumaça da CLI.
- `python -m hfpapers run --dry-run`: estima o custo de uma rodada.
- `python -m hfpapers schema`: cria/migra o banco e imprime o DDL.
- Painel v1: `python paineis/v1/gerar_painel.py --force --destino /tmp/previa.html`
  e abra o HTML. Mudança visual exige captura de tela (CLAUDE.md).
- Painel v2: front-end em `paineis/v2/` (Svelte), dados de
  `paineis/v2/gerar_painel_v2.py`. Leia `docs/adr/007-painel-v2.md` antes.

## Não rode sem confirmar

`run`, `reclassificar` e `ler` chamam o OpenRouter e custam dinheiro.
`reclassificar` e `ler` não têm dry-run. Peça confirmação e limite o `ler` com
`--limite`.

## Cuidados

- `data/hfpapers.db` é a fonte e não tem versão. Para mexer, use uma cópia.
- `.env` do checkout principal fornece a chave: `env -u OPENROUTER_API_KEY` não
  a remove. Para forçar o estado `erro` de `chave`, use um worktree sem `.env`.
- `relatorios/painel/` e `relatorios/painel-v2/` são gerados; não edite.
- O launchd publica o painel todo dia entre ~07:30 e 08:30 neste checkout.
  Mudança sem commit na `main` suspende a publicação do dia; prefira worktree.
- Opção errada, como `--semrede`, dá `No such option` com exit 2.
