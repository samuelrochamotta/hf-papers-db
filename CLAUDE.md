# CLAUDE.md

## Ambiente

- Python local: `/opt/miniconda3/envs/digest-hf/bin/python` (env conda
  `digest-hf`). Na nuvem, instale com `uv pip install -e ".[dev]"`.
- Testes: `python -m pytest -q`. É a porta única: sem rede, com banco em
  `tmp_path`, e já roda a suíte JS do painel via `node --test`.
- Lint e tipos: `python -m ruff check .` e `python -m mypy`. O CI roda os três.

## Vocabulário

`CONTEXT.md` é o glossário. Releia o verbete antes de nomear um conceito do
domínio em código, docs ou commits, e use o termo dele no lugar dos listados em
_Avoid_.

## Custo e dados

- `run`, `reclassificar` e `ler` chamam o OpenRouter e custam dinheiro. Estime
  com `run --dry-run`, limite o `ler` com `--limite` e peça confirmação antes de
  uma rodada real. `reclassificar` e `ler` não têm dry-run.
- `data/hfpapers.db` é a fonte e não tem versão. Experimente numa cópia ou com
  as fixtures de `tests/`.
- Antes de rodar, interromper ou retomar uma rodada, ou de mexer em `llm.*` no
  `config.yaml`, leia `docs/adr/003-tres-chaves-do-openrouter.md`.

## Classificação e taxonomia

Antes de mexer em `prompts/`, nos estágios A/B ou na grade, leia
`docs/adr/004-natureza-e-prerequisito.md`, o ADR da área tocada em `docs/adr/`
e a spec correspondente em `docs/specs/`.

## Painel

`relatorios/painel/` e `relatorios/painel-v2/` são gerados; edite a fonte.

- **v1:** `scripts/gerar_painel.py` e `scripts/painel_app.js`. Gere a prévia
  com `python scripts/gerar_painel.py --force --destino /tmp/previa.html`.
- **v2:** o front-end fica em `painel-v2/` (Svelte), e os dados vêm de
  `scripts/gerar_painel_v2.py`. Antes de mexer, leia
  `docs/adr/007-painel-v2.md`.

As abas, o agendamento e a publicação estão no `README.md`, nas seções
"Agendamento", "Painel HTML" e "Painel v2".

## Git

- Mensagens de commit curtas, em português.
- `main` recebe um commit diário automático do painel. Faça
  `git pull --rebase` antes de dar push.
- **Sessão local:** todo dia, entre ~07:30 e 08:30, o launchd roda
  `scripts/gerar_painel.sh` neste checkout.
  - O script faz `git pull --rebase --autostash` em `main`, gera o painel e
    commita só `relatorios/painel/`.
  - Fora de `main`, ele não publica.
  - Por isso trabalhe num worktree e mantenha este checkout em `main`, sem
    trabalho em andamento.
  - Quando o painel para, a causa aparece como `AVISO` em `logs/painel_*.log`.
