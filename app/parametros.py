"""Consulta os parâmetros extraídos no build, na redação vigente numa data.

    p = Parametros.carregar()
    p.valor("ART-41", "caput", "teto_urs", date(2026, 4, 25))
    # Valor(valor=Decimal('2.8'), fonte='CIRC-02-2026', dispositivo='ART-41', parte='caput')

O valor sai de storage/parametros.json; a redação vigente, do grafo normativo.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from functools import cache
from pathlib import Path

from app.vigencia import Grafo

STORAGE = Path(__file__).resolve().parents[1] / "storage"


@dataclass(frozen=True)
class Valor:
    valor: object
    fonte: str          # ART-41 ou a circular que deu a redação vigente
    dispositivo: str
    parte: str
    escopo: str | None = None


def _tipado(v):
    return Decimal(v) if isinstance(v, str) else v


class Parametros:
    def __init__(self, registros: list[dict], tabela: dict, grafo: Grafo):
        self.registros = registros
        self.tabela = tabela
        self.linhas = {l["codigo"]: l for l in tabela["linhas"]}
        self.grafo = grafo

    @classmethod
    @cache
    def carregar(cls) -> "Parametros":
        ler = lambda nome: json.loads((STORAGE / nome).read_text(encoding="utf-8"))
        return cls(ler("parametros.json"), ler("tabela_urs.json"), Grafo.carregar())

    def onde(self, tipo: str) -> list[tuple[str, str]]:
        """Em que (artigo, parte) do Regulamento esse tipo de parâmetro é fixado."""
        return sorted({(r["dispositivo"], r["parte"]) for r in self.registros
                       if r["tipo"] == tipo and r["fonte"] == r["dispositivo"]})

    def todos(self, dispositivo: str, parte: str, tipo: str, dia: date) -> list[Valor]:
        fonte = self.grafo.redacao(dispositivo, parte, dia).fonte
        achados = [Valor(_tipado(r["valor"]), fonte, dispositivo, parte, r.get("escopo"))
                   for r in self.registros
                   if (r["dispositivo"], r["parte"], r["fonte"], r["tipo"]) == (dispositivo, parte, fonte, tipo)]
        if not achados:
            raise KeyError(f"{tipo} não definido em {dispositivo} {parte} na redação {fonte}")
        return achados

    def valor(self, dispositivo: str, parte: str, tipo: str, dia: date) -> Valor:
        (unico,) = self.todos(dispositivo, parte, tipo, dia)
        return unico

    def unico(self, tipo: str, dia: date) -> Valor:
        """Para tipos fixados num só lugar do Regulamento (limite anual, coparticipação...)."""
        (lugar,) = self.onde(tipo)
        return self.valor(*lugar, tipo, dia)

    def valor_urs(self, dia: date) -> Decimal:
        """Valor da URS do exercício da data do atendimento (art. 33, parágrafo único)."""
        t = self.tabela
        if not (date.fromisoformat(t["vigencia_inicio"]) <= dia <= date.fromisoformat(t["vigencia_fim"])):
            raise LookupError(f"não há Tabela URS carregada para {dia}")
        return Decimal(t["valor_urs_brl"])

    def linha(self, codigo_tuss: str) -> dict:
        return self.linhas[codigo_tuss]
