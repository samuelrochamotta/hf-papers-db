#!/bin/bash
#
# Execucao diaria do hf-papers-db, para o launchd (macOS).
#
# Roda `python -m hfpapers run`, escreve a saida num log rotativo em logs/ e
# propaga o codigo de saida. Codigo != 0 fica registrado no log e o launchd
# marca a ultima execucao como falha (`launchctl list` mostra o status) - assim
# a falha aparece sem que ninguem precise ler o log toda hora.
#
# Uso:
#   scripts/run_daily.sh                # descobre os dias faltantes sozinho
#   scripts/run_daily.sh --data 2026-08-25

set -euo pipefail

RAIZ="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DIR_LOGS="$RAIZ/logs"
mkdir -p "$DIR_LOGS"

CARIMBO="$(date '+%Y-%m-%d_%H%M%S')"
LOG="$DIR_LOGS/run_$CARIMBO.log"

# Ambiente Python: ordem de procura - venv local, depois o conda env do
# projeto. Ajuste PYTHON_BIN se o ambiente ficar em outro lugar.
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
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] comando: $PYTHON_BIN -m hfpapers run $*"
} | tee -a "$LOG"

cd "$RAIZ"
set +e
"$PYTHON_BIN" -m hfpapers run "$@" 2>&1 | tee -a "$LOG"
CODIGO=${PIPESTATUS[0]}
set -e

echo "[$(date '+%Y-%m-%d %H:%M:%S')] codigo de saida: $CODIGO" | tee -a "$LOG"

# rotacao: mantem 30 dias de log
find "$DIR_LOGS" -name 'run_*.log' -mtime +30 -delete 2>/dev/null || true

exit "$CODIGO"
