"""Deixa legível para o modelo texto que o PDF achatou.

A extração do PDF transforma a tabela de coparticipação (art. 44, § 2º, e a nova
redação da CIRC-02-2026) numa linha corrida:

    "Plano Até 12 meses de adesão De 12 a 36 meses Acima de 36 meses Pleno 30% 20% 10% Essencial 35% 25% 15%"

Lida assim, não dá para saber qual percentual é de qual plano e faixa. Aqui ela
volta a ser tabela, em Markdown, só no texto que vai para o índice e para o
modelo. A extração de parâmetros (ingest/parametros.py) continua lendo o texto
original do PDF.
"""

from __future__ import annotations

import re

RE_TABELA_FAIXAS = re.compile(
    r"Plano (Até \d+ meses de adesão) (De \d+ a \d+ meses) (Acima de \d+ meses)"
    r"((?: [A-Z][a-zç]+ \d+% \d+% \d+%)+)")
RE_LINHA = re.compile(r"([A-Z][a-zç]+) (\d+%) (\d+%) (\d+%)")


def _markdown(m: re.Match) -> str:
    linhas = ["| Plano | " + " | ".join(m.group(1, 2, 3)) + " |", "|---|---|---|---|"]
    linhas += [f"| {p} | {a} | {b} | {c} |" for p, a, b, c in RE_LINHA.findall(m[4])]
    return "\n" + "\n".join(linhas) + "\n"


def legivel(texto: str) -> str:
    """Troca tabelas achatadas por tabelas em Markdown; o resto do texto fica igual."""
    return RE_TABELA_FAIXAS.sub(_markdown, texto).strip()
