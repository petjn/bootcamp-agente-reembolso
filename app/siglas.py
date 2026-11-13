"""Siglas de citação dos dispositivos normativos (art. 6º do Regulamento Geral).

    I   artigos do Regulamento   ART-12
    II  circulares               CIRC-11-2026
    III procedimentos            TUSS-50000462
    IV  anexos                   ANEXO-IV
    V   notas técnicas           NT-02

É a forma usada em `regras_aplicadas` e no metadado `citacao` de cada chunk. A
citação é sempre do artigo inteiro (ART-41), nunca do parágrafo: o parágrafo
fica em metadado à parte.

Manual da rede e FAQ não têm sigla: são material de apoio, sem caráter
normativo, e não fundamentam decisão (art. 5º, § 5º). `do_titulo` devolve None
para eles, e o chunk sai marcado como não citável.
"""

from __future__ import annotations

import re

ROMANO = r"[IVXLC]+"
PADRAO = re.compile(rf"ART-[1-9]\d*|CIRC-\d{{2}}-\d{{4}}|TUSS-\d{{8}}|ANEXO-{ROMANO}|NT-\d{{2}}")


def artigo(numero: int | str) -> str:
    return f"ART-{int(numero)}"


def circular(numero: int | str, ano: int | str) -> str:
    return f"CIRC-{int(numero):02d}-{int(ano)}"


def tuss(codigo: str) -> str:
    codigo = str(codigo).removeprefix("TUSS-")
    if not re.fullmatch(r"\d{8}", codigo):
        raise ValueError(f"código TUSS deve ter 8 dígitos: {codigo!r}")
    return f"TUSS-{codigo}"


def anexo(romano: str) -> str:
    if not re.fullmatch(ROMANO, romano.upper()):
        raise ValueError(f"anexo deve ser numerado em algarismo romano: {romano!r}")
    return f"ANEXO-{romano.upper()}"


def nota_tecnica(numero: int | str) -> str:
    return f"NT-{int(numero):02d}"


def valida(sigla: str) -> bool:
    return PADRAO.fullmatch(sigla) is not None


def numero_artigo(sigla: str) -> int:
    """'ART-41' -> 41, para ordenar artigos pelo número e não como texto."""
    return int(sigla.removeprefix("ART-"))


# Título do documento (primeira página) -> sigla do documento inteiro.
_TITULOS = [
    (re.compile(r"CIRCULAR NORMATIVA (\d+)/(\d{4})"), lambda m: circular(m[1], m[2])),
    (re.compile(rf"ANEXO ({ROMANO})\b"), lambda m: anexo(m[1])),
    (re.compile(r"NOTA TÉCNICA (\d+)"), lambda m: nota_tecnica(m[1])),
]


def do_titulo(texto_inicial: str) -> str | None:
    """Sigla de um documento citado por inteiro (circular, anexo, nota técnica), a partir do
    título na primeira página. None para o Regulamento e a Tabela, cujos chunks são citados
    pelo artigo (ART-n) e pelo código (TUSS-n), e para o material de apoio, que não se cita."""
    for padrao, montar in _TITULOS:
        m = padrao.search(texto_inicial)
        if m:
            return montar(m)
    return None
