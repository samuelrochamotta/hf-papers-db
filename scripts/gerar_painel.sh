#!/bin/bash
#
# Geracao do painel HTML estatico, para o launchd (macOS).
#
# Roda DEPOIS do pipeline, nao junto: o gatilho e `WatchPaths` em
# marts/_manifest.json, que o estagio de export escreve por ultimo e de forma
# atomica (os.replace). Ou seja, este job so acorda quando o run_daily.sh
# terminou de materializar os Parquet - nao e um horario chutado com folga.
#
# WatchPaths pode disparar mais de uma vez para a mesma escrita; a trava de
# run_id dentro de gerar_painel.py faz o disparo extra sair em no-op.
#
# Uso:
#   scripts/gerar_painel.sh              # janela padrao (30 dias)
#   scripts/gerar_painel.sh --dias 60
#   scripts/gerar_painel.sh --force      # ignora a trava de run_id

set -euo pipefail

RAIZ="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DIR_LOGS="$RAIZ/logs"
mkdir -p "$DIR_LOGS"

LOG="$DIR_LOGS/painel_$(date '+%Y-%m-%d_%H%M%S').log"

# Mesma ordem de procura do run_daily.sh - venv local, depois o conda do projeto.
if [ -x "$RAIZ/.venv/bin/python" ]; then
    PYTHON_BIN="$RAIZ/.venv/bin/python"
elif [ -x "/opt/miniconda3/envs/digest-hf/bin/python" ]; then
    PYTHON_BIN="/opt/miniconda3/envs/digest-hf/bin/python"
else
    PYTHON_BIN="$(command -v python3 || true)"
fi

if [ -z "$PYTHON_BIN" ]; then
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] ERRO: nenhum interpretador Python encontrado." | tee -a "$LOG"
    exit 2
fi

{
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] raiz:   $RAIZ"
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] python: $PYTHON_BIN"
} | tee -a "$LOG"

cd "$RAIZ"
set +e
"$PYTHON_BIN" scripts/gerar_painel.py "$@" 2>&1 | tee -a "$LOG"
CODIGO=${PIPESTATUS[0]}
set -e

echo "[$(date '+%Y-%m-%d %H:%M:%S')] codigo de saida: $CODIGO" | tee -a "$LOG"

# rotacao: mantem 30 dias de log, igual ao run_daily.sh
find "$DIR_LOGS" -name 'painel_*.log' -mtime +30 -delete 2>/dev/null || true

exit "$CODIGO"
