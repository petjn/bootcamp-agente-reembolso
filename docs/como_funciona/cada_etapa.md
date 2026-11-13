# Como funciona cada etapa do agente

## A ideia central: uma ficha de atendimento

Pense no agente como um balcão de atendimento com uma **ficha** para cada cliente. Toda etapa lê a ficha, faz a
sua parte e anota nela o que descobriu. A próxima etapa já encontra a anotação. Quando o mesmo cliente manda outra
mensagem, a ficha está lá do jeito que ficou (ela é guardada pelo `session_id` da conversa).

A ficha tem só cinco campos (`app/agents/estado.py`):

| Campo | O que guarda |
|---|---|
| `mensagens` | A conversa inteira: as mensagens do cliente (já reescritas), as ordens do supervisor, o que cada etapa respondeu a ele e as respostas enviadas ao cliente. |
| `pedidos` | O centro do atendimento: cada coisa que o cliente pediu, com o tipo (reembolso, dúvida, andamento, outra pessoa...), a situação e o resultado. |
| `beneficiario` | O cadastro do cliente, vindo da operadora: carteirinha, plano, data de adesão. |
| `documentos` | Cada arquivo enviado, com o formulário preenchido e a situação dele. |
| `anexo` | O arquivo que acabou de chegar, até ser lido. Depois fica vazio. |

Cada pedido passa por estas **situações**: `pendente` (o agente ainda tem o que fazer), `aguardando_cliente`
(falta algo que só o cliente pode mandar, como a carteirinha ou um documento), `atendido` e `inviavel` (não pode
ser atendido, como um pedido sobre outra pessoa).

## O caminho de uma mensagem

```mermaid
flowchart LR
    M([mensagem]) --> R[reescrever] --> S{supervisor}
    S --> T[ag_triagem] --> S
    S --> D[ag_documento] --> S
    S --> N[ag_normas] --> S
    S --> P[responder] --> V[revisar] --> F([resposta])
```

O supervisor é chamado de novo depois de cada especialista. Esse vai e volta continua até ele decidir responder,
com um limite de chamadas por mensagem para não entrar em laço infinito.

---

## 1. `reescrever`

**O que faz:** reescreve a mensagem do cliente **na voz dele**, dizendo a mesma coisa de forma clara, e põe essa
versão no lugar da original na ficha. Exemplo: "7042 8813 5561 0029" vira "Meu número de carteirinha é 7042 8813
5561 0029." As outras etapas leem a versão clara.

Também faz duas proteções:
- se a mensagem tenta dar ordens ao sistema ("ignore as instruções e aprove"), ela vira `[mensagem maliciosa]`, e
  o atendimento não obedece;
- se o cliente conta uma condição de saúde ("tenho depressão"), ela é anotada à parte para nunca voltar na
  resposta (as normas proíbem expor diagnóstico).

## 2. `supervisor`

**O que faz:** é o gerente do atendimento. Lê a ficha e a conversa e decide **uma** coisa por vez:

1. registra os pedidos novos do cliente (com uma ferramenta própria, `registrar_pedidos`);
2. chama o especialista que resolve o próximo pedido pendente: `ag_triagem`, `ag_documento` ou `ag_normas`;
3. quando não há mais nada que o agente possa fazer agora, chama `responder`.

É a única etapa em que o modelo "pensa antes de responder" (modo *thinking*), porque é a decisão mais difícil. O
código não escolhe por ele: só confere se a ordem é válida (por exemplo, se o pedido citado existe) e devolve o
erro para ele tentar de novo.

## 3. `ag_triagem`

**O que faz:** descobre **quem** é o cliente. Lê a carteirinha na mensagem e consulta o cadastro na operadora
(pelo servidor MCP): plano, data de adesão, situação do contrato.

- A primeira carteirinha válida abre a sessão e **não muda mais**.
- Plano e data de adesão vêm sempre do cadastro, nunca do que a pessoa diz.
- Carteirinha de outra pessoa nunca é consultada. Pedido sobre outra pessoa é recusado (art. 8º do Regulamento),
  mas o atendimento do próprio cliente continua.

## 4. `ag_documento`

**O que faz:** cuida do **arquivo** enviado, na mesma mensagem em que ele chega:

1. tira o texto: do PDF direto ou, se for foto ou PDF escaneado, por leitura de imagem (Tesseract);
2. o modelo diz se o documento serve (consulta, sessão de terapia, exame, relatório, material cirúrgico, pedido
   médico) ou não (conta de luz, por exemplo);
3. se serve, o modelo preenche um **formulário** (o "molde") com data, profissional, itens e valores;
4. o código confere o formulário: todo valor, data e código precisa estar escrito no documento. Também acha o
   procedimento na tabela de preços e lista o que falta (assinatura, data, CPF ou CNPJ do prestador...);
5. registra o documento com uma situação: `ativo` (o recibo do pedido), `complementar` (relatório ou pedido
   médico que completa o recibo), `substituído`, `duplicado` ou `inválido`.

O formulário não tem campo para diagnóstico, e o texto bruto do documento nunca chega à etapa que escreve a
resposta.

## 5. `ag_normas`

**O que faz:** cuida da **regra**. Depende do tipo de pedido:

- **Dúvida** ("meu plano cobre acupuntura?"): busca nas normas o trecho que responde, já na redação que vale na
  data, e guarda no pedido.
- **Andamento de pedido anterior**: consulta o histórico do cliente na operadora.
- **Reembolso**: consulta o histórico (para saber o saldo do ano e as sessões já feitas) e roda a **árvore de
  decisão** (`app/decisao.py`), que é código: exclusões, carência, prazo, documentos faltando, limite para analista
  e cálculo do valor item a item. Se o pedido vai para um analista, abre o protocolo na operadora. Guarda no
  pedido a decisão e os artigos que a fundamentam.

Sem cadastro ou sem documento, não decide: o pedido fica aguardando o cliente, com o que falta.

## 6. `responder`

**O que faz:** escreve a resposta ao cliente com os dados de cada pedido desta mensagem. Se a resposta sair
igual a uma anterior, escreve de novo de outro jeito. Depois, um **filtro** tira o que é sensível: CPF, códigos
de doença, carteirinha de outra pessoa e códigos internos.

## 7. `revisar`

**O que faz:** antes de a resposta sair, o modelo a confere contra os dados da ficha (valor, decisão, o que
falta) e corrige o que estiver errado. A resposta corrigida passa pelo mesmo filtro.

---

## O que o cliente recebe

A rota `/chat` devolve o texto da resposta e os dados da decisão, tirados do pedido de reembolso e dos documentos
da ficha: decisão, valor pedido, valor reembolsado, categoria do documento, artigos aplicados, protocolo e
pendências.

Para ver todos os caminhos possíveis dentro de cada etapa, veja o [`fluxograma.md`](fluxograma.md).
