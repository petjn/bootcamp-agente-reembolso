# Documentação: por onde começar

O README da raiz apresenta o projeto. Esta pasta é para quem quer entender mais a fundo. Sugestão de leitura, na
ordem:

## 1. Como o agente funciona (`como_funciona/`)

| Arquivo | O que explica |
|---|---|
| [`grafo.md`](como_funciona/grafo.md) | O desenho das etapas do agente e como elas se ligam. |
| [`cada_etapa.md`](como_funciona/cada_etapa.md) | O que cada etapa faz, com a ideia da "ficha de atendimento" que todas compartilham. Bom primeiro texto. |
| [`fluxograma.md`](como_funciona/fluxograma.md) | Todos os caminhos possíveis dentro de cada etapa, separando o que o modelo decide do que o código decide. |
| [`regras_de_negocio.md`](como_funciona/regras_de_negocio.md) | As regras de reembolso das normas que viraram código: prazos, carência, tetos, coparticipação. |
| [`divisao_das_normas_para_busca.md`](como_funciona/divisao_das_normas_para_busca.md) | Como as normas foram cortadas em trechos para a busca achar o artigo certo. |

## 2. Resultados (`resultados/`)

| Arquivo | O que mostra |
|---|---|
| [`medicao_final.md`](resultados/medicao_final.md) | O número principal: 8 conversas nunca vistas, rodadas 3 vezes cada. Decisão certa em 8/8; 89% dos turnos atendidos. |
| [`64_casos.md`](resultados/64_casos.md) | A última rodada com todos os casos importantes: 63/64 decisões certas; 90% dos turnos. Mostra cada erro e a causa. |
| [`64_casos_como_foram_escolhidos.md`](resultados/64_casos_como_foram_escolhidos.md) | Por que esses 64 casos, e quais ficaram de fora por repetir situações. |
| [`evolucao.md`](resultados/evolucao.md) | A tabela de todas as rodadas, da primeira (4 de 17 decisões certas) à última, com o que mudou antes de cada uma. Também em `evolucao.csv`. |

## 3. Como os erros foram encontrados (`analise_erros/`)

| Arquivo | O que tem |
|---|---|
| [`planilha_de_erros.md`](analise_erros/planilha_de_erros.md) | O método: para cada conversa errada, marcar qual etapa errou e contar os erros por etapa. |
| [`arvore_de_decisao.md`](analise_erros/arvore_de_decisao.md) | Todas as perguntas que as normas mandam fazer para decidir um pedido, na ordem. |
| [`cobertura_dos_ramos.md`](analise_erros/cobertura_dos_ramos.md) | Para cada caminho da árvore, qual conversa passa por ele. |
| [`auditoria_normas_x_codigo.md`](analise_erros/auditoria_normas_x_codigo.md) | Leitura das normas inteiras comparada com o código, procurando regras que faltavam. |

## 4. O diário (`diario_de_decisoes.md`)

O registro, em ordem de data, de cada mudança feita no projeto, com o motivo e as alternativas descartadas. Cada
entrada tem um número: **D1, D2... D99**. Quando um comentário no código ou um documento cita "D45", é a entrada 45
deste diário. É um documento de trabalho, longo e detalhado; não precisa ser lido inteiro.

---

## Glossário

**Do projeto**

| Termo | Significado |
|---|---|
| Caso | Uma conversa completa de teste, com o gabarito do resultado. Ficam em `casos/`. |
| Turno | Uma mensagem do cliente e a resposta do agente. "08 T5" = caso 08, turno 5. |
| Rodada | Uma execução de um conjunto de casos para medir o agente, sempre depois de um grupo de correções. |
| Decisão | O desfecho do pedido: aprovado, aprovado parcial, negado, pendente de documento, despesa não coberta, para analista. |
| Casos de ajuste | Os casos de `treino/` e `ramos/`, usados para encontrar e corrigir erros. |
| Casos de teste | Os de `teste/`, nunca usados para corrigir: só para medir. |
| Etapa (ou nó) | Cada passo do grafo: reescrever, supervisor, triagem, documento, normas, responder, revisar. |
| Supervisor | A etapa que decide qual será a próxima etapa, até haver o que responder. |
| Ficha (ou estado) | O que o agente sabe da conversa até agora; todas as etapas leem e escrevem nela. |
| Molde | O formulário que o modelo preenche ao ler um documento: tipo, data, itens, valores. |
| Árvore de decisão / ramo | A sequência de perguntas que decide um pedido; cada caminho possível é um ramo. |
| Lacuna | Uma regra das normas que o código ainda não aplicava. |
| Vazamento | Uma resposta que mostra CPF, código de doença ou dado de outra pessoa. |

**Técnicos**

| Termo | Significado |
|---|---|
| LangGraph | Biblioteca para montar o agente como um grafo de etapas. |
| RAG | Buscar os trechos certos das normas e entregá-los ao modelo junto com a pergunta. |
| Busca híbrida | Juntar a busca por palavras (BM25) com a busca por significado (embeddings). |
| Reranker | Um segundo modelo que reordena os trechos achados, do mais ao menos relevante. |
| MCP | O protocolo pelo qual o agente consulta o cadastro e o histórico do cliente na operadora. |
| Ollama / Gemma | O programa que roda os modelos na própria máquina, e a família de modelos usada. |
| Thinking | Modo em que o modelo "pensa" antes de responder; mais lento, usado só no supervisor. |

**Das normas da operadora** (os documentos ficam em `kb/`)

| Termo | Significado |
|---|---|
| Regulamento | A norma principal, com os artigos (art. 12, art. 45...). |
| Circular | Uma norma que altera artigos do Regulamento a partir de uma data. |
| Vigência | A regra que valia na data do atendimento, não a mais recente. |
| NT-02 | A Nota Técnica que diz quais documentos e campos são exigidos. |
| Anexo IV | A lista do que o plano não cobre (óculos, dentista, remédios...). |
| Tabela URS / TUSS | A tabela com o teto de reembolso de cada procedimento; TUSS é o código de cada um. |
| Carteirinha | O número do cliente no plano. |
| Carência | O tempo depois da adesão em que certo serviço ainda não é coberto. |
| Teto | O valor máximo reembolsado por um procedimento. |
| Coparticipação | A parte do valor que fica por conta do cliente. |
| Alçada | O limite acima do qual o pedido vai para um analista humano. |
| P01 a P35 | Os códigos de pendência da NT-02 (ex.: P09 = falta a data do atendimento). |
| C1 a C10 | Os campos que a NT-02 exige num recibo (data, valor, CPF ou CNPJ do prestador...). |
