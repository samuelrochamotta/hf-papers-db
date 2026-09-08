# Relatório de massa da grade facetada

- **Rodada**: `run-20260908-173724`
- **Base**: 3166 papers
- **Checagens**: `docs/specs/taxonomia-facetada.md`, seção *Operação*, passo 5

## 1. Cobertura

| | papers | % da base |
|---|---:|---:|
| com par primário (área > sub-área) | 3162 | 99.9% |
| com par secundário | 583 | 18.4% |
| com ao menos uma vertente | 3166 | 100.0% |
| com duas vertentes | 680 | 21.5% |
| com par, sem primária | 0 | 0.0% |
| **sem faceta nenhuma** | 4 | 0.1% |

## 2. Distribuição por área e sub-área

Percentual da sub-área **dentro da sua área**. Acima de 25% falta
ramificar; abaixo de 3% da área ou de 10 papers, a
regra manda fundir.

| Área | Sub-área | papers | % da área | leitura |
|---|---|---:|---:|---|
| **Modelo & treino** | _872 papers_ | | | |
| | Otimização de política & recompensa verificável | 213 | 24.4% | **no limiar** |
| | Pré-treino & arquitetura | 191 | 21.9% |  |
| | Pós-treino & RL | 175 | 20.1% |  |
| | RL agêntico & ambiente de treino | 144 | 16.5% |  |
| | Dados de treino & sintéticos | 78 | 8.9% |  |
| | Destilação & quantização | 71 | 8.1% |  |
| **Geração de mídia** | _577 papers_ | | | |
| | Imagem & difusão | 165 | 28.6% | **ramificar** (acima de 25%) |
| | Vídeo & animação | 123 | 21.3% |  |
| | 3D & cena | 99 | 17.2% |  |
| | World models generativos | 57 | 9.9% |  |
| | Edição & restauração de imagem | 48 | 8.3% |  |
| | Edição de vídeo | 31 | 5.4% | **no limiar** |
| | Vídeo longo & streaming | 28 | 4.9% | **no limiar** |
| | Áudio & música | 26 | 4.5% | **no limiar** |
| **Avaliação & instrumentação** | _495 papers_ | | | |
| | Benchmark de agente | 116 | 23.4% | **no limiar** |
| | Benchmark de percepção multimodal | 99 | 20.0% |  |
| | Protocolo & metodologia | 54 | 10.9% |  |
| | Benchmark de agente de código | 50 | 10.1% |  |
| | Benchmark de domínio | 48 | 9.7% |  |
| | Benchmark de agente de computador & web | 44 | 8.9% |  |
| | Diagnóstico de falha | 36 | 7.3% |  |
| | Benchmark científico & clínico | 29 | 5.9% | **no limiar** |
| | LLM como avaliador | 19 | 3.8% | **no limiar** |
| **Percepção & robótica** | _358 papers_ | | | |
| | VLA & manipulação | 128 | 35.8% | **ramificar** (acima de 25%) |
| | Dados & treino de política robótica | 58 | 16.2% |  |
| | Sensores & percepção 3D | 48 | 13.4% |  |
| | Rastreamento & detecção | 47 | 13.1% |  |
| | Modelo de mundo para ação | 41 | 11.5% |  |
| | Navegação & mundo físico | 36 | 10.1% |  |
| **Contexto & recuperação** | _237 papers_ | | | |
| | Modelos de embedding & ranking | 55 | 23.2% | **no limiar** |
| | Memória de longo prazo | 49 | 20.7% |  |
| | Skills & conhecimento compilado | 40 | 16.9% |  |
| | RAG & recuperação | 38 | 16.0% |  |
| | Compressão & alocação de contexto | 20 | 8.4% |  |
| | Memória multimodal & de vídeo | 18 | 7.6% |  |
| | Busca agêntica | 17 | 7.2% |  |
| **Harness & orquestração** | _221 papers_ | | | |
| | Auto-evolução do harness | 49 | 22.2% | **no limiar** |
| | Sistemas multiagente | 43 | 19.5% |  |
| | Laço de execução & trajetória | 37 | 16.7% |  |
| | Pesquisa autônoma | 27 | 12.2% |  |
| | Engenharia de código com agente | 24 | 10.9% |  |
| | Uso de ferramenta & orquestração | 21 | 9.5% |  |
| | Runtime & estado do agente | 20 | 9.0% |  |
| **Serving & inferência** | _152 papers_ | | | |
| | Atenção, kernel & cache | 39 | 25.7% | **ramificar** (acima de 25%) · **no limiar** |
| | Escala em tempo de inferência | 34 | 22.4% | **no limiar** |
| | Cache KV & compressão de contexto | 27 | 17.8% |  |
| | Infraestrutura & deployment | 20 | 13.2% |  |
| | Orçamento de token visual | 19 | 12.5% |  |
| | Roteamento de modelos | 13 | 8.6% |  |
| **Guardrails & controle** | _116 papers_ | | | |
| | Risco & dano | 29 | 25.0% | **no limiar** |
| | Ataque & red-teaming | 27 | 23.3% | **no limiar** |
| | Guard models | 19 | 16.4% |  |
| | Segurança de agente | 19 | 16.4% |  |
| | Detecção de alucinação | 11 | 9.5% |  |
| | Política & conformidade | 7 | 6.0% | fundir (7 papers) |
| | Injeção & delegação | 4 | 3.4% | fundir (4 papers) · **no limiar** |
| **Internos do modelo** | _92 papers_ | | | |
| | Interpretabilidade & sondas | 58 | 63.0% | **ramificar** (acima de 25%) |
| | Direção & edição de ativações | 17 | 18.5% |  |
| | Monitoramento & atribuição causal | 8 | 8.7% | fundir (8 papers) |
| | Fidelidade do raciocínio | 5 | 5.4% | fundir (5 papers) · **no limiar** |
| | Atalhos & espúrios | 4 | 4.3% | fundir (4 papers) · **no limiar** |
| **Interface & modalidade** | _42 papers_ | | | |
| | Fala & áudio | 20 | 47.6% | **ramificar** (acima de 25%) |
| | Documento & extração | 14 | 33.3% | **ramificar** (acima de 25%) |
| | GUI & visão de tela | 8 | 19.0% | fundir (8 papers) |

**Checagem A — nenhuma sub-área acima de ~25% da sua área**: FALHA, 6 acima do teto.
  - Geração de mídia > Imagem & difusão: 165 papers, 28.6%
  - Percepção & robótica > VLA & manipulação: 128 papers, 35.8%
  - Serving & inferência > Atenção, kernel & cache: 39 papers, 25.7%
  - Internos do modelo > Interpretabilidade & sondas: 58 papers, 63.0%
  - Interface & modalidade > Fala & áudio: 20 papers, 47.6%
  - Interface & modalidade > Documento & extração: 14 papers, 33.3%

## 3. Distribuição por vertente

Abaixo de ~2% o rótulo é absorvido. O denominador da
checagem são os papers **classificados**, e não a base: com cobertura
total os dois coincidem, e com cobertura parcial só o primeiro mede o
rótulo em vez de medir o buraco. A coluna *dominante* conta só a vertente
de ordem 1 — um rótulo com massa e sem dominante nenhuma não define paper
algum, só acompanha.

| Vertente | papers | % da base | % dos classificados | dominante | leitura |
|---|---:|---:|---:|---:|---|
| Treinar | 1435 | 45.3% | 45.3% | 1365 |  |
| Medir | 1007 | 31.8% | 31.8% | 868 |  |
| Baratear | 524 | 16.6% | 16.6% | 383 |  |
| Automatizar | 223 | 7.0% | 7.0% | 162 |  |
| Confiabilizar | 206 | 6.5% | 6.5% | 107 |  |
| Escalar | 152 | 4.8% | 4.8% | 77 | **no limiar** |
| Explicar | 150 | 4.7% | 4.7% | 113 | **no limiar** |
| Endurecer | 76 | 2.4% | 2.4% | 38 | **no limiar** |
| Adaptar | 38 | 1.2% | 1.2% | 28 | **absorver** (abaixo de 2%) · **no limiar** |
| Especificar | 35 | 1.1% | 1.1% | 25 | **absorver** (abaixo de 2%) · **no limiar** |

Atribuições no total: 3846 para 3166 papers (1.21 por paper).
**Checagem B — nenhuma vertente abaixo de ~2%**: FALHA, 2 abaixo do piso.
  - Adaptar: 38 papers, 1.2%
  - Especificar: 35 papers, 1.1%

## 4. Não-encaixes por eixo

| Eixo | registros | % da base |
|---|---:|---:|
| subarea | 49 | 1.5% |
| area | 30 | 0.9% |
| vertente | 2 | 0.1% |
| **total** | 81 | 2.6% |

### Desacordo de parentesco

Estes não são rótulos inventados: os dois lados existem na grade, e o
que o modelo recusou foi de quem a sub-área é filha. É a entrada da
fila que aponta um conserto concreto — mudar o pai, e não criar rótulo.

**A contagem é piso, e não o total.** `tax_nao_encaixe` guarda um
registro por paper, e a declaração do modelo (`nao_coube`) vence o par
rejeitado quando o paper tem os dois — então o paper que declarou
não-encaixe *e* teve o par derrubado aparece só como declaração. Quem
quer o total conta os `WARNING` de `par (area > sub-area) ignorado` no
log da rodada: na rodada 1 do ticket 07 foram 15 pares rejeitados, e a
tabela guardou 12.

| Par que o modelo tentou | papers | onde a grade pendura a sub-área |
|---|---:|---|
| Harness & orquestração > Skills & conhecimento compilado | 7 | Contexto & recuperação |
| Guardrails & controle > Monitoramento & atribuição causal | 2 | Internos do modelo |
| Serving & inferência > Destilação & quantização | 1 | Modelo & treino |
| Internos do modelo > Diagnóstico de falha | 1 | Avaliação & instrumentação |
| Harness & orquestração > Busca agêntica | 1 | Contexto & recuperação |

## 5. Custo real contra a estimativa

| | estimado | real |
|---|---:|---:|
| chamadas | — | 4407 |
| custo | US$ 2.0000 | US$ 2.0675 |
| tokens de entrada | — | 21.5 M |
| tokens de saída | — | 1.8 M |
| duração | — | 1.02 h |
| ritmo | — | 71.7 ch/min |

A estimativa errou por +3.4%.

Erros: 66. Respostas cortadas: 4 (0.1% das chamadas) — a conta inclui o `json invalido: Unterminated string`, que é corte com outro nome.

O custo acima é o do `log_llm` — **tudo o que foi cobrado**, inclusive as 66 chamadas que erraram e foram refeitas (US$ 0.0269). `log_execucao.custo_usd` conta só o que virou triagem, e por isso é menor: os dois estão certos e medem coisas diferentes.

Abandonadas pelo prazo (`llm.prazo_total_s`): 7 (0.2%). **O custo acima as subestima** — elas foram cobradas e saíram com uso zero, porque os tokens vinham na resposta que nunca foi lida.

## 6. Roteamento — por provedor do OpenRouter

Os endpoints do OpenRouter não se comportam igual, e a cauda é o que diz
se a rodada aguentou: uma média boa a esconde. Mas leia a coluna certa —
*pior 1ª tent.* é o provedor; *pior acum.* conta do início do laço de
`chamar`, então numa linha de tentativa 3 ela carrega as duas anteriores e
os backoffs. É tempo do paper, não da chamada.

A linha *(não registrado)* concentra as chamadas que morreram antes da
resposta — inclusive as abandonadas pelo prazo: quem não respondeu não
informou quem era, e atribuí-las a um provedor seria acusar inocente.

As três colunas de tempo saem de `latencia_ms`, que só é gravada na
chamada que respondeu: *média (s)* e *pior* contam só as chamadas que
responderam, e não a rodada. Um provedor cujas chamadas todas morreram
antes da resposta sai com travessão nas três — não há tempo a medir.

| Provedor | chamadas | cortadas | prazo | erros | média (s) | pior 1ª tent. (s) | pior acum. (s) |
|---|---:|---:|---:|---:|---:|---:|---:|
| Together | 4400 | 4 | 0 | 59 | 3.4 | 19.1 | 115.8 |
| (não registrado) | 7 | 0 | 7 | 7 | — | — | — |

## 7. Rótulos perto de um limiar

A grade tem ~19% de instabilidade intrínseca: o mesmo paper, mesma
configuração, temperatura 0, recebe pares diferentes em cerca de uma em
cada cinco rodadas (81-82% de auto-concordância, três medições em
2026-09-08). Fundir um rótulo que está a poucos pontos do corte é decidir
sobre ruído — o ticket 08 precisa tratar esta lista à parte.

- **Modelo & treino > Otimização de política & recompensa verificável**: 213 papers, 24.4% da área
- **Geração de mídia > Edição de vídeo**: 31 papers, 5.4% da área
- **Geração de mídia > Vídeo longo & streaming**: 28 papers, 4.9% da área
- **Geração de mídia > Áudio & música**: 26 papers, 4.5% da área
- **Avaliação & instrumentação > Benchmark de agente**: 116 papers, 23.4% da área
- **Avaliação & instrumentação > Benchmark científico & clínico**: 29 papers, 5.9% da área
- **Avaliação & instrumentação > LLM como avaliador**: 19 papers, 3.8% da área
- **Contexto & recuperação > Modelos de embedding & ranking**: 55 papers, 23.2% da área
- **Harness & orquestração > Auto-evolução do harness**: 49 papers, 22.2% da área
- **Serving & inferência > Atenção, kernel & cache**: 39 papers, 25.7% da área
- **Serving & inferência > Escala em tempo de inferência**: 34 papers, 22.4% da área
- **Guardrails & controle > Risco & dano**: 29 papers, 25.0% da área
- **Guardrails & controle > Ataque & red-teaming**: 27 papers, 23.3% da área
- **Guardrails & controle > Injeção & delegação**: 4 papers, 3.4% da área
- **Internos do modelo > Fidelidade do raciocínio**: 5 papers, 5.4% da área
- **Internos do modelo > Atalhos & espúrios**: 4 papers, 4.3% da área
- **vertente Escalar**: 152 papers, 4.8% dos classificados
- **vertente Explicar**: 150 papers, 4.7% dos classificados
- **vertente Endurecer**: 76 papers, 2.4% dos classificados
- **vertente Adaptar**: 38 papers, 1.2% dos classificados
- **vertente Especificar**: 35 papers, 1.1% dos classificados

