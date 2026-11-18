#!/usr/bin/env bash
# Hook PostToolUse (Edit|Write): formata e roda lint nos arquivos .py editados.
# Lê o JSON do evento no stdin. Erros de lint saem em stderr com exit 2,
# para o Claude vê-los e corrigir.
set -u

arquivo=$(jq -r '.tool_input.file_path // empty')

case "$arquivo" in
  *.py) ;;
  *) exit 0 ;;
esac
[ -f "$arquivo" ] || exit 0

PY=/opt/miniconda3/envs/digest-hf/bin/python
[ -x "$PY" ] || PY=python

"$PY" -m ruff format "$arquivo" >/dev/null 2>&1

if ! saida=$("$PY" -m ruff check "$arquivo" 2>&1); then
  echo "ruff check encontrou problemas em $arquivo:" >&2
  echo "$saida" >&2
  exit 2
fi
