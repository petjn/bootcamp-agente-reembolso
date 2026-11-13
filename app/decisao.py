"""Decisão do pedido de reembolso: a árvore de decisão (docs/analise_erros/arvore_de_decisao.md, D78 e D79),
na ordem da NT-02, item 6.1. A lista ARVORE, no fim, é a árvore: um nó por verificação.

    6.4   data do atendimento          sem ela, pendência
    4.1   OPME                         sempre a analista (art. 78, § 2º)
    3     exclusão do Anexo IV         o modelo julga, item a item quando cada item tem valor
    2.2   item sem código TUSS         o modelo acha a linha pela descrição; o de menor teto (art. 34)
    4     alçada                       cirurgia a analista (art. 83); valor solicitado acima do limite (art. 78)
    5.1   contrato ativo               art. 30
    5.3   carência                     item a item, pela categoria e pela data de cada um (arts. 21 a 26)
    5.5   prazo                        da última sessão (arts. 12 e 13)
    6     campos e valor por item      NT-02, C1 a C7; várias sessões num valor só
    6.9   terapia                      sessão a sessão: limite do art. 40 e relatório do art. 73, § 3º
    6.10  pedido médico                alta complexidade (art. 38)
    6.13  pendências                   todas de uma vez, com o prazo do art. 19
    7.4   relatório sozinho            uma vez por ano civil (NT-02, Caso 36)
    8     cálculo                      app/calculo, item a item

Para no primeiro desfecho; o item que não passa num nó sai do cálculo e os outros seguem. Todo número vem dos
parâmetros extraídos do texto (D7) e toda data de regra é a do atendimento. Só os nós 3 e 2.2 usam o modelo; o resto
é código. A ficha é o caminho percorrido: o que não está nela não foi conferido.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import Decimal
from functools import cache

from typing import Literal

from pydantic import BaseModel, Field

from app.calculo import _teto_urs, apurar
from app.parametros import Parametros


@dataclass
class Decisao:
    decisao: str | None                    # APROVADO, APROVADO_PARCIAL, PENDENTE_DOCUMENTO, NEGADO, ...
    categoria: str | None
    valor_solicitado: float | None = None
    valor_reembolso: float | None = None
    regras: list[str] = field(default_factory=list)
    pendencias: list[str] = field(default_factory=list)      # códigos P.. (vão no campo `pendencias`)
    falta_cliente: list[str] = field(default_factory=list)   # o que pedir, em palavras
    escalar: bool = False                                    # abrir protocolo para analista
    motivo: str = ""
    memoria: list[str] = field(default_factory=list)         # passo a passo, para explicar
    # a ficha do pedido: cada requisito conferido, na ordem da NT-02 (6.1), com a regra, a situação (cumprido, falta,
    # impede, analista, não se aplica) e o dado que a sustenta. O que não está na ficha não foi conferido.
    ficha: list[dict] = field(default_factory=list)


class JulgamentoExclusao(BaseModel):
    """O julgamento do procedimento do documento diante dos itens do Anexo IV."""
    item: str | None = Field(default=None, description=(
        "o número do item do Anexo IV que é o mesmo procedimento do documento, ex.: '3.3'; vazio se nenhum é"))
    motivo: str = Field(default="", description="o motivo do desfecho, em uma frase")
    desfecho: Literal["excluido", "falta_indicacao", "coberto"] = Field(description=(
        "excluido: o procedimento é um item de qualquer grupo que não o 3; "
        "falta_indicacao: é um item do grupo 3 e o documento não traz indicação clínica expressa; "
        "coberto: não é nenhum dos itens, ou é um item do grupo 3 com indicação clínica expressa"))


# ------------------------------------------------------------------ regime da categoria (NT-02, Anexo A)
@cache
def regime(categoria: str) -> str:
    from app.rag import carregar

    for n in carregar().nos.values():
        if n.metadata.get("citacao") == "NT-02" and n.metadata.get("parte") == f"3.1 {categoria}":
            return n.text
    return ""


def artigo_carencia(categoria: str) -> str | None:
    m = re.search(r"carência do art\. (\d+)", regime(categoria))
    return f"ART-{m[1]}" if m else None


@cache
def codigo_pendencia(trecho: str) -> str | None:
    """Código P.. da tabela da NT-02 cuja ocorrência contém o trecho."""
    from app.rag import carregar

    for n in carregar().nos.values():
        m = re.search(r"Código: (P\d+)\. Ocorrência: ([^.]*)", n.text) if n.metadata.get("citacao") == "NT-02" else None
        if m and trecho.lower() in m[2].lower():
            return m[1]
    return None


@cache
def validade_pedido_medico() -> int:
    """Dias de validade do pedido médico, lidos da NT-02 (Anexo E, 9.2)."""
    from app.rag import carregar

    for n in carregar().nos.values():
        m = re.search(r"pedido é válido por (\d+)", n.text) if n.metadata.get("citacao") == "NT-02" else None
        if m:
            return int(m[1])
    raise RuntimeError("validade do pedido médico não achada na NT-02 (9.2)")


@cache
def campos() -> dict[str, str]:
    """Campo C1..C10 -> o que o cliente precisa pedir ao prestador, nas palavras da NT-02."""
    from app.rag import carregar

    saida = {}
    for n in carregar().nos.values():
        m = re.search(r"Campo: (C\d+)\. Denominação: ([^.]*)\. Conteúdo exigido: ([^.]*)\.", n.text) \
            if n.metadata.get("citacao") == "NT-02" else None
        if m:
            saida[m[1]] = f"{m[2].lower()} ({m[3][0].lower() + m[3][1:]})"
    return saida


# ------------------------------------------------------------------ N2: Anexo IV
# Padrão dos exemplos do LangGraph: papel e regras no SystemMessage; os dados do caso, na
# mensagem do usuário.
JULGAR = """<papel>
Você confere se um procedimento de saúde está excluído da cobertura pelo Anexo IV do
Regulamento.
</papel>

<tarefa>
Com os dados que o usuário enviar (o procedimento do documento, os itens do Anexo IV que a
busca trouxe e as regras de aplicação do Anexo IV):
- Procure, entre os itens, o que for o mesmo procedimento do documento, pela finalidade e não
  pelo nome comercial. Os itens vieram de uma busca e podem não ter relação com o
  procedimento; se nenhum é o mesmo, o desfecho é coberto.
- Item do grupo 3 (procedimentos de fronteira): o desfecho é falta_indicacao quando o documento não
  traz indicação clínica expressa, e coberto quando traz.
- Item de qualquer outro grupo: o desfecho é excluido.
</tarefa>"""

DADOS_JULGAR = """<procedimento_do_documento categoria="{categoria}" indicacao_clinica_expressa="{indicacao}">
{procedimento}
</procedimento_do_documento>

<itens_do_anexo_iv>
{itens}
</itens_do_anexo_iv>

<regras_de_aplicacao_do_anexo_iv>
{regras}
</regras_de_aplicacao_do_anexo_iv>"""


def _sem_acento(s: str) -> str:
    import unicodedata

    return "".join(c for c in unicodedata.normalize("NFD", s.lower()) if unicodedata.category(c) != "Mn").strip()


def procedimento_na_tabela(molde: dict) -> str:
    """Os itens do documento para a busca da norma: a descrição da tabela TUSS quando o código foi
    achado, que é o vocabulário da norma (o recibo pode vir sem acento, abreviado ou com nome comercial)."""
    linhas = Parametros.carregar().linhas
    return "; ".join(linhas.get(i.get("codigo_tuss") or "", {}).get("descricao") or i["descricao"]
                     for i in molde["c5_itens"])


def julgar_anexo_iv(molde: dict, dia: date) -> JulgamentoExclusao | None:
    from langchain_core.messages import HumanMessage, SystemMessage

    from app.llm import estruturado
    from app.rag import buscar

    procedimento = "; ".join(i["descricao"] for i in molde["c5_itens"]) or ""
    if not procedimento:
        return None
    # a busca leva a descrição da Tabela (o vocabulário da norma) e, quando difere, a do recibo: só com a da Tabela, o
    # "consulta e taxa administrativa" do recibo virava "consulta em consultório" e a taxa sumia (D82)
    tabela = procedimento_na_tabela(molde)
    buscas = [buscar(tabela, dia)]
    # segunda busca com o que o recibo diz além da descrição da Tabela (ex.: "e taxa administrativa"): com a frase
    # inteira, "consulta em cardiologia" dominava a busca e o item do Anexo IV não vinha
    palavras_tabela = set(re.findall(r"\w+", _sem_acento(tabela)))
    resto = [w for w in re.findall(r"\w+", procedimento) if _sem_acento(w) not in palavras_tabela and len(w) > 2]
    if resto:
        buscas.append(buscar(" ".join(resto), dia))
    itens = list({t.id: t for r in buscas for t in r.trechos if t.tipo_documento == "anexo"}.values())
    if not itens:
        return None
    texto_itens = "\n".join(f"- {t.cabecalho}: {t.texto} (abertura do grupo: {t.contexto})" for t in itens)
    # só as regras de aplicação do Anexo IV: desde a D55, `regras_anexo` traz também a classificação da NT-02 da
    # categoria, que não é regra de exclusão e mudava o julgamento
    regras = "\n".join(dict.fromkeys(f"- {t.texto}" for r in buscas for t in r.regras_anexo
                                     if t.tipo_documento == "anexo_regra"))
    dados = DADOS_JULGAR.format(procedimento=procedimento, categoria=molde["classificacao"],
                                indicacao="sim" if molde.get("c10_indicacao_clinica") else "não",
                                itens=texto_itens, regras=regras)
    return estruturado(JulgamentoExclusao, [SystemMessage(JULGAR), HumanMessage(dados)], no="anexo_iv")

# ------------------------------------------------------------------ 2.2: item sem código, pela descrição (art. 34)
CLASSIFICAR = """<papel>
Você classifica um procedimento de saúde descrito num recibo, sem código TUSS, nas linhas da Tabela URS.
</papel>

<tarefa>
Com a descrição do procedimento e as linhas da Tabela que a busca trouxe:
- Escolha as linhas que são o mesmo procedimento, pela natureza do que foi feito e não pelo nome comercial. Pode ser
  mais de uma.
- Se nenhuma linha é o mesmo procedimento, ou se a descrição não diz o que foi feito (por exemplo, "atendimento" ou
  "serviços prestados"), não escolha nenhuma.
- Diga também se a descrição é genérica: não diz o que foi feito, ou só traz um nome comercial.
- A linha só é o mesmo procedimento se quem o executou é habilitado para ele, pelo registro no conselho do documento
  (ex.: consulta é de médico, CRM; sessão de fisioterapia é de fisioterapeuta, CREFITO; de psicoterapia, psicólogo,
  CRP). Procedimento de outra prática, feito por quem não tem o registro da linha, não é aquela linha.
</tarefa>"""


class ClassificacaoItem(BaseModel):
    """As linhas da Tabela que são o mesmo procedimento do item."""
    descricao_generica: bool = Field(default=False, description=(
        "a descrição não diz o que foi feito (ex.: 'atendimento', 'serviços prestados', só um nome comercial)?"))
    codigos: list[str] = Field(default_factory=list, description=(
        "os códigos das linhas que são o mesmo procedimento, como estão nas linhas, ex.: 'TUSS-10101012'; vazio se "
        "nenhuma é"))


# o conselho de cada tipo de atendimento (NT-02, C3: CRM, CRP, CREFITO, CRFa ou equivalente; Anexo A: a sessão de
# terapia é de profissional inscrito no conselho respectivo). Exames e materiais não entram: o registro no documento é o
# do responsável técnico
CONSELHO = [("consulta", r"\bCRM\b"), ("psicoterapia", r"\bCRP\b"), ("fonoaudiologia", r"\bCRFa\b"),
            ("fisioterapia", r"\bCREFITO\b"), ("terapia ocupacional", r"\bCREFITO\b"), ("nutrição", r"\bCRN\b")]


def habilitado(linha: dict, registro: str | None) -> bool:
    """O executante pode ter feito o procedimento da linha? Sem registro no documento, não se confere aqui (a falta do
    registro é pendência, C3)."""
    if not registro or linha.get("categoria_tabela") not in ("Consulta médica", "Sessão de terapia"):
        return True
    descricao = (linha.get("descricao") or "").lower()
    exigido = next((r for chave, r in CONSELHO if chave in descricao), None)
    return exigido is None or bool(re.search(exigido, registro, re.I))


# a descrição diz o que foi feito, e nenhuma linha da Tabela é esse procedimento: não é reembolsável, e a falta de
# previsão na Tabela não se sana por pendência (art. 56; Anexo IV, grupo 10). Descrição genérica é pendência (art. 34)
FORA_DA_TABELA = "FORA_DA_TABELA"


def classificar_pela_descricao(item: dict, dia: date) -> list[str]:
    """Os códigos da Tabela compatíveis com a descrição do item. O modelo só escolhe entre as linhas que a busca
    trouxe; o código fica com as que existem."""
    from langchain_core.messages import HumanMessage, SystemMessage

    from app.llm import estruturado
    from app.rag import buscar

    linhas = [t for t in buscar(item["descricao"], dia).trechos if t.tipo_documento == "tabela" and t.parte == "linha"]
    executor = f" executor=\"{item['executor']}\"" if item.get("executor") else ""
    dados = (f"<procedimento_do_documento{executor}>\n{item['descricao']}\n</procedimento_do_documento>\n\n<linhas_da_tabela>\n"
             + ("\n".join(f"- {t.citacao}: {t.texto}" for t in linhas) or "(nenhuma)") + "\n</linhas_da_tabela>")
    c = estruturado(ClassificacaoItem, [SystemMessage(CLASSIFICAR), HumanMessage(dados)], no="classificar_item")
    validos = {t.citacao for t in linhas}
    codigos = [x for x in dict.fromkeys(c.codigos) if x in validos]
    return codigos or ([] if c.descricao_generica else [FORA_DA_TABELA])


# ------------------------------------------------------------------ a decisão: a árvore
# A árvore de decisão (docs/analise_erros/arvore_de_decisao.md) é a lista ARVORE, no fim: cada nó é uma função que
# lê a análise, escreve na ficha o que conferiu e devolve o desfecho, ou None para seguir ao próximo nó. A ficha é o
# caminho percorrido. Cada item do documento segue sozinho onde a norma manda (carência, sessão, cálculo); o item
# que não passa sai do cálculo e os outros seguem.

# a Tabela escreve a categoria pelo nome; a NT-02 (Anexo A), pelo código
CATEGORIA_DA_TABELA = {"Consulta médica": "CONSULTA_MEDICA", "Sessão de terapia": "SESSAO_TERAPIA",
                       "Exame diagnóstico": "EXAME_DIAGNOSTICO", "Relatório clínico": "RELATORIO_CLINICO",
                       "Material / OPME": "MATERIAL_OPME"}


@dataclass
class Analise:
    """O que os nós da árvore leem e escrevem."""
    molde: dict
    complementares: list[dict]
    beneficiario: dict
    historico: list[dict]
    hoje: date
    julgar: object
    classificar: object
    p: Parametros
    itens: list[dict] = field(default_factory=list)       # os que ainda entram no cálculo
    dia: date | None = None                                # do atendimento; com várias sessões, a última (art. 13, § 2º)
    ficha: list[dict] = field(default_factory=list)
    pendencias: list[str] = field(default_factory=list)
    falta: list[str] = field(default_factory=list)
    regras: list[str] = field(default_factory=list)       # dispositivos aplicados antes do cálculo
    fora: list[str] = field(default_factory=list)         # itens que saíram do cálculo, para a memória
    sessao: dict = field(default_factory=dict)            # id do item de terapia -> sessões do ano antes dele
    no: str = ""

    def req(self, regra: str, requisito: str, situacao: str, detalhe: str = "") -> None:
        self.ficha.append({"no": self.no, "regra": regra, "requisito": requisito, "situacao": situacao,
                           "detalhe": detalhe})

    def base(self) -> dict:
        return dict(categoria=self.molde["classificacao"], valor_solicitado=self.molde.get("c6_valor_total"))

    def data(self, item: dict) -> date:
        return date.fromisoformat(item["data"]) if item.get("data") else self.dia

    def categoria(self, item: dict) -> str:
        return CATEGORIA_DA_TABELA.get(item.get("categoria_tabela") or "") or self.molde["classificacao"]

    def sai(self, item: dict, motivo: str) -> None:
        self.itens.remove(item)
        self.fora.append(f"{motivo}, não entra no cálculo: {item['descricao']}")

    def citar(self, *regras: str) -> None:
        self.regras += [r for r in regras if r and r not in self.regras]

    def mesmo_ano(self) -> list[dict]:
        return [h for h in self.historico if h.get("data") and h["data"][:4] == str(self.dia.year)]


def decidir(molde: dict, complementares: list[dict], beneficiario: dict, historico: list[dict],
            hoje: date, julgar=julgar_anexo_iv, classificar=classificar_pela_descricao) -> Decisao:
    """A decisão, com o código TUSS de cada item do documento entre as regras citadas: o
    procedimento é parte da fundamentação de qualquer desfecho (art. 6º)."""
    a = Analise(molde, complementares, beneficiario, historico, hoje, julgar, classificar, Parametros.carregar(),
                itens=[dict(i) for i in molde.get("c5_itens", [])])
    d = None
    for no, funcao in ARVORE:
        a.no = no
        d = funcao(a)
        if d:
            break
    d.ficha = a.ficha
    # só os códigos da tabela: código que não está nela não é dispositivo citável
    tuss = [i["codigo_tuss"] for i in molde.get("c5_itens", []) if i.get("codigo_tuss") and i.get("na_tabela")]
    d.regras = list(dict.fromkeys([*d.regras, *tuss]))
    return d


def _rs(valor) -> str:
    """Valor em reais como se escreve no Brasil, para a ficha: R$ 5.000,00."""
    return "R$ " + f"{Decimal(str(valor)):,.2f}".replace(",", "#").replace(".", ",").replace("#", ".")


def _pendente(a: Analise) -> Decisao:
    return Decisao("PENDENTE_DOCUMENTO", regras=list(a.regras), pendencias=list(dict.fromkeys(a.pendencias)),
                   falta_cliente=a.falta, **a.base())


# ---- 6.4: sem a data do atendimento, nada mais se confere
def n_data(a: Analise) -> Decisao | None:
    datas = [i["data"] for i in a.itens if i.get("data")]
    if datas:
        a.dia = date.fromisoformat(max(datas))   # documento com várias sessões: a última (art. 13, § 2º)
    elif a.molde.get("c4_data_atendimento"):
        a.dia = date.fromisoformat(a.molde["c4_data_atendimento"])
    else:
        a.req("NT-02, campo C4", "data do atendimento no documento", "falta", "o documento não mostra a data")
        a.pendencias += a.molde.get("pendencias") or []
        a.falta.append("o documento não mostra a data do atendimento")
        return _pendente(a)
    return None


def _opme(a: Analise) -> Decisao | None:
    if a.molde["classificacao"] == "MATERIAL_OPME" or any(a.categoria(i) == "MATERIAL_OPME" for i in a.itens):
        a.req("art. 78, § 2º", "alçada da análise automatizada", "analista",
              "material, órtese, prótese ou material especial vai sempre a analista humano")
        return Decisao("ESCALADO_ANALISTA", regras=["ART-78"], escalar=True,
                       motivo="material, órtese, prótese ou material especial vai sempre a analista (art. 78, § 2º)",
                       **a.base())
    return None



# ---- 3: exclusão do Anexo IV, item a item quando cada item tem valor (art. 59; Anexo IV, 11.3)
def n_anexo_iv(a: Analise) -> Decisao | None:
    if not a.julgar:
        return None
    # a indicação clínica pode vir no documento fiscal ou em relatório do profissional assistente, contemporâneo ao
    # atendimento (art. 55, §§ 1º e parágrafo único; art. 60): o relatório emitido depois do atendimento não o alcança
    relatorio = next((c["molde"] for c in a.complementares if c["molde"].get("classificacao") == "RELATORIO_CLINICO"
                      and c["molde"].get("c10_indicacao_clinica") and c["molde"].get("c4_data_atendimento")
                      and date.fromisoformat(c["molde"]["c4_data_atendimento"]) <= a.dia), None)
    molde = {**a.molde, "c5_itens": a.itens,
             "c10_indicacao_clinica": bool(a.molde.get("c10_indicacao_clinica") or relatorio)}
    if len(a.itens) > 1 and all(i.get("valor") is not None for i in a.itens):
        julgados = [(i, a.julgar({**molde, "c5_itens": [i]}, a.dia)) for i in a.itens]
        excluidos = [(i, x) for i, x in julgados if x and x.desfecho == "excluido"]
        if excluidos and len(excluidos) < len(a.itens):
            for i, x in excluidos:
                a.req(f"Anexo IV, item {x.item}; art. 59", f"cobertura do item \"{i['descricao']}\"", "impede",
                      "o item sai do cálculo; os outros itens do documento seguem")
                a.sai(i, f"item excluído pelo Anexo IV, item {x.item}")
            a.citar("ART-59", "ANEXO-IV")
            julgados = [(i, x) for i, x in julgados if not (x and x.desfecho == "excluido")]
        j = next((x for _, x in julgados if x and x.desfecho == "excluido"), None) \
            or next((x for _, x in julgados if x and x.desfecho == "falta_indicacao"), None)
    else:
        j = a.julgar(molde, a.dia)
    # despesa não assistencial (grupo 5: "ainda que constem do mesmo documento") num item que também tem o código de
    # um procedimento da Tabela: atendimento e despesa num valor só, sem discriminação (art. 59, § 2º; D80)
    misto = bool(j and j.desfecho == "excluido" and (j.item or "").startswith("5.")
                 and any(i.get("na_tabela") for i in a.itens))
    # material comprado avulso (Anexo IV, 4.11) vai a analista (D78: o art. 78, § 2º, diz "sempre"), que aplica a
    # exclusão; o Anexo IV vem antes do OPME para que o procedimento lido como material não escape da exclusão (D82)
    if j and j.desfecho == "excluido" and (j.item or "") == "4.11":
        return _opme(a)
    if j and j.desfecho == "excluido" and not misto:
        # excluído: o pedido é indeferido (NEGADO); a despesa não coberta é a categoria do documento.
        # DESPESA_NAO_COBERTA não é uma das decisões do contrato do /chat.
        a.req(f"Anexo IV, item {j.item}; art. 51", "cobertura do procedimento", "impede", j.motivo)
        return Decisao("NEGADO", categoria="DESPESA_NAO_COBERTA", valor_solicitado=a.molde.get("c6_valor_total"),
                       regras=["ART-51", "ANEXO-IV"], motivo=f"Anexo IV, item {j.item}: {j.motivo}")
    if j and j.desfecho == "falta_indicacao":
        a.req(f"Anexo IV, item {j.item}; arts. 55 e 60", "indicação clínica expressa (procedimento de fronteira)", "falta",
              "no documento fiscal ou em relatório do profissional assistente, contemporânea ao atendimento e com a "
              "condição tratada")
        a.citar("ANEXO-IV", "ART-55", "ART-60")
        a.pendencias.append(codigo_pendencia("Indicação clínica ausente") or "C10")
        # o texto segue a norma ao pé da letra (arts. 55 e 60, Anexo IV): "do profissional" sozinho fazia a resposta
        # exigir o relatório de quem fez o procedimento
        a.falta.append("indicação clínica expressa do profissional assistente, no documento fiscal ou em relatório, "
                       "contemporânea ao atendimento e com a condição tratada (procedimento de fronteira, grupo 3 do "
                       "Anexo IV)")
        d = _pendente(a)
        d.motivo = f"Anexo IV, item {j.item}"
        return d
    if misto:
        # despesa excluída e atendimento coberto num valor só: pendência de discriminação antes de qualquer
        # indeferimento (art. 59, § 2º; NT-02, Caso 16; D80). Segue para os outros nós: as pendências saem juntas.
        a.req(f"Anexo IV, item {j.item}; art. 59, § 2º", "valor de cada item do documento", "falta",
              "o documento traz um atendimento coberto e uma despesa excluída sem a discriminação do valor de cada um")
        a.citar("ART-59", "ANEXO-IV")
        a.pendencias.append(codigo_pendencia("Valor global sem discriminação") or "C6")
        a.falta.append("novo recibo ou nota com o valor de cada item discriminado: o documento traz sem discriminação o "
                       f"atendimento e uma despesa que não é reembolsável (Anexo IV, item {j.item})")
        return None
    a.req("Anexo IV", "cobertura do procedimento", "cumprido", "não é procedimento excluído"
          + ("; a indicação clínica veio no relatório do profissional assistente" if relatorio else ""))
    return None


# ---- 2.2: item sem código TUSS é classificado pela descrição; havendo mais de um código, o de menor teto (art. 34)
def n_sem_codigo(a: Analise) -> Decisao | None:
    if not a.classificar or a.molde["classificacao"] == "MATERIAL_OPME" \
            or any(a.categoria(i) == "MATERIAL_OPME" for i in a.itens):   # OPME vai a analista no nó seguinte
        return None
    if a.molde.get("moeda_estrangeira"):
        # despesa no exterior vai a analista no nó seguinte (art. 69), e o registro do profissional é de um conselho
        # estrangeiro, que a habilitação daqui não reconhece: a consulta saía como fora da Tabela (art. 56, D98)
        return None
    # sem código, ou com um código que não está na Tabela (NT-02, P14: reclassifica-se pela descrição)
    for item in [i for i in a.itens if not i.get("codigo_tuss") or i["codigo_tuss"] not in a.p.linhas]:
        # o registro de quem executou vai junto: a classificação segue a natureza do procedimento e a habilitação do
        # executante (art. 34, § 1º; NT-02, Anexo A e P34); sem ele, quiropraxia virava sessão de fisioterapia (D93)
        executor = " ".join(x for x in (a.molde.get("c2_prestador_nome"), a.molde.get("c3_registro_conselho")) if x)
        achados = a.classificar({**item, "executor": executor} if executor else item, a.data(item))
        if achados == [FORA_DA_TABELA]:
            a.req("art. 56", f"previsão na Tabela URS do item \"{item['descricao']}\"", "impede",
                  "o procedimento descrito não consta da Tabela URS; a falta de previsão não se sana por pendência")
            a.sai(item, "procedimento que não consta da Tabela URS (art. 56)")
            a.citar("ART-56")
            continue
        codigos = [c for c in achados if a.p.linhas.get(c, {}).get("teto_urs") is not None
                   or a.p.linhas.get(c, {}).get("categoria_tabela") == "Material / OPME"]
        # a linha só vale se quem executou tem o registro do conselho dela (NT-02, C3 e Anexo A): o modelo dava a sessão
        # de quiropraxia, de registro em associação, como sessão de fisioterapia (D93)
        habilitados = [c for c in codigos if habilitado(a.p.linhas[c], a.molde.get("c3_registro_conselho"))]
        if codigos and not habilitados:
            a.req("art. 34; NT-02, C3", f"procedimento do item \"{item['descricao']}\"", "impede",
                  "as linhas da Tabela parecidas exigem registro em conselho que o executante não tem; o procedimento "
                  "feito não consta da Tabela")
            a.sai(item, "procedimento que não consta da Tabela URS para o registro do executante (art. 56)")
            a.citar("ART-56")
            continue
        codigos = habilitados
        if not codigos:
            inexistente = bool(item.get("codigo_tuss"))
            a.req("art. 34", f"procedimento do item \"{item['descricao']}\"", "falta",
                  "o código do documento não está na Tabela URS, e a descrição não permite achá-lo" if inexistente else
                  "sem código TUSS e sem descrição que permita achá-lo na Tabela URS")
            a.pendencias.append(codigo_pendencia("Código TUSS inexistente" if inexistente else
                                                 "Descrição do procedimento genérica") or "C5")
            a.falta.append(f"descrição inequívoca do procedimento ou o código TUSS do item \"{item['descricao']}\"")
            a.citar("ART-34")
            continue
        teto = lambda c: Decimal(a.p.linhas[c]["teto_urs"]) if a.p.linhas[c].get("teto_urs") is not None else Decimal(0)  # noqa: E731
        codigo = min(codigos, key=teto)
        linha = a.p.linhas[codigo]
        item.update(codigo_tuss=codigo, na_tabela=True, categoria_tabela=linha["categoria_tabela"])
        a.req("art. 34", f"procedimento do item \"{item['descricao']}\"", "cumprido",
              f"sem código no documento; classificado pela descrição como {linha['descricao']} ({codigo})"
              + ("; havia mais de um código possível, vale o de menor teto" if len(codigos) > 1 else ""))
        a.citar("ART-34", codigo)
    if not a.itens:   # nenhum procedimento do documento consta da Tabela
        return Decisao("NEGADO", regras=["ART-56"], motivo="o procedimento não consta da Tabela URS (art. 56)",
                       **a.base())
    return None


# ---- 4: alçada. OPME de novo (item classificado agora); cirurgia vai a analista (D78: não é categoria da NT-02 nem
# tem carência, caso omisso do art. 83); valor solicitado acima do limite (art. 78, § 1º)
def n_alcada(a: Analise) -> Decisao | None:
    if d := _opme(a):
        return d
    if a.molde.get("moeda_estrangeira"):
        # despesa no exterior: converte-se pela taxa de câmbio de venda do dia do atendimento (art. 69; NT-02, Caso 26),
        # que a análise automatizada não tem; com o valor em outra moeda, nem a alçada se confere (D93)
        a.req("art. 69", "conversão da despesa em moeda estrangeira", "analista",
              "o valor ainda não foi convertido: o analista converte pela taxa de câmbio de venda do dia do atendimento")
        return Decisao("ESCALADO_ANALISTA", regras=["ART-69"], escalar=True,
                       motivo="despesa em moeda estrangeira: a conversão pelo câmbio do dia do atendimento (art. 69) é "
                              "feita na análise humana", **a.base())
    if any(i.get("categoria_tabela") == "Procedimento cirúrgico" for i in a.itens):
        a.req("art. 83", "procedimento cirúrgico ou hospitalar", "analista",
              "a NT-02 não tem categoria nem a norma tem carência para ele: caso omisso, resolvido pela área de análise")
        return Decisao("ESCALADO_ANALISTA", regras=["ART-83"], escalar=True,
                       motivo="procedimento cirúrgico ou hospitalar: caso omisso, vai a analista (art. 83)", **a.base())
    limites = a.p.todos("ART-78", "§ 1º", "alcada_brl", a.dia)
    limite = next((l for l in limites if "cirúrg" not in (l.escopo or "")), limites[0])
    solicitado = a.molde.get("c6_valor_total")
    if solicitado is not None and Decimal(str(solicitado)) > limite.valor:
        a.req("art. 78, § 1º", "alçada da análise automatizada", "analista",
              f"valor solicitado {_rs(solicitado)}, acima do limite de {_rs(limite.valor)}")
        return Decisao("ESCALADO_ANALISTA", regras=["ART-78"], escalar=True,
                       motivo=f"valor solicitado acima do limite de R$ {limite.valor} (art. 78, § 1º)", **a.base())
    a.req("art. 78, § 1º", "alçada da análise automatizada", "cumprido",
          f"valor solicitado {_rs(solicitado or 0)}; limite {_rs(limite.valor)}")
    return None


# ---- 5.1: contrato ativo (art. 30). O MCP dá a situação de hoje, não a da data do atendimento
def n_contrato(a: Analise) -> Decisao | None:
    if str(a.beneficiario.get("status", "")).upper() != "ATIVO":
        a.req("art. 30", "contrato ativo", "impede", f"situação de hoje no cadastro: {a.beneficiario.get('status')}")
        return Decisao("NEGADO", regras=["ART-30"], motivo="contrato não ativo", **a.base())
    a.req("art. 30", "contrato ativo", "cumprido", "situação de hoje no cadastro")
    return None


# ---- 5.3: carência de cada item, pela categoria dele e pela data dele (arts. 21 a 24; a da terapia, sessão a sessão,
# art. 24, parágrafo único); urgência declarada dispensa (art. 26)
def n_carencia(a: Analise) -> Decisao | None:
    adesao = date.fromisoformat(a.beneficiario["data_adesao"])
    cumpridas: dict[str, str] = {}
    negadas = []
    for item in list(a.itens):
        art = artigo_carencia(a.categoria(item))
        if not art:
            continue
        num = f"art. {art.split('-')[1]}"
        if a.molde.get("urgencia_declarada"):
            cumpridas.setdefault(num, "")
            a.citar("ART-26")
            continue
        dia = a.data(item)
        carencia = a.p.valor(art, "caput", "carencia_dias", dia).valor
        dias = (dia - adesao).days
        if dias < carencia:
            # a data em que a carência se cumpre vai pronta: a resposta errava a conta por um dia (D82)
            a.req(num, "carência", "impede", f"{dias} dias da adesão ({adesao:%d/%m/%Y}) até o atendimento de "
                  f"{dia:%d/%m/%Y}; o mínimo é {carencia}; atendimentos a partir de "
                  f"{adesao + timedelta(days=int(carencia)):%d/%m/%Y} já cumprem essa carência")
            negadas.append((art, carencia))
            a.sai(item, f"atendimento de {dia:%d/%m/%Y} antes da carência de {carencia} dias")
        else:
            cumpridas.setdefault(num, f"{dias} dias da adesão até o atendimento; o mínimo é {carencia}")
    for num, detalhe in cumpridas.items():
        if detalhe:
            a.req(num, "carência", "cumprido", detalhe)
        else:
            a.req("art. 26", "carência", "não se aplica", "o documento declara atendimento de urgência")
    if negadas:
        a.citar("ART-21", *[art for art, _ in negadas])
        if not a.itens:
            art, carencia = negadas[-1]
            return Decisao("NEGADO", regras=list(a.regras), motivo=f"carência de {carencia} dias não cumprida",
                           **a.base())
    return None


# ---- 5.4: mais de uma consulta com o mesmo profissional em 15 dias (art. 36; NT-02, Caso 34): no mesmo documento, o
# profissional é o mesmo; a especialidade é a da linha da Tabela (§ 2º). Sem justificativa clínica no
# documento (§ 1º), a consulta seguinte não é reembolsável e sai do cálculo. O histórico não traz o profissional dos
# pedidos anteriores: só se confere dentro do documento (D93)
def n_consulta_repetida(a: Analise) -> Decisao | None:
    consultas = sorted([i for i in a.itens if a.categoria(i) == "CONSULTA_MEDICA"], key=a.data)
    if len(consultas) < 2 or a.molde.get("c10_indicacao_clinica"):
        return None
    intervalo = a.p.unico("intervalo_consultas_dias", a.dia).valor
    anterior: dict[str, date] = {}
    for item in consultas:
        # a especialidade é a da linha da Tabela antes do travessão ("Consulta em clínica médica — consulta de
        # retorno"): consulta e retorno da mesma especialidade contam juntos
        descricao = a.p.linhas.get(item.get("codigo_tuss") or "", {}).get("descricao") or item["descricao"]
        dia, codigo = a.data(item), descricao.split("—")[0].strip().lower()
        if codigo in anterior and (dia - anterior[codigo]).days < intervalo:
            a.req("art. 36", f"consulta de {dia:%d/%m/%Y} com o mesmo profissional", "impede",
                  f"{(dia - anterior[codigo]).days} dias depois da consulta de {anterior[codigo]:%d/%m/%Y}; o mínimo, sem "
                  f"justificativa clínica no documento ou em relatório, é {intervalo}")
            a.sai(item, f"segunda consulta com o mesmo profissional em menos de {intervalo} dias, sem justificativa "
                        "clínica (art. 36)")
            a.citar("ART-36")
            continue
        anterior[codigo] = dia
    return None


# ---- 5.5: prazo para pedir, da data do atendimento (com várias sessões, da última) até hoje (arts. 12 e 13)
def n_prazo(a: Analise) -> Decisao | None:
    prazo = a.p.valor("ART-12", "caput", "prazo_dias", a.dia)
    passados = (a.hoje - a.dia).days
    if passados > prazo.valor:
        a.req("art. 12", "prazo para pedir", "impede", f"{passados} dias do atendimento até o pedido; o máximo é "
              f"{prazo.valor}")
        return Decisao("NEGADO", regras=a.p.grafo.fundamentos("ART-12", a.dia, partes=["caput"]),
                       motivo=f"pedido feito depois do prazo de {prazo.valor} dias", **a.base())
    a.req("art. 12", "prazo para pedir", "cumprido", f"{passados} dias do atendimento até o pedido; o máximo é "
          f"{prazo.valor}")
    return None


def prazo_sem_decisao(molde: dict, hoje: date) -> str | None:
    """O prazo para pedir (art. 12) depende só da data do atendimento no documento: a resposta pode dizê-lo antes de a
    decisão rodar, que espera a carteirinha. Sem ele, os dados diziam só "sem decisão", e a resposta a "ainda dá para
    pedir?" dizia que sim a um pedido fora do prazo (D89). Vale a data mais recente do documento (art. 13, § 2º)."""
    datas = [d for d in [molde.get("c4_data_atendimento"), *(i.get("data") for i in molde.get("c5_itens") or [])] if d]
    if not datas:
        return None
    dia = max(date.fromisoformat(d) for d in datas)
    prazo = Parametros.carregar().valor("ART-12", "caput", "prazo_dias", dia).valor
    passados = (hoje - dia).days
    return (f"prazo para pedir (art. 12, na redação vigente na data do atendimento, {dia:%d/%m/%Y}): {passados} dias do "
            f"atendimento até hoje; o máximo é {prazo}"
            + ("; o prazo já passou: o pedido é indeferido por decadência, seja qual for o cadastro (art. 12, parágrafo "
               "único)" if passados > prazo else "; está dentro do prazo"))


# ---- 6: campos obrigatórios (NT-02, C1 a C7); várias sessões ou procedimentos num valor só (NT-02, 4.4; Caso 03)
def n_campos(a: Analise) -> Decisao | None:
    nomes = campos()
    faltando = list(a.molde.get("campos_faltando") or [])
    a.pendencias += a.molde.get("pendencias") or []
    juntos = [i for i in a.itens if (i.get("quantidade") or 1) > 1]
    if juntos and "C6" not in faltando:
        faltando.append("C6")
        a.pendencias.append(codigo_pendencia("Valor global sem discriminação") or "C6")
    if faltando:
        a.falta.append("novo recibo ou nota em que constem: " + "; ".join(nomes.get(c, c) for c in faltando)
                       + (" (o documento traz várias sessões ou procedimentos sem a discriminação do valor de cada "
                          "um)" if juntos else ""))
        a.req("NT-02, campos C1 a C7", "campos obrigatórios do documento fiscal", "falta",
              "; ".join(nomes.get(c, c) for c in faltando))
    else:
        a.req("NT-02, campos C1 a C7", "campos obrigatórios do documento fiscal", "cumprido")
    return None


# ---- 7.1 e 6.9: terapia, sessão a sessão. Limite de sessões no ano (art. 40) e relatório clínico (art. 73, § 3º),
# contadas pelo histórico, somadas todas as terapias (art. 41, § 3º; art. 42, § 2º)
def n_terapia(a: Analise) -> Decisao | None:
    terapias = sorted([i for i in a.itens if a.categoria(i) == "SESSAO_TERAPIA"], key=a.data)
    if not terapias:
        return None
    antes = sum(1 for h in a.mesmo_ano() if (h.get("categoria") or "").upper() == "SESSAO_TERAPIA"
                and h["data"] < a.data(terapias[0]).isoformat())
    limite = a.p.unico("limite_sessoes_ano", a.dia).valor
    exige, porque, feitas = False, "", antes
    for item in terapias:
        # um item com várias sessões num valor só conta todas elas (a pendência de discriminação sai no nó 6)
        primeira, n = feitas + 1, feitas + (item.get("quantidade") or 1)
        dia = a.data(item)
        a.sessao[id(item)] = feitas
        feitas = n
        if primeira > limite:
            del a.sessao[id(item)]
            a.req("art. 40", "limite de sessões no ano", "impede", f"a sessão de {dia:%d/%m/%Y} seria a {primeira}ª do "
                  f"ano pelo histórico; o máximo é {limite}")
            a.sai(item, f"sessão acima do limite de {limite} no ano")
            continue
        a_partir = a.p.valor("ART-73", "§ 3º", "relatorio_a_partir_da_sessao", dia).valor
        excede = a.p.valor("ART-73", "§ 3º", "relatorio_excedente_teto_pct", dia).valor
        acima = False
        # o valor de várias sessões juntas não é o valor pago na sessão: fica para quando vier discriminado (nó 6)
        if item.get("codigo_tuss") in a.p.linhas and item.get("valor") is not None and (item.get("quantidade") or 1) == 1:
            teto_urs, _, _ = _teto_urs(a.p, item["codigo_tuss"], dia, n - 1)
            acima = Decimal(str(item["valor"])) > teto_urs * a.p.valor_urs(dia) * (1 + excede / 100)
        if (n >= a_partir or acima) and not exige:
            exige, regras_rel = True, a.p.grafo.fundamentos("ART-73", dia, partes=["§ 3º"])
            porque = (f"a sessão de {dia:%d/%m/%Y} é a {n}ª do ano, e o relatório é exigido a partir da {a_partir}ª"
                      + ("; o valor pago passa do teto em mais do que o permitido" if acima else ""))
        elif not exige:
            porque = f"esta é a {n}ª sessão do ano; o relatório é exigido a partir da {a_partir}ª"
    vistas = [a.sessao[id(i)] + 1 for i in terapias if id(i) in a.sessao]
    if not vistas:
        if not a.itens:
            return Decisao("NEGADO", regras=["ART-40"], motivo=f"limite de {limite} sessões no ano atingido",
                           **a.base())
        return None
    a.req("art. 40", "limite de sessões no ano", "cumprido",
          (f"esta é a {vistas[0]}ª sessão do ano" if len(vistas) == 1 else
           f"são as sessões {vistas[0]}ª a {vistas[-1]}ª do ano") + f" pelo histórico; o máximo é {limite}")
    if not exige:
        a.req("art. 73, § 3º", "relatório clínico do profissional assistente", "não se aplica", porque)
        return None
    a.citar(*regras_rel)
    relatorios = [c["molde"] for c in a.complementares if c["molde"].get("classificacao") == "RELATORIO_CLINICO"]
    com_manutencao = [r for r in relatorios if r.get("indica_manutencao_tratamento")]
    if any(r.get("c7_assinatura", True) for r in com_manutencao):
        a.req("art. 73, § 3º", "relatório clínico do profissional assistente", "cumprido", "relatório recebido")
    elif com_manutencao:   # o relatório é firmado pelo profissional (art. 73, § 3º; NT-02, Anexo D, 8.1, VII; P22)
        a.pendencias.append(codigo_pendencia("Relatório clínico não assinado") or "C8")
        a.falta.append("relatório clínico assinado pelo profissional assistente (o relatório enviado não tem assinatura)")
        a.req("art. 73, § 3º", "relatório clínico do profissional assistente", "falta",
              "o relatório enviado não está assinado")
    elif relatorios:   # o relatório tem de indicar a manutenção do tratamento (NT-02, Anexo D, 8.1, VI; P21)
        a.pendencias.append(codigo_pendencia("Relatório clínico sem indicação de manutenção") or "C8")
        a.falta.append("relatório clínico com a indicação expressa de manutenção do tratamento (o relatório enviado "
                       "não traz essa indicação)")
        a.req("art. 73, § 3º", "relatório clínico do profissional assistente", "falta",
              "o relatório enviado não indica a manutenção do tratamento")
    else:
        a.pendencias.append(codigo_pendencia("Relatório clínico exigido") or "C8")
        a.falta.append(f"relatório clínico do profissional ({porque})")
        a.req("art. 73, § 3º", "relatório clínico do profissional assistente", "falta", porque)
    return None


# ---- 6.10: exame de alta complexidade (marcado na Tabela URS com o art. 38): sem o pedido médico, pendência do
# campo C9 (art. 38, § 2º; NT-02, Caso 23); dispensado na urgência (art. 38, § 3º)
def n_pedido_medico(a: Analise) -> Decisao | None:
    alta = [i for i in a.itens if "ART-38" in (a.p.linhas.get(i.get("codigo_tuss") or "", {}).get("artigos") or [])]
    pedidos = [c["molde"] for c in a.complementares if c["molde"].get("classificacao") == "PEDIDO_MEDICO"]
    # válido por N dias da emissão (NT-02, 9.2): o vencido não serve. A data da solicitação é requisito do pedido (NT-02,
    # 9.1, IV): sem ela não há como saber se vale, e o pedido não serve (D92; antes, sem data, ele valia)
    exame = min((a.data(i) for i in alta), default=a.dia)
    validos = [m for m in pedidos if m.get("c4_data_atendimento") and (
        exame - date.fromisoformat(m["c4_data_atendimento"])).days <= validade_pedido_medico()]
    if alta and a.molde.get("urgencia_declarada"):
        a.req("art. 38, § 3º", "pedido médico do exame de alta complexidade", "não se aplica",
              "o documento declara atendimento de urgência")
    elif alta and not a.molde.get("c9_pedido_medico") and not validos:
        a.citar("ART-38")
        a.pendencias.append(codigo_pendencia("Pedido médico ausente") or "C9")
        vencido = ("" if not pedidos else
                   f"; o enviado foi emitido há mais de {validade_pedido_medico()} dias do exame (NT-02, 9.2)"
                   if any(m.get("c4_data_atendimento") for m in pedidos) else
                   "; o enviado não traz a data da solicitação, que o pedido precisa ter (NT-02, 9.1, IV)")
        a.falta.append("pedido médico do profissional que solicitou o exame (exame de alta complexidade, art. 38"
                       + vencido + ")")
        a.req("art. 38", "pedido médico do exame de alta complexidade", "falta",
              "a Tabela URS marca o exame como de alta complexidade" + vencido)
    elif alta and not a.molde.get("c9_pedido_medico") and not any(
            m.get("c2_prestador_nome") and m.get("c3_registro_conselho") for m in validos):
        # o pedido identifica o solicitante e o registro dele no conselho (art. 38, § 1º; P24)
        a.citar("ART-38")
        a.pendencias.append(codigo_pendencia("Pedido médico sem identificação") or "C9")
        a.falta.append("pedido médico com o nome e o registro no conselho do profissional que o solicitou")
        a.req("art. 38, § 1º", "pedido médico do exame de alta complexidade", "falta",
              "o pedido enviado não identifica o profissional solicitante e o registro dele")
    elif alta:
        a.req("art. 38", "pedido médico do exame de alta complexidade", "cumprido", "pedido médico recebido")
    elif any(a.categoria(i) == "EXAME_DIAGNOSTICO" for i in a.itens):
        a.req("art. 38", "pedido médico", "não se aplica", "o exame não é de alta complexidade na Tabela URS")
    return None


# ---- 6: as pendências saem todas de uma vez (art. 18, § 1º); o cliente tem o prazo do art. 19 para sanar
def n_pendencias(a: Analise) -> Decisao | None:
    if not a.pendencias:
        return None
    prazo = a.p.valor("ART-19", "caput", "prazo_sanar_dias", a.hoje).valor
    a.req("art. 19", "prazo para enviar o que falta", "falta",
          f"{prazo} dias corridos a partir deste aviso, prorrogáveis uma vez; o pedido fica aberto, sem valor até lá")
    return _pendente(a)


# ---- 7.4: relatório clínico apresentado sozinho: uma vez por ano civil (NT-02, Caso 36; Tabela, TUSS-10104011)
def n_relatorio_isolado(a: Analise) -> Decisao | None:
    if a.molde["classificacao"] != "RELATORIO_CLINICO":
        return None
    if any((h.get("categoria") or "").upper() == "RELATORIO_CLINICO" for h in a.mesmo_ano()):
        a.req("NT-02, Caso 36", "relatório apresentado sozinho, uma vez por ano civil", "impede",
              f"já há relatório clínico reembolsado em {a.dia.year} pelo histórico")
        return Decisao("NEGADO", regras=["NT-02"], motivo="relatório clínico apresentado sozinho é reembolsável uma vez "
                       "por ano civil, e já houve um neste ano", **a.base())
    a.req("NT-02, Caso 36", "relatório apresentado sozinho, uma vez por ano civil", "cumprido",
          "primeiro relatório do ano pelo histórico")
    return None


# ---- 8: cálculo, item a item (Título IV; app/calculo)
def n_calculo(a: Analise) -> Decisao:
    reembolsado = sum((Decimal(h["valor_reembolsado"]) for h in a.mesmo_ano()), Decimal(0))
    antes_doc = sum(1 for h in a.mesmo_ano() if (h.get("categoria") or "").upper() == "SESSAO_TERAPIA"
                    and h["data"] < a.dia.isoformat())
    total, parcial, regras, memoria = Decimal(0), False, [], list(a.fora)
    calculados, base = 0, Decimal(0)
    adesao = date.fromisoformat(a.beneficiario["data_adesao"])
    for item in a.itens:
        if not item.get("codigo_tuss") or item["codigo_tuss"] not in a.p.linhas or item.get("valor") is None:
            falta = "valor" if item.get("valor") is None else "código na tabela"
            memoria.append(f"item sem {falta} não entra no cálculo: {item['descricao']}")
            continue
        calculados += 1
        base += Decimal(str(item["valor"]))
        r = apurar(item["codigo_tuss"], Decimal(str(item["valor"])), a.data(item), a.beneficiario["plano"], adesao,
                   reembolsado + total, a.sessao.get(id(item), antes_doc))
        total += r.valor_reembolso
        parcial = parcial or r.parcial
        regras += [x for x in r.regras if x not in regras]
        if len(a.itens) > 1:   # com vários itens, cada linha diz de que item é (D85): com duas sessões iguais, a
            # resposta tomava as contas de uma sessão pelo pedido todo
            rotulo = item["descricao"] + (f" de {a.data(item):%d/%m/%Y}" if item.get("data") else "")
            memoria += [f"{rotulo}: {linha}" for linha in r.memoria]
        else:
            memoria += r.memoria
    if calculados > 1:
        memoria.append(f"total a reembolsar, somados os {calculados} itens: R$ {total:.2f}")
    if not calculados:   # nada para calcular não é limite esgotado: um analista confere o documento
        a.req("Tabela URS", "código e valor de cada item", "analista",
              "nenhum item do documento tem código da tabela e valor para o cálculo")
        return Decisao("ESCALADO_ANALISTA", escalar=True, memoria=memoria,
                       motivo="nenhum item do documento tem código da tabela e valor para o cálculo", **a.base())
    solicitado = a.molde.get("c6_valor_total")
    a.req("art. 43", "valor que entra no cálculo", "cumprido", f"{_rs(base)}"
          + (f" dos {_rs(solicitado)} do documento; fora do cálculo: " + "; ".join(a.fora)
             if a.fora and solicitado is not None else ""))
    saldo = max(Decimal(0), a.p.unico("limite_anual_urs", a.dia).valor * a.p.valor_urs(a.dia) - reembolsado)
    if total == 0:
        a.req("art. 45", "saldo do limite anual de reembolso", "impede", "o limite anual já foi usado no ano civil")
        return Decisao("NEGADO", regras=regras + ["ART-45"], motivo="limite anual de reembolso esgotado (o limite é "
                       "por beneficiário no ano civil, somados os reembolsos de todos os procedimentos)",
                       memoria=memoria, **a.base())
    a.req("art. 45", "saldo do limite anual de reembolso", "cumprido",
          f"saldo de {_rs(saldo)} antes deste pedido" + ("; o saldo limitou o valor" if parcial else ""))
    regras = a.regras + [x for x in regras if x not in a.regras]
    return Decisao("APROVADO_PARCIAL" if parcial else "APROVADO", valor_reembolso=float(total), regras=regras,
                   memoria=memoria, **a.base())


# A árvore, na ordem da NT-02, 6.1 (o número é o nó em docs/analise_erros/arvore_de_decisao.md)
ARVORE = [
    ("6.4", n_data),               # data do atendimento
    ("3", n_anexo_iv),             # exclusão do Anexo IV, item a item; material avulso (4.11) vai a analista
    ("2.2", n_sem_codigo),         # item sem código, pela descrição
    ("4", n_alcada),               # alçada; cirurgia vai a analista
    ("5.1", n_contrato),           # contrato ativo
    ("5.3", n_carencia),           # carência, item a item
    ("5.4", n_consulta_repetida),  # segunda consulta com o mesmo profissional em 15 dias
    ("5.5", n_prazo),              # prazo para pedir
    ("6", n_campos),               # campos obrigatórios e valor por item
    ("6.9", n_terapia),            # limite de sessões e relatório da terapia
    ("6.10", n_pedido_medico),     # pedido médico da alta complexidade
    ("6.13", n_pendencias),        # pendências de uma vez, com o prazo do art. 19
    ("7.4", n_relatorio_isolado),  # relatório sozinho, uma vez por ano
    ("8", n_calculo),              # cálculo
]
