"""Conteúdo da ficha: ``row -> sobrescritas de célula + extras`` (puro, sem PDF)."""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple

from openpyxl.utils import get_column_letter

from .constants import CID_COL_DIR, CONSULTAS_FIM, CONSULTAS_INI, RACAS, SEXOS, TIPOS_LOGRADOURO
from .template import Modelo, carregar_modelo
from .text import valor_texto, formatar, formatar_cep, nome_estabelecimento, procedimento_completo, rotulo_coluna

# ---------------------------------------------------------------------------
# Montagem da ficha (puro: linha -> sobrescritas de célula + extras)
# ---------------------------------------------------------------------------

def _caixa(texto: str, marcado: bool) -> str:
    """Marca o primeiro ``(      )`` do texto com um X, preservando o tamanho."""
    if not marcado:
        return texto
    m = re.search(r"\(\s*\)", texto)
    if not m:
        return texto
    interno = m.end() - m.start() - 2
    meio = max(int(interno / 2), 0)
    dentro = " " * meio + "X" + " " * max(interno - meio - 1, 0)
    return texto[:m.start()] + "(" + dentro + ")" + texto[m.end():]


def _caixa_do_codigo(texto: str, codigo: str) -> str:
    """Marca o checkbox que antecede ``codigo`` (ex.: motivo de saída 11)."""
    if not codigo or not texto:
        return texto
    m = re.search(r"\(\s*\)(\s*)" + re.escape(codigo) + r"(?!\d)", texto)
    if not m:
        return texto
    inicio = m.start()
    meio_txt = texto[inicio:m.end()]
    novo = _caixa(meio_txt, True)
    return texto[:inicio] + novo + texto[m.end():]


def _rotulo_celula(modelo: Modelo, linha: int, coluna: int) -> str:
    """Texto do rótulo do campo (célula à esquerda ou acima, terminada em ':')."""
    for c in range(coluna - 1, 0, -1):
        info = modelo.celulas.get(modelo.ancre(linha, c))
        if not info:
            continue
        texto = (info.get("valor") or "").strip()
        if texto:
            return texto if texto.endswith(":") else ""
    for l in range(linha - 1, max(linha - 4, 0), -1):
        info = modelo.celulas.get(modelo.ancre(l, coluna))
        if not info:
            continue
        texto = (info.get("valor") or "").strip()
        if texto:
            return texto if texto.endswith(":") else ""
    return ""


def _montar_blocos(modelo: Modelo, sobre: Dict[str, str],
                   adicionais: Optional[Dict[str, Sequence[Tuple[str, str, str]]]] = None,
                   ) -> List[Dict[str, Any]]:
    """Inventário do que cada seção do formulário imprime: ``(rótulo, valor)``.

    Percorre as seções do modelo na ordem em que aparecem, usando o valor da
    célula (sobrescrito pela linha do paciente, quando houver) e o rótulo que a
    antecede no próprio formulário. Assim os blocos refletem a ficha impressa,
    incluindo as listas fixas do modelo (procedimentos, CIDs, motivo de saída).
    """
    blocos: List[Dict[str, Any]] = []
    for titulo, r1, r2 in modelo.secoes:
        itens: List[Tuple[str, str, str]] = []
        for linha in range(r1, r2 + 1):
            for coluna in range(1, modelo.n_colunas + 1):
                info = modelo.celulas.get((linha, coluna))
                if info is None:
                    continue
                faixa = modelo.merges.get((linha, coluna))
                if faixa and (faixa[0], faixa[1]) != (linha, coluna):
                    continue                    # só a âncora da mesclagem
                ref = f"{get_column_letter(coluna)}{linha}"
                valor = str(sobre.get(ref, info["valor"]) or "").strip()
                if not valor or not any(ch.isalnum() for ch in valor):
                    continue
                if valor.endswith(":") and ref not in sobre:
                    continue                    # rótulo do próprio formulário
                itens.append((_rotulo_celula(modelo, linha, coluna) or ref,
                              valor, "texto"))
        itens.extend((adicionais or {}).get(titulo, ()))
        if itens:
            blocos.append({"titulo": titulo, "itens": itens})
    return blocos


def _linhas_em_branco(modelo: Modelo, sobre: Dict[str, str],
                      ocultar: Set[int]) -> Set[int]:
    """Linhas do formulário sem nenhuma tinta: sem texto, sem borda e sem
    fundo colorido (e fora de mesclagem, que liga a linha às vizinhas).

    Apagá-las não muda um traço do desenho — só devolve o espaço em branco
    que elas ocupavam, que é o que faz a ficha caber em uma página.
    """
    brancas: Set[int] = set()
    for linha in range(1, modelo.linhas_total + 1):
        if modelo.alturas[linha - 1] <= 0 or linha in ocultar:
            continue
        if any(modelo.merges.get((linha, c))
               for c in range(1, modelo.n_colunas + 1)):
            continue
        tem_tinta = False
        for coluna in range(1, modelo.n_colunas + 1):
            info = modelo.celulas.get((linha, coluna))
            if not info:
                continue
            ref = f"{get_column_letter(coluna)}{linha}"
            texto = sobre.get(ref, info["valor"])
            fundo = str(info.get("fill") or "").lstrip("#").upper()
            if (texto and str(texto).strip()) or info["bordas"] \
                    or (fundo and fundo != "FFFFFF"):
                tem_tinta = True
                break
        if not tem_tinta:
            brancas.add(linha)
    return brancas


def montar_ficha(row: Any) -> Dict[str, Any]:
    """Converte a linha da planilha no preenchimento da ficha do modelo.

    Retorna:

    * ``sobrescritas`` — ``{coordenada: texto}`` aplicado sobre o template
      (células de dados marcadas nos checklists inclusive);
    * ``cobertos`` — colunas da linha refletidas na ficha;
    * ``extras`` — colunas restantes (página final "OUTROS DADOS DA LINHA");
    * ``blocos`` — seções do formulário (``titulo`` + ``itens``
      ``(rótulo, valor, tipo)``) e a página final "OUTROS DADOS DA LINHA".

    Toda a linha é coberta: ``cobertos | {colunas de extras} == row.keys()``.
    """
    modelo = carregar_modelo()
    valores: Dict[str, str] = {}
    try:
        for chave, valor in dict(row).items():
            valores[valor_texto(chave)] = valor_texto(valor)
    except (TypeError, ValueError):  # linha que não é mapeável: nada a copiar
        pass

    cobertos: Set[str] = set()
    exibidos: Set[str] = set()
    sobre: Dict[str, str] = {}
    # O formulário tem listas fixas (procedimentos, CIDs): imprimir as opções
    # que o paciente não tem só ocupa espaço. ``ocultar`` são as linhas que
    # saem da ficha e ``suprimir`` as células que não devem ser desenhadas
    # (a metade sem marcação de uma linha de CID que fica na ficha).
    ocultar: Set[int] = set()
    suprimir: Set[Tuple[int, int]] = set()

    def definir(coords: Sequence[str], valor: str) -> str:
        texto = valor_texto(valor)
        for ref in coords:
            sobre[ref] = texto
        if texto:
            exibidos.add(texto)
        return texto

    def pegar(*colunas: str) -> str:
        """Primeiro valor não vazio. Vazio e vencedor entram em ``cobertos``;
        candidatos com valor que NÃO venceu ficam de fora (vão para extras)."""
        vencedor = None
        for coluna in colunas:
            if valores.get(coluna, "") and vencedor is None:
                vencedor = coluna
        for coluna in colunas:
            if coluna == vencedor or not valores.get(coluna, ""):
                cobertos.add(coluna)
        if vencedor:
            return formatar(vencedor, valores[vencedor])
        return ""    # ----------------------------------------------------------- cabeçalho
    estab = nome_estabelecimento()
    cnes_exec = pegar("Cnes_Executante")
    definir(("I2", "I70"), f"{cnes_exec} {estab}".strip())
    definir(("J3", "J71"), pegar("Numero_Apac"))
    definir(("U3", "U71"), pegar("Cod_Orgao_Emiss"))
    # OCI: usar a descrição do próprio modelo (com acentos corretos) quando
    # o procedimento da linha conhece a descrição do template; senão, base
    # S_PA (que pode vir sem acento).
    proc_bruto = pegar("Cod_Procedimento")
    # OCI: preferir a descrição do próprio modelo (com acentos corretos);
    # o template slim tem C5 vazio; usamos o original completo como
    # fonte do texto com acentuação correta.
    modelo_proc = modelo._valores_originais.get("C5") or ""
    # fallback: se C5 também não tem, tenta a coluna C da primeira linha de
    # procedimento secundário do modelo original (C36 contém o mesmo texto em
    # alguns modelos) ou o texto da célula D36 (descrição do procedimento)
    if not modelo_proc:
        modelo_proc = modelo._valores_originais.get("C36") or ""
    if not modelo_proc:
        for r in range(36, 46):
            v = modelo._valores_originais.get(f"C{r}") or modelo.valor(r, 4)
            if v:
                modelo_proc = v
                break
    if not modelo_proc:
        modelo_proc = modelo._valores_originais.get("D36") or ""
    definir(("C5", "C73"), procedimento_completo(proc_bruto, modelo_proc)) 

    # ------------------------------------------------------- dados paciente
    definir(("C9",), pegar("Cns_Paciente"))
    definir(("K9",), pegar("Cpf_Paciente"))
    definir(("S9",), pegar("Telefone"))
    definir(("G10",), pegar("Nome_Paciente"))

    sexo_bruto = valores.get("Sexo", "")
    if sexo_bruto:
        cobertos.add("Sexo")
        definir(("C12",), sexo_bruto[:1].upper())
        definir(("D12",), SEXOS.get(sexo_bruto[:1].upper(), ""))
    else:
        cobertos.add("Sexo")

    definir(("K12",), pegar("Data_Nascimento"))

    raca_bruta = valores.get("Raca", "")
    cobertos.add("Raca")
    if raca_bruta:
        definir(("U12",), raca_bruta)
        definir(("V12",), RACAS.get(raca_bruta, ""))

    definir(("F13",), pegar("Nome_Da_Mae"))

    cobertos.add("Cep")
    definir(("C15",), formatar_cep(valores.get("Cep", "")))

    # logradouro: código da via (J15), tipo (K15) e nome (L15)
    cod_via = (valores.get("Codigo_Logradouro", "")
               or re.sub(r"\D", "", valores.get("Logradouro", "")))
    rua = valores.get("Rua", "")
    if not rua and valores.get("Logradouro", "") and not cod_via:
        rua = valores.get("Logradouro", "")
    cobertos.update(("Codigo_Logradouro", "Logradouro", "Rua"))
    tipo = TIPOS_LOGRADOURO.get(cod_via, "")
    if not tipo and rua:
        m = re.match(r"^((?:RUA|AV\.?|AVENIDA|EST\.?|ESTRADA|TRAVESSA|ALAMEDA)"
                     r"(?:\s+[A-Z]\.)?)\s+(.*)$", rua, re.I)
        if m:
            tipo = m.group(1).upper()
            rua = m.group(2)
        else:
            tipo = ""
    elif tipo and rua.upper().startswith(tipo.rstrip(".")):
        resto = rua[len(tipo.rstrip(".")):].strip(" .-")
        rua = resto
    definir(("J15",), cod_via if not cod_via.isdigit() or len(cod_via) <= 3
            else cod_via)
    definir(("K15",), tipo)
    definir(("L15",), rua)
    definir(("X15",), pegar("Numero_Endereco"))
    definir(("F16",), pegar("Complemento"))
    definir(("J16",), pegar("Bairro"))
    definir(("U16",), pegar("Nome_Municipio", "Codigo_Municipio", "IBGE"))

    # ---------------------------------------------------- dados solicitante
    definir(("C21",), pegar("Cnes_Solicitante"))
    definir(("K21",), estab)
    definir(("K22",), pegar("Nome_Profissional", "Medico_Nome", "Autorizador_Nome"))
    definir(("J23",), pegar("Medico_Cns", "Autorizador_Cns"))
    cbo = pegar("Cbo")
    definir(("Q23",), cbo)
    definir(("H24",), pegar("Data_Solicitacao"))

    # ------------------------------------------------------ emissor da OCI
    definir(("G29",), pegar("Medico_Nome", "Autorizador_Nome", "Nome_Profissional"))
    definir(("V29",), pegar("Data_Emissao", "Data_Autorizacao"))
    definir(("F30",), pegar("Medico_Cns", "Autorizador_Cns"))
    definir(("N30",), cbo)
    cnes_terceiro = valores.get("Cnes_Terceiro", "")
    cobertos.add("Cnes_Terceiro")
    definir(("N35",), cnes_terceiro or "PROPRIO")
    definir(("T35",), cbo)

    # ------------------------------------------------------- procedimentos
    # código -> quantidade; colunas da linha que o formulário reflete
    entradas: Dict[str, Dict[str, str]] = {}

    def registrar(col_cod: str, col_cbo: str, col_qtd: str) -> None:
        cod = valores.get(col_cod, "")
        cod9 = re.sub(r"\D", "", cod)[:9]
        if not cod9:
            return
        entradas[cod9] = {"qtd": valores.get(col_qtd, ""),
                          "cols": f"{col_cod}|{col_cbo}|{col_qtd}"}

    registrar("Cod_Procedimento", "Cbo", "Quantidade")
    for i in range(1, 9):
        registrar(f"Sec{i}_Cod_Procedimento", f"Sec{i}_Cbo", f"Sec{i}_Quantidade")

    def cobrir_trio(cod9: str) -> str:
        entrada = entradas.get(cod9)
        if not entrada:
            return ""
        for coluna in entrada["cols"].split("|"):
            cobertos.add(coluna)
        return entrada["qtd"]

    for linha, cod9 in modelo.proc_linhas:
        if cod9 not in entradas:
            ocultar.add(linha)      # procedimento que o paciente não fez
            continue
        original = modelo.valor(linha, 2) or "(       )"
        definir((f"B{linha}",), _caixa(original, True))
        qtd = cobrir_trio(cod9)
        if qtd:
            definir((f"W{linha}",), qtd)

    for linha, cod9 in modelo.geral_linhas:
        if cod9 not in entradas:
            ocultar.add(linha)      # consulta/procedimento não realizado
            continue
        original = modelo.valor(linha, 2)
        definir((f"B{linha}",), _caixa(original, True))
        definir((f"R{linha}",), cbo)
        qtd = cobrir_trio(cod9)
        if qtd:
            definir((f"V{linha}",), qtd)

    # Nenhuma consulta da lista feita? Então a seção inteira sai — título e
    # nota de uma lista vazia só ocupariam espaço.
    if modelo.geral_linhas and all(r in ocultar for r, _ in modelo.geral_linhas):
        ocultar.update(range(CONSULTAS_INI, CONSULTAS_FIM + 1))

    # Por último, as linhas de puro espaço em branco do próprio formulário
    # (nada é desenhado nelas): também saem, para a ficha caber em 1 página.
    ocultar |= _linhas_em_branco(modelo, sobre, ocultar)

    # ----------------------------------------------------------- diagnósticos
    def codigos_cid(coluna: str) -> List[str]:
        return [c for c in re.split(r"[,;/\s]+", valores.get(coluna, "")) if c]

    cids_marcados: Set[str] = set()
    for coluna in ("Cid_Princ", "Cid_Secun", "Cid_Causas_Assoc"):
        cods = [c.upper() for c in codigos_cid(coluna)]
        if not cods:
            cobertos.add(coluna)
            continue
        if all(c in {c for _, c in modelo.cid_esq} | {c for _, c in modelo.cid_dir}
               for c in cods):
            cids_marcados.update(cods)
            cobertos.add(coluna)
    # A tabela de CIDs é um catálogo do modelo (H00..H59, C69x); a ficha fica
    # só com o(s) CID(s) do paciente — a linha em que ele está marcado. As
    # demais linhas saem, e a metade sem marcação não é desenhada.
    cid_esq = dict(modelo.cid_esq)
    cid_dir = dict(modelo.cid_dir)
    for linha in sorted(set(cid_esq) | set(cid_dir)):
        cod_esq = cid_esq.get(linha, "")
        cod_dir = cid_dir.get(linha, "")
        marcado_esq = bool(cod_esq) and cod_esq in cids_marcados
        marcado_dir = bool(cod_dir) and cod_dir in cids_marcados
        if not (marcado_esq or marcado_dir):
            ocultar.add(linha)
            continue
        if marcado_esq:
            original = modelo.valor(linha, 2) or "(      )"
            definir((f"B{linha}",), _caixa(original, True))
        else:
            suprimir.update((linha, col)
                            for col in range(2, CID_COL_DIR))
        if marcado_dir:
            original = modelo.valor(linha, 13) or "(      )"
            definir((f"M{linha}",), _caixa(original, True))
        else:
            suprimir.update((linha, col)
                            for col in range(CID_COL_DIR,
                                             modelo.n_colunas + 1))

    # ---------------------------------------------------------- encerramento
    definir(("J59",), pegar("Medico_Nome", "Autorizador_Nome", "Nome_Profissional"))
    definir(("W59",), cbo)
    definir(("F60",), pegar("Medico_Cns", "Autorizador_Cns"))
    definir(("V60",), pegar("Data_Alta_Obito"))

    motivo = valores.get("Motivo_Saida", "")
    cobertos.add("Motivo_Saida")
    if motivo:
        texto65 = modelo.valor(65, 2)
        texto66 = modelo.valor(66, 2)
        if motivo in {"11", "12", "14", "15"}:
            definir(("B65",), _caixa_do_codigo(texto65, motivo))
        elif motivo == "18":
            definir(("B66",), _caixa_do_codigo(texto66, motivo))
        else:
            cobertos.discard("Motivo_Saida")   # sem campo no formulário

    # -------------------------------------------- assinatura do autorizador
    definir(("I110",), pegar("Autorizador_Cns", "Medico_Cns"))
    definir(("H111",), pegar("Data_Autorizacao"))

    # --------------------------------- colunas cujo valor já está visível
    for coluna, bruto in valores.items():
        if bruto and formatar(coluna, bruto) in exibidos:
            cobertos.add(coluna)

    # Só vai para a página final o que tem informação e não coube no
    # formulário (coluna vazia não é informação — vazio nem é listado).
    extras_cols = [coluna for coluna in valores
                   if coluna not in cobertos]
    # validade: o formulário não tem o par — se um vai para os extras,
    # os dois vão juntos (nunca fica “fim de validade” órfão na ficha)
    if any(c in extras_cols for c in ("Inicio_Validade", "Fim_Validade")):
        for coluna in ("Inicio_Validade", "Fim_Validade"):
            if coluna not in extras_cols:
                extras_cols.append(coluna)
    extras_cols.sort(key=lambda coluna: list(valores).index(coluna))
    # Coluna vazia não é informação: o que o paciente não tem não é listado
    # (só ocuparia espaço na ficha, que agora tem de caber em uma página).
    extras: List[Tuple[str, str, str]] = []
    for coluna in extras_cols:
        valor = formatar(coluna, valores.get(coluna, "")).strip()
        if not valor:
            continue
        extras.append((rotulo_coluna(coluna) + ":", valor, "curto"))

    # sexo/raça: o formulário imprime código e descrição lado a lado
    # ("F" + "FEMININO"); no bloco o par aparece junto, como se lê na ficha.
    pares: List[Tuple[str, str, str]] = []
    for rotulo, ref_a, ref_b in (("SEXO", "C12", "D12"),
                                 ("RAÇA/COR", "U12", "V12")):
        junto = " - ".join(p for p in (sobre.get(ref_a, ""),
                                        sobre.get(ref_b, "")) if p)
        if junto:
            pares.append((rotulo, junto, "texto"))
    blocos: List[Dict[str, Any]] = _montar_blocos(
        modelo, sobre, {"DADOS DO PACIENTE": pares})
    if extras:
        blocos.append({"titulo": "OUTROS DADOS DA LINHA", "itens": extras})
    # Caso especial: linha vazia não deve explodir - mantém blocos
    if not blocos and not valores:
        blocos.append({"titulo": "OUTROS DADOS DA LINHA", "itens": []})

    return {"sobrescritas": sobre, "cobertos": cobertos, "extras": extras,
            "blocos": blocos, "ocultar": ocultar, "suprimir": suprimir}
