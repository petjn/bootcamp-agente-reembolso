"""Normas — recuperação, vigência, verificações e decisão (M5).

Recebe do supervisor uma chamada (o pedido vem nos argumentos) e devolve o pedido resolvido
e uma ToolMessage com o resultado:

  * dúvida de regra: busca a norma com o texto do pedido, guarda no resultado dele e o
    marca como atendido;
  * situação de pedido anterior: com o cliente identificado, consulta o histórico no MCP e
    guarda os pedidos anteriores junto da norma; sem ele, o pedido aguarda a carteirinha;
  * reembolso: consulta o histórico no MCP (na hora, para sair fresco da fonte), roda
    `app/decisao.decidir` sobre o documento ativo e o cadastro; se a decisão for escalar,
    abre o protocolo pelo MCP; guarda no pedido a decisão e a norma do procedimento (na
    data do atendimento), para a resposta explicar. Sem cadastro ou sem documento, não
    decide: o pedido aguarda o cliente, com o que falta.

Cada dúvida é um pedido próprio: duas dúvidas na mesma mensagem são duas buscas.
"""

from __future__ import annotations

import re
from dataclasses import asdict
from datetime import date

from langchain_core.messages import ToolMessage

from app.agents.documento import OUTRA_PESSOA, de_outra_pessoa, de_terceiro
from app.agents.estado import Estado, assinatura, carteirinha, chamada, complementares, documento_ativo, pedido, rodada
from app.datas import hoje
from app.decisao import decidir, procedimento_na_tabela
from app.rag import buscar, para_prompt
from app.tools import ErroMCP, abrir_protocolo, consultar_historico


TERMOS = """Você reescreve a dúvida de um cliente de plano de saúde nos termos do Regulamento de reembolso, para
buscar a regra que a responde. Devolva só a consulta: uma linha curta, de até 12 palavras, com o assunto
central da dúvida. Não responda à dúvida e não acrescente assuntos que ela não toca. Deixe de fora o
procedimento, o profissional e os valores do cliente, a não ser que a dúvida seja sobre eles (ex.: se o plano
cobre um procedimento).

Mantenha os termos técnicos que a dúvida já usa (ex.: indicação clínica, relatório clínico, teto). Prefira as
palavras do Regulamento quando couberem, por exemplo: requisitos do pedido de reembolso, documento
fiscal, prazo para protocolar, data do atendimento, carência, cobertura, teto do procedimento, coparticipação,
limite anual de reembolso, relatório clínico, indicação clínica do profissional assistente, procedimento de
fronteira, acompanhamento continuado, pendência documental, pedido de reanálise, alçada, prazo de análise,
prazo de pagamento, atendimento vinculado à carteirinha.

A dúvida pode vir depois da última resposta do atendimento. Use essa resposta só para entender a que se
referem "isso", "essa mudança", "esse limite", "vale para aquele?": a consulta diz o assunto por extenso. Se a
dúvida questiona uma decisão que essa resposta explicou ("por que foi negado?", "por que veio menos?"), a consulta
é sobre o motivo que ela deu (carência, teto, coparticipação, limite anual, pendência).

Exemplos (inventados):
"posso mandar foto do recibo?" -> documento fiscal fotografado ou digitalizado e legibilidade
"o plano paga nutricionista?" -> cobertura e teto de consulta com nutricionista
"posso recorrer se negarem?" -> pedido de reanálise da decisão de indeferimento e seu prazo
"por que recebi menos do que paguei?" -> teto do procedimento e coparticipação na apuração do valor
"e se eu tivesse ido a um médico da rede?" -> atendimento na rede credenciada e reembolso na livre escolha
"posso resolver o da minha mãe por aqui?" -> pedido referente a beneficiário diverso e atendimento vinculado à carteirinha"""


def nos_termos_do_regulamento(duvida: str, anterior: str = "") -> str:
    """A consulta da busca: a dúvida do cliente dita com as palavras do Regulamento. A última resposta do
    atendimento entra só para resolver as referências da dúvida ("essa mudança")."""
    from langchain_core.messages import HumanMessage, SystemMessage

    from app.llm import criar_llm

    entrada = (f"<ultima_resposta_do_atendimento>\n{anterior}\n</ultima_resposta_do_atendimento>\n\n" if anterior else "") \
        + f"<duvida>\n{duvida}\n</duvida>"
    consulta = criar_llm().invoke([SystemMessage(TERMOS), HumanMessage(entrada)]).content.strip().strip('"')
    return consulta or duvida


def _busca_da_duvida(duvida: str, anterior: str = "") -> tuple[str, list[str]]:
    """Duas buscas, juntas: com as palavras do cliente e com as do Regulamento. Cada uma acha o que a
    outra perde (scripts/eval_busca.py); os blocos repetidos entram uma vez só. Devolve também os artigos que
    a busca achou e os que as circulares fora de vigência achadas alteravam (para o quadro de mudanças)."""
    from app.rag import _alvos, carregar

    blocos: dict[str, str] = {}
    artigos: list[str] = []
    for consulta in dict.fromkeys((duvida, nos_termos_do_regulamento(duvida, anterior))):
        r = buscar(consulta)
        for bloco in para_prompt(r).split("\n### ")[1:]:
            blocos.setdefault(bloco.split("\n", 1)[0], "### " + bloco)
        artigos += [a.dispositivo for a in r.artigos if a.origem == "busca"]
        for nid in r.descartados:   # circular revogada ou ainda por vir: o artigo que ela alterava
            artigos += _alvos(carregar().nos[nid].metadata)
    return "\n\n".join(blocos.values()), list(dict.fromkeys(artigos))


def _quadro_de_mudancas(artigos: list[str], dia_cliente: date | None = None) -> str:
    """Para cada parte desses artigos cuja redação mudou por circular, as redações em ordem, com o período de
    cada uma. Responde "o que mudou?" e "por que o valor é diferente do de outra data" num quadro curto, no
    topo da norma; antes eram blocos longos no fim, que o modelo não usava (D46)."""
    from datetime import timedelta

    from app.rag import carregar
    from app.textos import legivel

    ind = carregar()
    datas = sorted({date.fromisoformat(c["inicio_vigencia"]) for c in ind.grafo.circulares.values()})
    linhas = []
    for art in artigos:
        partes = list(dict.fromkeys(
            [n.metadata["parte"] for n in ind.nos.values()
             if n.metadata["tipo_documento"] == "regulamento" and n.metadata["dispositivo"] == art]
            + list(ind.grafo.partes_alteradas(art))))
        for parte in partes:
            trechos = []   # (início, fonte, texto), juntando os períodos seguidos de mesma fonte
            for dia in [datas[0] - timedelta(days=1), *datas]:
                red = ind.grafo.redacao(art, parte, dia)
                texto = (next((n.text for n in ind.nos.values() if n.metadata["tipo_documento"] == "regulamento"
                               and n.metadata["dispositivo"] == art and n.metadata["parte"] == parte), "")
                         if red.fonte == art else legivel(red.texto or "")) or "(sem esta parte)"
                if trechos and (trechos[-1][1] == red.fonte or trechos[-1][2] == texto):
                    continue   # mesma redação (circular que repetiu o texto não é mudança)
                trechos.append((dia, red.fonte, texto))
            if len(trechos) < 2:
                continue
            linhas.append(f"{art}, {parte}:")
            for i, (inicio, fonte, texto) in enumerate(trechos):
                fim = trechos[i + 1][0] - timedelta(days=1) if i + 1 < len(trechos) else None
                periodo = (f"até {fim:%d/%m/%Y}" if i == 0 else f"de {inicio:%d/%m/%Y}"
                           + (f" a {fim:%d/%m/%Y}" if fim else " em diante"))
                # a redação vigente no dia do atendimento do cliente fica marcada: a comparação com outra data parte
                # dela. "Vigente", não "a que valeu": a marca vai em toda parte, e nem toda parte se aplicou a ele
                # (o caput e o teto do acompanhamento continuado do mesmo artigo ficam marcados juntos)
                vale = dia_cliente and (i == 0 or inicio <= dia_cliente) and (fim is None or dia_cliente <= fim)
                marca = f" [redação vigente na data do atendimento do cliente, {dia_cliente:%d/%m/%Y}]" if vale else ""
                linhas.append(f"- {periodo} (fonte {fonte}){marca}: {texto}")
    if not linhas:
        return ""
    return ("### Mudanças de redação das regras acima\nUse só quando a dúvida é sobre o que mudou ou sobre um valor "
            "diferente do de outra data; o atendimento do cliente segue a redação vigente na data dele.\n"
            + "\n".join(linhas))


def _decidido(estado: Estado) -> dict | None:
    return next((p for p in estado.get("pedidos", []) if p["tipo"] == "reembolso" and (p.get("resultado") or {}).get("decisao")), None)


def _fundamentos_da_decisao(estado: Estado, ja: str) -> str:
    """Os artigos do Regulamento em que se apoiou o reembolso já decidido nesta conversa, inteiros e na redação da
    data do atendimento. A dúvida sobre a decisão muitas vezes não diz o assunto (só "isso", "esse limite"), e a
    busca não acha o artigo; a decisão sabe qual é (D46)."""
    import re

    from app.rag import carregar, consolidar

    r = _decidido(estado)
    if not r:
        return ""
    doc = documento_ativo(estado)
    data = (doc or {}).get("molde", {}).get("c4_data_atendimento")
    dia = date.fromisoformat(data) if data else hoje()
    ind = carregar()
    blocos = []
    for art in r["resultado"].get("regras") or []:
        if not art.startswith("ART-") or re.search(rf"^Citar: (?:.*, )?{art}(?:,|$)", ja, re.M):
            continue
        a, _ = consolidar(art, dia, ind, set())
        partes = "\n".join(f"{x.texto} [{x.fonte}]" for x in a.partes)
        blocos.append(f"### {a.cabecalho} (fundamento da decisão do reembolso)\nCitar: {', '.join(a.fundamentos)}\n{partes}")
    return "\n\n".join(blocos)


ANDAMENTO = ("ART-81", "ART-15")   # prazo da análise e prazo do pagamento


def _andamento(ja: str) -> str:
    """Os artigos do andamento de um pedido (prazo da análise e do pagamento), inteiros e vigentes hoje, que a busca
    ainda não trouxe. A pergunta sobre a situação de um pedido ("já saiu?", "cai quando?") é respondida por eles e
    pelo histórico; a busca pelas palavras do cliente às vezes não os achava (D87)."""
    from app.rag import carregar, consolidar

    ind, blocos = carregar(), []
    for art in ANDAMENTO:
        if re.search(rf"^Citar: (?:.*, )?{art}(?:,|$)", ja, re.M):
            continue
        a, _ = consolidar(art, hoje(), ind, set())
        partes = "\n".join(f"{x.texto} [{x.fonte}]" for x in a.partes)
        blocos.append(f"### {a.cabecalho}\nCitar: {', '.join(a.fundamentos)}\n{partes}")
    return "\n\n".join(blocos)


def norma_da_duvida_no_atendimento(estado: Estado, duvida: str) -> str:
    """A norma de uma dúvida: a busca (com a última resposta para entender referências) e, havendo reembolso
    decidido, os artigos em que a decisão se apoiou."""
    anterior = next((m.content for m in reversed(estado.get("mensagens", [])) if m.type == "ai" and not m.tool_calls), "")
    norma, artigos = _busca_da_duvida(duvida, anterior)
    extra = _fundamentos_da_decisao(estado, norma)
    decisao = [a for a in ((_decidido(estado) or {}).get("resultado") or {}).get("regras") or [] if a.startswith("ART-")]
    data = ((documento_ativo(estado) or {}).get("molde") or {}).get("c4_data_atendimento")
    quadro = _quadro_de_mudancas(list(dict.fromkeys(artigos + decisao)), date.fromisoformat(data) if data else None)
    return "\n\n".join(x for x in (quadro, norma, extra) if x)


def _consultar(pergunta: str, dia: date | None = None) -> dict:
    r = buscar(pergunta, dia)
    return {"pergunta": pergunta, "contexto": para_prompt(r),
            "citaveis": sorted({f for a in r.artigos for f in a.fundamentos} | {t.citacao for t in r.trechos if t.citacao})}


def _linhas_da_pendencia(codigos: list[str]) -> str:
    """As linhas do Anexo B da NT-02 dos códigos de pendência que a decisão registrou, e a regra 5.3 (nenhum código
    autoriza indeferimento imediato), como texto de norma. O Anexo IV diz "ausente a indicação, o pedido é
    indeferido"; a NT diz que antes vem a pendência. Sem a linha da NT nos dados, a resposta dizia "indeferido"
    num pedido pendente (D60)."""
    from app.rag import carregar

    if not codigos:
        return ""
    blocos = [f"### {n.metadata['cabecalho']}\nCitar: NT-02\n{n.text}" for n in carregar().nos.values()
              if n.metadata.get("citacao") == "NT-02" and n.metadata.get("parte") in [*codigos, "5.3"]]
    return "\n\n".join(blocos)


def _norma_das_regras(regras: list[str], motivo: str | None, dia: date) -> str:
    """As regras que a decisão aplicou, sem busca: cada artigo inteiro e consolidado na data, a linha da Tabela com
    a classificação da categoria dela na NT-02 e, do Anexo IV, o item que o motivo cita com as regras de aplicação
    do grupo dele. Vazio se nenhuma regra é achada."""
    from app.rag import Resultado, _trecho, carregar, consolidar, para_prompt

    ind = carregar()
    existentes = {n.metadata["dispositivo"] for n in ind.nos.values() if n.metadata["tipo_documento"] == "regulamento"}
    artigos = [consolidar(r, dia, ind, set())[0] for r in regras if r in existentes]
    tabela = [n for n in ind.nos.values() if n.metadata["tipo_documento"] == "tabela" and n.metadata["citacao"] in regras]
    categorias = {{"Material / OPME": "Material, órtese, prótese ou material especial"}.get(c, c)
                  for n in tabela if (c := n.metadata.get("categoria_tabela"))}
    itens = re.findall(r"item (\d+(?:\.\d+)*)", motivo or "") if "ANEXO-IV" in regras else []
    anexo = [n for n in ind.nos.values() if n.metadata["tipo_documento"] == "anexo" and n.metadata["parte"] in itens]
    grupos = {n.metadata.get("grupo") for n in anexo}
    extras = [n for n in ind.nos.values()
              if (n.metadata["tipo_documento"] == "anexo_regra" and grupos
                  and (n.metadata["aplica_a"] == "todos" or n.metadata["aplica_a"] in grupos))
              or (n.metadata["tipo_documento"] == "nota_tecnica" and n.metadata["parte"].startswith("3.1 ")
                  and n.text.split(" — ", 1)[-1].split(".")[0] in categorias)]
    if not (artigos or tabela or anexo):
        return ""
    return para_prompt(Resultado(pergunta="", data_referencia=dia, artigos=artigos,
                                 trechos=[_trecho(n) for n in tabela + anexo], regras_anexo=[_trecho(n) for n in extras]))


def norma_do_reembolso(molde: dict, decisao: str, categoria: str | None, motivo: str | None,
                       falta_cliente: list[str], dia: date | None, pendencias: list[str] | None = None,
                       regras: list[str] | None = None) -> str:
    """A norma que acompanha o reembolso decidido. Não aprovado: as regras que a decisão aplicou (D63); antes,
    a busca pelo motivo (D58) trazia junto regras de outro assunto (o limite de sessões de terapia ao lado do
    limite anual, e a resposta dizia que o limite anual era dos exames). Sem regras achadas, segue a busca pelo
    motivo ou pelo que falta ao cliente. No aprovado, a resposta usa a memória de cálculo, e a busca segue pela
    categoria."""
    assunto = "" if decisao.startswith("APROVADO") else (motivo or "; ".join(falta_cliente))
    norma = _norma_das_regras(regras or [], motivo, dia or hoje()) if not decisao.startswith("APROVADO") else ""
    if not norma:
        consulta = f"{procedimento_na_tabela(molde)} {assunto or (categoria or '') + ' reembolso'}".strip()
        norma = _consultar(consulta, dia)["contexto"]
    pendencia = _linhas_da_pendencia(pendencias or []) if decisao == "PENDENTE_DOCUMENTO" else ""
    return f"{pendencia}\n\n{norma}" if pendencia else norma


def _historico(numero: str) -> list[dict]:
    return [{"data": p.data.isoformat() if p.data else None, "categoria": p.categoria,
             "valor_reembolsado": str(p.valor_reembolsado)} for p in consultar_historico(numero).pedidos]


def pedidos_anteriores(numero: str) -> list[dict]:
    """Os pedidos do histórico da operadora, com protocolo e decisão, para responder à situação de um deles."""
    return [{"protocolo": p.protocolo, "data_atendimento": p.data.isoformat() if p.data else None,
             "categoria": p.categoria, "decisao": p.decisao, "valor_reembolsado": str(p.valor_reembolsado)}
            for p in consultar_historico(numero).pedidos]


def ag_normas(estado: Estado) -> dict:
    """Atende a chamada do supervisor (o pedido vem nos argumentos dela) e devolve o
    resultado numa ToolMessage."""
    cid, args = chamada(estado)
    pedidos = [dict(p) for p in estado.get("pedidos", [])]
    p = pedido(pedidos, args.get("pedido_id"))
    update: dict = {"pedidos": pedidos}

    def devolve(texto: str) -> dict:
        return {**update, "mensagens": [ToolMessage(texto, tool_call_id=cid, name="ag_normas")]}

    if p is None:
        return devolve(f"não há pedido com o id {args.get('pedido_id')!r}")
    p["na_rodada"] = True
    if p["tipo"] == "status_pedido":
        # a situação de um pedido anterior está no histórico da operadora, não na norma: sem o histórico, a resposta
        # pedia o documento de um pedido já decidido (D87). A norma segue junto (prazo de pagamento, reanálise)
        if not estado.get("beneficiario"):
            p.update(situacao="aguardando_cliente", motivo="informar o número da carteirinha")
            return devolve("o histórico só pode ser consultado com o cliente identificado; ele precisa informar a carteirinha")
        try:
            anteriores = pedidos_anteriores(carteirinha(estado))
        except ErroMCP:
            p.update(situacao="aguardando_cliente", motivo="tentar de novo em instantes: o sistema da operadora não respondeu")
            return devolve("o histórico da operadora não respondeu; não dá para consultar agora")
        norma = norma_da_duvida_no_atendimento(estado, p["descricao"])
        p.update(situacao="atendido", resultado={"historico": anteriores,
                                                 "norma": "\n\n".join(x for x in (norma, _andamento(norma)) if x)})
        return devolve(f"histórico consultado ({len(anteriores)} pedidos anteriores) e norma encontrada; o pedido pode "
                       "ser respondido")
    if p["tipo"] != "reembolso":
        p.update(situacao="atendido", resultado={"norma": norma_da_duvida_no_atendimento(estado, p["descricao"])})
        return devolve("norma vigente encontrada; o pedido pode ser respondido")

    decidido = (p.get("resultado") or {}).get("decisao")
    if decidido and p.get("assinatura") == assinatura(estado):
        # nada mudou desde a decisão (mesmo documento, mesmos complementares, mesmo cadastro): não decide de
        # novo. A pergunta que o cliente faz sobre o pedido é um pedido próprio, com a norma que a responde.
        p["situacao"] = "aguardando_cliente" if decidido == "PENDENTE_DOCUMENTO" else "atendido"
        return devolve(f"o pedido {p['id']} já foi decidido ({decidido}) com estes mesmos documentos e nada mudou; "
                       "se a mensagem traz uma pergunta, registre-a com registrar_pedidos e chame o ag_normas para ela")

    doc = documento_ativo(estado)
    nome = (estado.get("beneficiario") or {}).get("nome")
    if doc and de_outra_pessoa(doc["molde"], nome):
        # o documento chegou antes da identificação: a comparação com o cadastro é feita agora
        documentos = [dict(x) for x in estado.get("documentos", [])]
        for x in documentos:
            if x["id"] == doc["id"]:
                x.update(situacao="de_outra_pessoa", molde=de_terceiro(x["id"], x["molde"]["classificacao"]))
        update["documentos"] = documentos
        p.update(situacao="aguardando_cliente", motivo=OUTRA_PESSOA)
        return devolve(f"{doc['id']}: {OUTRA_PESSOA}")
    falta = [o for o, tem in (("informar o número da carteirinha", estado.get("beneficiario")),
                              ("enviar o recibo ou a nota fiscal do atendimento", doc)) if not tem]
    if falta:   # o subagente não decide sem dados: devolve o pedido dizendo o que falta
        p.update(situacao="aguardando_cliente", motivo=" e ".join(falta))
        return devolve(f"não dá para decidir ainda; o cliente precisa {' e '.join(falta)}")
    try:
        historico = _historico(carteirinha(estado))
    except ErroMCP:
        p.update(situacao="aguardando_cliente", motivo="tentar de novo em instantes: o sistema da operadora não respondeu")
        return devolve("o histórico da operadora não respondeu; não dá para decidir agora")

    molde = doc["molde"]
    d = decidir(molde, complementares(estado), estado["beneficiario"], historico, hoje())
    protocolo, aviso = (p.get("resultado") or {}).get("protocolo"), ""
    if (d.escalar or d.decisao == "PENDENTE_DOCUMENTO") and not protocolo:   # o protocolo fica aberto (arts. 18 e 78)
        try:
            protocolo = abrir_protocolo(carteirinha(estado), {
                "categoria": d.categoria, "valor_solicitado_brl": d.valor_solicitado, "motivo": d.motivo,
                "documento": doc["arquivo"], "data_atendimento": molde.get("c4_data_atendimento")})
        except ErroMCP:
            aviso = "não foi possível abrir o protocolo agora: diga que vai tentar de novo"
    dia = date.fromisoformat(molde["c4_data_atendimento"]) if molde.get("c4_data_atendimento") else None
    norma = norma_do_reembolso(molde, d.decisao, d.categoria, d.motivo, d.falta_cliente, dia, d.pendencias, d.regras)
    if d.categoria == "DESPESA_NAO_COBERTA":   # sobrescreve a classificação, guardando a original
        documentos = [dict(x) for x in estado.get("documentos", [])]
        for x in documentos:
            if x["id"] == doc["id"]:
                x["molde"] = {**x["molde"], "classificacao": "DESPESA_NAO_COBERTA"}
        update["documentos"] = documentos
    pendente = d.decisao == "PENDENTE_DOCUMENTO"
    p.update(resultado={**asdict(d), "protocolo": protocolo, "norma": norma, "aviso": aviso},
             assinatura=assinatura(estado), rodada_resultado=rodada(estado),
             situacao="aguardando_cliente" if pendente else "atendido",
             motivo="; ".join(d.falta_cliente) or d.motivo)
    return devolve(f"decidido {d.decisao}"
                   + (f", R$ {d.valor_reembolso:.2f}" if d.valor_reembolso is not None and not pendente else "")
                   + (f"; o cliente precisa enviar: {'; '.join(d.falta_cliente)}" if d.falta_cliente else ""))