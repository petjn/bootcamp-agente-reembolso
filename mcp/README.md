# Servidor MCP da operadora

Simula o sistema da operadora de saúde: é por ele que o agente consulta o cadastro e o histórico do cliente e abre
protocolos. MCP é um protocolo padrão para dar ferramentas a agentes de IA. Este servidor veio pronto do bootcamp e
oferece três ferramentas:

| Ferramenta | Devolve |
|---|---|
| `consultar_beneficiario(carteirinha)` | plano, data de adesão, sessões de terapia no ano, situação do contrato. O CPF sai **mascarado** |
| `consultar_historico(carteirinha)` | os pedidos de reembolso anteriores, do mais antigo ao mais recente |
| `abrir_protocolo(carteirinha, payload)` | o número do protocolo gerado |

## Como subir

Com Docker, da raiz do projeto:

```bash
docker compose up mcp          # só o servidor, na porta 9000
docker compose up              # o servidor e o agente
```

Sem Docker, de dentro desta pasta (`mcp/`), com o mesmo ambiente Python do projeto:

```bash
MCP_OPERADORA_DADOS=../casos/treino MCP_OPERADORA_TOKEN=treino python -m mcp_operadora.server
```

O endereço é `http://localhost:9000/mcp`, e o token vai no cabeçalho `Authorization: Bearer treino`. Os dois já
estão no `.env.exemplo` da raiz.

## De onde vêm os clientes

`MCP_OPERADORA_DADOS` aceita duas coisas:

- **uma pasta de casos**, como `casos/treino/`: cada `*/persona.json` vira um cliente;
- **um arquivo JSON** com uma lista de clientes.

O agente não depende de nenhum cliente em particular: com outro cadastro, outras pessoas e outros planos, ele tem
de funcionar igual.

## O histórico

Quando o cadastro não traz o histórico explícito, o servidor cria pedidos anteriores coerentes com ele: um cliente
com 4 sessões no ano tem 3 pedidos anteriores, e os valores somam o total do ano. É desse histórico que o agente
tira o saldo do limite anual.

## Variáveis

| | Padrão |
|---|---|
| `MCP_OPERADORA_DADOS` | `../casos/treino` (no Docker, `/dados`) |
| `MCP_OPERADORA_TOKEN` | vazio: sem token, não exige autenticação |
| `MCP_OPERADORA_HOST` · `PORT` | `127.0.0.1` · `9000` |
| `MCP_OPERADORA_ESQUEMA` | `v1` |
