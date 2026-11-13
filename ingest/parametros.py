"""Extrai do texto normativo os valores que o cálculo usa. Nenhum valor vive no código.

    python -m ingest.parametros

Para cada redação — a original de cada (artigo, parte) do Regulamento e a nova
de cada parte alterada por circular — procura padrões de texto por *tipo* de
parâmetro ("teto de 2,8 URS" -> teto_urs = 2.8). O código conhece tipos e
padrões de redação; os números vêm sempre do documento.

Redação alterada por circular tem de trazer os mesmos tipos que a original:
  * se a circular elide o trecho mantido ("§ 2º ... nessa hipótese o teto é de
    2,6 URS"), o tipo ausente é herdado da redação anterior;
  * senão, o Gemma lê o trecho (ver ingest/modelo.py). O valor que ele devolve
    tem de aparecer literalmente no texto, e a resposta fica em cache no
    repositório, para o build seguir offline e determinístico;
  * se nada disso resolver, o build para: melhor parar do que seguir com valor velho.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from app import siglas
from ingest import regulamento
from ingest.grafo_normativo import DESTINO as GRAFO

RAIZ = Path(__file__).resolve().parents[1]
DESTINO = RAIZ / "storage" / "parametros.json"

NUM = r"\d+(?:,\d+)?"
POR_EXTENSO = r"\([^)]*\)"

# tipo -> padrão de redação. O grupo "v" é o valor; "escopo", quando há, diz a que se aplica.
PADROES: dict[str, re.Pattern] = {
    "teto_urs": re.compile(rf"teto (?:é )?de (?P<v>{NUM}) URS"),
    "prazo_dias": re.compile(rf"prazo de (?P<v>\d+) {POR_EXTENSO} dias"),
    "prazo_sanar_dias": re.compile(rf"dispõe de (?P<v>\d+) {POR_EXTENSO} dias corridos para sanar"),
    "carencia_dias": re.compile(rf"carência .{{0,150}}?é de (?P<v>\d+) {POR_EXTENSO}"),
    "intervalo_consultas_dias": re.compile(rf"mesmo profissional no intervalo de (?P<v>\d+) {POR_EXTENSO} dias"),
    "sessoes_para_continuado": re.compile(rf"pelo menos (?P<v>\d+) {POR_EXTENSO} sessões"),
    "limite_sessoes_ano": re.compile(rf"limitado a (?P<v>\d+) {POR_EXTENSO} por beneficiário"),
    "limite_anual_urs": re.compile(rf"não poderá exceder (?P<v>\d+) {POR_EXTENSO} URS"),
    "relatorio_a_partir_da_sessao": re.compile(r"a sessão for a (?P<v>\d+)ª ou posterior"),
    "relatorio_excedente_teto_pct": re.compile(r"exceder em mais de (?P<v>\d+)%"),
    "alcada_brl": re.compile(r"R\$ (?P<v>[\d.]+,\d{2}) para (?P<escopo>.+?)(?=, e de R\$|\.(?: |$))"),
}
RE_FAIXAS = re.compile(r"Até (\d+) meses de adesão De (\d+) a (\d+) meses Acima de (\d+) meses")
RE_LINHA_PLANO = re.compile(r"\b([A-Z][a-zç]+) (\d+)% (\d+)% (\d+)%")


class ParametroNaoEncontrado(RuntimeError):
    pass


def _numero(texto: str) -> str:
    """'1.234,56' -> '1234.56' (string, para não perder precisão no JSON)."""
    return texto.replace(".", "").replace(",", ".")


def extrair(texto: str) -> list[dict]:
    """Todos os parâmetros reconhecidos num trecho, com o pedaço de texto de onde saíram."""
    achados = []
    for tipo, padrao in PADROES.items():
        for m in padrao.finditer(texto):
            achados.append({"tipo": tipo, "valor": _numero(m["v"]),
                            "escopo": m.groupdict().get("escopo"), "trecho": m[0]})
    faixas = RE_FAIXAS.search(texto)
    if faixas:
        limites = sorted({int(n) for n in faixas.groups()})
        tabela = {plano: [str(int(p) / 100) for p in pcts]
                  for plano, *pcts in RE_LINHA_PLANO.findall(texto[faixas.end():])}
        achados.append({"tipo": "coparticipacao", "valor": {"faixas_meses": limites, "percentuais": tabela},
                        "escopo": None, "trecho": texto[faixas.start():faixas.end() + 60]})
    return achados


def _registro(dispositivo: str, parte: str, fonte: str, achado: dict, metodo: str) -> dict:
    return {"dispositivo": dispositivo, "parte": parte, "fonte": fonte, "metodo": metodo, **achado}


def construir(extrator_modelo=None) -> list[dict]:
    """Monta a lista completa de parâmetros. `extrator_modelo(texto, tipo)` é o fallback."""
    originais = regulamento.artigos()
    registros: list[dict] = []
    tipos_por_parte: dict[tuple[str, str], set[str]] = {}
    ultimo_por_parte: dict[tuple[str, str], list[dict]] = {}

    for dispositivo, partes in originais.items():
        for parte, texto in partes.items():
            achados = extrair(texto)
            regs = [_registro(dispositivo, parte, dispositivo, a, "regex") for a in achados]
            registros += regs
            tipos_por_parte[(dispositivo, parte)] = {a["tipo"] for a in achados}
            ultimo_por_parte[(dispositivo, parte)] = regs

    circulares = json.loads(GRAFO.read_text(encoding="utf-8"))["circulares"]
    for c in circulares:  # já em ordem de vigência
        for r in c["relacoes"]:
            if r["tipo"] != "altera":
                continue
            chave, texto = (r["alvo"], r["parte"]), r["texto"] or ""
            achados = extrair(texto)
            encontrados = {a["tipo"] for a in achados}
            novos = [_registro(*chave, c["sigla"], a, "regex") for a in achados]
            for tipo in sorted(tipos_por_parte.get(chave, set()) - encontrados):
                anterior = next(x for x in ultimo_por_parte[chave] if x["tipo"] == tipo)
                if "..." in texto:
                    # trecho elidido = mantido: herda o valor da redação anterior
                    novos.append({**anterior, "fonte": c["sigla"], "metodo": "herdado",
                                  "herdado_de": anterior["fonte"]})
                    continue
                achado = extrator_modelo(texto, tipo) if extrator_modelo else None
                if achado is None:
                    raise ParametroNaoEncontrado(
                        f"{c['sigla']} altera {chave[0]} {chave[1]}, mas não achei '{tipo}' no texto "
                        f"novo. Revise o padrão ou o trecho: {texto[:200]!r}")
                novos.append(_registro(*chave, c["sigla"], achado, "modelo"))
            registros += novos
            ultimo_por_parte[chave] = novos
    return registros


def main() -> int:
    from ingest.modelo import extrator_com_cache

    registros = construir(extrator_com_cache())
    registros.sort(key=lambda r: (siglas.numero_artigo(r["dispositivo"]), r["parte"], r["fonte"], r["tipo"],
                                  json.dumps(r["valor"])))
    DESTINO.write_text(json.dumps(registros, ensure_ascii=False, indent=2, sort_keys=True),
                       encoding="utf-8")
    por_metodo: dict[str, int] = {}
    for r in registros:
        por_metodo[r["metodo"]] = por_metodo.get(r["metodo"], 0) + 1
    print(f"{len(registros)} parâmetros {por_metodo} -> {DESTINO.relative_to(RAIZ)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
