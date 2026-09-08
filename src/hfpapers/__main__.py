"""CLI do hf-papers-db."""

from __future__ import annotations

import datetime as dt
import json
from pathlib import Path
from typing import Optional

import typer

from . import db, doutor as doutor_mod, execucao, log, taxonomia as mod_tax
from .config import config
from .estagios import classificacao
from .estagios import export as mod_export
from .llm.cliente import catalogo_modelos, suporta_saida_estruturada

app = typer.Typer(
    add_completion=False,
    no_args_is_help=True,
    help="Camada de preparacao de dados dos HF Daily Papers para o Power BI.",
)
app_tax = typer.Typer(no_args_is_help=True, help="Governanca do vocabulario controlado.")
app_modelos = typer.Typer(no_args_is_help=True, help="Catalogo de modelos do OpenRouter.")
app.add_typer(app_tax, name="taxonomia")
app.add_typer(app_modelos, name="modelos")

_SIMBOLO = {"ok": "[ok]   ", "aviso": "[aviso]", "erro": "[ERRO] "}


def _data(valor: Optional[str]) -> Optional[dt.date]:
    return dt.date.fromisoformat(valor) if valor else None


def _preparar():
    cfg = config()
    log.configurar(cfg.dir_logs)
    return cfg


# ── run ─────────────────────────────────────────────────────────────────────


@app.command()
def run(
    data: Optional[str] = typer.Option(None, "--data", help="Forca uma data (YYYY-MM-DD)."),
    only: Optional[str] = typer.Option(
        None, "--only", help="Subconjunto de estagios, separados por virgula."
    ),
    dry_run: bool = typer.Option(False, "--dry-run", help="Estima custo, nao chama LLM."),
    force: bool = typer.Option(False, "--force", help="Reclassifica papers que ja tem triagem."),
) -> None:
    """Pipeline completo do dia."""
    cfg = _preparar()
    alvo = _data(data)

    if dry_run:
        r = execucao.dry_run(cfg=cfg, data=alvo)
        typer.echo(f"Dias: {', '.join(r.dias)}")
        typer.echo(f"Coletados: {r.coletados} | ja triados: {r.ja_na_base} | a classificar: {r.a_classificar}")
        typer.echo("")
        for item in r.estimativa.itens:
            typer.echo(
                f"  {item['etapa']:<11} {item['modelo']:<34} "
                f"{item['papers']:>4} papers  ~{item['tokens_entrada']:>7} in / "
                f"{item['tokens_saida']:>6} out  US$ {item['custo_usd']:.4f}"
            )
        typer.echo(f"\nEstimativa total: US$ {r.estimativa.total_usd:.4f} (nenhum token gasto)")
        return

    apenas = [e.strip() for e in only.split(",")] if only else None
    if apenas:
        invalidos = [e for e in apenas if e not in execucao.ESTAGIOS]
        if invalidos:
            typer.echo(f"estagio desconhecido: {', '.join(invalidos)}")
            typer.echo(f"validos: {', '.join(execucao.ESTAGIOS)}")
            raise typer.Exit(code=2)

    r = execucao.rodar(cfg=cfg, data=alvo, apenas=apenas, force=force)

    typer.echo(f"\nrun_id: {r.run_id}  status: {r.status}")
    typer.echo(f"dias: {', '.join(r.dias) or '(nenhum)'}")
    typer.echo(
        f"coletados {r.coletados} | novos {r.novos} | ja vistos {r.ja_vistos} | refresh {r.refresh_papers}"
    )
    taxa = f"{r.taxa_fora:.0%}" if r.taxa_fora is not None else "—"
    typer.echo(
        f"fora {r.fora} | amplo {r.amplo} | estrito {r.estrito} | fichas {r.fichas} | "
        f"pendentes {r.nao_classificados} | taxa FORA {taxa}"
    )
    typer.echo(
        f"LLM: {r.uso.chamadas} chamadas, {r.uso.tokens_entrada} in / {r.uso.tokens_saida} out, "
        f"US$ {r.uso.custo_usd:.4f}"
    )
    if r.arquivos:
        typer.echo(f"export: {len(r.arquivos)} arquivos em {cfg.dir_marts}")
    for aviso in r.avisos:
        typer.echo(f"  [aviso] {aviso}")
    if r.status == "erro":
        raise typer.Exit(code=1)
    if any(a.startswith("coleta_falhou") for a in r.avisos):
        raise typer.Exit(code=1)


# ── export ──────────────────────────────────────────────────────────────────


@app.command()
def export() -> None:
    """Materializa os Parquet do Power BI em marts/."""
    cfg = _preparar()
    conn = db.abrir(cfg)
    try:
        r = mod_export.rodar(conn, cfg)
    finally:
        conn.close()
    for nome, n in r.arquivos.items():
        typer.echo(f"  {nome:<22} {n:>7} linhas")
    typer.echo(f"\n{len(r.arquivos)} arquivos em {r.dir_saida} (+ _manifest.json)")


# ── reclassificar ───────────────────────────────────────────────────────────


@app.command()
def reclassificar(
    data: Optional[str] = typer.Option(None, "--data", help="Reclassifica um dia inteiro."),
    paper: Optional[str] = typer.Option(None, "--paper", help="Reclassifica um paper."),
    tudo: bool = typer.Option(
        False, "--tudo", help="Reclassifica a base inteira (rodada total, horas)."
    ),
    concorrencia: Optional[int] = typer.Option(
        None,
        "--concorrencia",
        help=(
            "Chamadas simultaneas ao OpenRouter "
            f"(1 = sequencial, teto {classificacao.CONCORRENCIA_MAXIMA}). "
            "Padrao: llm.concorrencia do config.yaml. "
            "Acima de 1, Ctrl+C so age quando as chamadas em voo terminam "
            "(ate ~18 min no pior caso) - espere, nao mate o processo."
        ),
    ),
) -> None:
    """Roda a classificacao de novo, incrementando `revisao`.

    `--tudo` e exclusivo com `--data`/`--paper`: ou se varre a base inteira, ou
    se dirige a varredura. A rodada entra em `log_execucao` nos tres casos.

    `--concorrencia` mora aqui e nao no `run` de proposito: e a rodada total
    que passa horas em chamada sequencial. A rodada diaria segue o config.
    """
    cfg = _preparar()
    if tudo and (data or paper):
        typer.echo("--tudo nao combina com --data nem --paper")
        raise typer.Exit(code=2)
    if not tudo and not data and not paper:
        typer.echo("informe --tudo, --data ou --paper")
        raise typer.Exit(code=2)

    conn = db.abrir(cfg)
    try:
        r = execucao.reclassificar(
            cfg=cfg, conn=conn, ids=[paper] if paper else None, data=data, tudo=tudo,
            concorrencia=concorrencia,
        )
        if not r.selecionados:
            typer.echo("nada a reclassificar")
            return

        typer.echo(f"\nrun_id: {r.run_id}  status: {r.status}  ({r.selecionados} papers)")
        typer.echo(
            f"fora {r.fora} | amplo {r.amplo} | estrito {r.estrito} | fichas {r.fichas} | "
            f"pendentes {r.nao_classificados} | US$ {r.uso.custo_usd:.4f}"
        )
        for aviso in r.avisos:
            typer.echo(f"  [aviso] {aviso}")

        # O Estagio B caiu nas duas passadas nestes papers: eles ficaram sem
        # linha nova. A lista sai colavel de proposito - repetir um a um e o
        # passo 3 da rodada total (spec, secao 3).
        if r.falhas_estagio_b:
            typer.echo(
                f"\n{len(r.falhas_estagio_b)} paper(s) sem veredito novo "
                "(Estagio B falhou nas duas passadas) - rode:"
            )
            for pid in r.falhas_estagio_b:
                typer.echo(f"  python -m hfpapers reclassificar --paper {pid}")

        if tudo:
            c = execucao.conferir(conn, r.run_id)
            fim = "rodada completa" if not any(c.values()) else "ainda falta"
            typer.echo(
                f"\nconferencia ({fim}): {c['outro_run_id']} triagem(ns) de outra rodada, "
                f"{c['sem_triagem']} paper(s) sem triagem"
            )
    finally:
        conn.close()


# ── taxonomia ───────────────────────────────────────────────────────────────


@app_tax.command("listar")
def taxonomia_listar() -> None:
    """Areas (com as sub-areas), topicos e vertentes, com quantos papers cada
    rotulo carrega, mais o quanto a grade esta devendo por eixo."""
    cfg = _preparar()
    conn = db.abrir(cfg)
    try:
        dados = mod_tax.listar(conn)
    finally:
        conn.close()

    planas = [a for a in dados["areas"] if not a["subareas"]]
    subareas = sum(len(a["subareas"]) for a in dados["areas"])
    typer.echo(
        f"AREAS ({len(planas)} na grade plana + "
        f"{len(dados['areas']) - len(planas)} facetadas com {subareas} sub-areas)"
    )
    for a in dados["areas"]:
        typer.echo(f"  {a['papers']:>4}  {a['rotulo']}")
        for s in a["subareas"]:
            typer.echo(f"  {s['papers']:>4}    {s['rotulo']}")
    typer.echo(f"\nVERTENTES ({len(dados['vertentes'])})")
    for v in dados["vertentes"]:
        # a dominante entre parenteses: uma vertente que so aparece em segundo
        # lugar tem massa sem ter nenhum paper que ela defina
        typer.echo(
            f"  {v['papers']:>4}  ({v['dominantes']:>4} dom.)  "
            f"{v['rotulo']} — {v['definicao']}"
        )
    typer.echo(f"\nTOPICOS ({len(dados['topicos'])})")
    for t in dados["topicos"]:
        typer.echo(f"  {t['papers']:>4}  {t['rotulo']}")
    typer.echo("\nNAO-ENCAIXE (`taxonomia nao-encaixes` para ler a fila)")
    for eixo in mod_tax.EIXOS:
        typer.echo(f"  {dados['nao_encaixes'].get(eixo, 0):>4}  {eixo}")


@app_tax.command("nao-encaixes")
def taxonomia_nao_encaixes(
    eixo: Optional[str] = typer.Option(
        None, "--eixo", help="area | subarea | vertente (padrao: os tres)"
    ),
) -> None:
    """A fila de revisao da grade: onde ela nao serviu, e por que.

    Le por eixo porque a leitura de cada um e diferente: area nova e evento
    raro e grave, sub-area nova e rotina, e vertente nova quase nao devia
    acontecer. Quem promove a partir desta fila e a revisao da grade, por
    quorum - nunca a classificacao.
    """
    if eixo and eixo not in mod_tax.EIXOS:
        typer.echo(f"eixo invalido: {eixo} (use {' | '.join(mod_tax.EIXOS)})")
        raise typer.Exit(code=2)
    cfg = _preparar()
    conn = db.abrir(cfg)
    try:
        fila = mod_tax.nao_encaixes(conn, eixo=eixo)
    finally:
        conn.close()

    typer.echo(f"NAO-ENCAIXES ({len(fila)})")
    for r in fila:
        typer.echo(f"  [{r['eixo']}] {r['paper_id']} — {r['justificativa']}")


@app_tax.command("fundir")
def taxonomia_fundir(
    de: str = typer.Option(..., "--de", help="Rotulo que sera absorvido."),
    para: str = typer.Option(..., "--para", help="Rotulo que permanece."),
    tipo: str = typer.Option("topico", "--tipo", help="area | topico"),
) -> None:
    """Funde dois rotulos e reescreve as pontes. Operacao manual, por desenho."""
    cfg = _preparar()
    conn = db.abrir(cfg)
    try:
        r = mod_tax.fundir(conn, de=de, para=para, tipo=tipo)
    except ValueError as e:
        typer.echo(str(e))
        raise typer.Exit(code=2)
    finally:
        conn.close()
    typer.echo(f"'{de}' -> '{para}': {r['papers_no_destino']} papers no destino")


TAXONOMIA_INICIAL = "config/taxonomia_inicial.json"


def _taxonomia_inicial(cfg, informado: Optional[Path]) -> Path:
    """O padrao e o arquivo versionado do projeto, nao um homonimo no CWD.

    Resolver contra `cfg.raiz` e o que o resto do projeto faz (`config._abs`).
    Com o caminho relativo ao diretorio corrente, `exportar` rodado de fora da
    raiz criava um `config/` novo la e gravava nele em silencio - o operador
    achava ter atualizado o arquivo do git - e `carregar` reclamava de arquivo
    inexistente.
    """
    return informado if informado else cfg.raiz / TAXONOMIA_INICIAL


@app_tax.command("exportar")
def taxonomia_exportar(
    destino: Optional[Path] = typer.Option(
        None, "--destino", help=f"Arquivo JSON de saida (padrao: {TAXONOMIA_INICIAL})."
    ),
) -> None:
    """Grava areas, sub-areas, topicos e vertentes do banco num JSON versionavel.
    Candidatos nao entram."""
    cfg = _preparar()
    destino = _taxonomia_inicial(cfg, destino)
    conn = db.abrir(cfg)
    try:
        dados = mod_tax.exportar(conn)
    finally:
        conn.close()

    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(
        json.dumps(dados, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    typer.echo(
        f"{len(dados['areas'])} areas com "
        f"{sum(len(a['subareas']) for a in dados['areas'])} sub-areas, "
        f"{len(dados['topicos'])} topicos e {len(dados['vertentes'])} vertentes "
        f"em {destino}"
    )


@app_tax.command("carregar")
def taxonomia_carregar(
    arquivo: Optional[Path] = typer.Argument(
        None, help=f"JSON gerado por `taxonomia exportar` (padrao: {TAXONOMIA_INICIAL})."
    ),
) -> None:
    """Repoe o vocabulario num banco vazio. Idempotente: rotulo existente nao e tocado."""
    cfg = _preparar()
    arquivo = _taxonomia_inicial(cfg, arquivo)
    if not arquivo.exists():
        typer.echo(f"arquivo inexistente: {arquivo}")
        raise typer.Exit(code=2)
    dados = json.loads(arquivo.read_text(encoding="utf-8"))

    conn = db.abrir(cfg)
    try:
        with db.transacao(conn):
            r = mod_tax.carregar(conn, dados)
    finally:
        conn.close()
    typer.echo(
        f"{r['areas']} areas, {r['subareas']} sub-areas, {r['topicos']} topicos e "
        f"{r['vertentes']} vertentes inseridos "
        f"({r['ja_existiam']} rotulos ja existiam, intocados)"
    )


# ── modelos ─────────────────────────────────────────────────────────────────


@app_modelos.command("listar")
def modelos_listar(
    max_preco: float = typer.Option(
        5.0, "--max-preco", help="Teto de US$ por milhao de tokens de entrada."
    ),
    contem: Optional[str] = typer.Option(None, "--contem", help="Filtra por trecho do id."),
    limite: int = typer.Option(40, "--limite"),
) -> None:
    """Lista modelos com saida estruturada e preco por milhao de tokens.

    Os ids do OpenRouter mudam com frequencia: escolha aqui e escreva no
    config.yaml, nunca no codigo.
    """
    cfg = _preparar()
    modelos = [m for m in catalogo_modelos(cfg) if suporta_saida_estruturada(m)]
    linhas = []
    for m in modelos:
        p = m.get("pricing") or {}
        try:
            entrada = float(p.get("prompt") or 0) * 1e6
            saida = float(p.get("completion") or 0) * 1e6
        except (TypeError, ValueError):
            continue
        if entrada < 0 or entrada > max_preco:
            continue
        if contem and contem.lower() not in m["id"].lower():
            continue
        linhas.append((entrada, saida, m["id"], m.get("context_length")))

    typer.echo(f"{len(modelos)} modelos com saida estruturada; {len(linhas)} dentro do filtro\n")
    typer.echo(f"{'US$/Mtok in':>12} {'out':>9}  {'contexto':>9}  id")
    for entrada, saida, mid, ctx in sorted(linhas)[:limite]:
        typer.echo(f"{entrada:>12.3f} {saida:>9.3f}  {ctx or 0:>9}  {mid}")
    typer.echo(
        f"\nem uso: estagio_a={cfg.llm.estagio_a.modelo} | estagio_b={cfg.llm.estagio_b.modelo}"
    )


# ── operacao ────────────────────────────────────────────────────────────────


@app.command()
def custos(
    mes: Optional[str] = typer.Option(None, "--mes", help="AAAA-MM; padrao: mes corrente."),
) -> None:
    """Quanto a LLM custou no mes, por etapa e modelo."""
    cfg = _preparar()
    mes = mes or dt.date.today().strftime("%Y-%m")
    conn = db.abrir(cfg)
    try:
        linhas = conn.execute(
            "SELECT etapa, modelo, COUNT(*) AS chamadas, "
            "       SUM(tokens_entrada) AS tin, SUM(tokens_saida) AS tout, "
            "       SUM(custo_usd) AS usd "
            "FROM log_llm WHERE substr(criado_em, 1, 7) = ? "
            "GROUP BY etapa, modelo ORDER BY usd DESC",
            (mes,),
        ).fetchall()
    finally:
        conn.close()

    if not linhas:
        typer.echo(f"nenhuma chamada de LLM em {mes}")
        return
    total = 0.0
    typer.echo(f"{mes}\n")
    for r in linhas:
        total += r["usd"] or 0
        typer.echo(
            f"  {r['etapa']:<11} {r['modelo']:<34} {r['chamadas']:>5} chamadas  "
            f"{r['tin'] or 0:>8} in / {r['tout'] or 0:>7} out  US$ {r['usd'] or 0:.4f}"
        )
    typer.echo(f"\ntotal: US$ {total:.4f}")


@app.command()
def doutor(
    sem_rede: bool = typer.Option(False, "--sem-rede", help="Nao chama HF nem OpenRouter."),
) -> None:
    """Diagnostico: chave ok? API ok? banco integro?"""
    cfg = _preparar()
    itens = doutor_mod.rodar(cfg, sem_rede=sem_rede)
    for it in itens:
        typer.echo(f"{_SIMBOLO[it.estado]} {it.nome:<18} {it.detalhe}")
    erros = [i for i in itens if i.estado == "erro"]
    if erros:
        typer.echo(f"\n{len(erros)} problema(s) bloqueante(s).")
        raise typer.Exit(code=1)
    typer.echo("\nTudo pronto.")


@app.command("schema")
def mostrar_schema() -> None:
    """Cria/migra o banco e imprime o DDL efetivo."""
    cfg = _preparar()
    conn = db.abrir(cfg)
    try:
        db.garantir_calendario(conn)
        linhas = conn.execute(
            "SELECT type, name, sql FROM sqlite_master "
            "WHERE sql IS NOT NULL ORDER BY CASE type WHEN 'table' THEN 0 ELSE 1 END, name"
        ).fetchall()
        for r in linhas:
            typer.echo(r["sql"].strip() + ";")
        diag = db.diagnostico_banco(conn)
    finally:
        conn.close()
    typer.echo(f"\n-- banco: {cfg.caminho_banco}")
    typer.echo("-- linhas: " + ", ".join(f"{t}={n}" for t, n in diag["contagens"].items()))


if __name__ == "__main__":
    app()
