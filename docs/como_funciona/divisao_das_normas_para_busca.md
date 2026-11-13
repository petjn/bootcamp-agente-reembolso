# Como as normas foram divididas para a busca

Para achar a regra certa, o agente não lê as normas inteiras a cada pergunta: elas são cortadas antes em pedaços
(em inglês, *chunks*), e a busca devolve só os pedaços que interessam. Este documento explica onde cortar, o que
cada pedaço carrega junto (os *metadados*) e como isso permite saber qual versão de um artigo valia numa data. O
código está em `ingest/chunking.py`, `ingest/build.py` e `app/rag`.

## Princípios

1. **A unidade do chunk é a unidade da norma, não um número de tokens.** Em texto normativo, cortar por tamanho mistura dois dispositivos num pedaço só e confunde a citação. Cortamos onde a própria norma corta: artigo, parágrafo, item, linha da tabela.
2. **Todo chunk sai do build com metadados.** São eles que permitem decidir, com código, o que vale numa data. Os metadados vêm da estrutura do documento e da nossa leitura das normas, nunca de um modelo.
3. **A citação segue o art. 6º do Regulamento.** O metadado `citacao` usa as siglas `ART-12`, `CIRC-11-2026`, `TUSS-50000462`, `ANEXO-IV` e `NT-02`, geradas por `app/siglas.py`. A citação é sempre do artigo inteiro (`ART-41`), e o parágrafo fica num metadado separado.
4. **Material de apoio entra na busca, mas não se cita.** Manual e FAQ ajudam a entender a linguagem do cliente, mas não fundamentam decisão (art. 5º, § 5º) e, em conflito, perdem para o Regulamento e as circulares (art. 5º, § 3º).
5. **O cabeçalho de contexto é determinístico.** Cada chunk começa com a sua origem, por exemplo `[Regulamento Geral — Título III — Art. 41, § 2º]`. Ele é montado pelo código a partir da estrutura, e não escrito pelo modelo, que poderia inventar contexto.

## Metadados de cada chunk

| Campo | Exemplo | Para quê |
|---|---|---|
| `id` | hash de (arquivo, dispositivo, parte, texto) | índice igual em todo build (sem uuid aleatório) |
| `arquivo` | `circular_02_2026.pdf` | rastrear a origem |
| `tipo_documento` | `regulamento`, `circular`, `tabela`, `nota_tecnica`, `anexo`, `apoio` | filtros |
| `citacao` | `ART-41`, `CIRC-02-2026` ou nulo | o que vai em `regras_aplicadas` |
| `dispositivo`, `parte` | `ART-41`, `§ 2º` | montar o artigo consolidado |
| `vigencia_inicio`, `vigencia_fim` | `2026-04-20` | filtro por data |
| `acao`, `alvo`, `parte_alvo` | `altera`, `ART-41`, `§ 2º` | só nas circulares (ver abaixo) |
| `citavel` | `true` / `false` | material de apoio nunca é citado |

**Metadados das circulares declarados por nós.** Decidido com o usuário: o que cada circular faz (`altera`, `revoga`, `sobrepoe_tuss`, `eficacia_futura`), sobre quem e desde quando é registrado a partir da nossa leitura, como orientava o bootcamp ("ler e entender as regras"), e não por expressão regular, que quebra se a frase vier escrita de outro jeito. O texto novo de cada parte continua sendo lido do PDF. Uma checagem no build confirma que o artigo declarado aparece no texto da circular; se não aparecer, o build para.

O limite dessa decisão: declaramos **o que a norma é** (estrutura e relações). Nunca gravamos **respostas** no código. A conversa, a interpretação do pedido e a explicação continuam com o modelo, e os números continuam saindo do texto (D7).

## Estratégia por arquivo

| Arquivo | Chunk | Citação | Por quê |
|---|---|---|---|
| `regulamento_geral.pdf` (87 artigos) | um por **parte de artigo** (caput, cada §), com o artigo como pai e o título e capítulo no cabeçalho | `ART-n` | é a unidade que as circulares alteram; o pai permite montar o artigo inteiro |
| 4 circulares | um por **artigo da circular**, cada um com `acao`, `alvo`, `parte_alvo` e vigência | `CIRC-nn-aaaa` | cada artigo de circular faz uma coisa só (alterar uma parte, revogar outra circular); o metadado é o que o filtro usa |
| `tabela_urs_2026.pdf` (1.835 códigos) | **cadastro por código** (já feito) + um chunk pequeno por linha, para achar o procedimento pela descrição quando o recibo não traz o código; a abertura (valor da URS) e as notas viram chunks de texto | `TUSS-n` | código se consulta direto, não por semelhança; a busca por descrição cobre o recibo sem código |
| `nota_tecnica_02_documentos.pdf` | um por **seção**; as tabelas (campos C1 a C10, categorias do Anexo A, pendências P01 a P35) inteiras, em Markdown, e também como dados para o código | `NT-02` | cortar uma tabela de campos obrigatórios no meio perde a linha que o agente precisa |
| `anexo_iv_exclusoes.pdf` | um por **item de exclusão**, com o grupo no metadado | `ANEXO-IV` | o indeferimento cita grupo e item; o item é a unidade da decisão |
| `manual_rede_credenciada.pdf` | um por **seção** | não citável | material de orientação; ajuda a busca a entender a linguagem do cliente |
| `faq_interno.docx` | um por **par pergunta e resposta**, marcado como desatualizado | não citável | o próprio FAQ avisa que pode estar desatualizado; serve para entender a pergunta, nunca para decidir |

## Ajustes combinados com o usuário (2026-10-08, tarde)

**Contexto que cada chunk carrega.** Duas camadas, para não diluir o embedding de trechos curtos:
- *Texto que vira embedding:* o cabeçalho curto com nomes (título, capítulo, grupo).
- *Texto que vai para o modelo junto com o chunk:* o parágrafo de abertura do título ou do grupo, **na íntegra**. No LlamaIndex, isso é metadado excluído do embedding (`excluded_embed_metadata_keys`) e incluído para o LLM.
- Íntegra em vez de resumo: os parágrafos são curtos (44 a 117 palavras) e vários trazem exceções que um resumo perderia.

**Regulamento.** Cada título abre com um parágrafo explicativo, que o parser de hoje descarta e passa a ser guardado. Os capítulos têm só nome. Exemplo do art. 11 ("O pedido é formalizado..."): cabeçalho `Regulamento Geral — Título II — Do direito ao reembolso — Capítulo I — Das hipóteses e dos requisitos — Art. 11`, mais o parágrafo de abertura do Título II.

**Anexo IV.** Cada item leva o grupo e o parágrafo de abertura do grupo. Os parágrafos que mudam o sentido da lista:
- grupo 3: reembolsável com indicação clínica expressa;
- grupo 4: exceto se aplicado no próprio ato e discriminado;
- grupo 5: sai da base de cálculo, mas não indefere o pedido;
- grupos 7 a 9: ressalvada cobertura contratual específica.

O item 11 ("Regras de aplicação") não é lista de exclusão. São 4 regras sobre como aplicar o anexo:
- cada uma vira um chunk do tipo `regra_aplicacao`;
- elas vão junto sempre que um item do Anexo IV for recuperado (a 11.2 só com o grupo 3);
- a 11.3 (separar itens excluídos dos reembolsáveis) e a 11.4 (exclusão não gera pendência) também viram código;
- a abertura do anexo (a exclusão prevalece sobre teto, carência e limite) vai junto com qualquer item.

**Tabela URS.**
- O chunk por linha leva código, descrição, categoria e observação, mas **não o teto**. O teto vem da função de cálculo, já resolvido para a data, porque a linha da psicoterapia imprime 1,2 URS, que está desatualizado.
- A coluna Observação tem 31 textos distintos, vários com regra própria ("Máximo de 12 sessões por ano civil", "Reembolsável uma vez por ano civil", "Exige autorização prévia da auditoria", "Não utilizar: substituído por TUSS-50000462", remissões ao Anexo IV 3.x). O significado de cada um é declarado por nós em campos estruturados.
- **Achado:** em 124 exames, a coluna "Teto (R$)" não é igual a URS × R$ 95,10. Por exemplo, a dosagem de colesterol total tem 0,3 URS, mas R$ 33,28, que equivale a 0,35 URS. A diferença chega a R$ 4,76. O art. 33 e a seção 2 da própria tabela mandam calcular URS × valor da URS. Aguardando decisão do usuário.

## O que acontece na busca

```
1. Busca híbrida (BM25 + embedding) e reranker trazem os chunks
2. Filtro por data (do atendimento; sem data, a data de hoje):
     a. descarta circular com vigência posterior à data
     b. circular com acao=revoga remove do conjunto a circular alvo
     c. por (artigo, parte), vence a redação de vigência mais recente
3. Para cada artigo que sobrou, monta o artigo consolidado na data:
     cada parte na redação vigente, com a fonte marcada.
     Parte que a busca não trouxe é completada pelos metadados,
     e o caso é registrado no LangSmith como "busca não trouxe a circular"
4. O texto consolidado vai para o modelo explicar e citar
```

Sem data no pedido vale a regra **vigente hoje**, que não é a mesma coisa que a mais recente: uma eficácia futura (a CIRC-11-2026 agendou um teto para 2027) não vale antes da data dela. Para calcular valor, a data do documento fiscal é obrigatória.

## Técnicas consideradas

- **Chunking com contexto:** usado, na versão determinística (princípio 5).
- **Auto-merging:** usado no Regulamento, com a hierarquia montada pela estrutura do texto, e não pelo `HierarchicalNodeParser`, que corta por tokens. O passo 3 da busca é a versão "por data" do auto-merging.
- **Sentence-window:** não usado. A frase solta perde o sentido ("§ 2º Nesse caso...") e a janela cruza a fronteira entre artigos.
- **GraphRAG:** não usado na versão completa (um modelo pequeno extraindo relações jurídicas erra). Usamos o grafo normativo explícito, pequeno e conferível.
