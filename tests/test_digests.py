from hfpapers.digests import carregar_digests, fichas_por_id, parse_digest

ESPERADO_POR_ARQUIVO = {
    "hf-digest-2026-08-14.md": 9,
    "hf-digest-2026-08-17.md": 11,
    "hf-digest-2026-08-18.md": 12,
    "hf-digest-2026-08-19.md": 12,
    "hf-digest-2026-08-20.md": 6,
    "hf-digest-2026-08-21.md": 10,
    "hf-digest-2026-08-24.md": 9,
    "hf-digest-2026-08-25.md": 14,
}


def test_cada_digest_e_internamente_consistente(seed_dir):
    """Blocos `###` == Amplo + Estrito da tabela de Operacao, nos 8 arquivos.

    Se algum falhar, o parser esta errado - nao o arquivo.
    """
    for d in carregar_digests(seed_dir / "digests"):
        assert d.consistente, f"{d.arquivo}: {len(d.fichas)} fichas vs {d.aprovados_declarados}"
        assert len(d.fichas) == ESPERADO_POR_ARQUIVO[d.arquivo]


def test_total_de_83_fichas(seed_dir):
    fichas = fichas_por_id(carregar_digests(seed_dir / "digests"))
    assert len(fichas) == 83


def test_padrao_extraido_e_opcional(seed_dir):
    fichas = fichas_por_id(carregar_digests(seed_dir / "digests"))
    assert fichas["2608.12440"].tem_padrao is False
    assert fichas["2608.12440"].veredito == "estrito"


def test_campos_da_ficha_sao_extraidos(seed_dir):
    f = fichas_por_id(carregar_digests(seed_dir / "digests"))["2608.06867"]
    assert f.upvotes_dia1 == 103
    assert f.data.isoformat() == "2026-08-14"
    assert f.padrao_nome == "Decomposição em cinco componentes do roteamento"
    assert f.padrao_mecanismo.startswith("Qualquer sistema de seleção")
    assert f.achado and f.implicacao_pratica and f.exemplo_concreto and f.ressalva


def test_veredito_vem_da_secao(seed_dir):
    fichas = fichas_por_id(carregar_digests(seed_dir / "digests"))
    assert fichas["2608.14577"].veredito == "amplo"   # `## 4.` no digest de 18/08


def test_parser_tolera_digest_minimo():
    d = parse_digest(
        "# t\n\n## 1. Operação\n\n| Dia coberto | Coletados | Descartados por estado | FORA | Amplo | Estrito |\n"
        "|---|---|---|---|---|---|\n| 2026-08-14 | 10 | 0 | 9 | 0 | 1 |\n\n"
        "## 3. Critério estrito\n\n### Titulo\n"
        "**arXiv:** 2608.00001 | **Data:** 2026-08-14 | **Upvotes:** 3\n\n"
        "**ACHADO:** a\n\n**IMPLICAÇÃO PRÁTICA:** b\n\n**EXEMPLO CONCRETO:** c\n\n**RESSALVA:** d\n\n"
        "## 5. Avisos\n- nada\n"
    )
    assert d.consistente and len(d.fichas) == 1
    f = d.fichas[0]
    assert f.paper_id == "2608.00001" and f.achado == "a" and f.ressalva == "d"
    assert f.padrao_nome is None
