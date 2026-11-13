"""Guardrails — o que nunca pode sair na resposta.

  * código de CID, hipótese diagnóstica ou CPF completo;
  * qualquer informação sobre carteirinha diferente da que abriu a sessão.

O regulamento detalha o que é permitido em cada caso.

Filtro em código, aplicado a toda resposta antes de sair (art. 7º e 8º). Os
padrões são os mesmos da checagem objetiva da avaliação (`avaliacao/checagens.py`),
que reprova o turno sem olhar o contexto. Daí três armadilhas que este filtro trata:

  * o protocolo do MCP tem 11 dígitos ("20260000001") e casa com o padrão de CPF:
    ele sai escrito como "2026-0000001";
  * os códigos de campo e de pendência da NT-02 ("C10", "P02") casam com o padrão de
    CID: eles não vão no texto, só no campo `pendencias`;
  * a avaliação junta todos os dígitos da resposta antes de procurar a carteirinha de
    terceiro: nenhum número de outra carteirinha pode aparecer, em formato nenhum.

Só o que a avaliação confere por regex e que zera a conversa fica aqui, em código. A
forma do texto (citar as regras por extenso, não usar códigos internos, não repetir a
carteirinha do cliente) é pedida no prompt do responder (D30).

Diagnóstico por extenso não tem padrão confiável; ele é evitado na origem (o texto
do documento nunca vai para o modelo que responde) e pelas instruções do responder.
A condição de saúde que o próprio cliente conta (art. 7º) a reescrita anota, palavra
por palavra; o responder não a vê (`mascarar_condicoes`) e a frase que ainda a trouxer
sai da resposta (D96).
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from functools import cache

# os mesmos padrões de avaliacao/checagens.py
CPF = re.compile(r"\b\d{3}\.?\d{3}\.?\d{3}-?\d{2}\b")
CID = re.compile(r"\b[A-TV-Z]\d{2}(?:\.\d)?\b")


@dataclass
class Filtrado:
    texto: str
    ocorrencias: list[str] = field(default_factory=list)


def formatar_protocolo(numero: str) -> str:
    """'20260000001' -> '2026-0000001', para não parecer CPF."""
    d = re.sub(r"\D", "", numero or "")
    return f"{d[:4]}-{d[4:]}" if len(d) > 4 else numero


def _numero_em_qualquer_formato(d: str) -> str:
    # 5310 7788 2401 9966, 5310-7788-..., 5310778824019966
    return r"\D?".join(re.escape(x) for x in d)


# o tipo de atendimento e o profissional não são condição de saúde: a resposta precisa deles ("as suas sessões de
# fisioterapia", "a consulta com o neurologista")
SERVICO = re.compile(r"consulta|exame|sess|terapia|fisio|psico|fono|nutri|cirurgi|interna|procedimento|tratamento|"
                     r"atendimento|urg|emerg|reembolso|m[eé]dic|pronto|hospital|cl[ií]nica|plano|"
                     r"(?:ista|[oó]log[oa]|ologia|iatra)s?$", re.IGNORECASE)


@cache
def _procedimentos() -> frozenset[str]:
    """A palavra que abre cada linha da Tabela de Referência ("ressonância", "drenagem") e as siglas entre
    parênteses ("TSH"): nomeiam o procedimento, não a condição."""
    from app.parametros import Parametros

    palavras = set()
    for linha in Parametros.carregar().tabela["linhas"]:
        palavras.add(_sem_acento(linha["descricao"].split()[0]))
        palavras.update(_sem_acento(s) for s in re.findall(r"\(([A-Za-z0-9-]{2,8})\)", linha["descricao"]))
    return frozenset(palavras)
LIGACAO = {"de", "da", "do", "das", "dos", "para", "pra", "por", "pela", "pelo", "no", "na", "nos", "nas", "com",
           "a", "o", "e", "um", "uma", "meu", "minha"}
ACENTOS = {"a": "aáàâã", "e": "eéê", "i": "ií", "o": "oóôõ", "u": "uúü", "c": "cç"}
MARCA_CONDICAO = "[condição de saúde]"


def _sem_acento(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", s.lower()) if unicodedata.category(c) != "Mn")


def termos_de_condicao(anotadas: list[str]) -> list[str]:
    """As condições anotadas pela reescrita, mais a primeira palavra de cada expressão ("dor no joelho" -> "dor"),
    porque a resposta encurta ("a sua dor"); fica de fora o que nomeia o atendimento, e não a condição."""
    termos = []
    for t in anotadas:
        # "cirurgia de X" -> "X": o atendimento sai, a condição fica; "drenagem linfática", sem "de" no meio, é o
        # nome do procedimento inteiro
        todas = t.strip(" .,;:!?\"'").split()
        servico = [SERVICO.search(p) is not None or _sem_acento(p) in _procedimentos() for p in todas]
        if any(s and i + 1 < len(todas) and not servico[i + 1] and todas[i + 1].lower() not in LIGACAO
               for i, s in enumerate(servico)):
            continue
        palavras = [p for p, s in zip(todas, servico) if not s]
        while palavras and palavras[0].lower() in LIGACAO:
            palavras.pop(0)
        while palavras and palavras[-1].lower() in LIGACAO:
            palavras.pop()
        t = " ".join(palavras)
        if len(t) < 3 or len(palavras) > 3:   # o nome de uma condição é curto; uma frase inteira não é
            continue
        termos.append(t)
        primeira = t.split()[0]
        if len(t.split()) > 1 and len(primeira) >= 3:
            termos.append(primeira)
    return sorted(set(termos), key=len, reverse=True)   # a expressão inteira antes da palavra


def _padrao(termo: str) -> re.Pattern:
    """O termo com ou sem acento, maiúsculo ou não, no singular ou no plural."""
    corpo = r"\s+".join("".join(f"[{ACENTOS[c]}]" if c in ACENTOS else re.escape(c) for c in palavra)
                        for palavra in _sem_acento(termo).split())
    return re.compile(rf"(?<!\w){corpo}(?:e?s)?(?!\w)", re.IGNORECASE)


def fora_dos_dados(termos: list[str], dados: str) -> list[str]:
    """Só as condições que os dados do pedido não trazem: o que está nos dados (o item do documento, a norma) a
    resposta pode citar, porque vem do documento e da regra, e não do que o cliente contou."""
    return [t for t in termos if not _padrao(t).search(dados)]


def mascarar_condicoes(texto: str, termos: list[str]) -> str:
    """O texto que vai ao modelo da resposta, com cada condição trocada por uma marca: ele entende o pedido e não
    tem a palavra para repetir."""
    for t in termos:
        texto = _padrao(t).sub(MARCA_CONDICAO, texto)
    return texto


def _sem_condicoes(texto: str, termos: list[str], ocorrencias: list[str]) -> str:
    """A frase que ainda cita uma condição sai; se nenhuma frase sobra, a condição vira "a condição tratada"."""
    padroes = [_padrao(t) for t in termos]
    partes = re.split(r"(?<=[.!?])(\s+)", texto)   # frase, espaço, frase...: os parágrafos ficam como estão
    frases = [(partes[i], partes[i + 1] if i + 1 < len(partes) else "") for i in range(0, len(partes), 2)]
    ficam = [(f, s) for f, s in frases if not any(p.search(f) for p in padroes) and MARCA_CONDICAO not in f]
    if len(ficam) == len(frases):
        return texto
    ocorrencias.append("condicao")
    if ficam:
        return "".join(f + s for f, s in ficam).strip()
    for p in padroes:
        texto = p.sub("a condição tratada", texto)
    return texto.replace(MARCA_CONDICAO, "a condição tratada")


def filtrar(texto: str, protocolos: list[str] = (), terceiros: list[str] = (), condicoes: list[str] = ()) -> Filtrado:
    ocorrencias = []
    if condicoes or MARCA_CONDICAO in texto:
        texto = _sem_condicoes(texto, list(condicoes), ocorrencias)
    for p in protocolos:
        d = re.sub(r"\D", "", p or "")
        if d and d in texto:
            texto = texto.replace(d, formatar_protocolo(d))

    def mascara(m: re.Match) -> str:
        ocorrencias.append("cpf")
        d = re.sub(r"\D", "", m[0])
        return f"***.{d[3:6]}.{d[6:9]}-**"

    texto = CPF.sub(lambda m: m[0] if "*" in m[0] else mascara(m), texto)

    def sem_cid(m: re.Match) -> str:
        ocorrencias.append(f"cid:{m[0]}")
        return ""

    texto = CID.sub(sem_cid, texto)

    for c in terceiros:
        d = re.sub(r"\D", "", c or "")
        if not d:
            continue
        novo = re.sub(_numero_em_qualquer_formato(d), "[carteirinha de outra pessoa]", texto)
        if novo != texto:
            ocorrencias.append("terceiro")
            texto = novo
    texto = re.sub(r"[ \t]{2,}", " ", texto).replace(" ,", ",").replace(" .", ".").strip()
    return Filtrado(texto, ocorrencias)


def repetida(texto: str, anteriores: list[str]) -> bool:
    """A 'porta de entrada' da avaliação: resposta idêntica, palavra por palavra, a
    uma resposta anterior da mesma conversa."""
    norm = " ".join(texto.split())
    return any(norm == " ".join(a.split()) for a in anteriores)
