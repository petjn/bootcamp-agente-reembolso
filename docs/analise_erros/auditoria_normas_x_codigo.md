# Auditoria norma × código, segunda (2026-10-21, D93)

> Os códigos D (D78, D93...) são entradas do [diário de decisões](../diario_de_decisoes.md); os demais termos estão no [glossário](../LEIAME.md#glossário).

Refeita depois das D78 a D92. Fontes lidas por inteiro: Regulamento Geral (arts. 1º a 87), NT-02 (campos C1 a C10,
Anexos A a E, códigos P01 a P35, Casos 01 a 36) e Anexo IV (grupos 1 a 11). Código lido: `app/decisao.py` (a árvore),
`app/calculo`, `app/agents/documento.py`, `app/agents/normas.py`, `app/agents/supervisor.py`. A primeira auditoria
(de 17/10, não incluída aqui) teve as lacunas 1 a 6 e a maior parte das menores corrigidas nas D78 a D92.

## Lacunas achadas e corrigidas (D93)

| Regra | O que a norma manda | O que o código fazia | Correção |
|---|---|---|---|
| art. 35, § 2º; art. 70; NT-02, Caso 22 | consulta por telessaúde equipara-se à de consultório "para todos os efeitos, inclusive quanto a teto" | usava o teto "proporcional" da linha da Tabela (3,4 URS) | teto do art. 35 (5 URS) para a consulta médica por telessaúde; a linha da Tabela contraria três dispositivos e não prevalece (art. 5º, § 3º, e o preâmbulo: a Tabela complementa o Regulamento) |
| art. 36; NT-02, Caso 34 | segunda consulta com o mesmo profissional em 15 dias só com justificativa clínica | pagava as duas | no mesmo documento (mesmo profissional; mesma linha da Tabela = mesma especialidade, § 2º), a seguinte sai do cálculo sem justificativa clínica; o intervalo vem do texto (parâmetro novo) |
| art. 56; Anexo IV, grupo 10 | procedimento que não consta da Tabela não é reembolsável, e a falta de previsão não se sana por pendência | toda descrição sem código achado virava pendência (P12) | o classificador diz se a descrição é genérica: genérica → pendência (art. 34; P12); clara e sem linha na Tabela → o item sai e, sem outro item, negado (art. 56) |
| NT-02, P14 | código TUSS inexistente na Tabela: reclassificar pela descrição; persistindo, pendência | o item com código fora da Tabela não era reclassificado | passa pelo classificador; sem achar, P14 |
| NT-02, Caso 31; P10 | documento emitido antes da data do atendimento: pendência para o prestador esclarecer | não conferia | a data de emissão escrita é comparada com a do atendimento; sem falso positivo nos 71 anexos em PDF dos casos |
| art. 69; NT-02, Caso 26 | despesa em moeda estrangeira, convertida pelo câmbio de venda do dia | o valor em euro ou dólar seria lido como reais | vai a analista: a taxa do dia não está nos dados da análise automatizada, e sem ela nem a alçada se confere |
| NT-02, Anexo A e 8.4 | relatório cobrado à parte para sanar a pendência integra o pedido original | o relatório com valor virava o documento ativo, no lugar do recibo da sessão | com pendência de relatório aberta (P20, P21, P22), o relatório com valor é complementar |

Referência corrigida: o documento de despesa excluída não ser inválido é o art. **76**, § 2º (e a NT-02, 4.5), e não o
art. 75 (que é o da ilegibilidade); os textos da D92 citavam o 75.

## Conflitos entre normas, com a decisão

| Conflito | Decisão | Por quê |
|---|---|---|
| Anexo IV, 10.1 e 10.2 (sem descrição que permita classificar: não reembolsável) × art. 34, NT-02 Caso 35 e P12 (pendência) | pendência primeiro | o mesmo critério do art. 59, § 2º × Anexo IV 11.3 (D78): a NT-02, 5.3, diz que nenhum código de pendência autoriza indeferimento imediato |
| Tabela (telessaúde 3,4 URS) × art. 35, § 2º, art. 70 e Caso 22 | teto do art. 35 | três dispositivos dizem "para todos os efeitos, inclusive teto"; a Tabela complementa o Regulamento e não o altera |

## Gabaritos corrigidos pela auditoria

- 51 (telessaúde): a pergunta "o limite é o mesmo?" tem resposta "sim" (o gabarito dizia "não exatamente"). Na D91, o
  51 T3 foi julgado errado nas 3 execuções e estava certo.
- 54 (duas consultas no mesmo recibo, 7 dias): só a primeira é reembolsável (art. 36): R$ 300,00, e não R$ 600,00. Na
  D91, o 54 foi julgado certo e estava errado (decisão e T2).
- Efeito na D91: decisões 11/15 (e não 12/15); turnos iguais (o 51 T3 ganha 3, o 54 T2 perde 3).

## Sem dado (continua sem como aplicar)

Situação do contrato na data do atendimento (art. 30, § 1º), plano na data do atendimento (art. 3º, § 2º; art. 44, § 4º),
prestador credenciado (art. 62), profissional dos pedidos anteriores (art. 36 entre documentos), relatório de pedido
anterior (art. 73, § 5º), duplicidade em outro protocolo (art. 17), página faltando (art. 14, § 3º), registro irregular
no conselho (art. 68, § 2º).
