"""O que cada circular faz, declarado a partir da nossa leitura (D8).

Expressão regular quebra se a frase vier escrita de outro jeito ("Fica
revogada..." / "Revoga-se..."). Por isso a *estrutura* de cada circular — que
artigo dela faz o quê, sobre quem e desde quando — é declarada aqui, como o
bootcamp orientava: ler e entender a norma. O que continua vindo do PDF é o
*texto*: a redação nova de cada parte e os números dentro dela (D7).

O build confere a declaração contra o PDF e para se algo não bater:
  * a vigência declarada tem de ser a do cabeçalho "Início de vigência";
  * o artigo da circular declarado tem de existir e mencionar o alvo.

Cada relação: (tipo, alvo, parte). Tipos:
  altera          dá nova redação à parte do artigo, a partir da vigência
  revoga          revoga outra circular por inteiro (art. 5º, § 1º: volta a redação anterior)
  revoga_parte    revoga uma parte de artigo sem dar nova redação
  sobrepoe_tuss   o teto fixado na circular prevalece sobre a linha da Tabela URS
  eficacia_futura alteração já aprovada, com eficácia a partir de `inicio`
"""

from __future__ import annotations

import re

DECLARACOES: dict[str, dict] = {
    "CIRC-04-2025": {
        "arquivo": "circular_04_2025.pdf",
        "vigencia": "2025-07-01",
        "artigos": {
            1: [("altera", "ART-12", "caput")],
        },
    },
    "CIRC-09-2025": {
        "arquivo": "circular_09_2025.pdf",
        "vigencia": "2025-11-01",
        "artigos": {
            1: [("revoga", "CIRC-04-2025", None)],
        },
    },
    "CIRC-11-2026": {
        "arquivo": "circular_11_2026.pdf",
        "vigencia": "2026-02-01",
        "artigos": {
            1: [("altera", "ART-41", "caput"), ("altera", "ART-41", "§ 1º"), ("altera", "ART-41", "§ 2º")],
            2: [("revoga_parte", "ART-41", "parágrafo único")],
            3: [("sobrepoe_tuss", "TUSS-50000462", None)],
            14: [("altera", "ART-73", "§ 3º")],
            19: [("eficacia_futura", "ART-41", "caput", {"inicio": "2027-01-01"})],
        },
    },
    "CIRC-02-2026": {
        "arquivo": "circular_02_2026.pdf",
        "vigencia": "2026-04-20",
        "artigos": {
            1: [("altera", "ART-41", "caput")],
            2: [("altera", "ART-41", "§ 2º")],
            3: [("altera", "ART-44", "§ 2º")],
            14: [("altera", "ART-73", "§ 3º")],
        },
    },
}


RE_ARTIGO_CIRC = re.compile(r"(?:^| )Art\. (\d+)(?:º|\.)? ")


def artigos_da_circular(texto: str) -> dict[int, str]:
    """Texto normalizado da circular -> {número do artigo dela: texto do artigo}.

    Só a parte dispositiva (depois de "Disposições"); o fecho final, que não é
    artigo, fica com o último artigo.
    """
    corpo = texto[texto.index("Disposições") + len("Disposições"):] if "Disposições" in texto else texto
    marcas = list(RE_ARTIGO_CIRC.finditer(corpo))
    saida = {}
    for i, m in enumerate(marcas):
        fim = marcas[i + 1].start() if i + 1 < len(marcas) else len(corpo)
        saida[int(m[1])] = corpo[m.start():fim].strip()
    return saida


def menciona(texto_artigo: str, alvo: str) -> bool:
    """O artigo da circular fala do alvo declarado? (trava contra declaração errada)"""
    if alvo.startswith("ART-"):
        return re.search(rf"art\. {alvo[4:]}\b", texto_artigo) is not None
    if alvo.startswith("CIRC-"):
        _, num, ano = alvo.split("-")
        return f"{num}/{ano}" in texto_artigo
    return alvo in texto_artigo   # TUSS-50000462
