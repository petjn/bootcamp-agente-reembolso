"""Apuração do valor a reembolsar (Título IV do Regulamento). Código puro, sem modelo.

A ordem das etapas é norma e está no código; os valores (tetos, URS,
percentuais, limites) vêm todos de app.parametros, na redação vigente na data
do atendimento. Cada etapa registra o dispositivo que a fundamenta.

    teto_R$     = teto_URS × valor da URS do exercício        art. 33
    apurado     = min(valor pago, teto_R$)                     art. 43
    líquido     = apurado × (1 − coparticipação)               art. 44
    reembolso   = min(líquido, saldo do limite anual)          art. 45
    arredonda uma vez, no fim, meio para cima                  art. 47
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import ROUND_HALF_UP, Decimal

from app import siglas
from app.parametros import Parametros

# Fundamento legal de cada etapa da fórmula. São citações das etapas, não valores de regra.
ART_CONVERSAO, ART_MENOR_VALOR, ART_ARREDONDAMENTO = "ART-33", "ART-43", "ART-47"


@dataclass
class Apuracao:
    valor_solicitado: Decimal
    valor_reembolso: Decimal
    parcial: bool                     # o saldo anual cortou o valor (art. 45, § 2º); o teto não torna parcial
    regras: list[str] = field(default_factory=list)
    memoria: list[str] = field(default_factory=list)   # passo a passo, para explicar ao cliente


def _rs(valor: Decimal) -> Decimal:
    """Valor em reais com duas casas, só para o texto da memória (o cálculo segue sem arredondar até o fim, art. 47):
    com três casas ("R$ 152.160"), a resposta copiava o valor assim para o cliente."""
    return valor.quantize(Decimal("0.01"), ROUND_HALF_UP)


def meses_completos(inicio: date, fim: date) -> int:
    meses = (fim.year - inicio.year) * 12 + (fim.month - inicio.month)
    return meses - (1 if fim.day < inicio.day else 0)


def _teto_urs(p: Parametros, codigo_tuss: str, dia: date, sessoes_anteriores: int):
    """Teto em URS, as citações que o fundamentam e o nome dele para a memória de cálculo."""
    linha = p.linha(codigo_tuss)
    sobreposto = p.grafo.teto_sobre_tuss(codigo_tuss, dia)
    if linha.get("categoria_tabela") == "Consulta médica" and "telessaúde" in (linha.get("descricao") or "").lower():
        # a consulta por telessaúde equipara-se à de consultório, inclusive no teto (art. 35, § 2º; art. 70; NT-02,
        # Caso 22): vale o teto do art. 35, e não o "proporcional" da linha da Tabela, que a contraria (D93)
        teto = p.valor("ART-35", "caput", "teto_urs", dia)
        return teto.valor, ["ART-35", "ART-70", codigo_tuss], "teto da consulta (art. 35; telessaúde equiparada, art. 70)"
    if sobreposto is None:
        citar = [linha["artigo_teto"]] if linha["artigo_teto"] else []
        return Decimal(linha["teto_urs"]), citar + [codigo_tuss], "teto do procedimento"

    # O teto da tabela foi substituído por artigo alterado por circular (ex.: art. 41).
    # Se uma parte desse artigo define o mínimo de sessões do acompanhamento continuado
    # e ele foi atingido, vale o teto dessa parte; senão, o do caput.
    artigo = sobreposto.dispositivo
    num = f"art. {siglas.numero_artigo(artigo)}"
    parte, nome = "caput", f"teto do procedimento ({num}, caput)"
    for _, parte_cont in [l for l in p.onde("sessoes_para_continuado") if l[0] == artigo]:
        minimo = p.valor(artigo, parte_cont, "sessoes_para_continuado", dia).valor
        # a memória diz qual parte do artigo deu o teto e por quê: sem isso, a resposta lia o teto do caput
        # no artigo e o dava a quem estava no acompanhamento continuado. No caput, só o artigo: explicar ali o
        # continuado fazia a resposta chamar de "teto do acompanhamento continuado" o teto do caput
        if sessoes_anteriores >= minimo:
            parte, nome = parte_cont, (f"teto do acompanhamento continuado ({num}, {parte_cont}: já havia "
                                       f"{sessoes_anteriores} sessões no ano antes desta, e o mínimo é {minimo})")
    teto = p.valor(artigo, parte, "teto_urs", dia)
    return teto.valor, p.grafo.fundamentos(artigo, dia, partes=[parte]) + [codigo_tuss], nome


def apurar(codigo_tuss: str, valor_pago: Decimal, dia: date, plano: str, data_adesao: date,
           reembolsado_no_ano: Decimal, sessoes_anteriores: int = 0,
           p: Parametros | None = None) -> Apuracao:
    p = p or Parametros.carregar()
    urs = p.valor_urs(dia)
    teto_urs, regras, nome_teto = _teto_urs(p, codigo_tuss, dia, sessoes_anteriores)
    regras = regras + [ART_CONVERSAO, ART_MENOR_VALOR]
    teto = teto_urs * urs
    apurado = min(valor_pago, teto)
    # a memória vai para o modelo que explica o valor ao cliente: diz com todas as letras se o
    # teto limitou ou não, para ele não atribuir ao teto uma redução que veio de outra regra
    # a fonte do teto (artigo e circular vigentes na data do atendimento) responde "por que a minha regra
    # é diferente da de outra data?"
    fontes = ", ".join(r for r in regras if not r.startswith("TUSS-") and r not in (ART_CONVERSAO, ART_MENOR_VALOR))
    memoria = [f"{nome_teto}: {teto_urs} URS × R$ {_rs(urs)} = R$ {_rs(teto)}"
               + (f" (redação vigente na data do atendimento, {dia:%d/%m/%Y}: {fontes})" if fontes else ""),
               f"o teto limitou o valor: do pago (R$ {_rs(valor_pago)}) vale só o teto (R$ {_rs(apurado)})"
               if apurado < valor_pago
               else f"o teto não limitou o valor: o pago (R$ {_rs(valor_pago)}) está abaixo do teto e vale inteiro"]

    copart = p.unico("coparticipacao", dia)
    faixas, tabela = copart.valor["faixas_meses"], copart.valor["percentuais"]
    meses = meses_completos(data_adesao, dia)
    faixa = sum(1 for limite in faixas if meses > limite)
    pct = Decimal(tabela[plano][faixa])
    liquido = apurado * (1 - pct)
    fontes_copart = p.grafo.fundamentos(copart.dispositivo, dia, partes=[copart.parte])
    regras += fontes_copart
    # o valor descontado vem antes e o que fica tem nome: "R$ 142,65 − 45% = R$ 78,46" a resposta lia como "desconto
    # de R$ 78,46" (D84, D85)
    memoria.append(f"coparticipação de {pct:.0%} (plano {plano}, {meses} meses de adesão; redação vigente na data "
                   f"do atendimento: {', '.join(fontes_copart)}): desconto de R$ {_rs(apurado - liquido)} sobre "
                   f"R$ {_rs(apurado)}; ficam R$ {_rs(liquido)} a reembolsar")

    limite = p.unico("limite_anual_urs", dia)
    saldo = max(Decimal(0), limite.valor * urs - reembolsado_no_ano)
    reembolso = min(liquido, saldo)
    regras += p.grafo.fundamentos(limite.dispositivo, dia, partes=[limite.parte])   # o saldo é sempre apurado
    if saldo < liquido:
        memoria.append(f"o limite anual de reembolso ({limite.valor} URS por beneficiário no ano civil, somados os "
                       f"reembolsos de todos os procedimentos) limitou o valor: restava só R$ {_rs(saldo)} de saldo")

    reembolso = reembolso.quantize(Decimal("0.01"), ROUND_HALF_UP)
    # o saldo que sobra responde a "quanto ainda me resta?" sem conta na resposta
    memoria.append(f"saldo do limite anual: R$ {saldo.quantize(Decimal('0.01'))} antes deste pedido; "
                   f"R$ {(saldo - reembolso).quantize(Decimal('0.01'))} depois dele")
    regras.append(ART_ARREDONDAMENTO)
    return Apuracao(valor_pago, reembolso,
                    parcial=saldo < liquido,
                    regras=list(dict.fromkeys(regras)), memoria=memoria)
