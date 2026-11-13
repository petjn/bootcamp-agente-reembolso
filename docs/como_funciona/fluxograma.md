# Fluxograma do agente: todos os caminhos

O grafo do LangGraph (`grafo.md`) mostra só os nós e as ligações. Este
fluxograma abre cada nó e mostra os caminhos possíveis dentro dele. Em azul, o que o modelo
decide; em cinza, o que é código.

```mermaid
flowchart TD
    IN([Mensagem do cliente + anexo opcional]) --> RE

    subgraph REESCRITA[reescrever]
        RE["Modelo: reescreve na 1ª pessoa e lista os pedidos com o tipo"]:::llm --> RE2{"Pergunta sem pedido?"}
        RE2 -- sim --> RE3["vira pedido de dúvida"]
        RE2 -- não --> RE4
        RE3 --> RE4["Junta com os pedidos abertos: aguardando cliente volta a pendente"]
    end

    RE4 --> SP0

    subgraph SUPERVISOR[supervisor]
        SP0["Registro: anexo ou documento ativo abre o pedido de reembolso; reembolso decidido com dados novos volta a pendente"] --> SP1{"Mais de 10 passadas?"}
        SP1 -- não --> SP2["Modelo com thinking lê a ficha, os pedidos e os retornos e chama UMA ferramenta"]:::llm
    end

    SP1 -- sim --> RS0
    SP2 -- "ag_documento" --> DOC0
    SP2 -- "ag_triagem" --> TR0
    SP2 -- "ag_normas" --> NO0
    SP2 -- "responder / nenhuma ferramenta" --> ENC["Pedidos listados como aguardando cliente ficam aguardando; reembolso sem decisão segue pendente; o resto, atendido"]
    ENC --> RS0

    subgraph DOCUMENTO[ag_documento]
        DOC0{"Há arquivo novo?"} -- não --> DOCX["retorno: não há arquivo"]
        DOC0 -- sim --> DOC1{"PDF com texto?"}
        DOC1 -- sim --> DOC2["PyMuPDF"]
        DOC1 -- "não, ou imagem" --> DOC3["OCR Tesseract"]
        DOC2 --> DOC4["Modelo preenche o molde: tipo, categoria, datas, itens, valores; sem CPF e sem CID"]:::llm
        DOC3 --> DOC4
        DOC4 --> DOC5["Código confere o molde com o texto, acha a linha da Tabela URS e lista os campos que faltam"]
        DOC5 --> DOC6{"Situação"}
        DOC6 --> D1["duplicado"]
        DOC6 --> D2["complementar: relatório ou pedido médico"]
        DOC6 --> D3["inválido: não é documento fiscal"]
        DOC6 --> D4["terceiro: em nome de outra pessoa"]
        DOC6 --> D5["ativo: substitui o anterior do mesmo profissional e data"]
    end

    DOCX --> SP0
    D1 & D2 & D3 & D4 & D5 --> DOCR["retorno: o que foi lido e a situação"] --> SP0

    subgraph TRIAGEM[ag_triagem]
        TR0{"Carteirinha nova e sessão sem carteirinha?"} -- sim --> TR1["MCP: cadastro e histórico"]
        TR1 --> TR1a["ok: abre a sessão"]
        TR1 --> TR1b["não localizada: aviso para conferir"]
        TR1 --> TR1c["MCP fora: aviso para tentar de novo"]
        TR0 -- "não" --> TR2{"Sessão sem cadastro?"}
        TR2 -- sim --> TR1
        TR2 -- não --> TR3
        TR1a & TR1b & TR1c --> TR3{"Outra carteirinha ou pedido sobre outra pessoa?"}
        TR3 -- sim --> TR4["Fora do escopo, art. 8º: nada dela é consultado; aviso para a resposta"]
        TR3 -- não --> TR5["nada mais a fazer"]
    end

    TR4 & TR5 --> TRR["retorno: o que a triagem fez"] --> SP0

    subgraph NORMAS[ag_normas]
        NO0{"Pedido existe?"} -- não --> NOX["retorno: pedido não encontrado"]
        NO0 -- sim --> NO1{"Tipo do pedido"}
        NO1 -- "dúvida ou andamento" --> NO2["RAG: busca híbrida, reranker, vigência na data, artigos mencionados"] --> NO3["norma guardada no pedido; atendido"]
        NO1 -- reembolso --> NO4{"Tem cadastro e documento ativo?"}
        NO4 -- não --> NO5["retorno: falta cadastro ou documento"]
        NO4 -- sim --> N1{"Data do atendimento no documento?"}
        N1 -- não --> P0["PENDENTE_DOCUMENTO"]
        N1 -- sim --> N2["Anexo IV: RAG + modelo julga se o procedimento está excluído"]:::llm
        N2 -- "excluído" --> X1["DESPESA_NAO_COBERTA; sobrescreve a categoria"]
        N2 -- "grupo 3 sem indicação clínica" --> P1["PENDENTE_DOCUMENTO"]
        N2 -- "coberto" --> N3{"OPME ou valor acima da alçada, art. 78?"}
        N3 -- sim --> E1["ESCALADO_ANALISTA; abre protocolo no MCP"]
        N3 -- não --> N4{"Contrato ativo, carência cumprida, dentro do prazo?"}
        N4 -- não --> G1["NEGADO"]
        N4 -- sim --> N5{"Falta campo ou relatório da sessão?"}
        N5 -- sim --> P2["PENDENTE_DOCUMENTO com o que enviar"]
        N5 -- não --> N6["Cálculo item a item: teto, coparticipação, saldo anual"]
        N6 --> A1["APROVADO"]
        N6 --> A2["APROVADO_PARCIAL"]
        N6 --> G2["NEGADO: saldo esgotado"]
    end

    NOX & NO3 & NO5 --> NOR["retorno ao supervisor"] --> SP0
    P0 & X1 & P1 & E1 & G1 & P2 & A1 & A2 & G2 --> NO7["RAG da norma do procedimento na data do atendimento"] --> NOR

    subgraph RESPONDER[responder]
        RS0["Monta as partes: documento recebido, terceiro, reembolso se pertinente, cada pedido, avisos; ou só uma confirmação"] --> RS1["Modelo escreve cada parte só com os dados dela"]:::llm
        RS1 --> RS2{"Igual a uma resposta anterior?"}
        RS2 -- sim --> RS1b["reescreve"]:::llm --> RS3
        RS2 -- não --> RS3["Filtro: siglas viram nomes; sai código interno, CPF, CID e carteirinha"]
    end

    RS3 --> RV["revisar: o modelo confere a resposta contra os dados e corrige; passa de novo pelo filtro"]:::llm
    RV --> OUT([Resposta + campos estruturados: decisão, valor, regras, protocolo, pendências])

    classDef llm fill:#dbeafe,stroke:#2563eb,color:#1e3a8a
```
