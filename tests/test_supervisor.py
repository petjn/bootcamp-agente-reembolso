"""Supervisor no padrão dos exemplos do LangGraph: o nó chama o modelo e guarda a chamada nas
mensagens; a aresta condicional `rota` lê a chamada. Sem modelo: a resposta é montada à mão."""

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from app.agents import supervisor as sup
from app.agents.grafo import saida


def _estado(msg="ok", **extra):
    return {"mensagens": [HumanMessage(msg)], "pedidos": [], "documentos": [], **extra}


def _reembolso(**extra):
    return {"id": "1.1", "tipo": "reembolso", "descricao": "reembolso", "situacao": "pendente", "rodada": 1,
            "na_rodada": True, **extra}


class _Modelo:
    """Faz o papel do modelo: devolve sempre a mesma chamada de ferramenta."""

    def __init__(self, nome, args):
        self.msg = AIMessage("", tool_calls=[{"name": nome, "args": args, "id": "1"}])
        self.vistas = []

    def bind_tools(self, ferramentas):
        return self

    def invoke(self, conversa):
        self.vistas.append(list(conversa))
        return self.msg


class _ModeloQueErra(_Modelo):
    """Primeiro manda um id que não existe; depois de ler o erro, manda o certo."""

    def __init__(self):
        super().__init__("ag_normas", {})

    def invoke(self, conversa):
        self.vistas.append(list(conversa))
        pid = "7042 8813 5561 0029" if len(self.vistas) == 1 else "1.1"
        return AIMessage("", tool_calls=[{"name": "ag_normas", "args": {"pedido_id": pid}, "id": str(len(self.vistas))}])


def _passo(monkeypatch, modelo, estado):
    """Roda o nó do supervisor e a aresta condicional, como o grafo faria."""
    monkeypatch.setattr(sup, "criar_llm", lambda **k: modelo)
    update = sup.supervisor(estado)
    return update, sup.rota({**estado, "mensagens": [*estado["mensagens"], *update["mensagens"]]})


def test_a_chamada_vai_para_as_mensagens_e_a_rota_le_a_chamada(monkeypatch):
    update, destino = _passo(monkeypatch, _Modelo("ag_normas", {"pedido_id": "1.1"}), _estado(pedidos=[_reembolso()]))
    assert destino == "ag_normas" and update["mensagens"][0].tool_calls[0]["args"] == {"pedido_id": "1.1"}


def test_o_modelo_ve_system_message_e_a_conversa_com_chamadas_e_retornos(monkeypatch):
    modelo = _Modelo("responder", {})
    estado = _estado("quero reembolso", pedidos=[_reembolso()])
    estado["mensagens"] += [AIMessage("", tool_calls=[{"name": "ag_documento", "args": {"pedido_id": "1.1"}, "id": "a"}]),
                            ToolMessage("não há arquivo novo", tool_call_id="a")]
    _passo(monkeypatch, modelo, estado)
    assert [m.type for m in modelo.vistas[0]] == ["system", "human", "ai", "tool"]


def test_o_codigo_nao_corrige_a_escolha(monkeypatch):
    # sem cadastro nem documento, a escolha é seguida: quem recusa é o subagente
    _, destino = _passo(monkeypatch, _Modelo("ag_normas", {"pedido_id": "1.1"}), _estado(pedidos=[_reembolso()]))
    assert destino == "ag_normas"


def test_responder_encerra_os_pedidos_da_mensagem(monkeypatch):
    estado = _estado(pedidos=[_reembolso(), {**_reembolso(), "id": "1.2", "tipo": "duvida_regra"}])
    update, destino = _passo(monkeypatch, _Modelo("responder", {}), estado)
    situacao = {p["id"]: p["situacao"] for p in update["pedidos"]}
    assert destino == "responder" and situacao == {"1.1": "pendente", "1.2": "atendido"}


def test_teto_de_chamadas(monkeypatch):
    estado = _estado(pedidos=[_reembolso()])
    for i in range(sup.MAX_CHAMADAS):   # cada chamada já teve o retorno do agente
        estado["mensagens"] += [AIMessage("", tool_calls=[{"name": "ag_normas", "args": {}, "id": str(i)}]),
                                ToolMessage("ok", tool_call_id=str(i))]
    _, destino = _passo(monkeypatch, _Modelo("ag_normas", {"pedido_id": "1.1"}), estado)
    assert destino == "responder"


def test_argumento_invalido_volta_como_erro_e_o_modelo_corrige(monkeypatch):
    modelo = _ModeloQueErra()
    update, destino = _passo(monkeypatch, modelo, _estado(pedidos=[_reembolso()]))
    assert destino == "ag_normas" and update["mensagens"][0].tool_calls[0]["args"]["pedido_id"] == "1.1"
    erro = modelo.vistas[1][-1]
    # o id fora dos pendentes volta com a saída: registrar o pedido antes
    assert erro.type == "tool" and "não está entre os pendentes" in erro.content and "registrar_pedidos" in erro.content


def test_pedido_concluido_nao_pode_ser_chamado_de_novo(monkeypatch):
    _, destino = _passo(monkeypatch, _Modelo("ag_normas", {"pedido_id": "1.1"}),
                        _estado(pedidos=[_reembolso(situacao="atendido")]))
    assert destino == "responder"   # 3 erros seguidos: o id não está entre os pendentes


def test_sem_ferramenta_encerra_a_mensagem(monkeypatch):
    class _Calado(_Modelo):
        def invoke(self, conversa):
            return AIMessage("nada a fazer")

    update, destino = _passo(monkeypatch, _Calado("responder", {}), _estado(pedidos=[_reembolso()]))
    assert destino == "responder" and update["mensagens"] == []


def _registrar(estado, pedidos):
    lista = [dict(p) for p in estado["pedidos"]]
    msg = sup.registrar_pedidos(lista, {"name": "registrar_pedidos", "args": {"pedidos": pedidos}, "id": "r"},
                                sum(1 for m in estado["mensagens"] if m.type == "human"))
    return {"pedidos": lista, "mensagens": [msg]}


def test_registrar_pedidos_grava_pendentes_e_inviaveis():
    out = _registrar(_estado(), [{"tipo": "duvida_regra", "descricao": "O plano paga fono?"},
                                 {"tipo": "terceiro", "descricao": "Ver o pedido da minha esposa.",
                                  "inviavel": True, "motivo_inviavel": "pedido sobre outra pessoa"}])
    assert [(p["id"], p["situacao"]) for p in out["pedidos"]] == [("1.1", "pendente"), ("1.2", "inviavel")]
    assert out["mensagens"][0].tool_call_id == "r"


def test_reembolso_registrado_de_novo_nao_duplica():
    decidido = _reembolso(situacao="atendido", na_rodada=False, resultado={"decisao": "ESCALADO_ANALISTA",
                                                                          "protocolo": "20260000001"})
    estado = _estado(pedidos=[decidido])
    estado["mensagens"].append(HumanMessage("E o meu reembolso, como fica?"))
    out = _registrar(estado, [{"tipo": "reembolso", "descricao": "Como fica o meu reembolso?"}])
    assert len(out["pedidos"]) == 1
    p = out["pedidos"][0]
    assert p["id"] == "1.1" and p["na_rodada"] and p["resultado"]["protocolo"] == "20260000001"


def test_saida_vem_do_pedido_de_reembolso():
    estado = _estado(pedidos=[_reembolso(situacao="atendido", assinatura="-|[]|False",
                                         resultado={"decisao": "APROVADO", "valor_reembolso": 144.0,
                                                    "valor_solicitado": 240.0, "categoria": "CONSULTA_MEDICA",
                                                    "regras": ["ART-44"]})])
    estado["mensagens"].append(AIMessage("aprovado"))
    r = saida(estado)
    assert (r.decisao, float(r.valor_reembolso_brl), r.resposta) == ("APROVADO", 144.0, "aprovado")
