"""Fallback do build: o Gemma lê um trecho quando o padrão de texto não reconhece a redação.

Três travas mantêm o build confiável e determinístico:
  1. saída estruturada (Pydantic) com o valor copiado como aparece no texto;
  2. ancoragem: o valor tem de aparecer literalmente no trecho, senão é descartado;
  3. cache em storage/cache_modelo.json, indexado pelo hash de (modelo, tipo, trecho).
     Com o cache preenchido, o build não chama o modelo: roda offline e igual sempre.
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

from pydantic import BaseModel, Field

RAIZ = Path(__file__).resolve().parents[1]
CACHE = RAIZ / "storage" / "cache_modelo.json"

DESCRICAO_TIPO = {
    "teto_urs": "o teto de reembolso, em URS",
    "prazo_dias": "o prazo, em dias",
    "carencia_dias": "a carência, em dias",
    "sessoes_para_continuado": "o número mínimo de sessões para acompanhamento continuado",
    "limite_sessoes_ano": "o número máximo de sessões por ano",
    "limite_anual_urs": "o limite anual de reembolso, em URS",
    "relatorio_a_partir_da_sessao": "o número da sessão a partir da qual se exige relatório",
    "relatorio_excedente_teto_pct": "o percentual acima do teto que exige relatório",
    "alcada_brl": "o limite de alçada, em reais",
}


class Extracao(BaseModel):
    encontrado: bool = Field(description="o trecho fixa esse valor?")
    valor: str = Field(description="o número exatamente como escrito no trecho, ex.: '2,8' ou '90'")


def ancorado(valor: str, texto: str) -> bool:
    return re.search(rf"(?<![\d,]){re.escape(valor)}(?![\d,])", texto) is not None


def extrair_com_modelo(texto: str, tipo: str, llm=None) -> dict | None:
    from app.llm import criar_llm

    llm = llm or criar_llm(reasoning=False)
    pergunta = (f"Trecho de norma de plano de saúde:\n\"\"\"{texto}\"\"\"\n\n"
                f"Qual é {DESCRICAO_TIPO[tipo]} fixado neste trecho? Copie o número exatamente "
                "como está escrito. Se o trecho não fixar esse valor, responda encontrado=false.")
    r = llm.with_structured_output(Extracao).invoke(pergunta)
    # descarta: nada achado, valor que não é número (ex.: "duas URS e meia" — número por
    # extenso vai para revisão humana) e valor que não está escrito no trecho
    if not r or not r.encontrado or not re.fullmatch(r"[\d.]*\d(,\d+)?", r.valor.strip()) \
            or not ancorado(r.valor.strip(), texto):
        return None
    return {"tipo": tipo, "valor": r.valor.replace(".", "").replace(",", "."),
            "escopo": None, "trecho": r.valor}


def chave(modelo: str, tipo: str, texto: str) -> str:
    return hashlib.sha256(f"{modelo}\n{tipo}\n{texto}".encode()).hexdigest()


def extrator_com_cache(cache_path: Path = CACHE):
    from app.llm import config

    modelo = config("MODELO_CHAT")
    cache = json.loads(cache_path.read_text(encoding="utf-8")) if cache_path.exists() else {}

    def extrator(texto: str, tipo: str) -> dict | None:
        k = chave(modelo, tipo, texto)
        if k not in cache:
            cache[k] = extrair_com_modelo(texto, tipo)
            cache_path.write_text(json.dumps(cache, ensure_ascii=False, indent=2, sort_keys=True),
                                  encoding="utf-8")
        return cache[k]

    return extrator
