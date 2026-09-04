"""Uniformiza as justificativas de veredito ja gravadas em `fato_triagem`.

COMANDO TEMPORARIO (issue #3). Roda uma vez, depois e apagado - junto com
`prompt_faltantes.md`, `prompt_reescrever.md`, o estado em
`data/estado/justificativas_migradas.json`, os relatorios que ele gera em
`relatorios/justificativas_diff_*.md` e os backups `data/*.bak-*` que
`--aplicar` deixa para tras. Nao fica em `src/hfpapers/` porque nao e parte
do pipeline: nenhuma execucao futura precisa dele de novo.

## Por que existe

O cabecalho de decisao da issue #2 vai exibir a `justificativa` de cada paper.
Hoje ela vem em tres estilos diferentes, dependendo de quando e por onde o
paper passou:

1. aprovados do backfill (`run_id = 'backfill'`, com ficha) nao tem
   justificativa nenhuma - carregam a marca `"Importado do historico (...)"`
   gravada por `backfill/importacao.py`.
2. aprovados e descartados do pipeline vivo (`run_id != 'backfill'`) tem
   justificativa propria, mas no estilo antigo do prompt (~410 e ~181
   caracteres, respectivamente) - mais longo que o novo teto de 300
   caracteres que a issue #2 poe no schema do Estagio B.
3. descartados do backfill nao tem justificativa e NAO devem ganhar uma: o
   veredito historico e autoritativo, mas a base documental para escrever
   "por que fora" nunca existiu (backfill nao guarda ficha de descartado).

Este comando cobre (1) e (2) com prompts e criterios diferentes; (3) fica de
fora por desenho - ver `selecionar_faltantes` e `selecionar_reescrever`.

## Os dois lotes, e por que sao consulta e nao lista fixa

Os numeros da issue (~78, ~83, ~130) sao aproximados: cinco papers vao ser
reclassificados a mao antes desta migracao rodar. Uma lista fixa de paper_id
ficaria errada assim que isso acontecesse. Os dois lotes abaixo sao sempre
derivados de `fato_triagem` no momento da execucao:

- `--faltantes`: `run_id = 'backfill'`, veredito aprovado (`amplo`/`estrito`),
  com `dim_ficha` (o INNER JOIN e o que garante isso - sem ficha, sem lote).
  O prompt recebe o veredito como fato e escreve a justificativa *dele*;
  nunca decide, nunca discorda (criterio 2 da issue).
- `--reescrever`: `run_id != 'backfill'`, qualquer veredito. O prompt recebe
  a justificativa atual e o veredito. A issue pede "so a justificativa
  atual", mas o veredito tambem vai: condensar a justificativa de um `fora`
  sem saber que e uma rejeicao pode inverter o tom do texto (uma frase do tipo
  "explica X sem entregar Y" so soa como rejeicao se o leitor - aqui, o
  modelo - sabe que o veredito e `fora`). O veredito nao entra como dado a
  reavaliar, so como contexto de tom; nenhum abstract, nenhuma ficha.

## Dry-run gera e persiste incrementalmente; `--aplicar` so le e grava

O dry-run chama a LLM de verdade - e assim que ele consegue mostrar o
"depois" real no relatorio, nao uma estimativa - mas nao escreve em
`fato_triagem`. Em vez disso persiste o par antes/depois de cada paper, **um
por um, assim que a resposta chega** (`_gravar_estado_um`, escrita atomica
via arquivo temporario + `os.replace` - o mesmo padrao de
`estagios/export.py::_escrever`), em
`data/estado/justificativas_migradas.json` (o precedente do proprio lugar e
`backfill/regeneracao.py::registrar_veredito_regenerado`: "entrada de uma
etapa seguinte, nao artefato de leitura" - por isso mora em `data/estado/` e
nao em `relatorios/`).

A persistencia e por paper, nao em lote no final: o dinheiro da chamada de
LLM ja foi gasto quando a resposta chega, nao quando o lote inteiro termina.
Um Ctrl-C perto do fim de ~290 papers no lote `--reescrever` so descartaria o
que ainda nao tinha resposta - nao a rodada inteira. E como a escrita e
atomica, o Ctrl-C nunca encontra o JSON pela metade: ou a versao anterior
(intacta) ou a nova (com mais um paper) chegam ao disco, nunca algo entre as
duas.

Retomar uma geracao interrompida **nao reprocessa o que ja esta salvo**:
antes de gerar cada lote, `main` le `ja_gerados = estado.get(nome_lote, {})`
e `gerar_lote` pula todo `paper_id` ja presente ali. Sem isso, um dry-run
retomado chamaria a LLM de novo para papers ja migrados - pagando duas vezes
e, se um `--aplicar` acontecer entre as duas geracoes, arriscando gravar um
texto gerado numa segunda amostragem que ninguem revisou.

`--aplicar` **le esse arquivo e nao chama a LLM**. Isso e o que faz o
relatorio conferido no dry-run ser de fato o texto gravado: se `--aplicar`
gerasse de novo, com o mesmo prompt mas outra amostragem do modelo, o texto
revisado no relatorio e o texto gravado seriam dois textos diferentes - o
que anularia o proposito do dry-run (`data/` esta fora do git, entao o
relatorio e o unico ponto de conferencia antes de uma escrita irreversivel).
De quebra, evita pagar a geracao de ~290 papers duas vezes.

Antes de gravar cada paper, `aplicar_lote` confere que o `antes` salvo ainda
bate com `fato_triagem.justificativa` no banco. Nao bateu, pula e registra o
motivo no relatorio - e como se detecta que o banco mudou entre o dry-run e o
`--aplicar` (uma reclassificacao manual no meio do caminho, por exemplo).
`--aplicar` sem entrada salva para o lote pedido falha antes de tocar no
banco, com mensagem mandando rodar o dry-run primeiro.

## Backup do banco, sempre que `--aplicar` roda

Antes de abrir qualquer conexao de escrita, `--aplicar` copia
`cfg.caminho_banco` para `<banco>.bak-<carimbo>` usando a API de backup do
proprio SQLite (`Connection.backup`, ler `fazer_backup_banco` para o motivo
de nao ser `shutil.copy2`: o banco roda em WAL, e uma copia de arquivo simples
ignora o `-wal` e pode perder a transacao mais recente, ou ate corromper a
copia se cair no meio de um checkpoint alheio), com `PRAGMA quick_check`
validando o resultado antes de seguir - mesmo carimbo de tempo do relatorio
desta execucao. O caminho e impresso na tela e no cabecalho do relatorio. Se
a copia falhar ou nao passar no `quick_check`, o comando aborta **antes** de
qualquer `UPDATE` - `data/` esta fora do git, entao esta copia e o unico
jeito de desfazer um `--aplicar` errado. Isso nao substitui os cuidados de
idempotencia e de registro descritos abaixo; e a ultima rede de seguranca
quando todos os outros falharem.

## O que fica intocado

So a coluna `justificativa` e escrita, com um `UPDATE` direto
(`_aplicar_um`) - nunca um upsert. Todo `paper_id` deste comando vem de um
`SELECT` sobre `fato_triagem` (as duas consultas de selecao so leem linhas
que ja existem), entao nunca ha caso de insercao: um upsert seria a
ferramenta errada, e nao so por estilo. Um `INSERT ... ON CONFLICT DO
UPDATE` com um dict que so tem `paper_id` e `justificativa` gera uma linha de
INSERT com `veredito`, `classificado_em` e `run_id` nulos - e o SQLite valida
as restricoes NOT NULL dessa linha proposta **antes** de resolver o
`ON CONFLICT`, entao a instrucao morre com `IntegrityError` mesmo quando o
caminho real de execucao e sempre o UPDATE. `veredito`, `regra_fora`, os
campos de portabilidade, `decisao_fronteira`, `revisao` e `dim_ficha` ficam
como estavam (criterio 3). `--aplicar` nunca instancia `ClienteLLM` - so o
dry-run grava em `log_llm` (e assim que o custo e contabilizado); nenhum dos
dois modos toca em nenhuma coluna de `fato_triagem` alem de `justificativa`.

## Interrupcao e nova execucao

Cada paper aplicado e gravado na sua propria transacao (`db.transacao`),
como `estagios/classificacao.py` faz por paper - uma interrupcao no meio
nunca deixa uma escrita pela metade. As listas de diff (`diffs_faltantes`,
`diffs_reescrever`) sao criadas no `main`, **antes** do `try`, e passadas por
parametro para `gerar_lote`/`aplicar_lote`, que fazem `diffs.append(...)` a
cada paper - nunca `return` de uma lista local. Isso importa porque o
relatorio e escrito num `finally` do `main`: se o acumulador fosse o valor de
retorno dessas funcoes, uma interrupcao no meio do laco faria a lista morrer
no frame delas, sem nunca ser atribuida, e o `finally` escreveria um
relatorio vazio mesmo com paper ja commitado no banco.

Em `aplicar_lote`, o `diffs.append` de uma aplicacao bem-sucedida acontece
**antes** de `_aplicar_um` rodar o `UPDATE`, de proposito: se o Ctrl-C cair
entre as duas linhas, o pior cenario e o relatorio listar uma linha que na
verdade nao foi commitada (fica facil de conferir contra o banco) - nunca o
cenario ruim, de uma linha commitada sumir do relatorio.

Rodar o comando de novo tambem nao muda o efeito de uma execucao anterior:

- em `--faltantes`, a selecao exige `justificativa LIKE 'Importado do
  historico (%'`. Assim que um paper e aplicado, a marca some do banco e ele
  cai fora da proxima geracao - idempotente por construcao.
- em `--reescrever` isso e mais fraco na geracao (a consulta nao filtra por
  tamanho: um descartado do estilo antigo ja tem ~181 caracteres, abaixo do
  teto de 300, entao um filtro por tamanho excluiria o lote inteiro dos
  descartados). Quem fecha essa lacuna e o filtro por `ja_gerados` (ver acima)
  na geracao, e a comparacao do "antes" em `aplicar_lote`: rodar `--aplicar`
  duas vezes sobre o mesmo estado salvo so aplica na primeira vez - na
  segunda, o banco ja tem o "depois" gravado, o "antes" nao bate mais, e o
  paper e pulado.

## Limite de 300 caracteres

O schema de saida dos dois prompts usa `maxLength: 300` (`SCHEMA_JUSTIFICATIVA`
abaixo), o mesmo teto que a issue #2 poe em `justificativa_veredito` do
Estagio B - e o motivo de a issue pedir "no maximo 2 frases, no maximo 300
caracteres" nos dois prompts. O `strict` do `response_format` nao garante 100%
de aderencia a `maxLength` em todo provedor, entao `_validar_tamanho` reforca
em codigo: estoura, o cliente re-tenta com a mensagem anexada (o mesmo
mecanismo de `ErroValidacao` que `llm/estagio_b.py` usa).

## Relatorio: um arquivo por lote, por modo e por execucao

`escrever_relatorio` grava em
`relatorios/justificativas_diff_{lotes}_{modo}_{carimbo}.md` (por exemplo,
`justificativas_diff_faltantes_dry_20260904T101500.md`,
`justificativas_diff_reescrever_aplicado_20260904T103000.md`). Tres coisas
exigem isso:

1. o fluxo tipico e dry(`--faltantes`) -> `--aplicar --faltantes` ->
   dry(`--reescrever`) -> `--aplicar --reescrever`: sem o lote e o modo no
   nome, o relatorio do primeiro `--aplicar` seria sobrescrito antes de
   alguem le-lo;
2. `aplicado` e `interrompido` sao independentes (`dry-interrompido` x
   `aplicado-interrompido` sao situacoes muito diferentes: uma nao gravou
   nada, a outra gravou algumas linhas de verdade) e por isso cada combinacao
   tem seu proprio sufixo;
3. rodar `--aplicar` de novo sobre o mesmo estado e inofensivo para o banco
   (fica tudo "pulado", ver idempotencia acima), mas sem o carimbo de tempo
   sobrescreveria o relatorio da gravacao real anterior com uma versao onde
   tudo aparece pulado - apagando o unico registro de uma escrita
   irreversivel.

## Quando apagar

Depois de uma execucao com `--aplicar` bem sucedida e os relatorios
conferidos: apague este arquivo, `prompt_faltantes.md`,
`prompt_reescrever.md`, `data/estado/justificativas_migradas.json`,
`relatorios/justificativas_diff_*.md` e os backups `data/*.bak-*`. Nenhum
deles tem razao para sobreviver ao proprio proposito.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import sqlite3
import sys
import urllib.parse
from pathlib import Path
from typing import Any, Callable, NamedTuple, Optional, Sequence

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "src"))

from hfpapers import db, log
from hfpapers.config import Config, config
from hfpapers.llm import schemas
from hfpapers.llm.cliente import ClienteLLM, ErroLLM, ErroValidacao
from hfpapers.llm.prompts import preencher

DIR_SCRIPT = Path(__file__).resolve().parent

# Marca gravada por `backfill/importacao.py::importar_triagem`. Repetida aqui
# (nao importada de la) porque e um literal de dado, nao um simbolo de codigo.
MARCA_BACKFILL = "Importado do historico ("

# Tag de `log_llm.run_id` para esta migracao aparecer separada nas consultas
# de custo (`hfpapers custos`) - nunca escrita em `fato_triagem.run_id`.
RUN_ID_LOG = "migracao-justificativas"

LIMITE_CARACTERES = 300

# Chaves usadas tanto nas flags de CLI quanto no JSON de estado - o mesmo
# nome do inicio ao fim evita uma tabela de tradução entre os dois.
LOTE_FALTANTES = "faltantes"
LOTE_REESCREVER = "reescrever"

log_ = log.logger("migracao_justificativas")


# ── saida estruturada ────────────────────────────────────────────────────────

SCHEMA_JUSTIFICATIVA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["justificativa"],
    "properties": {
        "justificativa": {"type": "string", "maxLength": LIMITE_CARACTERES},
    },
}

SISTEMA_FALTANTES = (
    "Voce escreve, em portugues do Brasil, a justificativa de um veredito de "
    "classificacao de papers de IA que ja foi decidido por outra pessoa. Nunca "
    "questiona o veredito, nunca sugere outro - so explica por que ele e "
    "correto, em linguagem simples e direta. No maximo 2 frases, no maximo "
    "300 caracteres. Responde sempre em JSON valido."
)

SISTEMA_REESCREVER = (
    "Voce reescreve, em portugues do Brasil, uma justificativa de veredito que "
    "ja existe, condensando o estilo: linguagem simples e direta, no maximo 2 "
    "frases, no maximo 300 caracteres. Nao reavalia o veredito nem acrescenta "
    "informacao que nao esteja no texto original. Responde sempre em JSON "
    "valido."
)


def _validar_tamanho(dados: dict[str, Any]) -> None:
    texto = (dados.get("justificativa") or "").strip()
    if not texto:
        raise ErroValidacao("justificativa vazia")
    if len(texto) > LIMITE_CARACTERES:
        raise ErroValidacao(
            f"justificativa com {len(texto)} caracteres, teto e {LIMITE_CARACTERES}"
        )


def _carregar_prompt(nome: str) -> str:
    return (DIR_SCRIPT / f"{nome}.md").read_text(encoding="utf-8")


def _carimbo() -> str:
    """Carimbo com resolucao de microssegundo, nao de segundo.

    `--aplicar` nao chama a LLM - so `UPDATE`s, ~0,002s para 3 papers, muito
    abaixo de 1s mesmo com ~290. Dois `--aplicar` seguidos (seta pra cima e
    enter, o gesto mais provavel do mundo) cairiam no mesmo segundo com um
    carimbo `%S`: o segundo, onde tudo aparece "pulado: banco mudou desde o
    dry-run" (ver `aplicar_lote`), substituiria o relatorio da gravacao real
    - exatamente o que o carimbo existe para impedir. `%f` fecha essa janela;
    `escrever_relatorio` ainda recusa sobrescrever, como cinto e suspensorio.
    """
    # `dt.timezone.utc`, nao o alias `dt.UTC` (ruff UP017): o alias e Python
    # 3.11+ e o interpretador do projeto o tem, mas o `pyright` instalado
    # nesta maquina nao o reconhece (typeshed antigo) e pyright limpo e gate
    # de revisao nesta issue. Ja foi tentado e revertido - nao "conserte" de
    # volta para o alias sem checar se o pyright local aprendeu `dt.UTC`.
    return dt.datetime.now(dt.timezone.utc).astimezone().strftime("%Y%m%dT%H%M%S_%f")


# ── selecao dos dois lotes ───────────────────────────────────────────────────


def selecionar_faltantes(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    """Aprovados do backfill com ficha, ainda carregando a marca de importado.

    O INNER JOIN com `dim_ficha` e a exigencia do criterio 1: aprovado do
    backfill sem ficha fica de fora (nao ha base para escrever justificativa
    nenhuma). O filtro pela marca faz o lote encolher sozinho a cada execucao
    aplicada - ver a secao de idempotencia no docstring do modulo.
    """
    sql = """
        SELECT ft.paper_id, ft.veredito, ft.justificativa,
               dp.titulo, dp.abstract, dp.ai_summary,
               df.achado, df.padrao_nome, df.padrao_mecanismo,
               df.implicacao_pratica, df.exemplo_concreto, df.ressalva
        FROM fato_triagem ft
        JOIN dim_paper dp ON dp.paper_id = ft.paper_id
        JOIN dim_ficha df ON df.paper_id = ft.paper_id
        WHERE ft.run_id = 'backfill'
          AND ft.veredito IN ('amplo', 'estrito')
          AND ft.justificativa LIKE ?
        ORDER BY ft.paper_id
    """
    # A marca ("Importado do historico (") nao tem "_" nem "%" - dispensa
    # escape de LIKE.
    return conn.execute(sql, (MARCA_BACKFILL + "%",)).fetchall()


def selecionar_reescrever(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    """Papers do pipeline vivo, qualquer veredito, com justificativa propria.

    `run_id != 'backfill'` e a fronteira que a issue pede - inclui aprovados
    (~410 caracteres) e descartados (~181 caracteres) do estilo antigo. Sem
    filtro de tamanho de proposito: um filtro por caractere excluiria os
    descartados, que ja nascem abaixo do teto de 300 mas ainda estao no
    estilo antigo (ver a ressalva de idempotencia no docstring do modulo).
    """
    sql = """
        SELECT paper_id, veredito, justificativa
        FROM fato_triagem
        WHERE run_id != 'backfill'
          AND justificativa IS NOT NULL
          AND TRIM(justificativa) != ''
        ORDER BY paper_id
    """
    return conn.execute(sql).fetchall()


# ── prompts por linha ────────────────────────────────────────────────────────


def montar_prompt_faltantes(row: sqlite3.Row, template: str) -> str:
    return preencher(
        template,
        VEREDITO=row["veredito"],
        TITULO=row["titulo"],
        ABSTRACT=row["abstract"] or row["ai_summary"] or "(abstract indisponivel)",
        ACHADO=row["achado"] or "(nao registrado)",
        PADRAO_NOME=row["padrao_nome"] or "(achado empirico, sem padrao extraido)",
        PADRAO_MECANISMO=row["padrao_mecanismo"] or "-",
        IMPLICACAO_PRATICA=row["implicacao_pratica"] or "(nao registrada)",
        EXEMPLO_CONCRETO=row["exemplo_concreto"] or "(nao registrado)",
        RESSALVA=row["ressalva"] or "(nao registrada)",
    )


def montar_prompt_reescrever(row: sqlite3.Row, template: str) -> str:
    return preencher(
        template,
        VEREDITO=row["veredito"],
        JUSTIFICATIVA_ATUAL=row["justificativa"],
    )


# ── estado (data/estado/) ────────────────────────────────────────────────────


def _arquivo_estado(cfg: Config) -> Path:
    return cfg.dir_estado / "justificativas_migradas.json"


def _carregar_estado(cfg: Config) -> dict[str, dict[str, dict[str, str]]]:
    """Le o JSON de estado. Um arquivo corrompido precisa travar a execucao.

    Engolir `JSONDecodeError` e devolver `{}` teria duas consequencias ruins:
    `--aplicar` diria "nao ha estado salvo" e mandaria regerar (caro, e a
    ilusao de que nada foi perdido); e `_gravar_estado_um`, partindo de um
    dict vazio, sobrescreveria o arquivo apagando silenciosamente o lote que
    ja estava salvo. Deixar o erro propagar e mais barato que os dois.
    """
    caminho = _arquivo_estado(cfg)
    if not caminho.exists():
        return {}
    try:
        return json.loads(caminho.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise RuntimeError(
            f"{caminho} esta corrompido ({e}). Renomeie-o para '.corrompido' (preserva "
            "o lote que ainda estiver integro no meio do arquivo, para inspecao manual) "
            "e rode o dry-run de novo, ou restaure de um backup antes de rodar --aplicar "
            "- nao ha como saber, so por este arquivo, o que ja foi ou nao aplicado."
        ) from e


def _gravar_estado_um(
    cfg: Config, nome_lote: str, paper_id: str, antes: str, depois: str
) -> None:
    """Persiste um par assim que a LLM responde, com escrita atomica.

    `write_text` trunca o arquivo antes de escrever; um Ctrl-C nessa janela -
    que acontece ~290 vezes por rodada, exatamente onde o comando espera ser
    interrompido - deixaria o JSON pela metade, e `_carregar_estado` trava de
    proposito nesse caso (ver o docstring dela). Escrever num `.tmp` e trocar
    com `os.replace` (atomico no mesmo volume - o padrao ja usado em
    `estagios/export.py::_escrever`) elimina essa janela: o arquivo final e
    sempre a versao anterior intacta ou a nova, nunca as duas misturadas.
    """
    estado = _carregar_estado(cfg)
    estado.setdefault(nome_lote, {})[paper_id] = {"antes": antes, "depois": depois}
    cfg.dir_estado.mkdir(parents=True, exist_ok=True)
    destino = _arquivo_estado(cfg)
    tmp = destino.with_suffix(".json.tmp")
    try:
        tmp.write_text(
            json.dumps(estado, ensure_ascii=False, indent=2, sort_keys=True),
            encoding="utf-8",
        )
        os.replace(tmp, destino)
    except BaseException:
        # Um Ctrl-C entre o `write_text` e o `os.replace` deixaria o `.tmp`
        # para tras - inocuo (nunca e lido, a proxima chamada sobrescreve),
        # mas suja o diretorio que o docstring do modulo manda apagar no fim.
        tmp.unlink(missing_ok=True)
        raise


def carregar_lote_estado(cfg: Config, nome_lote: str) -> dict[str, dict[str, str]]:
    """O que `--aplicar` le - nunca chama a LLM.

    Falha cedo e com mensagem clara se o dry-run do lote nunca rodou: cair no
    caminho de gerar aqui reabriria exatamente o problema que o estado existe
    para evitar (o texto aplicado seria outra amostragem, nao a conferida).
    """
    itens = _carregar_estado(cfg).get(nome_lote)
    if not itens:
        raise SystemExit(
            f"nao ha estado salvo para o lote '--{nome_lote}' em {_arquivo_estado(cfg)}. "
            f"Rode `--{nome_lote}` sem `--aplicar` primeiro (o dry-run)."
        )
    return itens


# ── backup do banco (--aplicar) ──────────────────────────────────────────────


def fazer_backup_banco(cfg: Config, carimbo: str) -> Path:
    """Copia do banco antes de qualquer `UPDATE` - ver o docstring do modulo.

    NAO troque isto por `shutil.copy2`. `schema.sql` liga
    `PRAGMA journal_mode = WAL`, e isso e persistente no arquivo: o banco de
    producao roda em WAL. Em WAL, uma transacao commitada pode viver so no
    `-wal` ate o checkpoint - `copy2` copia o `.db` e ignora o `-wal`, entao a
    copia perde a linha commitada mais recente sempre que alguma outra
    conexao (um browser de SQLite aberto, um refresh do Power BI, um run
    anterior morto) ainda nao fez checkpoint. Pior: em WAL o arquivo
    principal so muda *durante* um checkpoint alheio, entao um `copy2` que
    caia no meio de um produz um `.bak` corrompido - e nada validava a copia
    depois.

    A API de backup do proprio SQLite (`Connection.backup`) serializa contra
    o WAL: le a origem em modo somente-leitura (`mode=ro` na URI - nunca abre
    para escrita, entao nunca dispara `migrar()`, que escreveria no banco
    antes mesmo do `--aplicar` comecar) e copia paginas de forma consistente,
    checkpoint ou nao. O `PRAGMA quick_check` depois e parte da correcao, nao
    um extra: sem ele a copia continua sendo uma promessa nao verificada, e
    uma rede de seguranca que pode estar rasgada e pior que nenhuma - muda o
    que alguem se permite arriscar depois, achando que tem como desfazer.

    Aborta em vez de seguir sem copia intacta: `data/` esta fora do git, e
    esta e a unica forma de desfazer um `--aplicar` que sair errado.
    """
    origem = cfg.caminho_banco
    if not origem.exists():
        raise SystemExit(
            f"banco nao encontrado em {origem}; nada para copiar, nada para aplicar."
        )
    destino = origem.with_name(f"{origem.name}.bak-{carimbo}")
    # `quote`: o caminho vira parte de uma URI (`file:...?mode=ro`) - um "%",
    # "?" ou "#" nele seria lido como sintaxe de URI em vez de caractere do
    # caminho, e abriria o arquivo errado (ou nenhum). Nao acontece com o
    # caminho atual do projeto, mas o custo de nao blindar e alto.
    uri_origem = f"file:{urllib.parse.quote(str(origem))}?mode=ro"
    origem_conn: Optional[sqlite3.Connection] = None
    destino_conn: Optional[sqlite3.Connection] = None
    try:
        origem_conn = sqlite3.connect(uri_origem, uri=True)
        destino_conn = sqlite3.connect(destino)
        with destino_conn:
            origem_conn.backup(destino_conn)
        (resultado,) = destino_conn.execute("PRAGMA quick_check").fetchone()
        if resultado != "ok":
            destino_conn.close()
            destino_conn = None
            # Um backup reprovado no disco e pior que nenhum: `ls
            # data/*.bak-*` mostraria o mais recente como se fosse valido -
            # a "rede de seguranca rasgada" que o quick_check existe para
            # impedir. Apaga antes de abortar.
            destino.unlink(missing_ok=True)
            raise SystemExit(
                f"backup do banco falhou no quick_check ({resultado}); arquivo invalido "
                f"{destino} foi apagado - abortando --aplicar sem gravar nada."
            )
    except sqlite3.Error as e:
        raise SystemExit(
            f"backup do banco falhou ({e}) - abortando --aplicar sem gravar nada."
        ) from e
    finally:
        if origem_conn is not None:
            origem_conn.close()
        if destino_conn is not None:
            destino_conn.close()
    return destino


# ── geracao (dry-run) ────────────────────────────────────────────────────────


def _gerar(
    cliente: ClienteLLM,
    *,
    etapa: str,
    sistema: str,
    prompt: str,
    paper_id: str,
) -> Optional[str]:
    try:
        resposta = cliente.chamar(
            etapa=etapa,
            modelo=cliente.cfg.llm.estagio_b.modelo,
            prompt=prompt,
            sistema=sistema,
            response_format=schemas.response_format(
                "justificativa_migrada", SCHEMA_JUSTIFICATIVA
            ),
            # temperatura baixa e teto curto: e reescrita/explicacao de uma
            # frase, nao geracao de ficha - nao ha razao para o orcamento de
            # `cfg.llm.estagio_b` (pensado para os 4 campos da ficha inteira).
            temperatura=0.2,
            max_tokens=400,
            paper_id=paper_id,
            validar=_validar_tamanho,
        )
    except ErroLLM as e:
        log_.error("%s falhou em %s: %s", etapa, paper_id, e)
        return None
    return resposta.dados["justificativa"].strip()


def gerar_lote(
    cliente: ClienteLLM,
    linhas: Sequence[sqlite3.Row],
    *,
    etapa: str,
    sistema: str,
    template: str,
    montar_prompt: Callable[[sqlite3.Row, str], str],
    cfg: Config,
    nome_lote: str,
    ja_gerados: dict[str, dict[str, str]],
    diffs: list[dict[str, Any]],
) -> None:
    """So gera e persiste o estado - nunca escreve em `fato_triagem`.

    `ja_gerados` e o estado salvo por uma execucao anterior deste mesmo lote:
    todo `paper_id` ja presente ali e pulado, sem chamar a LLM de novo - ver
    a secao "retomar uma geracao interrompida" no docstring do modulo.

    `diffs` e o acumulador do `main`, passado por referencia: cada paper faz
    `diffs.append(...)` diretamente nele, em vez de voltar num `return` -
    uma interrupcao no meio do laco nao perde o que ja foi processado (ver a
    secao de interrupcao no docstring do modulo).
    """
    for row in linhas:
        if row["paper_id"] in ja_gerados:
            continue
        antes = row["justificativa"]
        prompt = montar_prompt(row, template)
        depois = _gerar(
            cliente,
            etapa=etapa,
            sistema=sistema,
            prompt=prompt,
            paper_id=row["paper_id"],
        )
        if depois is None:
            diffs.append(
                {
                    "paper_id": row["paper_id"],
                    "antes": antes,
                    "depois": None,
                    "erro": "chamada LLM falhou",
                }
            )
            continue
        _gravar_estado_um(cfg, nome_lote, row["paper_id"], antes, depois)
        diffs.append(
            {
                "paper_id": row["paper_id"],
                "antes": antes,
                "depois": depois,
                "erro": None,
            }
        )


# ── gravacao (--aplicar) ─────────────────────────────────────────────────────


def _aplicar_um(conn: sqlite3.Connection, paper_id: str, justificativa: str) -> None:
    """UPDATE direto - nunca upsert. Ver "O que fica intocado" no docstring do modulo."""
    with db.transacao(conn):
        conn.execute(
            "UPDATE fato_triagem SET justificativa = ? WHERE paper_id = ?",
            (justificativa, paper_id),
        )


def aplicar_lote(
    conn: sqlite3.Connection,
    itens: dict[str, dict[str, str]],
    diffs: list[dict[str, Any]],
) -> None:
    """Grava o `depois` salvo, um paper por vez, so quando o `antes` ainda bate.

    A conferencia contra o banco atual e o que torna uma segunda chamada de
    `--aplicar` sobre o mesmo estado inofensiva (ver idempotencia no
    docstring do modulo): depois da primeira aplicacao, o banco tem o
    `depois`, o `antes` nao bate mais, e o paper e pulado em vez de reaplicado.

    `diffs` e o acumulador do `main`, passado por referencia - ver
    `gerar_lote` para a razao geral. Aqui o `append` acontece **antes** do
    `UPDATE`, de proposito - ver a secao de interrupcao no docstring do
    modulo: o pior caso vira "uma linha a mais no relatorio", nunca "uma
    linha gravada que ninguem registrou".
    """
    for paper_id, registro in itens.items():
        antes_esperado = registro.get("antes")
        depois = registro.get("depois")
        atual = conn.execute(
            "SELECT justificativa FROM fato_triagem WHERE paper_id = ?", (paper_id,)
        ).fetchone()
        if atual is None:
            diffs.append(
                {
                    "paper_id": paper_id,
                    "antes": antes_esperado,
                    "depois": None,
                    "erro": "paper nao existe mais em fato_triagem",
                }
            )
            continue
        if atual["justificativa"] != antes_esperado or not depois:
            diffs.append(
                {
                    "paper_id": paper_id,
                    "antes": atual["justificativa"],
                    "depois": None,
                    "erro": (
                        "estado salvo sem 'depois'"
                        if not depois
                        else "banco mudou desde o dry-run; pulado"
                    ),
                }
            )
            continue
        diffs.append(
            {
                "paper_id": paper_id,
                "antes": antes_esperado,
                "depois": depois,
                "erro": None,
            }
        )
        _aplicar_um(conn, paper_id, depois)


# ── relatorio ────────────────────────────────────────────────────────────────


def _escapar_md(texto: Optional[str]) -> str:
    return (
        (texto or "—")
        .replace("\r\n", " ")
        .replace("\n", " ")
        .replace("\r", " ")
        .replace("|", "\\|")
        .strip()
    )


def _tabela_lote(
    titulo: str, diffs: list[dict[str, Any]], *, pulados_ja_migrados: int = 0
) -> list[str]:
    md = [f"## {titulo}\n"]
    if pulados_ja_migrados:
        md.append(
            f"{pulados_ja_migrados} papers pulados por ja estarem no estado salvo "
            "(retomada de uma execucao anterior) - ver o relatorio dessa execucao "
            "para o antes/depois deles.\n"
        )
    if not diffs:
        md.append("Nenhum paper neste lote.\n")
        return md
    falhas = [d for d in diffs if d["erro"]]
    md.append(
        f"{len(diffs)} papers no lote, {len(falhas)} nao foram gravados/gerados.\n"
    )
    md.append("| paper_id | antes | depois |")
    md.append("|---|---|---|")
    for d in diffs:
        depois = (
            _escapar_md(d["depois"])
            if d["depois"] is not None
            else f"**(pulado: {_escapar_md(d['erro'])})**"
        )
        md.append(f"| {d['paper_id']} | {_escapar_md(d['antes'])} | {depois} |")
    md.append("")
    return md


def _nome_relatorio(
    *, lotes: Sequence[str], aplicado: bool, interrompido: bool, carimbo: str
) -> str:
    """Um arquivo por combinacao de lote(s), modo e execucao - ver o docstring do modulo.

    `aplicado` e `interrompido` sao dimensoes independentes: um dry-run
    interrompido ("nada gravado") e um --aplicar interrompido ("algumas
    linhas ja foram gravadas") nao podem colidir no mesmo nome. O carimbo de
    tempo impede que um segundo `--aplicar` (inofensivo para o banco, mas
    reprocessando so "pulados") sobrescreva o relatorio da gravacao real.
    """
    sufixo_lotes = "-".join(lotes)
    modo = ("aplicado" if aplicado else "dry") + (
        "-interrompido" if interrompido else ""
    )
    return f"justificativas_diff_{sufixo_lotes}_{modo}_{carimbo}.md"


def _caminho_disponivel(diretorio: Path, nome: str) -> Path:
    """Nunca sobrescreve um relatorio existente - cinto e suspensorio junto
    com o microssegundo de `_carimbo`. Se o nome ja existe (dois `--aplicar`
    tao rapidos que colidiram mesmo assim, ou um relatorio de execucao
    anterior que ninguem apagou), sufixa com um contador em vez de substituir
    o arquivo - o unico registro de uma escrita irreversivel nao pode ser
    vitima de uma colisao de nome.
    """
    caminho = diretorio / nome
    if not caminho.exists():
        return caminho
    base, _, ext = nome.rpartition(".")
    base, ext = (base, f".{ext}") if base else (nome, "")
    n = 2
    while True:
        candidato = diretorio / f"{base}-{n}{ext}"
        if not candidato.exists():
            return candidato
        n += 1


def _linha_modo(*, aplicado: bool, interrompido: bool) -> str:
    if interrompido and aplicado:
        return (
            "**APLICADO, INTERROMPIDO** - as linhas abaixo marcadas como gravadas JA foram "
            "escritas em `fato_triagem` antes da interrupcao."
        )
    if interrompido:
        return "**dry-run, INTERROMPIDO** - nada foi gravado em `fato_triagem`."
    if aplicado:
        return "**APLICADO** (gravado em `fato_triagem.justificativa`)"
    return "**dry-run** (nada foi gravado em `fato_triagem`)"


def escrever_relatorio(
    cfg: Config,
    *,
    diffs_faltantes: list[dict[str, Any]],
    diffs_reescrever: list[dict[str, Any]],
    lotes: Sequence[str],
    aplicado: bool,
    carimbo: str,
    interrompido: bool = False,
    backup: Optional[Path] = None,
    pulados: Optional[dict[str, int]] = None,
) -> Path:
    """Antes -> depois de cada paper - o padrao de `backfill/validacao.py`.

    E o unico ponto de conferencia desta migracao: `data/` esta fora do git,
    entao nao ha `git diff` do banco para olhar depois de um `--aplicar`. Por
    isso o `main` sempre chama esta funcao num `finally`: mesmo uma execucao
    interrompida (Ctrl-C, exception) deixa registrado o que foi efetivamente
    gravado ate ali - cada paper aplicado ja foi commitado na propria
    transacao antes de a interrupcao chegar.
    """
    pulados = pulados or {}
    md: list[str] = ["# Uniformização das justificativas de veredito\n"]
    md.append(f"Gerado em {db.agora()}  ")
    md.append(f"Modo: {_linha_modo(aplicado=aplicado, interrompido=interrompido)}\n")
    if backup is not None:
        md.append(f"Backup do banco antes desta gravacao: `{backup}`\n")
    md.extend(
        _tabela_lote(
            "Lote `--faltantes` (aprovados do backfill, ficha existente)",
            diffs_faltantes,
            pulados_ja_migrados=pulados.get(LOTE_FALTANTES, 0),
        )
    )
    md.extend(
        _tabela_lote(
            "Lote `--reescrever` (pipeline vivo, qualquer veredito)",
            diffs_reescrever,
            pulados_ja_migrados=pulados.get(LOTE_REESCREVER, 0),
        )
    )
    md.append(
        "> Descartados do backfill (`run_id = 'backfill'`, veredito `fora`) nao entram em "
        "lote nenhum: nao tem ficha, e o veredito historico segue autoritativo sem "
        "justificativa nova (issue #3)."
    )
    md.append("")
    if interrompido:
        md.append(
            "> Execucao interrompida antes de terminar o lote. As linhas acima ja foram "
            "processadas (gravadas, se `--aplicar`); rode o comando de novo para continuar - "
            "o dry-run pula quem ja esta no estado salvo, e `--aplicar` so aplica o que ainda "
            "bater com o banco."
        )
    elif not aplicado:
        md.append(
            '> Nada foi gravado em fato_triagem. Confira a coluna "depois" acima e rode de novo '
            "com `--aplicar` para gravar (le o estado salvo, nao chama a LLM de novo)."
        )

    cfg.dir_relatorios.mkdir(parents=True, exist_ok=True)
    nome = _nome_relatorio(
        lotes=lotes, aplicado=aplicado, interrompido=interrompido, carimbo=carimbo
    )
    caminho = _caminho_disponivel(cfg.dir_relatorios, nome)
    caminho.write_text("\n".join(md), encoding="utf-8")
    return caminho


# ── CLI ──────────────────────────────────────────────────────────────────────


class _Lote(NamedTuple):
    """Um lote: nome (== chave no JSON de estado), consulta, prompt, etapa
    (para `log_llm`), mensagem de sistema, montador de prompt. `NamedTuple`
    em vez de tupla solta - os seis campos tem tipos diferentes, e um
    desempacotamento posicional errado ao adicionar/remover um campo passaria
    batido pelo pyright."""

    nome: str
    selecionar: Callable[[sqlite3.Connection], list[sqlite3.Row]]
    prompt_nome: str
    etapa: str
    sistema: str
    montar_prompt: Callable[[sqlite3.Row, str], str]


# `main` itera esta lista em vez de repetir o par if-lote/if-aplicar para
# cada um dos dois lotes.
_LOTES: tuple[_Lote, ...] = (
    _Lote(
        LOTE_FALTANTES,
        selecionar_faltantes,
        "prompt_faltantes",
        "migracao_faltantes",
        SISTEMA_FALTANTES,
        montar_prompt_faltantes,
    ),
    _Lote(
        LOTE_REESCREVER,
        selecionar_reescrever,
        "prompt_reescrever",
        "migracao_reescrever",
        SISTEMA_REESCREVER,
        montar_prompt_reescrever,
    ),
)


def _parse_args(argv: Optional[Sequence[str]]) -> argparse.Namespace:
    ap = argparse.ArgumentParser(
        description=(
            "Uniformiza as justificativas de veredito ja gravadas (issue #3). "
            "Comando temporario - ver o docstring do modulo."
        )
    )
    ap.add_argument(
        "--faltantes",
        action="store_true",
        help="Gera (dry-run) ou grava (--aplicar) a justificativa post-hoc dos aprovados do backfill com ficha.",
    )
    ap.add_argument(
        "--reescrever",
        action="store_true",
        help="Gera (dry-run) ou grava (--aplicar) a condensacao das justificativas do pipeline vivo.",
    )
    ap.add_argument(
        "--aplicar",
        action="store_true",
        help=(
            "Faz backup do banco, le data/estado/justificativas_migradas.json e grava em "
            "fato_triagem.justificativa. Sem esta flag, so gera esse estado e o relatorio de "
            "diff - nao toca em fato_triagem (o dry-run ainda registra custo em log_llm, via "
            "ClienteLLM)."
        ),
    )
    args = ap.parse_args(argv)
    if not args.faltantes and not args.reescrever:
        ap.error("informe --faltantes e/ou --reescrever")
    return args


def _lotes_pedidos(args: argparse.Namespace) -> list[_Lote]:
    pedidos = {LOTE_FALTANTES: args.faltantes, LOTE_REESCREVER: args.reescrever}
    return [lote for lote in _LOTES if pedidos[lote.nome]]


def _rodar_aplicar(
    conn: sqlite3.Connection,
    lotes: Sequence[_Lote],
    estados: dict[str, dict[str, dict[str, str]]],
    diffs: dict[str, list[dict[str, Any]]],
) -> None:
    for lote in lotes:
        aplicar_lote(conn, estados[lote.nome], diffs[lote.nome])


def _rodar_dry(
    cfg: Config,
    conn: sqlite3.Connection,
    lotes: Sequence[_Lote],
    diffs: dict[str, list[dict[str, Any]]],
    pulados: dict[str, int],
) -> ClienteLLM:
    """`pulados` e preenchido por lote, por referencia - mesma razao de `diffs`
    (ver a secao de interrupcao no docstring do modulo): sem isso, uma
    retomada interrompida perderia a contagem de quanto ja estava no estado
    salvo, e o relatorio nao teria como avisar "veja o relatorio anterior"."""
    cliente = ClienteLLM(cfg, conn=conn, run_id=RUN_ID_LOG)
    estado_atual = _carregar_estado(cfg)
    for lote in lotes:
        linhas_db = lote.selecionar(conn)
        ja_gerados = estado_atual.get(lote.nome, {})
        pulados[lote.nome] = sum(1 for r in linhas_db if r["paper_id"] in ja_gerados)
        template = _carregar_prompt(lote.prompt_nome)
        gerar_lote(
            cliente,
            linhas_db,
            etapa=lote.etapa,
            sistema=lote.sistema,
            template=template,
            montar_prompt=lote.montar_prompt,
            cfg=cfg,
            nome_lote=lote.nome,
            ja_gerados=ja_gerados,
            diffs=diffs[lote.nome],
        )
    return cliente


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = _parse_args(argv)
    cfg = config()
    lotes = _lotes_pedidos(args)
    carimbo = _carimbo()

    # Falha antes de abrir conexao, fazer backup ou gerar relatorio: --aplicar
    # sem estado salvo nunca deve cair no caminho de gerar (ver docstring).
    estados = (
        {lote.nome: carregar_lote_estado(cfg, lote.nome) for lote in lotes}
        if args.aplicar
        else {}
    )

    backup: Optional[Path] = None
    if args.aplicar:
        backup = fazer_backup_banco(cfg, carimbo)
        print(f"backup do banco: {backup}")

    log.configurar(cfg.dir_logs)
    conn = db.abrir(cfg)
    diffs: dict[str, list[dict[str, Any]]] = {LOTE_FALTANTES: [], LOTE_REESCREVER: []}
    pulados: dict[str, int] = {LOTE_FALTANTES: 0, LOTE_REESCREVER: 0}
    cliente: Optional[ClienteLLM] = None
    interrompido = False
    try:
        if args.aplicar:
            _rodar_aplicar(conn, lotes, estados, diffs)
        else:
            cliente = _rodar_dry(cfg, conn, lotes, diffs, pulados)
    except BaseException:
        # Cobre Ctrl-C (KeyboardInterrupt) e qualquer excecao: o relatorio no
        # `finally` abaixo ainda precisa refletir o que ja foi processado.
        interrompido = True
        raise
    finally:
        conn.close()
        caminho = escrever_relatorio(
            cfg,
            diffs_faltantes=diffs[LOTE_FALTANTES],
            diffs_reescrever=diffs[LOTE_REESCREVER],
            lotes=[lote.nome for lote in lotes],
            aplicado=args.aplicar,
            carimbo=carimbo,
            interrompido=interrompido,
            backup=backup,
            pulados=pulados,
        )
        print(
            f"faltantes: {len(diffs[LOTE_FALTANTES])} papers | reescrever: {len(diffs[LOTE_REESCREVER])} papers"
        )
        if cliente is not None:
            print(
                f"LLM: {cliente.uso.chamadas} chamadas, US$ {cliente.uso.custo_usd:.4f}"
            )
        print(f"relatorio: {caminho}")

    if not args.aplicar:
        print(
            "dry-run: nada foi gravado em fato_triagem. Rode de novo com --aplicar para gravar."
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
