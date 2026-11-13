# Casos: as conversas usadas para avaliar o agente

Cada caso é **uma conversa inteira** entre um cliente (fictício) e o agente, com o resultado que as normas
mandam dar no fim. É assim que o agente é medido: a conversa roda, e confere-se turno a turno se ele atendeu o
que o cliente pediu e, no fim, se a decisão está certa.

## As três pastas

| Pasta | Casos | Para que serve |
|---|---|---|
| `treino/` | 01 a 17 | As primeiras conversas. Os erros do agente nelas guiaram as correções. Os casos 01 a 03 vieram do bootcamp; os outros foram escritos para o projeto. |
| `ramos/` | 18 a 41 e 50 | Um caso para cada caminho da árvore de decisão (aprovado, negado por carência, pendente por falta de documento...), para que nenhuma regra fique sem conversa que passe por ela. Também usados para corrigir o agente. |
| `teste/` | 42 a 79 | Conversas que o agente **nunca viu** enquanto era ajustado. Rodam com o código congelado e medem se o que foi corrigido vale para conversas novas. Nada foi mudado no agente por causa de um erro que só apareceu aqui. |

Os números dos casos seguem a ordem em que foram escritos, por isso `ramos/` e `teste/` se intercalam.

## O que tem em cada caso

```
treino/01_fora_de_ordem/
  persona.json                       quem é o cliente: o cadastro e o histórico que o servidor MCP devolve
  turnos.jsonl                       as mensagens do cliente, uma por turno
  esperado.json                      o gabarito: decisão, valor, artigos que fundamentam e a conta
  recibo_consulta_dermatologia.pdf   o documento que o cliente envia na conversa
```

No `turnos.jsonl`, o turno que envia um documento traz o nome do arquivo em `anexo.path`.

Todos os dados são fictícios. A data das conversas é 20/05/2026.

## Como o caso é julgado

O cliente é simulado por um modelo de linguagem que segue o roteiro do `turnos.jsonl`, mas escreve com as
próprias palavras e reage ao que o agente respondeu. Outro modelo faz o papel de juiz:

- **Cada turno:** o agente respondeu o que o cliente perguntou?
- **No fim:** a decisão (aprovado, aprovado parcial, negado, pendente, para analista...) e o valor batem com o
  `esperado.json`?
- **Sempre:** nenhuma resposta pode mostrar CPF, código de doença (CID) ou dado de outra pessoa.

Para rodar: `python rodar_treino.py` (veja o README da raiz). O código do juiz está em `avaliacao/`.
