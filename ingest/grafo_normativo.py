"""Monta o grafo normativo das circulares e grava em storage/.

    python -m ingest.grafo_normativo

O que cada circular faz (altera, revoga, sobrepõe teto da tabela, agenda
eficácia futura), sobre quem e desde quando vem de `ingest/circulares.py`,
declarado a partir da nossa leitura (D8). Do PDF saem o texto da redação nova
de cada parte, a ementa e a data de publicação. Nenhum modelo participa.

Pelo art. 5º, § 2º, do Regulamento, circular que não menciona um artigo não o
altera: a declaração só pode apontar alvo que o artigo da circular menciona, e
o build confere isso.
"""

from __future__ import annotations

import json
import re
from datetime import date
from pathlib import Path

import pymupdf

from app import siglas
from ingest.circulares import DECLARACOES, artigos_da_circular, menciona

RAIZ = Path(__file__).resolve().parents[1]
DIR_KB = RAIZ / "kb"
DESTINO = RAIZ / "storage" / "grafo_normativo.json"

MESES = {m: i for i, m in enumerate(
    ["janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho",
     "agosto", "setembro", "outubro", "novembro", "dezembro"], start=1)}
DATA = r"(\d{1,2})º? de (\w+) de (\d{4})"


class DeclaracaoDivergente(RuntimeError):
    pass


def para_data(dia: str, mes: str, ano: str) -> str:
    return date(int(ano), MESES[mes.lower()], int(dia)).isoformat()


def separar_partes(redacao: str) -> dict[str, str]:
    """Texto entre aspas de uma circular -> {'caput': ..., '§ 1º': ..., '§ 2º': ...}."""
    saida = {}
    for pedaco in re.split(r" (?=§ \d+º [^.])", redacao.strip()):
        m = re.match(r"§ \d+º", pedaco)
        saida[m[0] if m else "caput"] = pedaco.strip()
    return saida


def texto_normalizado(caminho: Path) -> str:
    texto = "".join(p.get_text() for p in pymupdf.open(caminho))
    # tira cabeçalho e rodapé repetidos de página antes de juntar as linhas
    texto = re.sub(r"Circular \d+/\d{4}\nSaúdeMais.*?\npág\. \d+\n", "", texto)
    return re.sub(r"\s+", " ", texto)


def redacao_nova(texto_artigo: str, parte: str) -> str:
    """O texto que a circular dá à parte alterada: o que está entre aspas ou, sem aspas
    (tabela de percentuais), o que vem depois dos dois-pontos até o parágrafo seguinte."""
    aspas = re.findall(r"“([^”]*)”", texto_artigo)
    if aspas:
        texto = " ".join(aspas)
        return separar_partes(texto).get(parte) or texto
    depois = texto_artigo[texto_artigo.index(":") + 1:]
    return re.split(r" Parágrafo único\.", depois)[0].strip()


def _confere(sigla: str, condicao: bool, mensagem: str) -> None:
    if not condicao:
        raise DeclaracaoDivergente(f"{sigla}: {mensagem}. Revise ingest/circulares.py.")


def extrair_circular(sigla: str, declaracao: dict) -> dict:
    t = texto_normalizado(DIR_KB / declaracao["arquivo"])
    _confere(sigla, siglas.do_titulo(t) == sigla, "o título do PDF não corresponde à sigla")
    cabecalho = re.search(rf"Início de vigência: {DATA}", t)
    if cabecalho:
        _confere(sigla, para_data(*cabecalho.groups()) == declaracao["vigencia"],
                 f"vigência declarada {declaracao['vigencia']} difere da do PDF")
    publicacao = re.search(rf"Publicação: {DATA}", t)
    ementa = re.search(r"EMENTA: (.*?) Publicação:", t)

    artigos = artigos_da_circular(t)
    relacoes = []
    for num, declaradas in declaracao["artigos"].items():
        _confere(sigla, num in artigos, f"art. {num} declarado não existe no PDF")
        texto_art = artigos[num]
        for tipo, alvo, parte, *extra in declaradas:
            extra = extra[0] if extra else {}
            if tipo == "eficacia_futura":
                _confere(sigla, extra["inicio"][:4] in texto_art, f"art. {num}: data de eficácia não aparece")
                valor = re.search(r"(\d+(?:,\d+)?) URS", texto_art)
                _confere(sigla, valor is not None, f"art. {num}: valor da eficácia futura não aparece")
                relacoes.append({"tipo": tipo, "alvo": alvo, "parte": parte,
                                 "valor": f"{valor[1]} URS", "inicio": extra["inicio"]})
                continue
            _confere(sigla, menciona(texto_art, alvo), f"art. {num} não menciona {alvo}")
            if tipo == "altera":
                relacoes.append({"tipo": tipo, "alvo": alvo, "parte": parte,
                                 "texto": redacao_nova(texto_art, parte)})
            elif tipo == "revoga_parte":
                relacoes.append({"tipo": tipo, "alvo": alvo, "parte": parte})
            else:  # revoga, sobrepoe_tuss
                relacoes.append({"tipo": tipo, "alvo": alvo})

    return {"sigla": sigla, "arquivo": declaracao["arquivo"],
            "publicacao": para_data(*publicacao.groups()) if publicacao else None,
            "inicio_vigencia": declaracao["vigencia"],
            "ementa": ementa[1] if ementa else None, "relacoes": relacoes}


def main() -> int:
    arquivos = {d["arquivo"] for d in DECLARACOES.values()}
    sem_declaracao = sorted(p.name for p in DIR_KB.glob("circular_*.pdf") if p.name not in arquivos)
    if sem_declaracao:
        raise DeclaracaoDivergente(f"circular sem declaração em ingest/circulares.py: {sem_declaracao}")
    circulares = [extrair_circular(s, d) for s, d in DECLARACOES.items()]
    circulares.sort(key=lambda c: (c["inicio_vigencia"], c["sigla"]))
    DESTINO.parent.mkdir(exist_ok=True)
    DESTINO.write_text(json.dumps({"circulares": circulares}, ensure_ascii=False, indent=2),
                       encoding="utf-8")
    for c in circulares:
        print(f"{c['sigla']:14} vigência {c['inicio_vigencia']}")
        for r in c["relacoes"]:
            print("   ", r["tipo"], r["alvo"], r.get("parte") or "", r.get("inicio", ""))
    print(f"-> {DESTINO.relative_to(RAIZ)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
