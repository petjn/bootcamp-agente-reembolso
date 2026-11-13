# Evolução do agente, rodada a rodada

Cada linha é uma **rodada**: todas as conversas de teste rodadas de novo depois de um grupo de correções. A
tabela mostra como o agente saiu de 4 decisões certas em 17 conversas para o resultado final. Termos novos
estão no glossário de [`docs/README.md`](../README.md).

Como ler as colunas:
- **Decisão certa**: em quantas conversas o desfecho do último turno bateu com o gabarito.
- **Artigos completos**: em quantas a resposta citou todos os artigos que fundamentam a decisão.
- **Turnos atendidos**: em quantas mensagens o agente respondeu o que o cliente pediu.
- **Vazamentos**: respostas que mostraram CPF, código de doença ou dado de outra pessoa (sempre zero).
- **O que entrou antes da rodada**: as correções feitas; o código entre parênteses (D34, D35...) é a entrada do
  [`diário de decisões`](../diario_de_decisoes.md) que explica cada uma.

Até a rodada 34 o conjunto era de 17 conversas de treino; da 35 em diante entram as conversas de `ramos/` (chamadas de "novos" na tabela), e as
linhas "teste" medem conversas nunca vistas. Linhas de conjuntos diferentes não são comparáveis entre si.

O detalhe das duas medições finais está em [`medicao_final.md`](medicao_final.md) e [`64_casos.md`](64_casos.md).
A mesma tabela, para planilha, está em `evolucao.csv`.

## Tabela

| Rodada | Data | Decisão certa | Artigos completos | Turnos atendidos | Vazamentos | Casos errados | O que entrou antes da rodada |
|---|---|---|---|---|---|---|---|
| Base | 2026-10-09 | 4/17 | 4/17 | não medido | 0 | 01 02 04 05 06 07 08 09 10 11 15 16 17 | — |
| 9 | 2026-10-11 | 13/17 | 13/17 | 98/132 (74%) | 0 | 03 07 08 12 | Análise de baixo para cima, níveis 0 a 3 (motor de decisão, leitura de documento, Anexo IV, reescrita, supervisor, resposta) |
| 10 | 2026-10-11 | 15/17 | 15/17 | 109/132 (83%) | 0 | 02 03 | D34: reescrita devolve a carteirinha; arquivo visível na mensagem; Anexo IV pela descrição da tabela; recibo com mensagem é reembolso; resposta reconhece a carteirinha; busca com 5 trechos |
| 11 | 2026-10-11 | 16/17 | 16/17 | 117/132 (89%) | 0 | 15 | D35: triagem obrigatória; TUSS só da tabela; reembolso sem mudança não é redecidido; busca lê a resposta anterior; circular revogada como histórico; saldo na memória |
| 12 | 2026-10-13 | 17/17 | 17/17 | 118/132 (89%) | 0 | — | D36: redação anterior do artigo nas dúvidas "o que mudou?"; fonte da regra na memória de cálculo; recibo com mensagem vira reembolso no ag_documento; terceiro sempre inviável |
| 13 | 2026-10-13 | 17/17 | 17/17 | 121/132 (92%) | 0 | — | D37: dúvida de regra nunca é inviável; regra do terceiro reescrita sem ambiguidade; fora do escopo com o tipo outro |
| 14 | 2026-10-13 | 16/17 | 16/17 | 116/132 (88%) | 0 | 09 | D38: norma do procedimento com o Anexo IV; histórico de circulares só quando perguntado; redação anterior só dos artigos achados |
| 15 | 2026-10-13 | 17/17 | 17/17 | 119/132 (90%) | 0 | — | Triagem em código quando chega carteirinha; reescrita não trata "usa a carteirinha dele" como mensagem maliciosa |
| 16 (teste: Qwen3.5-9B) | 2026-10-13 | 15/17 | 15/17 | 100/132 (76%) | 0 | 09 15 | Janela de 16 mil (D40); chat trocado pelo Qwen3.5-9B só para o teste (D41); conferência aceita valor com ponto decimal; reescrita que inventa carteirinha é descartada |
| 17 (teste: gemma4:12b na GPU) | 2026-10-13 | 15/17 | 15/17 | 115/132 (87%) | 0 | 01 12 | Chat trocado pelo 12b inteiro na GPU, reranker e embeddings na CPU, só para o teste (D42). Os 2 casos errados: item sem valor zerava o cálculo (corrigido depois) |
| 17 com 01 e 12 refeitos | 2026-10-14 | 17/17 | 17/17 | 123/132 (93%) | 0 | — | Mesma configuração da 17, com a correção do item sem valor (D42); só os casos 01 e 12 rodaram de novo |
| 18 | 2026-10-14 | 17/17 | 17/17 | 114/132 (86%) | 0 | — | e4b (padrão) com a correção do item sem valor (D42), para comparar com o 12b; 57 min |
| 19 | 2026-10-14 | 17/17 | 17/17 | 121/132 (92%) | 0 | — | e4b com os ajustes gerais da D44 e o revisor da resposta ligado (REVISAR_RESPOSTA=1); 85 min |
| 20 (teste: gemma4:12b na GPU) | 2026-10-14 | 17/17 | 17/17 | 123/132 (93%) | 0 | — | 12b com os ajustes da D44, sem revisor; aviso ao supervisor marcado como não sendo do cliente; teto de tokens no supervisor; 173 min |
| 21 | 2026-10-14 | 17/17 | 17/17 | 121/132 (92%) | 0 | — | Padrão D45 (e4b + revisor); busca com o caput em cada parágrafo e os artigos da decisão nas dúvidas (D46); 76 min |
| 22 | 2026-10-14 | 17/17 | 17/17 | 124/132 (94%) | 0 | — | Supervisor registra toda pergunta; quadro "Mudanças de redação" no topo da norma; nó `revisar` no grafo; índice original (D46); 78 min |
| 23 | 2026-10-15 | 17/17 | 17/17 | 124/132 (94%) | 0 | — | Ajustes da D47 (resposta e revisor; pendência de fronteira ao pé da letra; quadro marca a data do cliente); 78 min |
| 24 | 2026-10-15 | 17/17 | 17/17 | 125/132 (95%) | 0 | — | Janela de 24 mil, sem teto de tokens no supervisor, traces no LangSmith (D49); 78 min |
| 24 rejulgada | 2026-10-15 | 17/17 | 17/17 | 129/132 (98%) | 0 | — | Mesmas respostas da 24, com os critérios revistos com o usuário: perguntar para ter certeza, pedir documento para seguir e citar TUSS não são erro (ver rodada24/resultado.md) |
| 25 | 2026-10-15 | 17/17 | 17/17 | 123/132 (93%) | 0 | 14 (porta) | D50: resposta (TUSS, profissional assistente, documento contemporâneo, data de hoje), memória com o teto que valeu, marca do quadro; 79 min |
| 26 | 2026-10-15 | 16/17 | 16/17 | 113/132 (86%) | 0 | 06 07 13 (porta), 15 | D52 (revisor não encurta demais, valores com duas casas) e D53 (prompts por princípio, sem frases das conversas de treino); 79 min |
| 27 | 2026-10-15 | 17/17 | 17/17 | 128/132 (97%) | 0 | — | D54: regras da rodada 25 de volta, escritas sem as frases das conversas de treino, com o princípio no topo; NT-02 citável; sem a data de hoje |
| 28 | 2026-10-16 | 17/17 | 17/17 | 122/132 (92%) | 0 | — | D55 (revisor em campos; classificação da NT-02 junto da Tabela) e D56 (ancoragem na situação do pedido; regra condicionada). A 27 fica em 130/132 com o critério "não é erro o que não foi perguntado" |
| 29 | 2026-10-16 | 17/17 | 17/17 | 121/132 (92%) | 0 | — | D58 (norma do reembolso não aprovado pelo motivo), D59 (condição de saúde não se repete, com exemplos) e D60 (linha da NT-02 do código de pendência). Corrigiu 08 T3/T4/T6; errou 04 T6, 12 T3 (data), 16 T3 e outros |
| 30 | 2026-10-16 | 17/17 | 17/17 | 123/132 (93%) | 0 | — | D63: norma do reembolso não aprovado pelas regras da decisão; art. 8º na busca; perguntar o que o cliente quer. Corrigiu 04 T6, 07 T5, 12 T2/T3, 13 T5, 16 T3, 17 T3; o caso 14 caiu para 3/7 (saudação com as opções do canal) |
| 31 | 2026-10-17 | 17/17 | 17/17 | 125/132 (95%) | 0 | — | D64: a regra de perguntar o que o cliente quer só vale para quem não disse; saudação sem opções. Caso 14 de volta a 7/7; 01 T4 pediu os dados da esposa |
| 32 | 2026-10-17 | 17/17 | 17/17 | 128/132 (97%) | 0 | — | D65 (revisor: mandar a outra pessoa abrir o próprio atendimento está certo; comparação não) e D66 (“dele” e “dela” na descrição do pedido). Erros: 04 T5, 04 T6, 09 T1, 14 T3 |
| 33 | 2026-10-17 | 17/17 | 17/17 | 127/132 (96%) | 0 | — | D71 (dois exemplos inventados na regra do quadro: outra pessoa e atendimento anterior do próprio cliente) e D72 (data do outro atendimento dita antes, sem perguntar de novo). Corrigiu 04 T5, 04 T6, 11 T5; erros: 01 T6, 02 T1, 07 T7, 09 T1, 15 T7 |
| 34 | 2026-10-17 | 17/17 | 17/17 | 126/132 (95%) | 0 | — | D75: art. 38 (pedido médico de exame de alta complexidade) e item excluído discriminado, no código da decisão. Nenhuma decisão de treino mudou; casos novos 19 e 22 com a decisão certa |
| 35 | 2026-10-17 | 34/39 | — | 205/237 (86%) | 0 | 24 30 32 37 41 | D79 e D80: árvore no código, itens de fora da D79, conjunto novo de 39 casos (16 de treino sem o 06; 23 novos, um por ramo). Não comparável com as anteriores: outro conjunto. Treino 16/16 e 113/124; novos 18/23 e 92/113. Decisões erradas no leitor e na busca, nenhuma no código da árvore |
| 36 | 2026-10-18 | 38/39 | — | 216/237 (91%) | 0 | 33 | D82 (leitor sem o nome do cadastro; relatório sem valor vira complementar; categoria da Tabela; Anexo IV antes do OPME; busca com o resto da descrição do recibo; data da carência na ficha). Mesmo conjunto da 35: treino 16/16 e 116/124; novos 22/23 e 100/113 |
| 37 | 2026-10-20 | 39/39 | — | 227/237 (96%) | 0 | — | D84 e D85 (documento complementar ligado ao reembolso; indicação clínica só com o trecho; memória de cálculo por item e com total; itens não pagos nos dados da resposta; categoria pelo nome). Mesmo conjunto da 35: treino 16/16 e 118/124; novos 23/23 e 109/113. Os 10 turnos errados são todos da resposta |
| teste 1 | 2026-10-20 | 8/8 | — | 28/32 (88%) | 0 | — | Casos de teste 42 a 49, nunca vistos, com o código da 37 sem ajuste (D86). Outro conjunto: não comparável com as linhas acima. Erros: 47 T2 e T3, 48 T2 (supervisor), 49 T2 (resposta) |
| 38 | 2026-10-20 | 38/40 | — | 228/241 (95%) | 0 | 35 36 | D87 e D89 (histórico na pergunta de situação; prazo antes da carteirinha; pedido decidido pelo documento; lembrete do art. 8º). Os 39 de sempre e o 50; nos 39 comuns: 37/39 e 225/237. As duas decisões erradas são do leitor, que não mudou: variação do modelo |
| teste 2 | 2026-10-21 | 12/15 | — | 47,7/58 (82%) | 0 | 45 51 56 | 15 casos de teste nunca vistos (os dois lotes, sem o 47), código da D90 sem ajuste, 3 execuções: turnos 49, 47 e 47; decisões 12/15 nas três. Outro conjunto: não comparável com as linhas de rodada, mas mede a generalização (D91) |
| teste 3 | 2026-10-21 | 8/8 | — | 23,3/27 (86%) | 0 | — | 3º lote de casos de teste (59 a 66), nunca vistos, escrito depois das correções da D92; código congelado, 3 execuções: turnos 23, 23 e 24; decisões 8/8 nas três. Os erros que sobram são da resposta (D92) |
| teste 5 | 2026-10-21 | 8/8 | — | 22,3/25 (89%) | 0 | — | Medição final: 72 a 74 (4º lote) e 75 a 79 (5º lote), nunca vistos, código da D93 (auditoria norma × código) sem ajuste, 3 execuções: turnos 23, 22 e 22 (D94) |
| 39 | 2026-10-21 | 63/64 | — | 281/312 (90%) | 0 | 71 | D96 (a condição de saúde que o cliente conta não volta na resposta). Outro conjunto: os 64 casos essenciais de treino, novos e teste, sem os 13 que repetiam um ramo (D97). Treino 15/15 e 107/115; novos 23/23 e 103/110; teste 25/26 e 71/87. Nos 38 comuns com a 38: 38/38 e 210/225 (na 38, 213/225) |

## Evals de componente (último valor medido antes de cada rodada)

| Componente | R9 | R10 | R11 | R12 | R13 | R14 | R15 |
|---|---|---|---|---|---|---|---|
| Leitura de documento (19 anexos) | 35/38 | 38/38 | 38/38 | 38/38 | 38/38 | 38/38 | 38/38 |
| Julgamento do Anexo IV | 24/24 | 26/26 | 26/26 | 26/26 | 26/26 | 13/13 | 13/13 |
| Reescrita (segurança e texto) | 34/34 | 40/40 | 40/40 | 40/40 | 40/40 | 40/40 | 40/42 |
| Decisão do ag_normas (12 casos) | 12/12 | 12/12 | 12/12 | 12/12 | 12/12 | 12/12 | 12/12 |
| Supervisor (estados reais) | 24/24 | 30/32 | 26/26 | — | 18/24 | 18/24 | 18/24 |
| Busca das dúvidas reais | 9/11 | 77% | 56%* | — | — | — | — |
| Resposta, dúvidas difíceis da R13 (sem thinking) | — | — | — | — | — | 5/18 | 5/18 |
| Testes de código | 224 | 226 | 228 | 228 | 228 | 228 | 229 |

\* a partir da R11 o eval de busca inclui as dúvidas difíceis das rodadas 9 e 10; não é comparável com a
coluna anterior. "—": não medido antes dessa rodada.
