"""Coleta retroativa: dias anteriores ao pipeline entram na base, sem classificacao.

Nao ha decisao nova aqui. Coleta e enriquecimento ja sabem tratar um dia; o que
faltava era o laco sobre uma janela de meses e a retomada de uma queda no meio.
Isso e operacao, e operacao mora em `scripts/` - mesmo lugar de
`gerar_painel.py`.

Custo de LLM zero por construcao: este arquivo nao importa a classificacao nem
o cliente de modelo, entao nao existe caminho por onde a chamada possa entrar.
`conferir` confirma isso pelo banco depois, que e o que o operador precisa ver.

Uso:
    python scripts/coleta_retroativa.py --inicio 2026-05-01 --fim 2026-08-13
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "src"))

from hfpapers import db  # noqa: E402
from hfpapers.config import config  # noqa: E402
from hfpapers.estagios import coleta, enriquecimento  # noqa: E402
from hfpapers.fontes.hf_client import ClienteHF  # noqa: E402
from hfpapers.log import configurar as configurar_log, logger  # noqa: E402

log = logger("retroativa")

DIA = dt.timedelta(days=1)


@dataclass
class ResultadoRetroativo:
    run_id: str
    status: str = "parcial"
    dias: list[dt.date] = field(default_factory=list)
    coletados: int = 0
    novos: int = 0
    ja_vistos: int = 0
    enriquecidos: int = 0
    por_dia: dict[str, int] = field(default_factory=dict)
    avisos: list[str] = field(default_factory=list)


@dataclass
class Conferencia:
    """O que o operador confere depois da varredura, direto do banco."""

    por_mes: dict[str, int] = field(default_factory=dict)
    chamadas_llm: int = 0
    triagens: int = 0
    sem_enriquecimento: int = 0
    dias_pendentes: int = 0


def dias_da_janela(inicio: dt.date, fim: dt.date) -> list[dt.date]:
    dias, d = [], inicio
    while d <= fim:
        dias.append(d)
        d += DIA
    return dias


def dias_pendentes(conn, inicio: dt.date, fim: dt.date) -> list[dt.date]:
    """Dias da janela que ainda tem trabalho, lidos do proprio banco.

    Um dia esta pronto quando tem paper e nenhum deles esta sem
    `enriquecido_em`. Nao ha arquivo de progresso: o processo pode morrer de
    qualquer jeito que o estado continua legivel, e reprocessar um dia nao
    duplica nada, porque `dim_paper` tem chave primaria e a gravacao e upsert.

    Fim de semana sem paper volta a ser consultado a cada retomada - "nenhum
    paper" e indistinguivel de "nunca visitado" pelo banco. Sao segundos numa
    janela de tres meses, e o preco de nao inventar tabela de progresso.
    """
    prontos = {
        r["data_hf_daily"]
        for r in conn.execute(
            "SELECT data_hf_daily FROM dim_paper "
            "WHERE data_hf_daily BETWEEN ? AND ? "
            "GROUP BY data_hf_daily "
            "HAVING SUM(enriquecido_em IS NULL) = 0",
            (inicio.isoformat(), fim.isoformat()),
        )
    }
    return [d for d in dias_da_janela(inicio, fim) if d.isoformat() not in prontos]


def _sem_enriquecimento(conn, dia: dt.date) -> list[str]:
    """Papers do dia que ainda nao passaram pelo endpoint por-paper.

    A fila sai do banco, e nao da lista que a coleta acabou de devolver, para
    que a retomada apanhe tambem o dia que caiu entre coletar e enriquecer.
    """
    return [
        r["paper_id"]
        for r in conn.execute(
            "SELECT paper_id FROM dim_paper "
            "WHERE data_hf_daily = ? AND enriquecido_em IS NULL "
            "ORDER BY paper_id",
            (dia.isoformat(),),
        )
    ]


def novo_run_id(agora: Optional[dt.datetime] = None) -> str:
    """Prefixo proprio: e por ele que se separa o que esta varredura fez.

    `run-` e da rodada diaria. Com `retro-`, a pergunta "quanto de modelo esta
    etapa gastou" tem resposta de uma linha em `log_llm`.
    """
    return (agora or dt.datetime.now()).strftime("retro-%Y%m%d-%H%M%S")


def _fechar_execucao(conn, res: ResultadoRetroativo) -> None:
    db.upsert_execucao(
        conn,
        {
            "run_id": res.run_id,
            "iniciado_em": db.agora(),
            "finalizado_em": db.agora(),
            "status": res.status,
            "dias_cobertos": json.dumps([d.isoformat() for d in res.dias]),
            "qtd_coletados": res.coletados,
            "qtd_novos": res.novos,
            "qtd_ja_vistos": res.ja_vistos,
            # Zero e a verdade, nao buraco: nenhum estagio de modelo roda aqui.
            "qtd_fora": 0,
            "qtd_amplo": 0,
            "qtd_estrito": 0,
            "qtd_refresh": 0,
            "tokens_entrada": 0,
            "tokens_saida": 0,
            "custo_usd": 0.0,
            "avisos": json.dumps(res.avisos, ensure_ascii=False),
        },
    )


def rodar(
    conn,
    cliente: ClienteHF,
    *,
    inicio: dt.date,
    fim: dt.date,
    hoje: Optional[dt.date] = None,
    run_id: Optional[str] = None,
) -> ResultadoRetroativo:
    """Varre a janela dia a dia, coletando e enriquecendo o que falta.

    A rodada entra em `log_execucao` mesmo quando morre no meio, pelo mesmo
    motivo que a classificacao absorve o parcial no `finally`: os papers ja
    gravados sao fato no banco, e o log tem de refletir isso.
    """
    hoje = hoje or db.hoje()
    res = ResultadoRetroativo(run_id=run_id or novo_run_id())
    db.upsert_execucao(
        conn, {"run_id": res.run_id, "iniciado_em": db.agora(), "status": "parcial"}
    )

    try:
        fila = dias_pendentes(conn, inicio, fim)
        log.info("%s dias pendentes entre %s e %s", len(fila), inicio, fim)
        for n, dia in enumerate(fila, start=1):
            # `coletados_min_dia_util=0` desliga o aviso de dia magro: o piso
            # calibra o volume de UM dia recem-coletado, e numa varredura de
            # tres meses ele so produz uma linha de ruido por fim de semana.
            r = coleta.rodar(
                conn, cliente, datas=[dia], hoje=hoje, coletados_min_dia_util=0
            )
            res.dias.append(dia)
            res.coletados += r.coletados
            res.novos += len(r.novos)
            res.ja_vistos += r.ja_vistos
            res.por_dia.update(r.por_dia)
            res.avisos.extend(r.avisos)

            pendentes = _sem_enriquecimento(conn, dia)
            if pendentes:
                e = enriquecimento.rodar(conn, cliente, pendentes, data_snapshot=hoje)
                res.enriquecidos += e.enriquecidos
                res.avisos.extend(e.avisos)

            log.info(
                "[%s/%s] %s: %s coletados, %s novos (acumulado: %s)",
                n, len(fila), dia, r.coletados, len(r.novos), res.novos,
            )

        res.status = (
            "parcial" if any(a.startswith("coleta_falhou") for a in res.avisos) else "ok"
        )
    except BaseException:
        res.status = "erro"
        raise
    finally:
        _fechar_execucao(conn, res)

    return res


def conferir(conn, *, inicio: dt.date, fim: dt.date, run_id: str) -> Conferencia:
    """Le do banco o que a varredura promete: massa por mes e custo zero."""
    faixa = (inicio.isoformat(), fim.isoformat())
    return Conferencia(
        por_mes={
            r["mes"]: r["n"]
            for r in conn.execute(
                "SELECT substr(data_hf_daily, 1, 7) AS mes, COUNT(*) AS n "
                "FROM dim_paper WHERE data_hf_daily BETWEEN ? AND ? "
                "GROUP BY mes ORDER BY mes",
                faixa,
            )
        },
        chamadas_llm=conn.execute(
            "SELECT COUNT(*) AS n FROM log_llm WHERE run_id = ?", (run_id,)
        ).fetchone()["n"],
        triagens=conn.execute(
            "SELECT COUNT(*) AS n FROM fato_triagem t JOIN dim_paper p USING (paper_id) "
            "WHERE p.data_hf_daily BETWEEN ? AND ?",
            faixa,
        ).fetchone()["n"],
        sem_enriquecimento=conn.execute(
            "SELECT COUNT(*) AS n FROM dim_paper "
            "WHERE data_hf_daily BETWEEN ? AND ? AND enriquecido_em IS NULL",
            faixa,
        ).fetchone()["n"],
        dias_pendentes=len(dias_pendentes(conn, inicio, fim)),
    )


def _parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(
        description="Coleta e enriquece uma janela de dias antigos, sem classificar."
    )
    ap.add_argument("--inicio", type=dt.date.fromisoformat, required=True,
                    help="Primeiro dia da janela (YYYY-MM-DD).")
    ap.add_argument("--fim", type=dt.date.fromisoformat, required=True,
                    help="Ultimo dia da janela, inclusive (YYYY-MM-DD).")
    return ap


def _imprimir(res: ResultadoRetroativo, conf: Conferencia) -> None:
    """A conferencia na tela e o que fecha os criterios do ticket.

    Sai depois da varredura e le do banco, nao dos contadores em memoria: e a
    diferenca entre "o laco acha que fez" e "esta gravado".
    """
    print(f"\nrun_id: {res.run_id}  status: {res.status}  dias visitados: {len(res.dias)}")
    print(
        f"coletados {res.coletados} | novos {res.novos} | ja vistos {res.ja_vistos} | "
        f"enriquecidos {res.enriquecidos}"
    )
    print("\npapers por mes na janela (banco):")
    for mes, n in conf.por_mes.items():
        print(f"  {mes}  {n:>6}")
    print(f"  {'total':<5} {sum(conf.por_mes.values()):>6}")
    print(
        f"\nchamadas de LLM desta rodada: {conf.chamadas_llm}"
        f"\ntriagens na janela: {conf.triagens}"
        f"\npapers sem enriquecimento: {conf.sem_enriquecimento}"
        f"\ndias ainda pendentes: {conf.dias_pendentes}"
    )
    for aviso in res.avisos:
        print(f"  [aviso] {aviso}")


def main() -> int:
    args = _parser().parse_args()
    if args.inicio > args.fim:
        print("ERRO: --inicio depois de --fim", file=sys.stderr)
        return 2

    cfg = config()
    configurar_log(cfg.dir_logs)
    conn = db.abrir(cfg)
    try:
        with ClienteHF(cfg) as cliente:
            res = rodar(conn, cliente, inicio=args.inicio, fim=args.fim)
        conf = conferir(conn, inicio=args.inicio, fim=args.fim, run_id=res.run_id)
    finally:
        conn.close()

    _imprimir(res, conf)
    return 0 if res.status == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
