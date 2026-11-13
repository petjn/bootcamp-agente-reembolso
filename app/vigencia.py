"""Resolve qual redação de um dispositivo vale numa data. Código puro, sem modelo.

Implementa o art. 5º do Regulamento Geral sobre o grafo que
`ingest/grafo_normativo.py` gravou em storage/:

  caput  circulares prevalecem sobre a redação anterior com que conflitem;
  § 1º   revogada uma circular, volta a redação imediatamente anterior;
  § 2º   circular que não menciona o artigo não o altera;
  § 4º   entre circulares, vale a de início de vigência mais recente,
         não a de número maior.

A data de referência é a do atendimento (documento fiscal), não a do pedido.

    from app.vigencia import Grafo
    g = Grafo.carregar()
    g.redacao("ART-41", "caput", date(2026, 3, 10)).fonte   # 'CIRC-11-2026'
    g.fundamentos("ART-41", date(2026, 3, 10))               # ['ART-41', 'CIRC-11-2026']
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date
from functools import cache
from pathlib import Path

ARQUIVO = Path(__file__).resolve().parents[1] / "storage" / "grafo_normativo.json"
ORIGINAL = date.min  # a redação do Regulamento consolidado vale desde sempre


@dataclass(frozen=True)
class Redacao:
    dispositivo: str            # ART-41
    parte: str                  # caput, § 2º, tabela do § 2º...
    fonte: str                  # ART-41 (redação original) ou CIRC-11-2026
    inicio: date
    texto: str | None = None
    fim: date | None = None     # revogação: deixa de valer a partir desta data
    # início de vigência da circular que deu esta redação. Difere de `inicio` só quando a
    # circular agenda uma eficácia futura; é por ela que se decide a precedência (§ 4º).
    vigencia_circular: date = ORIGINAL

    def vale_em(self, dia: date) -> bool:
        return self.inicio <= dia and (self.fim is None or dia < self.fim)


class Grafo:
    def __init__(self, circulares: list[dict]):
        self.circulares = {c["sigla"]: c for c in circulares}
        revogacao = {r["alvo"]: date.fromisoformat(c["inicio_vigencia"])
                     for c in circulares for r in c["relacoes"] if r["tipo"] == "revoga"}

        self.redacoes: list[Redacao] = []
        self.revogacoes_de_parte: list[Redacao] = []
        # TUSS -> (desde quando, artigo e parte cujo teto passa a valer no lugar da tabela)
        self.tuss_sobreposto: dict[str, tuple[date, str, str]] = {}
        for c in circulares:
            inicio = date.fromisoformat(c["inicio_vigencia"])
            fim = revogacao.get(c["sigla"])
            primeira_alteracao = next((r for r in c["relacoes"] if r["tipo"] == "altera"), None)
            for r in c["relacoes"]:
                if r["tipo"] == "altera":
                    self.redacoes.append(Redacao(r["alvo"], r["parte"], c["sigla"], inicio,
                                                 r.get("texto"), fim, inicio))
                elif r["tipo"] == "eficacia_futura":
                    self.redacoes.append(Redacao(r["alvo"], r["parte"], c["sigla"],
                                                 date.fromisoformat(r["inicio"]), r["valor"], fim,
                                                 inicio))
                elif r["tipo"] == "revoga_parte":
                    self.revogacoes_de_parte.append(Redacao(r["alvo"], r["parte"], c["sigla"], inicio))
                elif r["tipo"] == "sobrepoe_tuss":
                    # "o teto fixado no art. 1º desta Circular prevalece sobre ... a Tabela"
                    self.tuss_sobreposto[r["alvo"]] = (inicio, primeira_alteracao["alvo"],
                                                       primeira_alteracao["parte"])

    @classmethod
    @cache
    def carregar(cls, arquivo: Path = ARQUIVO) -> "Grafo":
        return cls(json.loads(arquivo.read_text(encoding="utf-8"))["circulares"])

    def partes_alteradas(self, dispositivo: str) -> list[str]:
        return sorted({r.parte for r in self.redacoes if r.dispositivo == dispositivo})

    def redacao(self, dispositivo: str, parte: str, dia: date) -> Redacao:
        """A redação de (dispositivo, parte) vigente no dia."""
        candidatas = [Redacao(dispositivo, parte, dispositivo, ORIGINAL)] + [
            r for r in self.redacoes if r.dispositivo == dispositivo and r.parte == parte]
        validas = [r for r in candidatas if r.vale_em(dia)]           # § 1º: revogada sai
        # § 4º: vence a circular de vigência mais recente. Uma eficácia futura agendada por
        # circular anterior perde para circular posterior que alterou a mesma parte.
        return max(validas, key=lambda r: (r.vigencia_circular, r.inicio))

    def fundamentos(self, dispositivo: str, dia: date, partes: list[str] | None = None) -> list[str]:
        """O que citar ao aplicar o dispositivo no dia: o artigo e as circulares que deram a
        redação vigente das partes efetivamente aplicadas (art. 6º, parágrafo único: só o que
        se aplica ao caso). Sem `partes`, considera todas as partes já alteradas."""
        partes = partes if partes is not None else self.partes_alteradas(dispositivo)
        fontes = {self.redacao(dispositivo, p, dia).fonte for p in partes}
        return [dispositivo] + sorted(f for f in fontes if f != dispositivo)

    def teto_sobre_tuss(self, tuss: str, dia: date) -> Redacao | None:
        """Se, no dia, o teto da tabela para o código foi substituído por um artigo
        alterado por circular, devolve a redação vigente desse artigo; senão, None."""
        if tuss not in self.tuss_sobreposto:
            return None
        desde, dispositivo, parte = self.tuss_sobreposto[tuss]
        return self.redacao(dispositivo, parte, dia) if dia >= desde else None
