# Casos de teste (42 a 49)

Conversas que o agente nunca viu, escritas depois da rodada 36 (D86) para medir se o que foi ajustado nos 39 casos de
treino e novos vale para conversas diferentes.

- Rodam **uma vez só**, com o código congelado. Nada no código ou nos prompts é ajustado por causa deles: um erro
  aqui só vira mudança se o mesmo erro também aparecer nos casos de treino ou nos novos.
- Cada caso tem `persona.json` (o que o MCP devolve), `turnos.jsonl` (as mensagens do cliente) e `esperado.json` (o
  que as normas mandam, com a fonte e a conta). Os anexos estão em `anexos/teste_novos/`.
- As decisões dos gabaritos foram conferidas no código de decisão a partir do documento lido certo (8 de 8).
- Dados fictícios. A data das conversas é 20/05/2026.
- **Já visto:** o 47 deixou de ser caso de teste. Ele mostrou um ramo sem caso de treino (situação de pedido anterior
  pelo histórico); o ramo foi coberto pelo caso de treino 50, escrito de outro jeito, e corrigido na D87. O resultado
  do 47 depois da D87 não mede mais generalização.

| Caso | O que testa | Esperado |
|---|---|---|
| 42 | Exames de laboratório, três itens com teto próprio | Aprovado, R$ 59,52 |
| 43 | Sessão de terapia paga muito acima do teto | Pendente: relatório clínico (art. 73, § 3º, II) |
| 44 | Recibo sem assinatura nem carimbo | Pendente: assinatura (P18) |
| 45 | Tomografia com pedido médico de mais de 90 dias | Pendente: pedido médico válido (NT-02, 9.2) |
| 46 | Dentista (consulta e limpeza) | Negado (Anexo IV, 7.1 e 7.2) |
| 47 (já visto, D87) | Situação de um pedido anterior, pelo histórico | Sem pedido novo; aprovado em abril, R$ 213,75 |
| 48 | Mamografia e pergunta sobre a conta do crédito | Aprovado, R$ 180,00; conta do titular (art. 15, § 2º) |
| 49 | Fonoaudiologia e pergunta sobre recibo mensal | Aprovado, R$ 105,00; sessões discriminadas (NT-02, C6) |

## Segundo lote (51 a 58, D91)

Escrito depois da rodada 38 e das D87 a D90, com as mesmas regras do primeiro: código congelado, nenhum ajuste por causa
deles. Os 15 casos de teste ainda não vistos (os dois lotes, sem o 47) rodam 3 vezes, para o resultado vir com a faixa
de variação do modelo. Gabaritos conferidos no código de decisão (8 de 8) e nas normas.

| Caso | O que testa | Esperado |
|---|---|---|
| 51 | Consulta por telessaúde | Aprovado, R$ 200,00 (art. 70; teto próprio da telessaúde) |
| 52 | Tomografia com o pedido médico em dia, mandado depois | Pendente no 1º turno; aprovado, R$ 390,00 |
| 53 | Recibo sem data do atendimento | Pendente: data (P09; art. 13, § 5º) |
| 54 | Duas consultas de datas diferentes no mesmo recibo | Aprovado, R$ 600,00 |
| 55 | Terapia ocupacional, 4ª sessão do ano | Aprovado, R$ 91,00; relatório só a partir da 5ª |
| 56 | Óculos de grau | Negado (Anexo IV, 4.12) |
| 57 | Só dúvidas, sem pedido (prazo; consulta no exterior) | Sem decisão; art. 12 e art. 69 |
| 58 | Carteirinha digitada errada, depois a certa | Aprovado, R$ 247,00 |

## Terceiro lote (59 a 66, D92)

Os lotes 1 e 2 deixaram de ser casos de teste: as correções da D92 saíram dos erros deles (45, 51 e 56). O 3º lote foi
escrito depois dessas correções, com as mesmas regras: código congelado, nenhum ajuste por causa deles, 3 execuções.
Gabaritos conferidos no código de decisão (7 de 7 com decisão) e nas normas.

| Caso | O que testa | Esperado |
|---|---|---|
| 59 | Ultrassom e pergunta "e se eu fosse do outro plano?" | Aprovado, R$ 132,00; no Essencial seriam R$ 121,00 |
| 60 | 5ª sessão de psicoterapia, relatório enviado depois | Pendente no 1º turno; aprovado, R$ 199,71; relatório vale para as seguintes (art. 73, § 5º) |
| 61 | Consulta na carência de cliente novo | Negado (art. 22); vale a partir de 23/05/2026 |
| 62 | Recibo sem CPF ou CNPJ do prestador | Pendente (P05); registro no conselho não substitui |
| 63 | Exame de alta complexidade com pedido médico sem data | Pendente (NT-02, 9.1, IV) |
| 64 | Situação de pedido anterior que ficou pendente | Sem pedido novo; pendente; prazo do art. 19 |
| 65 | Remédios de uso contínuo da farmácia | Negado (Anexo IV, 4.1 e 4.2) |
| 66 | Quer revisão humana de uma negativa | Sem pedido novo; reanálise (art. 20) e revisão humana (art. 77, § 2º) |
## Quarto lote (67 a 74, D93)

Escrito depois da segunda auditoria norma × código (D93), com as mesmas regras: código congelado, nenhum ajuste por causa
deles, 3 execuções. Gabaritos conferidos no código de decisão (7 de 7 com decisão) e nas normas. Os casos 51 e 54 do 2º
lote tiveram o gabarito corrigido pela auditoria (D93).

| Caso | O que testa | Esperado |
|---|---|---|
| 67 | Teleconsulta acima do teto "proporcional" da Tabela | Aprovado, R$ 280,00 (teto do art. 35) |
| 68 | Consulta e retorno com o mesmo médico em 10 dias | Aprovado, R$ 225,00; o retorno sai (art. 36) |
| 69 | Quiropraxia | Negado: não consta da Tabela (art. 56) |
| 70 | Recibo emitido antes do atendimento | Pendente (P10; Caso 31) |
| 71 | Consulta em Lisboa, paga em euro | Para analista (art. 69), sem valor |
| 72 | Exame em casa com taxa de deslocamento discriminada | Aprovado, R$ 28,53; a taxa sai (Anexo IV, 5.5) |
| 73 | Tomografia em urgência, sem pedido médico | Aprovado, R$ 520,00 (art. 38, § 3º) |
| 74 | Saldo do limite anual | Sem pedido novo; R$ 4.114,80 |
**Já vistos:** 67 a 71 rodaram na conferência das lacunas (D93), e o 69 levou a correções: deixam de ser casos de teste.
Seguem nunca vistos 72 a 74.

## Quinto lote (75 a 79, D94)

Escrito depois das correções das lacunas (D93). Roda com 72 a 74 (8 casos), 3 vezes, com o código congelado. Gabaritos
conferidos no código de decisão (5 de 5) e nas normas.

| Caso | O que testa | Esperado |
|---|---|---|
| 75 | Psicoterapia por vídeo, com 12 meses completos de adesão | Aprovado, R$ 82,50 (art. 70; faixa até 12 meses) |
| 76 | Foto do recibo (imagem) | Aprovado, R$ 227,50 (art. 14) |
| 77 | Consulta e eletrocardiograma no mesmo recibo | Aprovado, R$ 396,08 (cada item com o seu teto) |
| 78 | Desistir de um pedido pendente | Pendente (P02); desistência e novo pedido no prazo (art. 16) |
| 79 | Exame no último dia da carência | Aprovado, R$ 13,75 (60 dias cumprem, art. 23) |