"""As siglas seguem o art. 6º do Regulamento, e tudo o que o build grava já as usa.

O primeiro teste lê o próprio art. 6º: se uma nova redação mudar a convenção,
ele falha e avisa que app/siglas.py tem de acompanhar.
"""

import json
import re
from pathlib import Path

import pytest

from app import siglas
from ingest import regulamento

RAIZ = Path(__file__).resolve().parents[1]


def test_exemplos_do_art_6_sao_reproduzidos():
    art6 = regulamento.artigos()["ART-6"]["caput"]
    exemplos = re.findall(r"na forma ([A-Z]+-[\w-]+?)[;.]", art6)
    assert exemplos == ["ART-12", "CIRC-11-2026", "TUSS-50000462", "ANEXO-IV", "NT-02"]
    assert [siglas.artigo(12), siglas.circular(11, 2026), siglas.tuss("50000462"),
            siglas.anexo("iv"), siglas.nota_tecnica(2)] == exemplos
    assert all(siglas.valida(e) for e in exemplos)


@pytest.mark.parametrize("sigla", ["ART-041", "ART-41-§2", "CIRC-2-2026", "CIRC-02/2026",
                                   "TUSS-5000046", "ANEXO-4", "NT-2", "FAQ-1"])
def test_formas_fora_da_convencao_sao_rejeitadas(sigla):
    assert not siglas.valida(sigla)


@pytest.mark.parametrize("titulo, sigla", [
    ("CIRCULAR NORMATIVA 02/2026", "CIRC-02-2026"),
    ("ANEXO IV — EXCLUSÕES DE COBERTURA", "ANEXO-IV"),
    ("NOTA TÉCNICA 02", "NT-02"),
    ("REGULAMENTO GERAL DE REEMBOLSO", None),        # citado por artigo
    ("TABELA URS 2026", None),                      # citada por código TUSS
    ("MANUAL DA REDE CREDENCIADA E DO REEMBOLSO", None),  # material de apoio, não se cita
])
def test_sigla_pelo_titulo_do_documento(titulo, sigla):
    assert siglas.do_titulo(titulo) == sigla


def test_storage_so_tem_siglas_validas():
    grafo = json.loads((RAIZ / "storage" / "grafo_normativo.json").read_text(encoding="utf-8"))
    tabela = json.loads((RAIZ / "storage" / "tabela_urs.json").read_text(encoding="utf-8"))
    params = json.loads((RAIZ / "storage" / "parametros.json").read_text(encoding="utf-8"))
    usadas = {c["sigla"] for c in grafo["circulares"]}
    usadas |= {r["alvo"] for c in grafo["circulares"] for r in c["relacoes"]}
    usadas |= {l["codigo"] for l in tabela["linhas"]}
    usadas |= {a for l in tabela["linhas"] for a in l["artigos"]}
    usadas |= {r[k] for r in params for k in ("dispositivo", "fonte")}
    assert sorted(s for s in usadas if not siglas.valida(s)) == []


def test_gabaritos_usam_a_mesma_convencao():
    for esperado in (RAIZ / "casos" / "treino").glob("*/esperado.json"):
        regras = json.loads(esperado.read_text(encoding="utf-8"))["regras_aplicadas"]
        assert all(siglas.valida(r) for r in regras), esperado.parent.name
