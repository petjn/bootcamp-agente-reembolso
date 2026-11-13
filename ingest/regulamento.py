"""Separa o Regulamento Geral em artigo e parte (caput, §§, parágrafo único).

É a unidade em que as circulares alteram o texto (ver grafo_normativo.py), e
portanto a unidade em que os parâmetros são extraídos e citados.
"""

from __future__ import annotations

import re
from pathlib import Path

import pymupdf

from app import siglas

RAIZ = Path(__file__).resolve().parents[1]
ARQUIVO = RAIZ / "kb" / "regulamento_geral.pdf"

RE_CABECALHO = re.compile(r"\n[^\n]*\nSaúdeMais Saúde Suplementar S\.A\. — documento normativo\npág\. \d+\n")
RE_ARTIGO = re.compile(r"\nArt\. (\d+)(?:º|\.)? ")
# fim do artigo: próximo artigo, ou abertura de Título/Capítulo
RE_FIM = re.compile(r"\n(?:Art\. \d+|TÍTULO |Capítulo |Publicado no portal)")
RE_PARTE = re.compile(r"\n(?=§ \d+º |Parágrafo único\. )")


def _normalizar(texto: str) -> str:
    return re.sub(r"\s+", " ", texto).strip()


def texto_bruto(caminho: Path = ARQUIVO) -> str:
    texto = "\n" + "".join(p.get_text() for p in pymupdf.open(caminho))
    return RE_CABECALHO.sub("\n", texto)


RE_TITULO = re.compile(r"\n(TÍTULO [IVX]+) — ([^\n]+)\n")
RE_CAPITULO = re.compile(r"\nCapítulo (Único|[IVX]+) — ([^\n]+)\n")


def _nome(caixa_alta: str) -> str:
    """'DO DIREITO AO REEMBOLSO' -> 'Do direito ao reembolso'."""
    return caixa_alta.strip().capitalize()


def estrutura(caminho: Path = ARQUIVO) -> dict:
    """Onde cada artigo está e o que cada título diz de si mesmo.

    {'titulos': {'TÍTULO II': {'nome': 'Do direito ao reembolso', 'abertura': 'Este Título ...'}},
     'artigos': {'ART-11': {'titulo': 'TÍTULO II', 'capitulo': 'Capítulo I — Das hipóteses e dos requisitos'}}}

    A abertura é o parágrafo que cada título traz antes do primeiro capítulo ou artigo:
    diz de que trata o título e como lê-lo (ex.: no Título IV, que a ordem das operações
    é parte da norma). Os capítulos têm só nome.
    """
    texto = texto_bruto(caminho)
    eventos = sorted(
        [(m.start(), "titulo", m) for m in RE_TITULO.finditer(texto)]
        + [(m.start(), "capitulo", m) for m in RE_CAPITULO.finditer(texto)]
        + [(m.start(), "artigo", m) for m in RE_ARTIGO.finditer(texto)], key=lambda e: e[0])
    titulos: dict[str, dict] = {}
    artigos_: dict[str, dict] = {}
    titulo = capitulo = None
    for i, (_, tipo, m) in enumerate(eventos):
        if tipo == "titulo":
            titulo, capitulo = m[1], None
            fim = eventos[i + 1][2].start() if i + 1 < len(eventos) else len(texto)
            titulos[titulo] = {"nome": _nome(m[2]), "abertura": _normalizar(texto[m.end():fim])}
        elif tipo == "capitulo":
            capitulo = f"Capítulo {m[1]} — {m[2].strip()}"
        else:
            artigos_[siglas.artigo(m[1])] = {"titulo": titulo, "capitulo": capitulo}
    return {"titulos": titulos, "artigos": artigos_}


def artigos(caminho: Path = ARQUIVO) -> dict[str, dict[str, str]]:
    """{'ART-41': {'caput': 'Art. 41. A sessão ...', '§ 1º': '§ 1º Tratando-se ...', ...}}"""
    texto = texto_bruto(caminho)
    saida: dict[str, dict[str, str]] = {}
    for m in RE_ARTIGO.finditer(texto):
        inicio = m.start() + 1
        fim = RE_FIM.search(texto, m.end())
        bloco = texto[inicio:fim.start() if fim else len(texto)]
        partes = RE_PARTE.split(bloco)
        dispositivo = siglas.artigo(m[1])
        saida[dispositivo] = {"caput": _normalizar(partes[0])}
        for p in partes[1:]:
            p = _normalizar(p)
            nome = "parágrafo único" if p.startswith("Parágrafo único") else re.match(r"§ \d+º", p)[0]
            saida[dispositivo][nome] = p
    return saida
