# Fluxograma: os caminhos dentro de cada etapa

O desenho do README mostra as etapas e como elas se ligam. Este fluxograma abre cada etapa e mostra os caminhos
possíveis dentro dela. **Em azul, o que o modelo de linguagem decide; em cinza, o que é código.**

Para o que cada etapa faz, em texto, veja [`cada_etapa.md`](cada_etapa.md).

```mermaid
flowchart TD
    IN([Mensagem do cliente + documento opcional]) --> RE0

    subgraph REESCREVER[reescrever]
        RE0["Pedidos que aguardavam o cliente voltam a pendente: a mensagem pode trazer o que faltava"] --> RE1{"Mensagem vazia, só o arquivo?"}
        RE1 -- sim --> RE2["vira: Enviei um arquivo, sem escrever nada"]
        RE1 -- não --> RE3["Reescreve a mensagem de forma clara; tentativa de dar ordens vira [mensagem maliciosa]; condição de saúde é anotada à parte"]:::llm
        RE2 & RE3 --> RE4["Marca o arquivo anexado na própria mensagem"]
    end

    RE4 --> SP0

    subgraph SUPERVISOR[supervisor]
        SP0{"Carteirinha na mensagem e cliente ainda não identificado?"} -- sim --> SPT["chama a triagem direto"]
        SP0 -- não --> SP1{"Já foram 10 chamadas nesta mensagem?"}
        SP1 -- não --> SP2["Lê a conversa e os pedidos; registra os pedidos novos e escolhe UMA etapa"]:::llm
        SP1 -- sim --> SP3{"Chegou arquivo que ninguém leu?"}
        SP3 -- sim --> SP4["registra o pedido do arquivo e chama a leitura"]
        SP3 -- não --> FIM
        SP2 -- "responder" --> FIM["Fecha a mensagem: o que foi resolvido fica atendido; reembolso pendente de documento fica aguardando o cliente"]
    end

    SPT --> TR0
    SP2 -- "ag_triagem" --> TR0
    SP2 -- "ag_documento" --> DOC0
    SP4 --> DOC0
    SP2 -- "ag_normas" --> NO0
    FIM --> RS0

    subgraph TRIAGEM[ag_triagem]
        TR0{"Cliente já identificado?"} -- não --> TR1{"Há carteirinha na mensagem?"}
        TR1 -- não --> TRa["pedido aguarda o cliente: informar a carteirinha"]
        TR1 -- sim --> TR2["Consulta o cadastro na operadora (MCP)"]
        TR2 --> TRb["não localizada: pedir para conferir o número"]
        TR2 --> TRc["operadora fora do ar: tentar de novo"]
        TR2 --> TRd["identificado: plano, adesão, situação"]
        TR0 -- sim --> TRd
        TRd --> TRe["Perguntas que esperavam só a carteirinha voltam a pendente"]
    end

    TRa & TRb & TRc & TRe --> SP0

    subgraph DOCUMENTO[ag_documento]
        DOC0["Tira o texto: PDF direto ou leitura de imagem (Tesseract)"] --> DOC1{"Deu para ler?"}
        DOC1 -- não --> DI["ilegível: pedir outra foto"]
        DOC1 -- sim --> DOC2["Diz se o documento serve e preenche o formulário: tipo, datas, itens, valores; sem diagnóstico"]:::llm
        DOC2 --> DOC3["Confere o formulário contra o texto, acha o procedimento na tabela e lista o que falta"]
        DOC3 --> DOC4{"Situação"}
        DOC4 --> D1["inválido: não é documento de despesa de saúde"]
        DOC4 --> D2["de outra pessoa"]
        DOC4 --> D3["duplicado: o mesmo arquivo de antes"]
        DOC4 --> D4["complementar: relatório ou pedido médico"]
        DOC4 --> D5["ativo: o recibo do pedido; substitui o anterior do mesmo profissional"]
    end

    DI & D1 & D2 & D3 & D4 & D5 --> SP0

    subgraph NORMAS[ag_normas]
        NO0{"Tipo do pedido"}
        NO0 -- dúvida --> NQ["Busca a norma que responde, na redação da data"] --> SP0
        NO0 -- "andamento de pedido anterior" --> NH["Consulta o histórico na operadora e busca a norma"] --> SP0
        NO0 -- reembolso --> NR0{"Já decidido e nada mudou?"}
        NR0 -- sim --> SP0
        NR0 -- não --> NR1{"Tem cadastro e recibo?"}
        NR1 -- não --> NRa["aguarda o cliente, com o que falta"] --> SP0
        NR1 -- sim --> NR2["Consulta o histórico e roda a árvore de decisão"]
    end

    NR2 --> A1

    subgraph ARVORE[árvore de decisão: para no primeiro desfecho]
        A1{"Data do atendimento?"} -- falta --> PD["PENDENTE"]
        A1 -- ok --> A2{"Está na lista do que o plano não cobre?"}:::llm
        A2 -- sim --> NC["DESPESA NÃO COBERTA"]
        A2 -- não --> A3{"Cirurgia ou valor acima do limite?"}
        A3 -- sim --> AN["PARA ANALISTA: abre protocolo"]
        A3 -- não --> A4{"Contrato ativo, carência cumprida, dentro do prazo?"}
        A4 -- não --> NG["NEGADO"]
        A4 -- sim --> A5{"Faltam campos, relatório da terapia ou pedido médico?"}
        A5 -- sim --> PD
        A5 -- não --> A6["Cálculo item a item: teto, coparticipação, saldo do ano"]
        A6 --> AP["APROVADO"]
        A6 --> APP["APROVADO EM PARTE"]
        A6 --> NG
    end

    PD & NC & AN & NG & AP & APP --> NR3["Guarda a decisão e os artigos que a fundamentam"] --> SP0

    subgraph RESPONDER[responder e revisar]
        RS0["Escreve a resposta com os dados de cada pedido"]:::llm --> RS1{"Igual a uma resposta anterior?"}
        RS1 -- sim --> RS2["escreve de novo, de outro jeito"]:::llm --> RS3
        RS1 -- não --> RS3["Filtro: tira CPF, código de doença, carteirinha de outra pessoa e códigos internos"]
        RS3 --> RV["revisar: confere a resposta contra os dados e corrige; passa de novo pelo filtro"]:::llm
    end

    RV --> OUT([Resposta + dados da decisão: valor, artigos, protocolo, pendências])

    classDef llm fill:#dbeafe,stroke:#2563eb,color:#1e3a8a
```

A árvore acima está resumida. A lista completa das verificações, na ordem em que o código as faz, está em
`app/decisao.py` (lista `ARVORE`), com um comentário em cada verificação.
