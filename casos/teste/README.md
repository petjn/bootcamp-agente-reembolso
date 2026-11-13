# Casos de teste

Conversas que o agente nunca viu enquanto era ajustado. Servem para medir se as correções feitas com os casos de
`treino/` e `ramos/` valem para conversas diferentes.

**Regras:** cada lote rodou com o código congelado, e nada no agente foi mudado por causa de um erro que só
apareceu aqui. Quando um caso de teste revelou uma situação que nenhum caso de ajuste cobria, a correção veio com
um caso novo em `ramos/`, escrito de outro jeito, e o caso de teste deixou de contar como "nunca visto".

Os casos foram escritos em cinco lotes, um depois do outro. A **medição final** do README usa os casos 72 a 79, os
últimos ainda nunca vistos, rodados 3 vezes cada.

Os gabaritos foram conferidos nas normas e no código de decisão, a partir do documento lido corretamente.

| Caso | O que testa | Resultado esperado |
|---|---|---|
| 42 | Exames de laboratório, três itens com teto próprio | Aprovado, R$ 59,52 |
| 43 | Sessão de terapia paga muito acima do teto | Pendente: relatório clínico (art. 73, § 3º, II) |
| 44 | Recibo sem assinatura nem carimbo | Pendente: assinatura |
| 45 | Tomografia com pedido médico de mais de 90 dias | Pendente: pedido médico válido |
| 46 | Dentista (consulta e limpeza) | Negado: odontologia não é coberta (Anexo IV) |
| 47 | Situação de um pedido anterior, pelo histórico | Sem pedido novo; aprovado em abril, R$ 213,75 |
| 48 | Mamografia e pergunta sobre a conta do crédito | Aprovado, R$ 180,00; crédito na conta do titular |
| 49 | Fonoaudiologia e pergunta sobre recibo mensal | Aprovado, R$ 105,00; sessões discriminadas |
| 51 | Consulta por telessaúde | Aprovado, R$ 200,00 (teto próprio da telessaúde) |
| 52 | Tomografia com o pedido médico mandado depois | Pendente no 1º turno; depois aprovado, R$ 390,00 |
| 53 | Recibo sem data do atendimento | Pendente: data |
| 54 | Duas consultas de datas diferentes no mesmo recibo | Aprovado, R$ 600,00 |
| 55 | Terapia ocupacional, 4ª sessão do ano | Aprovado, R$ 91,00; relatório só a partir da 5ª |
| 56 | Óculos de grau | Negado (Anexo IV) |
| 57 | Só dúvidas, sem pedido (prazo; consulta no exterior) | Sem decisão; responde pelos arts. 12 e 69 |
| 58 | Carteirinha digitada errada, depois a certa | Aprovado, R$ 247,00 |
| 59 | Ultrassom e "e se eu fosse do outro plano?" | Aprovado, R$ 132,00; no outro plano seriam R$ 121,00 |
| 60 | 5ª sessão de psicoterapia, relatório enviado depois | Pendente; depois aprovado, R$ 199,71 |
| 61 | Consulta de cliente novo, ainda na carência | Negado (art. 22); vale a partir de 23/05/2026 |
| 62 | Recibo sem CPF ou CNPJ do prestador | Pendente; o registro no conselho não substitui |
| 63 | Exame de alta complexidade com pedido médico sem data | Pendente: pedido médico com data |
| 64 | Situação de pedido anterior que ficou pendente | Sem pedido novo; pendente, com o prazo (art. 19) |
| 65 | Remédios de uso contínuo da farmácia | Negado (Anexo IV) |
| 66 | Quer revisão humana de uma negativa | Sem pedido novo; explica reanálise e revisão humana |
| 67 | Teleconsulta acima do teto | Aprovado, R$ 280,00 (teto do art. 35) |
| 68 | Consulta e retorno com o mesmo médico em 10 dias | Aprovado, R$ 225,00; o retorno não é reembolsado (art. 36) |
| 69 | Quiropraxia | Negado: não consta da Tabela (art. 56) |
| 70 | Recibo emitido antes do atendimento | Pendente |
| 71 | Consulta em Lisboa, paga em euro | Para analista (art. 69), sem valor |
| 72 | Exame em casa com taxa de deslocamento | Aprovado, R$ 28,53; a taxa não é reembolsada |
| 73 | Tomografia em urgência, sem pedido médico | Aprovado, R$ 520,00 (art. 38, § 3º) |
| 74 | Saldo do limite anual | Sem pedido novo; saldo de R$ 4.114,80 |
| 75 | Psicoterapia por vídeo, com 12 meses de plano | Aprovado, R$ 82,50 (art. 70) |
| 76 | Foto do recibo (imagem, não PDF) | Aprovado, R$ 227,50 |
| 77 | Consulta e eletrocardiograma no mesmo recibo | Aprovado, R$ 396,08 (cada item com o seu teto) |
| 78 | Desistir de um pedido pendente | Pendente; explica desistência e novo pedido no prazo (art. 16) |
| 79 | Exame no último dia da carência | Aprovado, R$ 13,75 (60 dias cumprem a carência, art. 23) |
