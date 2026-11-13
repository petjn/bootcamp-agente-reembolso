"""Eval da leitura de documento: classificação e molde dos 19 anexos dos casos de treino.

    python -m scripts.eval_documento [repeticoes] [nomes]

Para cada anexo, chama `documento.analisar` com o nome do beneficiário da persona do caso em que o anexo
aparece (o cliente já identificado) e confere contra o gabarito abaixo, montado lendo cada PDF:
classificação, se é documento fiscal, data do atendimento, valor total, códigos TUSS e, no relatório,
a indicação de manter o tratamento.
"""

from __future__ import annotations

import base64
import json
import sys
from pathlib import Path

from app.agents.documento import analisar

RAIZ = Path(__file__).resolve().parents[1]

# arquivo: (classificação, documento fiscal, data, valor total, TUSS, mantém tratamento)
GABARITO: dict[str, tuple] = {
    "conta_energia.pdf": ("INVALIDO",),
    "estacionamento_hospital.pdf": ("INVALIDO",),
    "recibo_consulta_dermatologia.pdf": ("CONSULTA_MEDICA", True, "2026-04-30", 240.0, ["TUSS-10101012"], None),
    "recibo_psicoterapia.pdf": ("SESSAO_TERAPIA", True, "2026-04-25", 320.0, ["TUSS-50000462"], None),
    "relatorio_clinico_psicoterapia.pdf": ("RELATORIO_CLINICO", False, None, None, [], True),
    "nota_protese_ortopedica.pdf": ("MATERIAL_OPME", True, "2026-04-30", 9200.0, ["TUSS-70000039"], None),
    "recibo_psico_marco.pdf": ("SESSAO_TERAPIA", True, "2026-03-10", 200.0, ["TUSS-50000462"], None),
    "recibo_cardiologia_injetado.pdf": ("CONSULTA_MEDICA", True, "2026-05-04", 300.0, ["TUSS-10101055"], None),
    "recibo_oftalmologia.pdf": ("CONSULTA_MEDICA", True, "2026-05-06", 380.0, ["TUSS-10101135"], None),
    "recibo_exame_tsh.pdf": ("EXAME_DIAGNOSTICO", True, "2026-05-10", 90.0, ["TUSS-40301258"], None),
    "recibo_acupuntura.pdf": ("SESSAO_TERAPIA", True, "2026-05-11", 150.0, ["TUSS-50000646"], None),
    "nota_avaliacao_neuropsicologica.pdf": ("SESSAO_TERAPIA", True, "2026-05-13", 5200.0, ["TUSS-50000550"], None),
    "recibo_psico_trigesima.pdf": ("SESSAO_TERAPIA", True, "2026-05-12", 400.0, ["TUSS-50000462"], None),
    "relatorio_psico_vera.pdf": ("RELATORIO_CLINICO", False, None, None, [], True),
    "recibo_psico_tulio.pdf": ("SESSAO_TERAPIA", True, "2026-05-08", 260.0, ["TUSS-50000462"], None),
    "recibo_geriatria.pdf": ("CONSULTA_MEDICA", True, "2026-05-07", 420.0, ["TUSS-10101087"], None),
    "recibo_clinica_medica.pdf": ("CONSULTA_MEDICA", True, "2026-05-11", 350.0, ["TUSS-10101047"], None),
    "recibo_relatorio_medico.pdf": ("RELATORIO_CLINICO", True, "2026-05-13", 150.0, ["TUSS-10104011"], None),
    "recibo_exame_tgo.pdf": ("EXAME_DIAGNOSTICO", True, "2026-05-18", 180.0, ["TUSS-40301082"], None),
}


# campos que de fato faltam no PDF (a nota da avaliação neuropsicológica não tem assinatura nem carimbo)
FALTANDO = {"nota_avaliacao_neuropsicologica.pdf": ["C7"]}


def _anexos() -> dict[str, tuple[dict, str]]:
    """arquivo -> (anexo do turno, nome da persona do caso)."""
    saida = {}
    for pasta in sorted(p.parent for p in (RAIZ / "casos" / "treino").glob("*/persona.json")):
        nome = json.loads((pasta / "persona.json").read_text(encoding="utf-8"))["nome"]
        for linha in (pasta / "turnos.jsonl").read_text(encoding="utf-8").splitlines():
            a = json.loads(linha).get("anexo")
            if a:
                arq = (pasta / a["path"]).resolve()
                saida[a["filename"]] = ({"filename": a["filename"], "mime_type": a["mime_type"],
                                         "base64": base64.b64encode(arq.read_bytes()).decode()}, nome)
    return saida


def conferir(novo: dict, esperado: tuple, faltando: list[str] = ()) -> list[str]:
    m = novo["molde"]
    erros = []
    if m["classificacao"] != esperado[0]:
        return [f"classificou {m['classificacao']} ({m.get('descricao', '')})"]
    if esperado[0] == "INVALIDO":
        return []
    _, fiscal, data, total, tuss, mantem = esperado
    if m["documento_fiscal"] != fiscal:
        erros.append(f"documento_fiscal={m['documento_fiscal']}")
    if fiscal and m["c4_data_atendimento"] != data:
        erros.append(f"data {m['c4_data_atendimento']}")
    if fiscal and m["c6_valor_total"] != total:
        erros.append(f"valor {m['c6_valor_total']}")
    achados = [i["codigo_tuss"] for i in m["c5_itens"] if i["codigo_tuss"]]
    if fiscal and not set(tuss) <= set(achados):
        erros.append(f"TUSS {achados}")
    if mantem is not None and m.get("indica_manutencao_tratamento") != mantem:
        erros.append("manutenção do tratamento")
    if fiscal and m.get("campos_faltando", []) != list(faltando):
        erros.append(f"faltando {m['campos_faltando']}")
    return erros


def main(repeticoes: int = 2, so: list[str] | None = None) -> None:
    anexos = _anexos()
    acertos = total = 0
    for arquivo, esperado in GABARITO.items():
        if so and arquivo not in so:
            continue
        anexo, nome = anexos[arquivo]
        for _ in range(repeticoes):
            erros = conferir(analisar(anexo, 1, [], nome), esperado, FALTANDO.get(arquivo, []))
            acertos += not erros
            total += 1
            print(f"{'ok ' if not erros else 'ERR'} {arquivo}: {erros or esperado[0]}", flush=True)
    print(f"\nTOTAL: {acertos}/{total} ({100 * acertos / total:.0f}%)")


if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 2, sys.argv[2].split(",") if len(sys.argv) > 2 else None)
