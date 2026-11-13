# Árvore de decisão do pedido de reembolso (2026-10-17)

> Os códigos D (D78, D93...) são entradas do [diário de decisões](../diario_de_decisoes.md); os demais termos estão no [glossário](../LEIAME.md#glossário).

Mapa de todas as regras das normas que decidem um pedido, na ordem da NT-02, item 6.1. Cada nó diz a pergunta, o fato
de que ela precisa, de onde esse fato pode vir, os desfechos de cada ramo, a regra e se o código de hoje faz isso.
Fontes lidas: Regulamento Geral, Circulares 04/2025, 09/2025, 11/2026 e 02/2026, NT-02, Anexo IV e Tabela URS 2026
(inclusive as observações de cada linha e as notas do fim). Parte da auditoria (`auditoria_normas_x_codigo.md`).
Este documento não muda o agente. Revisto no mesmo dia (ver "Revisão" no fim).

## Quando a árvore é usada

Só na decisão de um pedido de reembolso que tem documento: do nível 1 ao 8. Ela é código, chamada pelo `ag_normas`
quando há documento ativo; numa saudação, numa dúvida, numa pergunta de andamento ou num pedido de outra pessoa, não é
chamada. O nível 0 não é parte dela: é o que o supervisor já faz para decidir se o pedido entra na árvore; está aqui só
para mostrar onde ela começa. Numa dúvida ("e se eu fizer 30 sessões?"), a resposta usa a busca na norma, como hoje;
a ficha que a árvore deixa no estado serve depois para explicar um pedido já analisado ("o que ainda falta?").

## Como ler

**Fontes de um fato** (quem pode preenchê-lo):

| Sigla | Fonte | Quem preenche |
|---|---|---|
| D | o documento enviado | o modelo lê; o código confere no texto (valores, datas, códigos) |
| T | a Tabela URS | código (linha do código TUSS: categoria, teto, observação) |
| N | a norma vigente na data do atendimento | código (parâmetros extraídos no build, D7) |
| M | cadastro do MCP | código (plano, adesão, situação do contrato, nome) |
| H | histórico do MCP | código (pedidos do ano: data, categoria, decisão, valor) |
| C | a conversa | o modelo (só o que a norma aceita do cliente; ver abaixo) |
| J | julgamento | o modelo, com o texto da norma na frente (hoje só o Anexo IV) |

**O que a conversa pode preencher.** Pela norma, a palavra do cliente nunca prova um fato da decisão: a contagem de
sessões é pelo histórico e "não pela informação que ele prestar" (art. 41, § 3º); a urgência é a declarada pelo
profissional (art. 26); a indicação clínica é a do profissional assistente (arts. 55 e 60). A conversa preenche só:
o que o cliente quer (reembolso, dúvida, situação de um pedido), de quem é o pedido (art. 8º) e, numa dúvida, a data de
outro atendimento para dizer qual regra valia.

**Desfechos:** SEGUE (vai ao próximo nó) · PENDENTE Pxx (código do Anexo B da NT-02; protocolo aberto, sem valor) ·
NEGADO · ANALISTA (protocolo aberto, sem valor) · INVÁLIDO (orienta o documento certo, protocolo aberto) ·
ITEM SAI (o item não entra no cálculo, os outros seguem) · NÃO PROCESSA (orienta abrir atendimento próprio).

**Código hoje:** sim · parcial · não · sem dado (o MCP não dá o fato) · texto (só se explica na resposta).

Cada nó vale **por item** do documento quando o documento tem mais de um item ou mais de uma sessão (art. 33, § 1º;
art. 37, § 1º; art. 41, § 4º; art. 74, § 2º). Hoje o código decide por documento, salvo no Anexo IV (D75).

---

## Nível 0 — Antes do documento (porta de entrada)

| Nó | Pergunta | Fato (fonte) | Ramos → desfecho | Regra | Código |
|---|---|---|---|---|---|
| 0.1 | O pedido é de quem abriu o atendimento? | de quem é o pedido (C) | de outra pessoa, inclusive dependente → NÃO PROCESSA, sem nenhuma informação sobre ela · da própria pessoa → SEGUE | art. 8º, §§ 1º a 3º; NT-02, Casos 19 e 20 | sim (supervisor, D65, D66) |
| 0.2 | O cliente está identificado? | carteirinha (C → M) | sem carteirinha → pedir · não achada → pedir de novo · achada → SEGUE | art. 2º, II | sim |
| 0.3 | O que o cliente quer? | intenção (C) | não disse → perguntar (D63) · reembolso → nível 1 · dúvida → busca na norma · situação de pedido → histórico | — | sim |
| 0.4 | O atendimento foi na rede credenciada? | prestador credenciado na data (sem fonte) | credenciado → não há reembolso; cobrança indevida segue procedimento próprio | art. 9º, parágrafo único; art. 62 | sem dado (texto) |

## Nível 1 — O arquivo (NT-02, 6.1, primeiro)

| Nó | Pergunta | Fato (fonte) | Ramos → desfecho | Regra | Código |
|---|---|---|---|---|---|
| 1.1 | É documento fiscal de despesa assistencial? | tipo do arquivo (D) | conta de consumo, comprovante bancário, cupom → INVÁLIDO · relatório ou pedido médico sozinho → complementar do pedido · recibo ou nota → SEGUE | art. 76; NT-02, 3.1 e 4.5; Casos 10 e 11 | sim |
| 1.2 | O arquivo é legível e inteiro? | legibilidade, páginas, rasura (D) | parcialmente ilegível → PENDENTE P27 · cortado → P28 · corrompido ou formato não aceito → P29 · rasura em campo obrigatório → P30 · página faltando → pendência (Caso 27) | art. 14, § 3º; art. 75; NT-02, 1.2 e 5.2 | parcial (o OCR lê o que der; sem pendência de imagem) — ver ponto 1 |
| 1.3 | O mesmo documento já foi apresentado? | o mesmo arquivo na conversa (D); o mesmo recibo em outro protocolo (H, sem o documento) | repetido → prevalece o primeiro protocolo; o segundo é encerrado com explicação · procedimento distinto no mesmo dia, discriminado → não é duplicidade | art. 17; NT-02, Caso 28 | parcial (só na conversa) |
| 1.4 | O documento é em idioma ou moeda estrangeira? | idioma, moeda (D) | sem tradução dos campos → PENDENTE P32 · moeda estrangeira → converter pelo câmbio de venda do dia do atendimento, mesmos tetos | arts. 46 e 69; NT-02, Caso 26 | não |
| 1.5 | O paciente do documento é o beneficiário? | nome do paciente (D) × nome do cadastro (M) | diverge → NÃO PROCESSA pelo art. 8º (P03: "verificar titularidade; aplicando-se o art. 8º, orientar abertura de atendimento próprio"); o Anexo IV, 6.5, e o Caso 21 dizem que não é reembolsável · confere (também com abreviação ou sem acento) → SEGUE | art. 9º, § 3º; art. 58; Anexo IV, 6.5; NT-02, P03 e Caso 21 | parcial (hoje vira INVÁLIDO) — ver ponto 2 |

## Nível 2 — Classificação de cada item (NT-02, 6.1, segundo)

| Nó | Pergunta | Fato (fonte) | Ramos → desfecho | Regra | Código |
|---|---|---|---|---|---|
| 2.1 | Qual a categoria de cada item? | natureza do procedimento e habilitação de quem fez (D: descrição, registro CRM, CRP, CREFITO, CRFa); categoria da linha (T) | consulta médica · sessão de terapia · exame · relatório clínico · OPME. Psiquiatra é consulta, mesmo em acompanhamento (4.2; Caso 02); psicólogo é sessão de terapia, mesmo chamado "consulta" (4.3; Caso 01); vale a natureza, não o nome (4.1) | art. 74; NT-02, 3.1 e 4.1 a 4.3 | parcial: uma categoria por documento — ver 2.4 |
| 2.2 | O item tem código TUSS da Tabela? | código (D) × linha (T) | código na Tabela → SEGUE · código fora da Tabela → reclassificar pela descrição (P14) · código desativado (ex.: 50000494) → o código que o substitui · sem código → classificar pela descrição: vale a natureza (§ 1º); mais de um código possível → o de menor teto (§ 2º) · descrição genérica ("atendimento", "serviços prestados") → PENDENTE P12 · sem descrição → P13 · procedimento que não existe na Tabela → NEGADO sem pendência (art. 56, parágrafo único) | art. 34; art. 37, § 2º; art. 56; NT-02, C5, P12 a P14, Caso 35; Anexo IV, 10 | não: item sem código "não entra no cálculo"; nenhum com código → ANALISTA — ver ponto 9 |
| 2.3 | Cada item e cada sessão têm valor próprio? | valor por item, quantidade de sessões (D) | vários itens ou sessões num valor só → PENDENTE P16, sem dividir por estimativa (Caso 03) · discriminado → SEGUE, um item por sessão. O Anexo IV, 10.3 e 10.4, exclui "pacote sem discriminação" e "valor mensal fechado": ver ponto 3 | NT-02, C6, 4.4, P16, Casos 03 e 04; art. 59, § 2º; Anexo IV, 10.3 e 10.4 | parcial: a `quantidade` é lida e ignorada; "10 sessões" num item só passa como uma |
| 2.4 | O documento reúne categorias distintas? | categorias dos itens (D, T) | sim e discriminado → cada item segue no seu regime (carência, teto, alçada) · sim e sem discriminação → PENDENTE P16 | art. 74, § 2º; NT-02, 4.4 e Caso 33; Tabela, 5.5 | não |
| 2.5 | O item é procedimento cirúrgico ou em regime hospitalar? | categoria da linha (T: "Procedimento cirúrgico", 347 linhas) | não há categoria própria na NT-02 nem carência própria nos arts. 22 a 25 | art. 78, § 1º; art. 83 | parcial: só a alçada de R$ 7.500,00 — ver ponto 8 |

## Nível 3 — Exclusão do Anexo IV, por item (NT-02, 6.1, terceiro)

| Nó | Pergunta | Fato (fonte) | Ramos → desfecho | Regra | Código |
|---|---|---|---|---|---|
| 3.1 | O item é de um grupo excluído (1, 2, 4 a 10)? | finalidade do procedimento (D), itens do Anexo IV (N) | excluído e é o único item → NEGADO, com grupo e item, sem pendência (11.4) · excluído e discriminado ao lado de itens cobertos → ITEM SAI (taxa, estacionamento, Caso 15) · excluído num valor só com item coberto → PENDENTE P16 antes de indeferir (art. 59, § 2º; Caso 16) · medicamento ou material aplicado no próprio ato e discriminado → não é excluído (art. 54, parágrafo único; grupo 4) · não é item do Anexo → SEGUE | arts. 51 a 54, 56 a 59; Anexo IV, 11.1, 11.3 e 11.4; NT-02, Casos 12, 15 e 16 | sim para o discriminado (D75); parcial para o valor só — ver ponto 3 |
| 3.2 | O item é de fronteira (grupo 3)? | indicação clínica expressa, contemporânea, com a condição tratada, no documento ou em relatório do profissional assistente (D, inclusive complementar) | com indicação → coberto e reclassificado na categoria (drenagem pós-operatória ou de linfedema → sessão de terapia, Caso 14) e SEGUE · indicação genérica ("finalidade terapêutica") → PENDENTE P26 · sem indicação → PENDENTE P25; não apresentada no prazo → NEGADO pela presunção estética · documento que declara finalidade estética, modelagem ou redução de medidas → NEGADO | art. 55, §§ 1º e 2º e parágrafo único; art. 60; Anexo IV, grupo 3 e 11.2; NT-02, C10, P25, P26, Casos 13, 14 e 32 | parcial: só lê o recibo; relatório enviado depois não é lido — ver pontos 4 e 5 |

## Nível 4 — Alçada (NT-02, 6.1, quarto)

| Nó | Pergunta | Fato (fonte) | Ramos → desfecho | Regra | Código |
|---|---|---|---|---|---|
| 4.1 | É material, órtese, prótese ou material especial? | categoria (D, T: "sob análise", 101 linhas) | sim → ANALISTA, qualquer valor, sem informar valor | art. 78, § 2º; NT-02, 4.6, Caso 17; Tabela, 5.3 | sim — ver ponto 7 |
| 4.2 | O valor solicitado passa do limite? | valor total do documento (D); limite da natureza (N) | acima de R$ 5.000,00 (consulta, exame, terapia, relatório) ou de R$ 7.500,00 (cirúrgico, hospitalar) → ANALISTA, sem informar valor, mesmo que o reembolso fosse menor · dentro → SEGUE | art. 78, §§ 1º, 3º e 4º; NT-02, 6.3 e Caso 18 | sim |

## Nível 5 — Vínculo, carência e prazo (NT-02, 6.1, quinto; art. 10)

| Nó | Pergunta | Fato (fonte) | Ramos → desfecho | Regra | Código |
|---|---|---|---|---|---|
| 5.1 | O contrato estava ativo na data do atendimento? | situação do contrato (M, só a de hoje) | suspenso ou cancelado na data → NEGADO, mesmo regularizado depois (Caso 29) · ativo → SEGUE | art. 10, I; art. 30; NT-02, Caso 29 | parcial: usa a situação de hoje (sem dado da data) |
| 5.2 | Qual o plano na data do atendimento? | plano (M, só o atual) | migrou depois do atendimento → vale o plano da data (Caso 30) | art. 3º, §§ 1º e 2º; art. 44, § 4º | sem dado |
| 5.3 | A carência do item estava cumprida na data do atendimento? | data de adesão (M); data do atendimento, de cada sessão (D); categoria do item | consulta 15 dias, inclusive telessaúde (art. 22) · exame 60 dias, pela data do exame; coleta seriada, a primeira (art. 23) · terapia 150 dias, cada sessão sozinha (art. 24) · OPME 180 dias (art. 25) · relatório clínico: sem carência na norma · não cumprida → NEGADO, não pendência (Caso 05) · urgência declarada pelo profissional, com nome e data, no documento ou relatório anexo → sem carência (art. 26) · sem declaração → carência normal (art. 26, § 2º) | arts. 21 a 26; NT-02, Caso 05 | sim por documento; parcial: urgência basta "declarada" (sem conferir profissional e data); não por sessão |
| 5.4 | Há regra especial de contagem da carência? | portabilidade, reingresso, inscrição do dependente, suspensão anterior (sem fonte) | portabilidade → conta o tempo do plano de origem (art. 27) · reingresso até 15 dias → não cumpre de novo (art. 29) · dependente → conta da inscrição (art. 28) · suspensão por inadimplência → interrompe a contagem (art. 21, § 3º) | arts. 21, § 3º, e 27 a 29 | sem dado |
| 5.5 | O pedido foi feito no prazo? | data do atendimento (D; com várias sessões, a última); data do pedido (hoje); prazo vigente na data do atendimento (N) | 90 dias, em dias corridos, sem prorrogação para dia útil · atendimentos de 01/07/2025 a 31/10/2025: 150 dias (CIRC-04-2025, revogada pela CIRC-09-2025 a partir de 01/11/2025; prazos já decaídos não voltam) · fora do prazo → NEGADO por decadência, sem examinar o mérito (Caso 06) · data do atendimento diferente da de emissão → vale a do atendimento (art. 13, § 1º) · emissão antes do atendimento → PENDENTE P10 (Caso 31) | arts. 12 e 13; CIRC-04-2025; CIRC-09-2025; NT-02, Casos 06 e 31 | sim para data única; não para a última sessão (art. 13, § 2º) nem P10 |

## Nível 6 — Campos e exigências do documento (NT-02, 6.1, sexto)

Todas as pendências do documento saem de uma vez (art. 18, § 1º; NT-02, 2.3). Não se pede o que a operadora já tem nem
o que o cliente já disse no atendimento (art. 18, § 2º; NT-02, 5.4). Pendência não é indeferimento: protocolo aberto,
sem valor (art. 18, parágrafo único).

| Nó | Pergunta | Fato (fonte) | Ramos → desfecho | Regra | Código |
|---|---|---|---|---|---|
| 6.1 | C1: nome e CPF do paciente? | (D) | sem nome → P01 · sem CPF → P02 | NT-02, C1 | parcial: os dois saem como P01 |
| 6.2 | C2: nome e CPF ou CNPJ do prestador? | (D) | sem nome → P04 · sem CPF ou CNPJ → P05 | NT-02, C2 | parcial: os dois saem como P04 |
| 6.3 | C3: registro no conselho, com sigla e UF? | (D); validade e habilitação (sem fonte) | ausente → P06 · ilegível → P07 · incompatível com o procedimento (ex.: CRP numa fisioterapia) → P08 ou P34; não sanado → NEGADO · registro irregular confirmado → NEGADO definitivo | arts. 67 e 68; NT-02, C3, P06 a P08, P34 | parcial: só a ausência; não confere a UF nem a compatibilidade |
| 6.4 | C4: data do atendimento? | (D) | ausente → P09 · ilegível → P11 | NT-02, C4 | sim (ausente) |
| 6.5 | C5: descrição do procedimento? | (D) | ver nó 2.2 | NT-02, C5 | parcial |
| 6.6 | C6: valor total e por item? | (D) | sem valor → P15 · sem discriminação → P16 · extenso diferente do numérico → P17 | NT-02, C6 | parcial: falta de discriminação sai como P15; P17 não |
| 6.7 | C7: assinatura ou carimbo? | (D) | ausente → P18 | NT-02, C7 | sim |
| 6.8 | C8: número da sessão no ano (terapia)? | (D); histórico (H) | ausente → apurar pelo histórico; sem histórico → P19 (pedir ao prestador). Nunca é pendência sozinho | NT-02, C8 e 2.2 | sim (usa o histórico) |
| 6.9 | Terapia: é preciso relatório clínico? | número da sessão no ano, somadas todas as terapias (H); valor pago × teto (D, T) | exigido quando ocorrer primeiro: a sessão é a 24ª ou posterior (redação original), a 10ª (CIRC-11-2026, de 01/02/2026), a 5ª (CIRC-02-2026, de 20/04/2026); ou o valor pago passa do teto em mais de 75% · sem relatório → P20 (Caso 08) · relatório sem indicação de manutenção → P21 · não assinado → P22 · relatório já apresentado no ano vale para as sessões seguintes (art. 73, § 5º; CIRC-02-2026, art. 16) · relatório enviado para sanar pendência entra no mesmo protocolo e não é pedido à parte (NT-02, 8.4) | art. 42, § 2º; art. 73, §§ 3º a 5º; CIRC-11-2026, arts. 14 e 17; CIRC-02-2026, arts. 14 a 16; NT-02, Anexo D | parcial: P20 sim; P21 e P22 não; relatório de pedido anterior: sem dado — ver ponto 6 |
| 6.10 | Exame de alta complexidade (marcado na Tabela): há pedido médico? | pedido no documento ou complementar (D); marca da linha (T, 297 linhas) | sem pedido → P23 (Caso 23) · pedido sem nome e registro do solicitante → P24 · urgência comprovada (art. 26) → dispensado (Caso 24) · um pedido pode servir a vários exames descritos nele (9.3) · pedido emitido há mais de 90 dias, salvo prazo nele escrito (9.2) → sem código de pendência na norma | art. 38; NT-02, C9, P23, P24, Anexo E | parcial: P23 e urgência sim (D75); P24 e validade não |
| 6.11 | Outras exigências da linha da Tabela | observação da linha (T) | "Exige indicação clínica (art. 60)" (380 exames, 18 terapias) · "Exige relatório do cirurgião / do médico assistente (art. 60)" (327 linhas) · "Exige prescrição médica" (hidroterapia) · "Exige autorização prévia da auditoria" (psicoterapia intensiva) · "Exige identificação do solicitante" (parecer) | art. 60; art. 65, § 2º; NT-02, 2.2 | não — ver pontos 5 e 10 |
| 6.12 | Pendências sem regra de quando cabem | (D, canal) | comprovante de pagamento "quando exigido" → P31 · dados bancários → P33 · numeração fiscal "quando exigível" → P35 | NT-02, P31, P33, P35; art. 15 | não (nenhuma norma diz quando) |

**Depois da pendência:** 60 dias corridos da comunicação para sanar, prorrogáveis uma vez (art. 19) · sanada → a análise
volta do ponto em que parou, sem reiniciar prazos (art. 19, § 2º; Caso 09) · não sanada → NEGADO por documentação
insuficiente, com reapresentação possível se o prazo do art. 12 ainda não acabou (art. 19, § 3º). Código: a ficha não
traz os 60 dias (D77).

## Nível 7 — Limites de terapia, consulta e relatório

| Nó | Pergunta | Fato (fonte) | Ramos → desfecho | Regra | Código |
|---|---|---|---|---|---|
| 7.1 | A sessão passa do limite de 40 no ano? | sessões do ano, somadas psicoterapia, fono, TO e fisioterapia; consultas, mesmo de psiquiatra, não contam (H) | 41ª em diante → NEGADO a sessão excedente, mesmo com relatório (Caso 07) | art. 40; NT-02, Caso 07 | sim por documento; não por sessão — ver ponto 12 |
| 7.2 | O código tem limite próprio? | observação da linha (T) | psicoterapia breve focal: no máximo 12 sessões por ano | Tabela, TUSS-50000470 | não |
| 7.3 | É a segunda consulta com o mesmo profissional em 15 dias? | prestador e data das consultas anteriores (H, sem o prestador) | especialidades distintas → não se aplica · com justificativa clínica no documento ou relatório → SEGUE · sem justificativa → a segunda não é reembolsável | art. 36; NT-02, Caso 34 | sem dado — ver ponto 11 |
| 7.4 | É relatório clínico apresentado sozinho? | categoria (D); relatórios do ano (H) | para sanar pendência → entra no pedido original, sem valor próprio · sozinho → teto do TUSS-10104011 (1 URS), uma vez por ano civil; segundo no ano → NEGADO | NT-02, 3.1, 8.4 e Caso 36; Tabela, TUSS-10104011 | não |
| 7.5 | É item que só vale com o procedimento principal? | observação da linha (T: anestesias, 20 linhas) | sem o procedimento principal no pedido → não reembolsável | Tabela, observação | não |

## Nível 8 — Cálculo, item a item (NT-02, 6.1, último; Título IV)

| Nó | Passo | Fato (fonte) | Regra | Código |
|---|---|---|---|---|
| 8.1 | Teto do item = URS da linha × valor da URS do exercício da data do atendimento (R$ 95,10 em 2026) | código (T); data (D) | arts. 32 e 33, parágrafo único; NT-02, Caso 25 | sim (só há a Tabela 2026) |
| 8.2 | Psicoterapia individual (TUSS-50000462): teto da circular vigente na data, não o impresso na Tabela. Até 31/01/2026: 1,2 URS (continuado 1,0); de 01/02/2026: 1,6 (1,4); de 20/04/2026: 2,8 (2,6). Continuado = 8 ou mais sessões no ano antes desta, somadas as terapias, pelo histórico | data (D); sessões do ano (H) | art. 41; CIRC-11-2026; CIRC-02-2026; Tabela, nota (1) e 5.2 | sim |
| 8.3 | Teto por sessão, mesmo com várias sessões no documento; por procedimento e por atendimento, não por documento | quantidade e valor por sessão (D) | art. 33, § 1º; art. 41, § 4º; NT-02, Caso 04 | não — lacuna 1 da auditoria |
| 8.4 | Base = menor entre o valor pago no item e o teto; o valor pago já sem os itens não reembolsáveis discriminados; tributos retidos fazem parte do valor pago | (D) | arts. 43 e 48 | sim |
| 8.5 | Coparticipação pelo plano e pela faixa de meses completos de adesão na data do atendimento (até 12; de 12 a 36; acima de 36). Original: Pleno 30/20/10%, Essencial 35/25/15%. De 20/04/2026 (CIRC-02-2026): Pleno 40/30/20%, Essencial 45/35/25%. Aplicada depois do teto, sempre deduzida | plano e adesão (M); data (D) | art. 44; CIRC-02-2026, art. 3º | sim (12 meses exatos fica na primeira faixa) |
| 8.6 | Limite anual: 48 URS por beneficiário no ano civil, somadas todas as categorias, menos o já reembolsado no ano pelo histórico · valor maior que o saldo → aprovado parcial pelo saldo · saldo zero → NEGADO | reembolsos do ano (H) | art. 45 | sim |
| 8.7 | Arredondamento meio para cima, uma vez, no fim | — | art. 47 | sim |
| 8.8 | Outro benefício da operadora para o mesmo atendimento → não acumula | (sem fonte) | art. 44, § 6º | sem dado |

**Fim:** APROVADO ou APROVADO_PARCIAL, com a decisão, os dispositivos aplicados, o valor e as pendências, sem CID nem
quadro clínico (arts. 6º, 7º, 79, 80 e 82). Informação que só vai em texto: pagamento em 15 dias do deferimento (art. 15),
reanálise em 150 dias (art. 20), revisão humana a qualquer tempo (art. 77, § 2º), análise em 30 dias do protocolo
completo (art. 81), desistência (art. 16).

---

## Pontos em que as normas se contradizem ou se calam

Revistos um a um contra o texto e contra os casos de treino. Ficaram três grupos: o que você já decidiu, o que a própria
norma resolve pela hierarquia (art. 5º; regra específica antes da geral; Regulamento antes da observação da Tabela) e o
que é escolha sua.

### Já decidido por você

| # | O conflito | Como fica |
|---|---|---|
| 4 | Fronteira (grupo 3) sem indicação: o Caso 13 e a abertura do grupo 3 dizem "presume-se estética, indeferido"; o Caso 32, o C10 e o P25 dizem pendência. | **Pendência P25**, como hoje. Você ajustou o gabarito do caso 08 em 2026-10-09 ("a NT-02, caso 32 e P25, manda abrir pendência antes"). Documento que declara finalidade estética é negado direto. |

### A norma resolve (sigo assim, salvo se você discordar)

| # | O conflito | Como fica e por quê |
|---|---|---|
| 1 | Imagem ilegível ou arquivo corrompido: a NT-02, 3.1, põe em INVÁLIDO; o art. 75, a NT-02, 1.2, e os códigos P27 a P29 tratam como pendência. | **Pendência.** O art. 75 é do Regulamento e o Anexo B tem um código para cada vício de imagem. Para o cliente muda pouco: nos dois casos ele manda o documento de novo. |
| 3 | Valor só para item excluído e item coberto, ou para várias sessões ("pacote"): o art. 59, § 2º, a NT-02, 4.4, e os Casos 03 e 16 mandam pendência; o Anexo IV, 10.3, 10.4 e 11.3, e o art. 52, § 3º, mandam indeferir o documento inteiro. | **Pendência P16 primeiro**; o documento inteiro só é negado se a discriminação não vier no prazo do art. 19. Os Casos 03 e 16 tratam exatamente dessa situação, e a NT-02, 5.3, diz que não se indefere antes de esgotar a pendência. |
| 6 | Relatório da terapia: a CIRC-02-2026 reescreveu o art. 73, § 3º, sem "indicação da hipótese de manutenção"; a NT-02, Anexo D, 8.1, VI, e o P21 continuam exigindo. | **Continuar exigindo a manutenção.** A CIRC-02-2026 não menciona a NT-02, e circular que não menciona um dispositivo não o altera (art. 5º, § 2º). |
| 9 | Item sem código ou só com nome comercial: o art. 34 e o Caso 35 mandam classificar pela descrição e, sem como, pendência; o Anexo IV, 10.1 e 10.2, exclui. | **Classificar pela descrição; sem como, pendência P12; não sanada, NEGADO pelo 10.1.** O art. 34 é a regra específica para esse caso. |
| 10 | Psicoterapia em regime intensivo: a Tabela diz "Exige autorização prévia da auditoria"; o art. 65, § 2º, diz que a falta de autorização não é motivo de indeferimento na livre escolha. | **Seguir o art. 65, § 2º**: artigo do Regulamento antes da observação da Tabela. |
| 11 | Segunda consulta em 15 dias sem justificativa (art. 36): o MCP não dá o prestador dos pedidos anteriores. | **Só texto** (sem dado). |
| 12 | Contagem das sessões: o histórico de pedidos ou o campo `sessoes_terapia_ano` do cadastro. | **O histórico**, como hoje: é a fonte que o art. 41, § 3º, nomeia. |
| 13 | Teto da psicoterapia em 2027: CIRC-11-2026, art. 19 (1,8 URS) × CIRC-02-2026 (2,8, a reavaliar no fim de 2026). | **Nada agora**: a data de referência é 2026. |
| 14 | Contrato e plano na data do atendimento: o MCP só dá os de hoje. | **Usar os de hoje e dizer isso na ficha.** |

### Decididos por você depois da revisão

Opção (a) nos quatro (2026-10-17): documento de outra pessoa não é processado (art. 8º; P03); exigências da Tabela fora do
grupo 3 não geram pendência (NT-02, 2.2); órtese ou material avulso vai a analista (art. 78, § 2º); procedimento
cirúrgico ou hospitalar vai a analista (art. 83).

| # | O conflito | Opções (recomendada primeiro) |
|---|---|---|
| 2 | Documento em nome de outra pessoa. Hoje vira INVÁLIDO, mas o art. 76, § 2º, diz que despesa excluída não é inválido. O P03 manda "verificar titularidade; aplicando-se o art. 8º, orientar abertura de atendimento próprio"; o Anexo IV, 6.5, e o Caso 21 dizem "não reembolsável". | **(a) Não processar pelo art. 8º**: a pessoa atendida abre o próprio atendimento, sem dado dela; é o que o P03 manda e é o mesmo caminho do pedido de terceiro na conversa. (b) Negar pelo Anexo IV, 6.5. (c) Deixar como está (inválido). Na primeira versão eu tinha recomendado (b); revendo, o P03 é a regra do campo e a (a) não emite decisão sobre o pedido de outra pessoa, que o art. 8º, § 1º, proíbe processar. |
| 5 | A Tabela marca "Exige indicação clínica (art. 60)" em 398 linhas (exames em regime hospitalar, em day hospital, em pediatria com sedação, exames de especialidade, 18 terapias) e "Exige relatório do cirurgião ou do médico assistente" em 327; a NT-02, 2.2, diz que a indicação só se exige no grupo 3 e que, fora dele, a falta não gera pendência. | **(a) Seguir a NT-02, 2.2**: pendência de indicação só no grupo 3 e nas fisioterapias (Caso 32); a observação da Tabela vira informação. O art. 73, § 1º, faz da NT-02 a norma da documentação. (b) Seguir a Tabela e pedir a indicação nessas linhas, sem código de pendência próprio (usaria o P25 por analogia). |
| 7 | Órtese ou material comprado avulso: o Anexo IV, 4.11, exclui; a NT-02, 3.1 ("com ou sem procedimento associado"), e o art. 78, § 2º ("independentemente do valor"), mandam a analista. | **(a) Analista**: o art. 78, § 2º, diz "sempre", e o analista pode aplicar o 4.11; negar errado custa mais que encaminhar. (b) Negar pelo 4.11, que é o que a ordem da NT-02, 6.1 (exclusão antes da alçada), e o código de hoje fazem. |
| 8 | Procedimento cirúrgico ou hospitalar: está na Tabela (347 linhas) e tem alçada própria de R$ 7.500,00 (art. 78, § 1º), mas não é categoria da NT-02 nem tem carência nos arts. 22 a 25. | **(a) Analista** (caso omisso, art. 83): simples e seguro, mas deixa sem uso a alçada de R$ 7.500,00, que supõe que a análise automática decida cirurgia abaixo dela. (b) Decidir no código, sem carência (nenhuma está prevista) e com o relatório do cirurgião que a Tabela pede. |

## O que falta no código, em resumo

Pela árvore, os ramos que mudam desfecho e não existem hoje: decompor o documento por item e por sessão (2.3, 2.4, 5.3,
5.5, 7.1, 8.3); classificar item sem código (2.2); ler o relatório enviado depois no grupo 3 (3.2); pendência de valor só
com item excluído (3.1); relatório isolado uma vez por ano (7.4); limite de 12 sessões da breve focal (7.2); códigos de
pendência certos por campo (6.1, 6.2, 6.6); P21, P22 e P24 (6.9, 6.10); prazo de 60 dias da pendência na ficha.

## Revisão (2026-10-17, mesmo dia)

Reconferido contra o texto das normas e os gabaritos de `casos/treino`. Mudou: o ponto 4 já estava decidido (ajuste do
caso 08); a recomendação do ponto 2 passou de negar pelo Anexo IV, 6.5, para não processar pelo art. 8º (P03); o ponto 3
ganhou o pacote sem discriminação (Anexo IV, 10.3 e 10.4, contra o Caso 03); o ponto 8 ganhou o custo da opção
recomendada; a seção "Quando a árvore é usada" diz que ela vale só para a decisão de um pedido com documento.
