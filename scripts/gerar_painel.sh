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
GRAVA_NO_CHECKOUT=1   # 0 so com --destino: a previa grava fora de $PAINEL_DIR
for arg in "$@"; do
    case "$arg" in
        --dias|--dias=*|--dias-hall|--dias-hall=*) PUBLICAVEL=0 ;;
        --destino|--destino=*) PUBLICAVEL=0; GRAVA_NO_CHECKOUT=0 ;;
    esac
done

SUSPENSA=0   # trabalho em andamento ou pull que falhou: gera, mas nao publica
RAMO="$(git -C "$RAIZ" rev-parse --abbrev-ref HEAD 2>/dev/null || echo '?')"
CARIMBO="$RAIZ/marts/.painel_run_id"

# O painel e saida gerada: o que sobrou dele no checkout (de uma rodada que nao
# publicou) e descartado, e o carimbo do run_id vai junto para o gerador
# refazer o painel inteiro em vez de sair em no-op sobre uma arvore suja.
# Volta indice E arvore ao HEAD: so a arvore deixaria o painel em stage (de um
# `git add` cujo commit falhou), e o `pull --rebase` recusa indice sujo todo dia.
descartar_painel() {
    git -C "$RAIZ" restore -q --source=HEAD --staged --worktree -- "$PAINEL_DIR" 2>/dev/null || true
    git -C "$RAIZ" clean -fdq -- "$PAINEL_DIR" 2>/dev/null || true
    rm -f "$CARIMBO"
}

# PR mergeado no GitHub deixa a `main` local para tras. Sem puxar, o painel sai
# do codigo velho e o push e recusado todo dia, deixando so um AVISO no log -
# foi o que parou o painel de 15 a 18/11/2026. Por isso a `main` e alinhada
# ANTES de gerar, e o painel sai do codigo que esta no GitHub.
#
# Sem `--autostash`: trabalho em andamento neste checkout (mudanca rastreada
# fora de `$PAINEL_DIR`, em stage ou nao) suspende o pull e a publicacao da
# rodada, com AVISO. Stash automatico que conflita some com o trabalho sem
# deixar rastro no log.
# Merge, rebase, cherry-pick ou revert em andamento, ou conflito nao resolvido
# no indice, sao de quem esta trabalhando: a rodada nao toca em nada - nem
# descarta nem gera o painel -, para nao apagar o estado do conflito.
operacao_em_andamento() {
    local p
    for p in MERGE_HEAD CHERRY_PICK_HEAD REVERT_HEAD rebase-merge rebase-apply; do
        [ -e "$(git -C "$RAIZ" rev-parse --git-path "$p")" ] && return 0
    done
    [ -n "$(git -C "$RAIZ" ls-files -u)" ]
}

# Sai antes de gerar, em qualquer branch (no rebase o HEAD fica destacado): o
# gerador reescreveria os arquivos do painel em conflito e apagaria os
# marcadores de quem esta resolvendo. Vale tambem para `--dias`/`--dias-hall`
# sem `--destino`, que gravam no checkout; so a previa com `--destino` escapa.
if [ "$GRAVA_NO_CHECKOUT" -eq 1 ] && operacao_em_andamento; then
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] AVISO: merge/rebase ou conflito em andamento no checkout; nao gera nem publica nesta rodada." | tee -a "$LOG"
    exit 0
fi

if [ "$PUBLICAVEL" -eq 1 ] && [ "$RAMO" = "main" ]; then
    if [ -n "$(git -C "$RAIZ" status --porcelain --untracked-files=no -- . ":(exclude)$PAINEL_DIR")" ]; then
        echo "[$(date '+%Y-%m-%d %H:%M:%S')] AVISO: trabalho em andamento no checkout; nao puxa nem publica nesta rodada." | tee -a "$LOG"
        SUSPENSA=1
    else
        if [ -n "$(git -C "$RAIZ" status --porcelain -- "$PAINEL_DIR")" ]; then
            descartar_painel
        fi
        if ! git -C "$RAIZ" pull --rebase origin main >>"$LOG" 2>&1; then
            git -C "$RAIZ" rebase --abort >>"$LOG" 2>&1 || true
            echo "[$(date '+%Y-%m-%d %H:%M:%S')] AVISO: main nao alinhou com origin/main; nao publica nesta rodada." | tee -a "$LOG"
            SUSPENSA=1
        fi
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
# * o commit leva so `$PAINEL_DIR` (`git commit -- <caminho>`);
# * se o GitHub andou entre o pull acima e o push, puxa de novo. Se esse rebase
#   conflitar, aborta, desfaz so o commit do painel e descarta o painel: um
#   commit preso aqui faria a `main` divergir de novo todo dia, e a proxima
#   rodada refaz o painel do zero.
publicar() {
    git -C "$RAIZ" add -A -- "$PAINEL_DIR" || return 1
    git -C "$RAIZ" commit -m "chore: atualiza painel ($(date '+%Y-%m-%d %H:%M'))" -- "$PAINEL_DIR" || return 1
    git -C "$RAIZ" push origin main && return 0
    if git -C "$RAIZ" pull --rebase origin main; then
        git -C "$RAIZ" push origin main && return 0
    else
        git -C "$RAIZ" rebase --abort 2>/dev/null || true
    fi
    git -C "$RAIZ" reset -q --soft HEAD~1
    git -C "$RAIZ" restore -q --staged -- "$PAINEL_DIR"
    descartar_painel
    return 1
}

if [ "$CODIGO" -eq 0 ] && [ "$PUBLICAVEL" -eq 0 ]; then
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] geracao com recorte manual, nao publica." | tee -a "$LOG"
elif [ "$CODIGO" -eq 0 ] && [ "$SUSPENSA" -eq 1 ]; then
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] rodada suspensa (ver AVISO acima), nao publica." | tee -a "$LOG"
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
