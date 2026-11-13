# Regras de negócio que viram código

As regras de reembolso das normas da operadora, na ordem em que são verificadas, escritas como o código as aplica.
Os nomes das normas e as siglas estão no [glossário](../README.md#glossário).

Fonte: leitura integral do Regulamento Geral (87 artigos), da Nota Técnica 02, do Anexo IV, das 4 circulares e da introdução e notas da Tabela URS 2026. Cada regra traz o dispositivo, que é também a citação usada em `regras_aplicadas` (convenção do art. 6º: `ART-12`, `CIRC-11-2026`, `TUSS-50000462`, `ANEXO-IV`, `NT-02`).

**Validação:** com as regras abaixo, recalculei os dois gabaritos com valor e os dois bateram ao centavo (seção 9). O terceiro (escalonamento) não tem valor e bate pela regra de alçada.

## 1. Ordem de verificação (NT-02, item 6.1)

1. O arquivo é documento fiscal de despesa assistencial? Se não for → `INVALIDO` (art. 76).
2. Categoria do Anexo A (7 classes).
3. Exclusão do Anexo IV? → `DESPESA_NAO_COBERTA`, sem pendência e sem valor (art. 51).
4. Alçada (art. 78) → `ESCALADO_ANALISTA`, abre protocolo e não informa valor.
5. Vínculo, carência e prazo (arts. 10, 21–30, 12).
6. Campos obrigatórios da NT-02 → pendência (art. 18).
7. Apuração do valor (arts. 43–47).

A ordem é norma: evita pedir documento que não muda o resultado (art. 10, § 2º).

## 2. Categoria → regime (NT-02, Anexo A)

| Categoria | Regime | Observação |
|---|---|---|
| `CONSULTA_MEDICA` | teto do art. 35 (5 URS); carência do art. 22 (15 dias) | psiquiatra é consulta, não terapia (art. 35, parágrafo único) |
| `SESSAO_TERAPIA` | arts. 40–42; carência do art. 24 (150 dias); relatório do art. 73, § 3º | psicólogo é terapia mesmo que o recibo diga "consulta" |
| `EXAME_DIAGNOSTICO` | teto individual da tabela; carência do art. 23 (60 dias); pedido médico na alta complexidade (art. 38) | vários exames: teto item a item |
| `RELATORIO_CLINICO` | teto do TUSS-10104011 (1 URS), uma vez por ano | quando sana pendência, integra o protocolo original e não gera pedido |
| `MATERIAL_OPME` | **sempre analista humano**, qualquer valor (art. 78, § 2º) | na tabela: "sob análise", sem teto |
| `DESPESA_NAO_COBERTA` | indeferimento de plano, sem pendência e sem valor | cita `ANEXO-IV` com grupo e item |
| `INVALIDO` | sem pendência e sem valor; protocolo **continua aberto** | conta de consumo, comprovante bancário, cupom |

Documento com itens de categorias distintas é decomposto, item a item (art. 74, § 2º).

## 3. Alçada — quando não decidir (art. 78)

- Valor **solicitado** (não o apurado) acima de **R$ 5.000,00** em consultas, exames, terapias e relatórios; acima de **R$ 7.500,00** em procedimentos cirúrgicos e hospitalares.
- **OPME vai sempre** para analista.
- Ação: `abrir_protocolo` no MCP, decisão `ESCALADO_ANALISTA`, `valor_reembolso_brl = null`.

## 4. Prazos e carências

| Regra | Valor | Contagem | Dispositivo |
|---|---|---|---|
| Prazo para protocolar | **90 dias** (CIRC-04-2025 mudou para 150 entre 01/07 e 31/10/2025; CIRC-09-2025 restaurou 90) | dias corridos desde a data do atendimento | ART-12, ART-13 |
| Perdeu o prazo | decai; indeferido sem exame do mérito | — | ART-12, parágrafo único |
| Reanálise | 150 dias da decisão de indeferimento; não reabre prazo decaído | — | ART-20 |
| Pendência | 60 dias para sanar, prorrogável uma vez | — | ART-19 |
| Carência consulta | 15 dias | desde a adesão, na data do atendimento | ART-22 |
| Carência exame | 60 dias | idem | ART-23 |
| Carência terapia | 150 dias | idem, por sessão | ART-24 |
| Carência OPME | 180 dias | idem | ART-25 |
| Urgência/emergência | sem carência, com declaração no documento | — | ART-26 |

Data do atendimento vem do documento fiscal e prevalece sobre a data de emissão e sobre o que o cliente diz (art. 13, § 1º e § 5º).

## 5. Apuração do valor — a ordem é norma (Título IV)

```
teto_R$      = URS_da_linha × 95,10                       ART-33 (URS de 2026)
apurado      = min(valor_pago, teto_R$)                   ART-43
liquido      = apurado × (1 − coparticipação)             ART-44
saldo_anual  = 48 URS × 95,10 − soma(historico do ano)    ART-45, § 1º  (= R$ 4.564,80 − já pago)
reembolso    = min(liquido, saldo_anual)                  ART-45, § 2º
arredondar uma vez, ao final, meio para cima              ART-47
```

- **Coparticipação (art. 44, tabela do § 2º)** por plano e meses completos de adesão na data do atendimento:

| Plano | até 12 meses | 12 a 36 | acima de 36 | Fonte |
|---|---|---|---|---|
| Pleno | 30% | 20% | 10% | ART-44 (até 19/04/2026) |
| Essencial | 35% | 25% | 15% | ART-44 (até 19/04/2026) |
| Pleno | **40%** | **30%** | **20%** | CIRC-02-2026 (a partir de 20/04/2026) |
| Essencial | **45%** | **35%** | **25%** | CIRC-02-2026 (a partir de 20/04/2026) |

- **Decisão:** `APROVADO_PARCIAL` quando o **teto** (art. 43) ou o **saldo anual** (art. 45) cortam o valor. Coparticipação sozinha não torna o pedido parcial. Saldo zerado → `NEGADO` (art. 45, § 3º).

## 6. Terapias

- Limite de **40 sessões** por ano civil, somadas todas as modalidades (art. 40). Excedente é negado mesmo com relatório.
- Teto da psicoterapia individual (art. 41), por data do atendimento:

| Período | Normal (caput) | Acompanhamento continuado (§ 2º: ≥ 8 sessões anteriores no ano) | Fonte |
|---|---|---|---|
| até 31/01/2026 | 1,2 URS | 1 URS | ART-41 |
| 01/02 a 19/04/2026 | 1,6 URS | 1,4 URS | CIRC-11-2026 |
| a partir de 20/04/2026 | 2,8 URS | 2,6 URS | CIRC-02-2026 |

- Contagem de sessões **pelo histórico do MCP**, nunca pelo que o cliente diz (art. 41, § 3º; NT-02, campo C8).
- **Relatório clínico obrigatório** (art. 73, § 3º) quando ocorrer primeiro: sessão nº X ou posterior no ano, ou valor pago > 175% do teto. X = 24 (original), 10 (CIRC-11-2026, a partir de 01/02/2026), **5 (CIRC-02-2026, a partir de 20/04/2026)**. Sem relatório → `PENDENTE_DOCUMENTO`, sem valor; o relatório que chega depois retoma a análise (NT-02, casos 08 e 09). O relatório vale para o resto do ano.

## 7. Documento: campos e pendências (NT-02)

- Obrigatórios sempre: C1 beneficiário + CPF, C2 prestador + CPF/CNPJ, C3 registro no conselho + UF, C4 data do atendimento, C5 descrição/TUSS, C6 valor (discriminado se houver vários itens), C7 assinatura/carimbo.
- Só em hipóteses: C8 número da sessão (terapias; se faltar, apura pelo histórico — **não gera pendência**), C9 pedido médico (alta complexidade), C10 indicação clínica (grupo 3 do Anexo IV).
- Pendência lista **todos** os faltantes de uma vez, com códigos P01–P35 (Anexo B). Nunca indefere de imediato.

## 8. Guardrails

- **Art. 7º:** nunca reproduzir CID, hipótese diagnóstica, descrição de quadro clínico ou CPF inteiro. CPF só mascarado.
- **Art. 8º:** o atendimento é da carteirinha que o abriu. Pedido sobre cônjuge, dependente ou familiar, mesmo vindo do titular: não processa, orienta a abrir atendimento próprio e não dá nenhuma informação sobre o terceiro → `FORA_DE_ESCOPO`. O atendimento do próprio beneficiário continua.
- **Art. 5º, § 5º:** FAQ e manuais não fundamentam decisão.

## 9. Conferência contra os gabaritos

| Caso | Conta | Resultado | Gabarito |
|---|---|---|---|
| 01 consulta | min(240; 5 × 95,10 = 475,50) = 240 → Pleno, 7 meses de adesão em 30/04/2026, tabela da **CIRC-02** = 40% → 240 × 0,60 | **R$ 144,00**, `APROVADO` (teto não cortou) | R$ 144,00 ✔ (com a tabela original daria R$ 168,00) |
| 02 psicoterapia | 10 sessões anteriores → continuado; 25/04/2026 → CIRC-02: 2,6 × 95,10 = 247,26 → min(320; 247,26) → Essencial, 49 meses = 25% → 185,445 → saldo 4.564,80 − 4.453,53 = 111,27 | **R$ 111,27**, `APROVADO_PARCIAL` | R$ 111,27 ✔ |
| 03 prótese | OPME → art. 78, § 2º (e R$ 9.200 > R$ 7.500) | `ESCALADO_ANALISTA`, protocolo, sem valor | ✔ |

## 10. Achados e inconsistências da base

1. **O gabarito do caso 01 aplica a coparticipação da CIRC-02-2026 mas não a cita** (lista só `ART-44`). Já o caso 02 cita a CIRC-02. Pelo critério de avaliação (todos os dispositivos do gabarito e nenhum inexistente), citar a CIRC-02 no caso 01 é permitido. Pelo art. 6º, parágrafo único, é o correto, porque ela foi aplicada. Proposta: citar.
2. A NT-02 remete o OPME ao "art. 78, § 1º", mas no Regulamento a regra está no **§ 2º** (o § 1º trata dos limites em reais). A tabela URS repete o "§ 1º". Citamos `ART-78`, sem parágrafo, como o gabarito.
3. O TUSS **30105048** (artroplastia, item da nota da prótese) **não existe na Tabela URS 2026**. E o TUSS 70000039 aparece na tabela como "componente femoral", na nota como "componente tibial". Não muda o caso 03, que escala por ser OPME.
4. A Tabela URS tem **1.835 códigos**: 1.243 exames, 347 cirúrgicos, 101 OPME (todos "sob análise"), 87 consultas, 53 terapias, 4 relatórios. As observações das linhas carregam regras ("Exige indicação clínica (art. 60)", "Alta complexidade — exige pedido médico (art. 38)") e viram campos estruturados.
5. O art. 9º e o art. 45 têm "parágrafo único" junto com §§ numerados, o que formalmente não existe numa norma. É ruído do documento fictício; não muda regra.
