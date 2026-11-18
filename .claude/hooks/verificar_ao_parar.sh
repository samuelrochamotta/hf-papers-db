#!/usr/bin/env bash
# Hook Stop: roda format, lint, tipos e testes rápidos antes de o Claude parar.
# Falhou: imprime o problema em stderr com exit 2, e o Claude continua e corrige.
#
# Contra loop infinito:
#  1. stop_hook_active=true significa que o Claude já está continuando por causa
#     deste hook; nesse caso saímos 0 e deixamos parar (padrão da documentação).
#  2. Sem .py/.mjs/.js/.svelte alterado no checkout, não há o que verificar.
#  3. "timeout" no settings.json mata o hook se algo travar.
set -u

entrada=$(cat)

if [ "$(printf '%s' "$entrada" | jq -r '.stop_hook_active // false')" = "true" ]; then
  exit 0
fi

cd "$(printf '%s' "$entrada" | jq -r '.cwd // empty')" 2>/dev/null \
  || cd "${CLAUDE_PROJECT_DIR:-.}" || exit 0

if ! git status --porcelain 2>/dev/null | grep -qE '\.(py|mjs|js|svelte)$|pyproject\.toml$'; then
  exit 0
fi

PY=/opt/miniconda3/envs/digest-hf/bin/python
[ -x "$PY" ] || PY=python

falhas=""
rodar() {
  local nome=$1; shift
  local saida
  if ! saida=$("$@" 2>&1); then
    falhas+=$'\n'"=== $nome falhou: $* ==="$'\n'"$(printf '%s' "$saida" | tail -n 40)"$'\n'
  fi
}

rodar "format" "$PY" -m ruff format --check .
rodar "lint"   "$PY" -m ruff check .
rodar "tipos"  "$PY" -m mypy
# Só os rápidos: testes marcados com @pytest.mark.slow ficam de fora.
rodar "testes" "$PY" -m pytest -q -x -m "not slow" -p no:cacheprovider

if [ -n "$falhas" ]; then
  {
    echo "[Stop] Verificação falhou. Corrija e tente de novo:"
    printf '%s' "$falhas"
  } >&2
  exit 2
fi
exit 0
