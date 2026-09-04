# Prototipar o Estágio B com critérios

Type: prototype
Status: open
Blocked by: 06

## Question

O enum decidido no ticket 06 produz, na LLM real, vereditos e justificativas
que o usuário aceita? Rodar o prompt do Estágio B alterado (`criterios_veredito`
como lista, justificativa que aplica o critério, `regra_fora` obrigatória com
os seis rótulos do ticket 02) numa amostra de ~20 papers — HarnessDev, os 6
`fora` sem regra do ticket 02, e estritos/amplos de setembro — **sem gravar em
`fato_triagem`**: saída em arquivo no scratch, lado a lado com o veredito e a
justificativa atuais.

O usuário reage à tabela: critérios errados, justificativas que ainda
descrevem em vez de aplicar, `fora_de_escopo` engolindo demais.

Resolvido quando: o usuário aprova a amostra ou devolve ajustes ao enum (reabre
06). O prompt e o schema do protótipo ficam linkados como asset — são o
rascunho da implementação.
