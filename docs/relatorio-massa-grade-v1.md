# Relatório de massa — grade v1 (ticket 07, rodada 1)

> **Não regenere este arquivo.** Ele é a medição que causou a grade v2, e o banco
> já não o reproduz: as fusões da regra 2 do ticket 08 reescreveram a ponte de
> área. `scripts/relatorio_massa.py` grava neste caminho por **padrão**, em
> silêncio — sempre passe o arquivo de destino como segundo argumento. A medição
> vigente é `relatorio-massa-grade-v2.md`.

- **Rodada**: `run-20260908-162429` — Estágio A apenas, concorrência 4
- **Base**: 3166 papers
- **Checagens**: `docs/spec-taxonomia-facetada.md`, seção *Operação*, passo 5

## 1. Cobertura

| | papers | % da base |
|---|---:|---:|
| com par primário (área > sub-área) | 3163 | 99.9% |
| com par secundário | 1024 | 32.3% |
| com ao menos uma vertente | 3166 | 100.0% |
| com duas vertentes | 628 | 19.8% |
| **sem faceta nenhuma** | 0 | 0.0% |

## 2. Distribuição por área e sub-área

Percentual da sub-área **dentro da sua área**. Acima de 25% falta
ramificar; abaixo de 3% da área ou de 10 papers, a
regra manda fundir.

| Área | Sub-área | papers | % da área | leitura |
|---|---|---:|---:|---|
| **Modelo & treino** | _899 papers_ | | | |
| | Pós-treino & RL | 547 | 60.8% | **ramificar** (acima de 25%) |
| | Pré-treino & arquitetura | 204 | 22.7% | **no limiar** |
| | Dados de treino & sintéticos | 80 | 8.9% |  |
| | Destilação & quantização | 68 | 7.6% |  |
| **Geração de mídia** | _593 papers_ | | | |
| | Imagem & difusão | 204 | 34.4% | **ramificar** (acima de 25%) |
| | Vídeo & animação | 188 | 31.7% | **ramificar** (acima de 25%) |
| | 3D & cena | 112 | 18.9% |  |
| | World models generativos | 56 | 9.4% |  |
| | Áudio & música | 33 | 5.6% | **no limiar** |
| **Avaliação & instrumentação** | _450 papers_ | | | |
| | Benchmark de agente | 190 | 42.2% | **ramificar** (acima de 25%) |
| | Benchmark de domínio | 143 | 31.8% | **ramificar** (acima de 25%) |
| | Protocolo & metodologia | 57 | 12.7% |  |
| | Diagnóstico de falha | 37 | 8.2% |  |
| | LLM como avaliador | 21 | 4.7% | **no limiar** |
| | Custo da avaliação | 2 | 0.4% | fundir (0.4% da área e 2 papers) · **no limiar** |
| **Percepção & robótica** | _366 papers_ | | | |
| | VLA & manipulação | 194 | 53.0% | **ramificar** (acima de 25%) |
| | Rastreamento & detecção | 65 | 17.8% |  |
| | Navegação & mundo físico | 57 | 15.6% |  |
| | Sensores & percepção 3D | 50 | 13.7% |  |
| **Contexto & recuperação** | _228 papers_ | | | |
| | RAG & recuperação | 86 | 37.7% | **ramificar** (acima de 25%) |
| | Memória de longo prazo | 67 | 29.4% | **ramificar** (acima de 25%) |
| | Skills & conhecimento compilado | 48 | 21.1% |  |
| | Compressão & alocação de contexto | 21 | 9.2% |  |
| | Verificação de fonte & citação | 6 | 2.6% | fundir (2.6% da área e 6 papers) · **no limiar** |
| **Harness & orquestração** | _225 papers_ | | | |
| | Laço de execução & trajetória | 72 | 32.0% | **ramificar** (acima de 25%) |
| | Sistemas multiagente | 52 | 23.1% | **no limiar** |
| | Auto-evolução do harness | 49 | 21.8% |  |
| | Engenharia de código com agente | 25 | 11.1% |  |
| | Pesquisa autônoma | 25 | 11.1% |  |
| | Elicitação & requisito | 2 | 0.9% | fundir (0.9% da área e 2 papers) · **no limiar** |
| **Serving & inferência** | _145 papers_ | | | |
| | Atenção, kernel & cache | 59 | 40.7% | **ramificar** (acima de 25%) |
| | Escala em tempo de inferência | 37 | 25.5% | **ramificar** (acima de 25%) · **no limiar** |
| | Infraestrutura & deployment | 19 | 13.1% |  |
| | Orçamento de token visual | 15 | 10.3% |  |
| | Roteamento de modelos | 15 | 10.3% |  |
| **Guardrails & controle** | _114 papers_ | | | |
| | Risco & dano | 48 | 42.1% | **ramificar** (acima de 25%) |
| | Guard models | 23 | 20.2% |  |
| | Detecção de alucinação | 17 | 14.9% |  |
| | Injeção & delegação | 16 | 14.0% |  |
| | Política & conformidade | 10 | 8.8% |  |
| **Internos do modelo** | _91 papers_ | | | |
| | Interpretabilidade & sondas | 73 | 80.2% | **ramificar** (acima de 25%) |
| | Atalhos & espúrios | 9 | 9.9% | fundir (9 papers) |
| | Fidelidade do raciocínio | 9 | 9.9% | fundir (9 papers) |
| **Interface & modalidade** | _52 papers_ | | | |
| | Fala & áudio | 19 | 36.5% | **ramificar** (acima de 25%) |
| | GUI & visão de tela | 18 | 34.6% | **ramificar** (acima de 25%) |
| | Documento & extração | 12 | 23.1% | **no limiar** |
| | Vídeo & streaming | 3 | 5.8% | fundir (3 papers) · **no limiar** |

**Checagem A — nenhuma sub-área acima de ~25% da sua área**: FALHA, 15 acima do teto.
  - Modelo & treino > Pós-treino & RL: 547 papers, 60.8%
  - Geração de mídia > Imagem & difusão: 204 papers, 34.4%
  - Geração de mídia > Vídeo & animação: 188 papers, 31.7%
  - Avaliação & instrumentação > Benchmark de agente: 190 papers, 42.2%
  - Avaliação & instrumentação > Benchmark de domínio: 143 papers, 31.8%
  - Percepção & robótica > VLA & manipulação: 194 papers, 53.0%
  - Contexto & recuperação > RAG & recuperação: 86 papers, 37.7%
  - Contexto & recuperação > Memória de longo prazo: 67 papers, 29.4%
  - Harness & orquestração > Laço de execução & trajetória: 72 papers, 32.0%
  - Serving & inferência > Atenção, kernel & cache: 59 papers, 40.7%
  - Serving & inferência > Escala em tempo de inferência: 37 papers, 25.5%
  - Guardrails & controle > Risco & dano: 48 papers, 42.1%
  - Internos do modelo > Interpretabilidade & sondas: 73 papers, 80.2%
  - Interface & modalidade > Fala & áudio: 19 papers, 36.5%
  - Interface & modalidade > GUI & visão de tela: 18 papers, 34.6%

## 3. Distribuição por vertente

Abaixo de ~2% o rótulo é absorvido. O denominador da
checagem são os papers **classificados**, e não a base: com cobertura
total os dois coincidem, e com cobertura parcial só o primeiro mede o
rótulo em vez de medir o buraco. A coluna *dominante* conta só a vertente
de ordem 1 — um rótulo com massa e sem dominante nenhuma não define paper
algum, só acompanha.

| Vertente | papers | % da base | % dos classificados | dominante | leitura |
|---|---:|---:|---:|---:|---|
| Baratear | 1063 | 33.6% | 33.6% | 938 |  |
| Medir | 1001 | 31.6% | 31.6% | 888 |  |
| Automatizar | 549 | 17.3% | 17.3% | 511 |  |
| Confiabilizar | 488 | 15.4% | 15.4% | 330 |  |
| Escalar | 274 | 8.7% | 8.7% | 182 |  |
| Explicar | 198 | 6.3% | 6.3% | 164 |  |
| Endurecer | 103 | 3.3% | 3.3% | 64 | **no limiar** |
| Adaptar | 72 | 2.3% | 2.3% | 57 | **no limiar** |
| Especificar | 46 | 1.5% | 1.5% | 32 | **absorver** (abaixo de 2%) · **no limiar** |

Atribuições no total: 3794 para 3166 papers (1.20 por paper).
**Checagem B — nenhuma vertente abaixo de ~2%**: FALHA, 1 abaixo do piso.
  - Especificar: 46 papers, 1.5%

## 4. Não-encaixes por eixo

| Eixo | registros | % da base |
|---|---:|---:|
| area | 32 | 1.0% |
| subarea | 30 | 0.9% |
| vertente | 13 | 0.4% |
| **total** | 75 | 2.4% |

### Desacordo de parentesco

Estes não são rótulos inventados: os dois lados existem na grade, e o
que o modelo recusou foi de quem a sub-área é filha. É a entrada da
fila que aponta um conserto concreto — mudar o pai, e não criar rótulo.

| Par que o modelo tentou | papers | onde a grade pendura a sub-área |
|---|---:|---|
| Harness & orquestração > Skills & conhecimento compilado | 3 | Contexto & recuperação |
| Harness & orquestração > Benchmark de agente | 1 | Avaliação & instrumentação |

## 5. Custo real contra a estimativa

| | estimado | real |
|---|---:|---:|
| chamadas | 3166 | 3169 |
| custo | US$ 1,2300 | US$ 1.2326 |
| tokens de entrada | 13,9 M | 13.9 M |
| tokens de saída | 0,7 M | 0.7 M |
| duração | ~1,4 h | 0.52 h |
| ritmo | 36,6 ch/min | 101.2 ch/min |

Erros: 3. Respostas cortadas: 2 (0.1% das chamadas).

## 6. Roteamento — por provedor do OpenRouter

Os endpoints do OpenRouter não se comportam igual, e a coluna *pior* é o
que diz se a rodada aguentou: uma média boa esconde a cauda.

A linha *(não registrado)* concentra as chamadas que morreram antes da
resposta — inclusive as abandonadas pelo prazo: quem não respondeu não
informou quem era, e atribuí-las a um provedor seria acusar inocente.

| Provedor | chamadas | cortadas | prazo | erros | latência média (s) | pior (s) |
|---|---:|---:|---:|---:|---:|---:|
| Together | 3164 | 0 | 0 | 1 | 2.3 | 75.7 |
| Wafer | 3 | 2 | 0 | 2 | 67.6 | 67.6 |
| DeepInfra | 2 | 0 | 0 | 0 | 23.9 | 25.4 |

## 7. Rótulos perto de um limiar

A grade tem ~19% de instabilidade intrínseca: o mesmo paper, mesma
configuração, temperatura 0, recebe pares diferentes em cerca de uma em
cada cinco rodadas (81-82% de auto-concordância, três medições em
2026-09-08). Fundir um rótulo que está a poucos pontos do corte é decidir
sobre ruído — o ticket 08 precisa tratar esta lista à parte.

- **Modelo & treino > Pré-treino & arquitetura**: 204 papers, 22.7% da área
- **Geração de mídia > Áudio & música**: 33 papers, 5.6% da área
- **Avaliação & instrumentação > LLM como avaliador**: 21 papers, 4.7% da área
- **Avaliação & instrumentação > Custo da avaliação**: 2 papers, 0.4% da área
- **Contexto & recuperação > Verificação de fonte & citação**: 6 papers, 2.6% da área
- **Harness & orquestração > Sistemas multiagente**: 52 papers, 23.1% da área
- **Harness & orquestração > Elicitação & requisito**: 2 papers, 0.9% da área
- **Serving & inferência > Escala em tempo de inferência**: 37 papers, 25.5% da área
- **Interface & modalidade > Documento & extração**: 12 papers, 23.1% da área
- **Interface & modalidade > Vídeo & streaming**: 3 papers, 5.8% da área
- **vertente Endurecer**: 103 papers, 3.3% dos classificados
- **vertente Adaptar**: 72 papers, 2.3% dos classificados
- **vertente Especificar**: 46 papers, 1.5% dos classificados

