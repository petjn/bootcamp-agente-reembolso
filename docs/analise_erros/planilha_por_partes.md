# Análise de erros por partes (rodadas 1 e 2, casos 01 a 03)

Cada componente tem partes com saída própria, e o erro é marcado na parte que saiu bem pior do que um
especialista com a mesma entrada. Para separar, li as saídas intermediárias: o que cada parte devolveu (os
argumentos de cada chamada do supervisor, a norma que a busca trouxe, a memória de cálculo da decisão, os
dados que a resposta recebeu).

## As partes

| Componente | Parte | Tipo | Saída que se confere |
|---|---|---|---|
| Reescrita | segurança | modelo | marca "[mensagem maliciosa]" ou não |
| | reescrita do texto | modelo | a mensagem reescrita |
| Supervisor | S1 registro | modelo | os pedidos registrados e o tipo de cada um (e se retoma o que já existe) |
| | S2 escolha do agente | modelo | qual ferramenta chama a seguir e com qual pedido |
| | S3 encerramento | modelo | quando chama o responder |
| Triagem | leitura da carteirinha e consulta | código + MCP | o cadastro |
| Documento | leitura (PDF/OCR) | código | o texto |
| | classificação | modelo | categoria ou INVALIDO |
| | molde | modelo | os campos C1 a C10 |
| | conferência | código | o que fica no molde e o que falta |
| Normas | busca da norma | busca (RAG) | os trechos trazidos |
| | decisão | código | decisão, valor, memória de cálculo |
| | Anexo IV | modelo | excluído ou não |
| Resposta | montagem dos dados | código | o bloco `<dados>` |
| | escrita | modelo | o texto ao cliente |

## Rodada 1 (11 turnos com erro)

| Caso-turno | Parte com erro | O que a parte devolveu |
|---|---|---|
| 01-T6 | Resposta · escrita | pediu "a data correta" ao cliente, com a data do documento nos dados |
| 01-T7 | Resposta · escrita | não falou do teto, que a memória diz ter sido conferido |
| 02-T1 | Normas · busca | trouxe o art. 73 (classificação do documento), não a regra de como pedir; a resposta improvisou em cima |
| 02-T2 | Resposta · montagem dos dados | a triagem identificou o cliente, mas a resposta recebeu "nenhum" e inventou |
| 02-T3 | Supervisor · S1 registro | registrou o recibo como "documento", não "reembolso" |
| 02-T4 | Supervisor · S1 registro; Resposta · escrita | registrou "outro" em vez de retomar o reembolso; a resposta pediu "os recibos de cada atendimento" |
| 02-T5 | Supervisor · S2 escolha; Resposta · escrita | registrou a dúvida e encerrou sem chamar o ag_normas; a resposta entendeu "relatório de reembolsos" |
| 02-T6 | Supervisor · S1 registro | registrou o relatório como "documento"; não havia reembolso para decidir |
| 02-T7 | Supervisor · S1 registro | registrou "andamento" em vez de retomar o reembolso |
| 02-T8 | Supervisor · S2 escolha | não chamou o ag_normas para a dúvida |
| 02-T9 | Supervisor · S2 escolha | idem |

| Parte | Turnos | % (de 11) |
|---|---|---|
| Supervisor · S1 registro | 4 | 36% |
| Resposta · escrita | 4 | 36% |
| Supervisor · S2 escolha do agente | 3 | 27% |
| Normas · busca | 1 | 9% |
| Resposta · montagem dos dados | 1 | 9% |
| demais partes | 0 | 0% |

## Rodada 2 (5 turnos com erro), depois da correção do supervisor

| Caso-turno | Parte com erro | O que a parte devolveu |
|---|---|---|
| 01-T7 | Resposta · escrita | memória: "o teto não limitou"; a resposta não falou do teto |
| 02-T1 | Normas · busca | de novo o art. 73; a resposta pediu que a pessoa "consulte o cadastro" |
| 02-T2 | Resposta · montagem dos dados; Resposta · escrita | dados "nenhum"; a escrita aplicou a linha do art. 8º sem haver terceiro |
| 02-T6 | Supervisor · S1 registro | registrou o relatório como "documento" em vez de retomar o reembolso pendente; por isso não chamou o ag_normas |
| 02-T7 | Resposta · escrita | memória: "o limite anual limitou: restava R$ 111,27"; a resposta atribuiu o corte ao teto e à coparticipação |

| Parte | Turnos | % (de 5) |
|---|---|---|
| Resposta · escrita | 3 | **60%** |
| Resposta · montagem dos dados | 1 | 20% |
| Normas · busca | 1 | 20% |
| Supervisor · S1 registro | 1 | 20% |
| Supervisor · S2 e S3 | 0 | 0% |
| demais partes | 0 | 0% |

## Leitura

- A correção do supervisor resolveu o S2 (escolha do agente) e quase todo o S1 (registro); sobra o caso do
  documento que completa um pedido pendente (o relatório do 02-T6).
- A parte que mais erra agora é a **escrita da resposta**: com os dados certos na mão (memória de cálculo),
  ela omite ou troca o motivo. O eval da próxima etapa deve isolar essa parte: dados fixos de entrada (os
  `<dados>` reais destes turnos) e conferir se o texto cita o que a memória diz que limitou.
- A **busca** aparece duas vezes no mesmo turno (02-T1): para "como funciona o reembolso", ela traz o art. 73.
  Vale um eval próprio da busca com perguntas desse tipo.
- A **montagem dos dados** da resposta não leva o resultado da triagem: quando a mensagem só identifica o
  cliente, a resposta recebe "nenhum".
