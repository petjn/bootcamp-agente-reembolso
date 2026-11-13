# Medição final: 8 conversas nunca vistas, 3 vezes cada (2026-10-21)

**O que é:** o teste mais honesto do agente. São as conversas 72 a 79 de `casos/teste/`, escritas depois de todas
as correções e nunca usadas para ajustar nada. O código ficou congelado, e cada conversa rodou 3 vezes, porque o
modelo não responde sempre igual. Nenhuma resposta mostrou CPF, código de doença ou dado de outra pessoa.

Os códigos D85, D93... indicam a versão do código: a entrada do [`diário de decisões`](../diario_de_decisoes.md)
até a qual as correções tinham entrado. Termos novos estão no glossário de [`docs/LEIAME.md`](../LEIAME.md).

**Resultado:** decisão certa **8/8 nas 3 execuções**; turnos **23, 22 e 22 de 25 (média 89%)**.

As medições anteriores com conversas de teste, para comparar (cada lote foi escrito depois das correções do
anterior):

| Medição de teste | Código | Decisão | Turnos |
|---|---|---|---|
| 1º lote (D86), 8 casos, 1 execução | D85 | 8/8 | 28/32 (88%) |
| 1º e 2º lotes (D91), 15 casos, 3 execuções | D90 | 11/15 (73%)* | 47,7/58 (82%) |
| 3º lote (D92), 8 casos, 3 execuções | D92 | 8/8 | 23,3/27 (86%) |
| 72 a 79 (D94), 8 casos, 3 execuções | D93 | 8/8 | 22,3/25 (89%) |

\* depois da correção dos gabaritos de 51 e 54 pela auditoria (D93).

Nos casos de ajuste, os turnos ficam em 95% (rodada 38).

## Turnos errados

| Turno | O que saiu | Execuções |
|---|---|---|
| 74 T1 | o cliente pergunta o saldo do limite anual, e a resposta pergunta o que ele quer em vez de dizer o saldo | 3/3 |
| 74 T2 | diz que o limite anual "não vale para qualquer procedimento" e mistura teto e limite de sessões; o art. 45 soma todos os procedimentos | 3/3 |
| 78 T3 | depois da desistência, diz que o protocolo segue aberto com prazo de 60 dias, sem o prazo de 90 dias do novo pedido (art. 16, parágrafo único) | 2/3 |

## Leitura

As decisões saíram todas certas, inclusive foto do recibo, consulta e exame no mesmo recibo, carência no último dia,
urgência sem pedido médico e taxa de deslocamento discriminada. Os erros que sobram são da resposta, e o do saldo (74)
é do mesmo tipo dos lotes anteriores: a pergunta que só os dados do histórico respondem recebe uma pergunta de volta.
