"""O relatorio de massa e o instrumento das duas checagens objetivas da spec.

Ele estava sem teste nenhum, e o ticket 08 funde rotulo com base no que ele
imprime: uma contagem errada aqui vira uma fusao irreversivel la. `gerar` e
funcao pura de uma conexao, entao a seam e barata - um banco em memoria com meia
duzia de linhas cobre as duas checagens, a cobertura e a tabela de roteamento.

Os testes afirmam o texto de saida porque o texto **e** a interface: quem le o
relatorio e um humano decidindo fusao, e um numero certo numa variavel que nao
chega ao Markdown nao serve para nada.
"""

from __future__ import annotations

import pytest

from hfpapers import db

import relatorio_massa


def _paper(conn, pid: str) -> None:
    db.upsert_paper(conn, {"paper_id": pid, "titulo": "T", "primeiro_visto_em": db.agora()})


def _par(conn, pid: str, area: str, subarea: str, primaria: int) -> None:
    db.inserir_ignorando(
        conn,
        "ponte_paper_area",
        {"paper_id": pid, "area": area, "subarea": subarea, "is_primaria": primaria},
    )


@pytest.fixture()
def base(conn):
    """Uma area raiz com duas sub-areas irmas, uma vertente, e tres papers.

    A grade e minima de proposito: a checagem A mede a sub-area **dentro da sua
    area**, entao duas irmas com 2 e 1 papers ja produzem 66,7% contra 33,3% -
    as duas acima do teto de 25%, que e o caso que a v2 tem sete vezes.
    """
    with db.transacao(conn):
        db.upsert_area(conn, {"area": "Contexto & recuperação", "definicao": "d"})
        for sub in ("Memória de longo prazo", "RAG & recuperação"):
            db.upsert_area(
                conn, {"area": sub, "definicao": "", "area_pai": "Contexto & recuperação"}
            )
        db.upsert_vertente(conn, {"vertente": "Medir", "definicao": "d"})
        for i in range(3):
            _paper(conn, f"2608.0000{i}")
        _par(conn, "2608.00000", "Contexto & recuperação", "Memória de longo prazo", 1)
        _par(conn, "2608.00001", "Contexto & recuperação", "Memória de longo prazo", 1)
        _par(conn, "2608.00002", "Contexto & recuperação", "RAG & recuperação", 1)
        for i in range(3):
            db.inserir_ignorando(
                conn,
                "ponte_paper_vertente",
                {"paper_id": f"2608.0000{i}", "vertente": "Medir", "ordem": 1},
            )
    return conn


def _linhas(texto: str, prefixo: str) -> list[str]:
    return [l for l in texto.splitlines() if l.startswith(prefixo)]


def test_a_cobertura_conta_o_paper_com_par_e_sem_primaria(base):
    """A linha que faltava, e por causa da qual quatro papers ficaram invisiveis.

    O relatorio dizia "com par primário: 3158" e "sem faceta nenhuma: 4" numa
    base de 3.166 - e os outros 4 tinham ponte, so nao tinham primaria. Nenhuma
    das duas linhas os pegava, entao o defeito de `aplicar_classificacao` que os
    produziu nao apareceu em leitura nenhuma. A linha existe para que o proximo
    caso apareca no dia em que acontecer, e nao meses depois.
    """
    with db.transacao(base):
        _paper(base, "2608.00009")
        _par(base, "2608.00009", "Contexto & recuperação", "RAG & recuperação", 0)

    texto = relatorio_massa.gerar(base, None)

    assert "| com par, sem primária | 1 | 25.0% |" in texto


def test_a_base_sadia_nao_tem_paper_com_par_e_sem_primaria(base):
    """A linha nova sai zerada quando a base esta sa - e e assim que ela vira
    conferencia, e nao so diagnostico de um incidente."""
    assert "| com par, sem primária | 0 | 0.0% |" in relatorio_massa.gerar(base, None)


def test_a_checagem_a_reprova_a_sub_area_acima_do_teto(base):
    """66,7% e 33,3% dentro da mesma area: as duas acima dos 25% da spec."""
    texto = relatorio_massa.gerar(base, None)

    assert "**Checagem A — nenhuma sub-área acima de ~25% da sua área**: FALHA, 2 acima do teto." in texto
    assert "  - Contexto & recuperação > Memória de longo prazo: 2 papers, 66.7%" in texto


def test_a_checagem_b_passa_com_a_vertente_unica(base):
    """Uma vertente so, em todos os papers: 100% dos classificados, nada abaixo
    do piso de 2%."""
    texto = relatorio_massa.gerar(base, None)

    assert "**Checagem B — nenhuma vertente abaixo de ~2%**: passa, 0 abaixo do piso." in texto
    assert "Atribuições no total: 3 para 3 papers (1.00 por paper)." in texto


def test_a_sub_area_que_ninguem_recebeu_entra_com_zero(base):
    """A sub-area vazia e o achado mais forte do relatorio e nao aparece num
    GROUP BY sobre a ponte: ela entra da grade."""
    with db.transacao(base):
        db.upsert_area(
            base,
            {"area": "Janela & contexto longo", "definicao": "", "area_pai": "Contexto & recuperação"},
        )

    assert "| | Janela & contexto longo | 0 | 0.0% |" in _linhas(
        relatorio_massa.gerar(base, None), "| | Janela"
    )[0]


def _chamada(conn, **campos) -> None:
    db.inserir_ignorando(
        conn,
        "log_llm",
        {
            "run_id": "run-teste",
            "paper_id": "2608.00000",
            "etapa": "estagio_a",
            "modelo": "modelo/teste",
            "tentativas": 1,
            "criado_em": db.agora(),
            **campos,
        },
    )


def test_o_provedor_sem_latencia_sai_com_travessao_e_nao_com_None(base):
    """`AVG`/`MAX` sobre um grupo todo-NULL devolvem NULL, e o `None` do Python
    vazava para dentro da tabela Markdown: a linha *(não registrado)* saia como
    `| (não registrado) | 7 | 0 | 7 | 7 | None | None | None |`.

    O grupo e todo-NULL por construcao, e nao por acaso: `latencia_ms` so e
    gravada na chamada que respondeu, e a linha *(não registrado)* concentra
    justamente as que morreram antes da resposta.
    """
    with db.transacao(base):
        _chamada(base, erro="ErroPrazo: prazo de 90,0 s estourado", custo_usd=0.0)

    linha = _linhas(relatorio_massa.gerar(base, "run-teste"), "| (não registrado)")[0]

    assert "None" not in linha
    assert linha == "| (não registrado) | 1 | 0 | 1 | 1 | — | — | — |"


def test_a_media_de_latencia_diz_que_conta_so_a_chamada_bem_sucedida(base):
    """A coluna *média (s)* e media sobre `latencia_ms`, que e NULL na linha de
    erro - entao ela mede quem respondeu, e nao a rodada. O texto precisa dizer:
    sem isso ela e lida como tempo medio por chamada, que e outro numero."""
    with db.transacao(base):
        _chamada(base, provedor="Together", latencia_ms=3300, custo_usd=0.0001)

    texto = relatorio_massa.gerar(base, "run-teste")

    assert "*média (s)* e *pior* contam só as chamadas que" in texto
    assert "responderam, e não a rodada" in texto


def test_o_relatorio_avisa_que_a_fila_de_parentesco_e_piso(base):
    """`tax_nao_encaixe` tem `paper_id` como PK e a declaracao do modelo vence o
    par rejeitado, entao o paper que tem os dois so aparece como declaracao. A
    secao de parentesco conta menos rejeicoes do que houve, e quem le decide
    parentesco a partir dela."""
    with db.transacao(base):
        db.inserir_ignorando(
            base,
            "tax_nao_encaixe",
            {
                "paper_id": "2608.00000",
                "eixo": "subarea",
                "justificativa": (
                    "par rejeitado pelo parentesco da grade: "
                    "Contexto & recuperação > Fala & áudio"
                ),
                "registrado_em": db.agora(),
            },
        )

    texto = relatorio_massa.gerar(base, None)

    assert "### Desacordo de parentesco" in texto
    assert "piso, e não o total" in texto


def test_main_exige_o_arquivo_de_saida(monkeypatch):
    """Sem o segundo argumento, o default apontava para o relatorio da v1 - a
    evidencia que justifica cada fusao do ticket 08 - e a rodada seguinte o
    sobrescrevia em silencio. Agora o script recusa e diz como se usa."""
    monkeypatch.setattr("sys.argv", ["relatorio_massa.py", "run-20260908-173724"])

    with pytest.raises(SystemExit) as e:
        relatorio_massa.main()

    assert "uso:" in str(e.value).lower()
