"""Eval da busca da norma, parte isolada (método de análise de erros).

    python -m scripts.eval_busca

Chama `app.rag.buscar` com as descrições de pedido que o supervisor registrou nos traces (a entrada real
do ag_normas) e confere se a norma que responde veio. Cada item tem grupos obrigatórios; o grupo é
atendido quando qualquer alternativa aparece nos trechos ou nos artigos trazidos. Sem modelo: a busca é
determinística, então uma rodada basta.
"""

from __future__ import annotations

from datetime import date

from app.agents.normas import nos_termos_do_regulamento
from app.rag import buscar

TERMOS_LIGADOS = True   # False mede a busca crua, com a descrição do pedido

DIA = date(2026, 5, 20)

ITENS: list[tuple[str, list[list[str]], str]] = [
    ("Queria entender como funciona o reembolso de terapia com psicóloga particular.",
     [["ART-9", "ART-10", "ART-11"]], "o que é reembolso, requisitos e como pedir"),
    ("Quero saber como está o meu reembolso.", [["ART-81", "ART-15"]], "prazo de análise ou de pagamento"),
    ("Quando o valor do meu reembolso vai ser pago?", [["ART-15"]], "prazo de pagamento"),
    ("Acho que a consulta não foi nessa data, foi uns dias antes.", [["ART-13", "NT-02|C4"]],
     "a data que vale é a do atendimento no documento"),
    ("Por que não volta os 240 inteiros?", [["ART-43", "ART-44"]], "teto e coparticipação"),
    ("O plano cobre acupuntura?", [["ANEXO-IV", "ART-55"]], "procedimento de fronteira"),
    ("Posso pedir o relatório clínico ao meu profissional?", [["ART-73"]], "relatório clínico exigido"),
    ("Se eu já pedi muitos reembolsos este ano, isso afeta o valor do reembolso?", [["ART-45"]], "limite anual"),
    ("Se eu perder o prazo de pedir, ainda dá para recorrer de alguma forma?", [["ART-12"], ["ART-20"]],
     "prazo e reanálise"),
    ("Quanto tempo essa análise costuma levar?", [["ART-81"]], "prazo de análise"),
    ("Por que você não consegue me dizer o valor agora? O sistema não calcula?", [["ART-78"]], "alçada"),
]


def _achados(r) -> set[str]:
    ids = set()
    for t in [*r.trechos, *r.regras_anexo]:
        ids |= {t.dispositivo, f"{t.dispositivo}|{t.parte}"} | ({t.citacao} if t.citacao else set())
    for a in r.artigos:
        ids |= {a.dispositivo, *a.fundamentos}
    return ids


def main() -> None:
    acertos = 0
    for pergunta, grupos, porque in ITENS:
        r = buscar(pergunta, DIA)
        achados = _achados(r) | (_achados(buscar(nos_termos_do_regulamento(pergunta), DIA)) if TERMOS_LIGADOS else set())
        falta = [g for g in grupos if not any(any(a == x or x.startswith(a + "|") for x in achados) for a in g)]
        acertos += not falta
        trazidos = sorted({t.dispositivo for t in r.trechos})
        print(f"{'ok ' if not falta else 'ERR'} {pergunta} ({porque})\n    trouxe: {trazidos}"
              + (f"\n    faltou: {falta}" if falta else ""))
    print(f"\nTOTAL: {acertos}/{len(ITENS)} ({100 * acertos / len(ITENS):.0f}%)")


if __name__ == "__main__":
    main()
