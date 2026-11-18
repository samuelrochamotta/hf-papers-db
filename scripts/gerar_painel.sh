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
#   scripts/gerar_painel.sh                        # janela padrao (90 dias)
#   scripts/gerar_painel.sh --force                # ignora a trava de run_id
#
#   # inspecao: SEMPRE com --destino, o painel publicado nao e rascunho
#   scripts/gerar_painel.sh --dias 10 --dias-hall 10 --force --destino /tmp/previa.html
#
#   # a mesma aba como ficara depois que o trimestre fechar (sem o aviso de
#   # consolidacao). O `=` e obrigatorio: sem ele o argparse le -30 como opcao.
#   scripts/gerar_painel.sh --dias 10 --dias-hall=-30 --force --destino /tmp/fechado.html
#
# --dias recorta so a aba viva. A aba historica segue refresh.janela_morna_dias
# do config.yaml; --dias-hall existe para inspeciona-la antes de o primeiro
# trimestre fechar, nao para a geracao diaria.

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

# O painel publicado e a pasta relatorios/painel/ (index.html, dados.json,
# fichas.json e o ECharts), que o workflow do GitHub Pages copia para o site.
PAINEL_DIR="relatorios/painel"

# Recorte na mao nao vai para o ar. `--dias`/`--dias-hall` mudam o QUE o painel
# mostra: com --dias 10 sao 270 papers em vez de 455, e os 185 que sobram nao
# aparecem em aba nenhuma. Publicar isso trocaria o painel do dia por um
# rascunho - e, como o run_id ja estaria carimbado, nem a rede de seguranca das
# 08:30 desfaria. Quem recorta na mao usa --destino e olha local.
PUBLICAVEL=1
for arg in "$@"; do
    case "$arg" in
        --dias|--dias=*|--dias-hall|--dias-hall=*|--destino|--destino=*) PUBLICAVEL=0 ;;
    esac
done

RAMO="$(git -C "$RAIZ" rev-parse --abbrev-ref HEAD 2>/dev/null || echo '?')"

# PR mergeado no GitHub deixa a `main` local para tras. Sem puxar, o painel sai
# do codigo velho e o push e recusado todo dia, deixando so um AVISO no log -
# foi o que parou o painel de 15 a 18/11/2026. Por isso a `main` e alinhada
# ANTES de gerar, e o painel sai do codigo que esta no GitHub.
if [ "$PUBLICAVEL" -eq 1 ] && [ "$RAMO" = "main" ]; then
    if ! git -C "$RAIZ" pull --rebase --autostash origin main >>"$LOG" 2>&1; then
        git -C "$RAIZ" rebase --abort >>"$LOG" 2>&1 || true
        echo "[$(date '+%Y-%m-%d %H:%M:%S')] AVISO: main nao alinhou com origin/main; o push deve falhar." | tee -a "$LOG"
    fi
fi

set +e
"$PYTHON_BIN" scripts/gerar_painel.py "$@" 2>&1 | tee -a "$LOG"
CODIGO=${PIPESTATUS[0]}
set -e

echo "[$(date '+%Y-%m-%d %H:%M:%S')] codigo de saida: $CODIGO" | tee -a "$LOG"

# Publica o painel no repo remoto so quando o script deu certo: o push dispara
# o deploy do GitHub Pages (.github/workflows/pages.yml).
#
# Este script roda sozinho no checkout de trabalho, entao:
# * so publica a partir de `main`: em outro branch o commit cairia nele e o
#   push de `main` iria sem o painel novo;
# * o commit leva so `$PAINEL_DIR` (`git commit -- <caminho>`), nunca o que
#   estiver em stage por outro motivo;
# * se o GitHub andou entre o pull acima e o push, puxa de novo. Se esse rebase
#   conflitar, aborta e desfaz o commit do painel: o painel e saida gerada, a
#   proxima rodada o refaz, e um commit preso aqui faria a `main` divergir de
#   novo todo dia.
publicar() {
    git -C "$RAIZ" add -A -- "$PAINEL_DIR" || return 1
    git -C "$RAIZ" commit -m "chore: atualiza painel ($(date '+%Y-%m-%d %H:%M'))" -- "$PAINEL_DIR" || return 1
    git -C "$RAIZ" push origin main && return 0
    if git -C "$RAIZ" pull --rebase --autostash origin main; then
        git -C "$RAIZ" push origin main && return 0
    else
        git -C "$RAIZ" rebase --abort 2>/dev/null || true
    fi
    git -C "$RAIZ" reset -q --mixed HEAD~1
    return 1
}

if [ "$CODIGO" -eq 0 ] && [ "$PUBLICAVEL" -eq 0 ]; then
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] geracao com recorte manual, nao publica." | tee -a "$LOG"
elif [ "$CODIGO" -eq 0 ] && [ -z "$(git -C "$RAIZ" status --porcelain -- "$PAINEL_DIR" 2>/dev/null)" ]; then
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] painel sem alteracoes, nada a publicar." | tee -a "$LOG"
elif [ "$CODIGO" -eq 0 ] && [ "$RAMO" != "main" ]; then
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] AVISO: checkout em '$RAMO', nao em main; painel gerado mas nao publicado." | tee -a "$LOG"
elif [ "$CODIGO" -eq 0 ]; then
    publicar >>"$LOG" 2>&1 || echo "[$(date '+%Y-%m-%d %H:%M:%S')] AVISO: falha ao publicar o painel no repo." | tee -a "$LOG"
fi

# rotacao: mantem 30 dias de log, igual ao run_daily.sh
find "$DIR_LOGS" -name 'painel_*.log' -mtime +30 -delete 2>/dev/null || true

exit "$CODIGO"
