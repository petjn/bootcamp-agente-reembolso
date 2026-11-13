# Cobertura dos ramos da árvore pelos casos (atualizada em 2026-10-21, D95)

Cada ramo da árvore de decisão (`app/decisao.py`, lista `ARVORE`; `arvore_de_decisao.md`) e da conversa, com os casos
que passam por ele: treino (01 a 17), novos (18 a 41 e 50) e de teste (42 a 79). A primeira versão (D80) cobria só os
39 casos de ajuste.

## Conversa

| Ramo | Casos |
|---|---|
| saudação, fora de escopo, outra empresa | 14 |
| pedido só de outra pessoa (art. 8º) | 17 |
| pedido próprio e de outra pessoa na mesma conversa | 01, 12 |
| pergunta para resolver o de outra pessoa por outro caminho | 17 |
| texto no documento dirigido ao agente | 05 |
| documento antes da carteirinha | 01, 20 |
| carteirinha digitada errada | 58 |
| só dúvidas, sem pedido | 57 |
| situação de pedido anterior, pelo histórico | 47, 50, 64 |
| saldo do limite anual | 74 |
| revisão de uma negativa (reanálise, revisão humana) | 66 |
| desistência do pedido (art. 16) | 78 |
| conta do crédito (art. 15, § 2º) | 48 |

## Leitura do documento

| Ramo | Casos |
|---|---|
| não é documento de despesa de saúde → inválido (art. 76) | 03 |
| despesa de saúde que o leitor marcava inválida → segue (art. 76, § 2º) | 56, 65, 69 |
| imagem ilegível → nova imagem | 40 |
| foto legível (imagem) | 76 |
| o mesmo arquivo de novo (art. 17) | 23 |
| documento em nome de outra pessoa | 24 |
| relatório ou pedido médico como complementar | 02, 10, 19, 33, 37, 45, 52, 60, 63 |
| recibo enviado com a carteirinha, depois de uma dúvida | 51 |

## Decisão

| Nó | Ramo | Casos |
|---|---|---|
| 6.4 | sem data do atendimento → P09 | 53 |
| 3 | procedimento excluído → negado | 32, 46, 56, 65 |
| 3 | item excluído discriminado sai do cálculo | 22, 72 |
| 3 | atendimento e despesa excluída num valor só → P16 | 41 |
| 3 | fronteira sem indicação → P25; com relatório → aprovado | 08; 33 |
| 2.2 | item sem código, descrição clara → achado pela descrição | 26 |
| 2.2 | descrição genérica → P12 | 27 |
| 2.2 | descrito, fora da Tabela → negado (art. 56) | 69 |
| 2.2 | linha da Tabela só com o conselho do executante | 69 |
| 4 | OPME → analista | 03 |
| 4 | cirurgia → analista (art. 83) | 31 |
| 4 | valor acima da alçada → analista | 09 |
| 4 | moeda estrangeira → analista (art. 69) | 71 |
| 5.1 | contrato não ativo → negado | 34 |
| 5.3 | carência não cumprida: consulta, exame, terapia | 61, 07, 25 |
| 5.3 | carência item a item; categorias distintas no mesmo recibo | 28, 30 |
| 5.3 | carência no último dia (cumprida) | 79 |
| 5.3 | urgência dispensa a carência | 35 |
| 5.4 | segunda consulta com o mesmo profissional em 15 dias (art. 36) | 54, 68 |
| 5.5 | prazo vencido → negado; dito antes da carteirinha | 20 |
| 5.5 | prazo e regras pela redação da data do atendimento | 04, 11, 13 |
| 6 | campos ausentes → P02, P05, P06, P18 | 36, 78; 62; 36; 44 |
| 6 | emissão antes do atendimento → P10 | 70 |
| 6 | várias sessões num valor só → P16 | 29 |
| 6.9 | sessão acima de 40 no ano → negado | 38 |
| 6.9 | relatório exigido pela sessão → P20; recebido → segue | 02, 11, 60; 02, 10, 60 |
| 6.9 | relatório exigido pelo valor acima do teto → P20 | 43 |
| 6.9 | relatório sem manutenção → P21 | 37 |
| 6.10 | alta complexidade sem pedido → P23; com pedido → aprovado | 19, 52 |
| 6.10 | pedido vencido ou sem data → P23 | 45, 63 |
| 6.10 | urgência dispensa o pedido médico | 73 |
| 7.4 | relatório sozinho: primeiro do ano; segundo → negado | 15; 39 |
| 8 | teto, continuado, coparticipação por faixa, saldo parcial, saldo esgotado | 01, 10, 15, 16, 75 |
| 8 | vários itens, cada um com o seu teto | 42, 54, 77 |
| 8 | telessaúde com o teto da consulta | 51, 67, 75 |

## Sem caso de conversa

| Ramo | Onde está coberto | Por que não tem caso |
|---|---|---|
| código TUSS que não existe na Tabela → P14 | teste de código (`test_auditoria_d93.py`) | lacuna da D93, sem caso ainda |
| relatório cobrado à parte para sanar a pendência → complementar (NT-02, 8.4) | só o código | lacuna da D93, sem caso ainda |
| relatório sem assinatura → P22 | teste de código | ramo raro |
| pedido médico sem o solicitante → P24 | teste de código | ramo raro |
| material comprado avulso (Anexo IV, 4.11) → analista | teste de código | ramo raro |
| contrato cancelado | o mesmo nó do suspenso (34) | mesmo desfecho |

## Fora da árvore (sem dado ou sem regra no código)

Situação do contrato e plano na data do atendimento (art. 30, § 1º; art. 3º, § 2º), prestador credenciado (art. 62),
profissional dos pedidos anteriores (art. 36 entre documentos), relatório de pedido anterior (art. 73, § 5º),
duplicidade em outro protocolo (art. 17), página faltando (art. 14, § 3º), registro irregular (art. 68, § 2º), valor por
extenso diferente do numérico (P17), rasura (P30), comprovante de pagamento (P31), idioma estrangeiro sem tradução
(P32), dados bancários (P33), numeração fiscal (P35). Ver `auditoria_norma_codigo_2.md`.
