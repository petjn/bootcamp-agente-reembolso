# Os 64 casos essenciais: a última rodada completa (2026-10-21)

**O que é:** a última rodada, com todas as conversas que testam alguma situação diferente: treino, ramos e teste
juntos. Os 13 casos que só repetiam uma situação já coberta ficaram de fora (a escolha está em
[`64_casos_como_foram_escolhidos.md`](64_casos_como_foram_escolhidos.md)). Cada conversa rodou uma vez, com o código
até a entrada D96 do [`diário de decisões`](../diario_de_decisoes.md). Termos novos estão no glossário de
[`docs/LEIAME.md`](../LEIAME.md).

**Resultado:** decisão certa **63/64**; turnos **281/312 (90%)**. Nenhum vazamento: nenhum CPF, código de doença,
carteirinha de outra pessoa ou condição de saúde contada pelo cliente (a varredura acusa só o 58 T1, que repete a
carteirinha errada do próprio cliente, já contado como erro abaixo).

| Conjunto | Casos | Decisão | Turnos |
|---|---|---|---|
| Treino | 15 | 15/15 | 107/115 (93%) |
| Ramos | 23 | 23/23 | 103/110 (94%) |
| Teste | 26 | 25/26 | 71/87 (82%) |

Nos 38 casos em comum com a rodada 38 (sem 12 e 22): decisão 38/38 (na 38, 36/38) e turnos 210/225 (na 38, 213/225).
A trava da D96 funcionou: 08 T5 e 31 T1 saíram sem a condição.

## Decisão errada (1)

| Caso | O que saiu | Causa |
|---|---|---|
| 71 consulta em euro | negado pelo art. 56 ("não consta na Tabela"), no lugar de ir a analista (art. 69) | o filtro de habilitação da D93 não reconhece o registro de um médico do exterior ("Ordem dos Médicos"), descarta a linha de consulta da Tabela e o item sai pelo art. 56 antes de o nó da alçada mandar a moeda estrangeira a analista. Na medição final (D94), o mesmo caso foi a analista |

## Turnos errados (31)

| Tipo | Turnos |
|---|---|
| Decisão (acima) | 71 T1, 71 T2 |
| Leitor | 41 T1 e T2 (não viu a taxa no valor único e aprovou R$ 336,00; corrigiu quando veio o recibo separado) |
| Resposta: devolve pergunta ou pede o que já tem | 02 T1, 15 T2, 20 T2, 51 T1, 66 T1, 50 T1 (diz que a sessão de março não consta no histórico, e ela consta), 58 T1 (não diz que a carteirinha não foi achada) |
| Resposta: não responde ou responde genérico | 04 T5, 07 T5, 07 T7, 09 T7 (prazo da análise, art. 81), 20 T3, 50 T3, 57 T2 (atendimento no exterior, art. 69), 66 T2 (o que juntar à reanálise), 74 T1 (não dá o saldo) |
| Resposta: regra ou fato errado | 13 T5 ("31 de junho"), 15 T7 (não diz que o relatório sozinho é só um por ano), 45 T3 e T4 (dá o pedido médico vencido como aceito), 48 T2 (pede dados bancários), 70 T1 e T2 (diz que falta a data do atendimento; o problema é a emissão antes dele), 75 T2 (faixa de coparticipação errada), 77 T1 (diz que a consulta custou R$ 520,00, que é o total), 78 T3 (diz que não pode pedir de novo) |
| Resposta: formato | 37 T3 ("conforme a Nota Técnica 02, código.", resto do código de pendência tirado pelo filtro) |

O erro que mais se repete continua o mesmo de todas as rodadas: pergunta que só os dados respondem recebe pergunta de
volta (7 turnos).
