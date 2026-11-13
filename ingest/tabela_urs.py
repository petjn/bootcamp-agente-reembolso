"""Lê a Tabela URS: valor da URS, vigência e uma linha estruturada por código TUSS.

    python -m ingest.tabela_urs

A tabela não passa por chunking: cada linha vira registro consultado pelo
código. A coluna "Observação" diz qual artigo governa a linha ("Teto do
art. 35", "(1)" -> nota que remete ao art. 41); é ela que liga o procedimento
à regra, sem tabela de correspondência escrita no código.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pymupdf

from app import siglas

from ingest.grafo_normativo import para_data

RAIZ = Path(__file__).resolve().parents[1]
DESTINO = RAIZ / "storage" / "tabela_urs.json"


def _limpa(celula: str | None) -> str:
    return re.sub(r"\s+", " ", celula or "").strip()


def _decimal(texto: str) -> str | None:
    """'1,2' -> '1.2'; '—' -> None. Fica como string para não perder precisão."""
    m = re.fullmatch(r"[\d.]*\d(,\d+)?", texto.replace("R$", "").strip())
    return m[0].replace(".", "").replace(",", ".") if m else None


def ler(caminho: Path) -> dict:
    doc = pymupdf.open(caminho)
    texto = re.sub(r"\s+", " ", "".join(p.get_text() for p in doc))

    valor_urs = _decimal(re.search(r"1 URS = R\$ ([\d.,]+)", texto)[1])
    # "vigência de 1º de janeiro a 31 de dezembro de 2026": a primeira data herda o ano
    vig = re.search(r"vigência de (\d{1,2})º? de (\w+) a (\d{1,2})º? de (\w+) de (\d{4})", texto)
    inicio = para_data(vig[1], vig[2], vig[5])
    fim = para_data(vig[3], vig[4], vig[5])

    notas = dict(re.findall(r"\((\d+)\) (.*?)(?= \(\d+\) | 5\. Observações)", texto))

    linhas = []
    for pagina in doc:
        for tabela in pagina.find_tables().tables:
            for celulas in tabela.extract():
                cel = [_limpa(c) for c in celulas]
                if len(cel) < 6 or not re.fullmatch(r"\d{8}", cel[0]):
                    continue
                codigo, descricao, teto_urs, _, categoria, observacao = cel[:6]
                nota = re.fullmatch(r"\((\d+)\)", observacao)
                fonte_regra = notas.get(nota[1], "") if nota else observacao
                # artigo que fixa o teto ("Teto do art. 35"; nota: "reproduz a redação do art. 41")
                teto_art = re.search(r"Teto do art\. (\d+)|reproduz a redação do art\. (\d+)", fonte_regra)
                linhas.append({
                    "codigo": siglas.tuss(codigo),
                    "descricao": descricao,
                    "teto_urs": _decimal(teto_urs),        # None = sem teto automatizado
                    "categoria_tabela": categoria,
                    "observacao": observacao,
                    "nota": fonte_regra if nota else None,
                    # todos os artigos citados na observação (teto, exigências, alçada)
                    "artigos": sorted({siglas.artigo(n) for n in re.findall(r"art\. (\d+)", fonte_regra)},
                                      key=siglas.numero_artigo),
                    "artigo_teto": siglas.artigo(teto_art[1] or teto_art[2]) if teto_art else None,
                })
    linhas.sort(key=lambda l: l["codigo"])
    return {"documento": caminho.name, "valor_urs_brl": valor_urs,
            "vigencia_inicio": inicio, "vigencia_fim": fim, "linhas": linhas}


def main() -> int:
    tabela = ler(RAIZ / "kb" / "tabela_urs_2026.pdf")
    DESTINO.write_text(json.dumps(tabela, ensure_ascii=False, indent=2, sort_keys=True),
                       encoding="utf-8")
    com_artigo = sum(1 for l in tabela["linhas"] if l["artigos"])
    print(f"URS = R$ {tabela['valor_urs_brl']} ({tabela['vigencia_inicio']} a {tabela['vigencia_fim']})")
    print(f"{len(tabela['linhas'])} códigos, {com_artigo} remetem a algum artigo")
    print(f"-> {DESTINO.relative_to(RAIZ)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
