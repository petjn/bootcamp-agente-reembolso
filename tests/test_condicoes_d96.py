"""A condição de saúde que o cliente conta não volta na resposta (art. 7º, D96). Exemplos inventados."""

from langchain_core.messages import AIMessage, HumanMessage

from app.agents.estado import condicoes
from app.agents.responder import _conversa
from app.guardrails import MARCA_CONDICAO, filtrar, fora_dos_dados, mascarar_condicoes, termos_de_condicao


def test_termos_tiram_o_atendimento_e_guardam_a_primeira_palavra():
    termos = termos_de_condicao(["dor de garganta", "fisioterapia", "cirurgia", "rinite", " ", "x"])
    assert termos == ["dor de garganta", "rinite", "dor"]


def test_termo_com_o_atendimento_fica_so_com_a_condicao():
    assert termos_de_condicao(["exame para a rinite", "sessões de fisioterapia"]) == ["rinite"]


def test_procedimento_da_tabela_profissional_e_frase_longa_nao_sao_condicao():
    assert termos_de_condicao(["tomografia", "TSH", "reumatologista", "pediatra", "biópsia hepática",
                               "piora grande depois de muitos meses"]) == []


def test_condicao_que_esta_nos_dados_pode_ser_citada():
    dados = "Documento enviado: exame (Tela de polipropileno para hérnia)"
    assert fora_dos_dados(["hérnia", "rinite"], dados) == ["rinite"]


def test_mascara_sem_acento_maiuscula_e_plural():
    termos = termos_de_condicao(["enxaqueca", "lesão"])
    texto = mascarar_condicoes("Tenho Enxaquecas e uma lesao antiga.", termos)
    assert texto == f"Tenho {MARCA_CONDICAO} e uma {MARCA_CONDICAO} antiga."


def test_mascara_nao_pega_pedaco_de_palavra():
    assert mascarar_condicoes("O fornecedor emitiu a nota.", ["dor"]) == "O fornecedor emitiu a nota."


def test_filtro_tira_a_frase_com_a_condicao_e_guarda_os_paragrafos():
    texto = "Seu reembolso foi aprovado.\n\nEspero que a sua dor melhore logo. O valor cai em 5 dias."
    saida = filtrar(texto, condicoes=termos_de_condicao(["dor de garganta"]))
    assert saida.texto == "Seu reembolso foi aprovado.\n\nO valor cai em 5 dias."
    assert "condicao" in saida.ocorrencias


def test_filtro_tira_a_marca_que_o_modelo_copiou():
    texto = f"Recebi o pedido da consulta. Ela foi por causa da {MARCA_CONDICAO}."
    assert filtrar(texto).texto == "Recebi o pedido da consulta."


def test_filtro_sem_outra_frase_troca_pela_condicao_tratada():
    assert filtrar("Rinite.", condicoes=["rinite"]).texto == "a condição tratada."


def test_filtro_sem_condicao_deixa_o_texto():
    texto = "A consulta foi aprovada. O fornecedor emitiu a nota."
    assert filtrar(texto, condicoes=["dor"]).texto == texto


def test_valor_em_moeda_estrangeira_nao_sai_como_reais():
    # D99: o valor do documento no exterior vai aos dados sem "R$" e como ainda não convertido
    from app.agents.responder import _pedido

    p = {"id": "1", "tipo": "reembolso", "situacao": "atendido", "descricao": "x", "na_rodada": True,
         "resultado": {"decisao": "ESCALADO_ANALISTA", "categoria": "CONSULTA_MEDICA", "valor_solicitado": 80.0}}
    doc = {"situacao": "ativo", "rodada": 1, "molde": {"classificacao": "CONSULTA_MEDICA", "moeda_estrangeira": True}}
    texto = _pedido({"mensagens": [], "pedidos": [p], "documentos": [doc]}, p)
    assert "R$ 80.0" not in texto and "ainda não convertido" in texto


def test_condicoes_vem_do_historico_e_a_resposta_nao_as_ve():
    estado = {"mensagens": [
        HumanMessage("Fiz uma consulta por causa da enxaqueca.", additional_kwargs={"condicoes": ["enxaqueca"]}),
        AIMessage("Pode enviar o recibo da consulta."),
        HumanMessage("Segue o recibo."),
    ]}
    assert condicoes(estado) == ["enxaqueca"]
    assert _conversa(estado)[0].content == f"Fiz uma consulta por causa da {MARCA_CONDICAO}."
