"""Demonstrativo por APAC no estilo do relatório R0201 do programa original."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from penna.core import text
from penna.layout import build_patient_lines, header_competence
from penna.layout.constants import MAX_PROCEDIMENTOS_SECUNDARIOS

from . import establishment, formatting
from .formatting import com_dv, digitos
from .locations import SEM_COMPETENCIA, default_remittances_dir

Row = Dict[str, Any]
Procedimento = Tuple[str, str, str]  # (código, CBO, quantidade)


def _procedimentos(serie: Row) -> List[Procedimento]:
    itens = [(digitos(serie.get("Cod_Procedimento")), digitos(serie.get("Cbo")), digitos(serie.get("Quantidade")))]
    for i in range(1, MAX_PROCEDIMENTOS_SECUNDARIOS + 1):
        codigo = digitos(serie.get(f"Sec{i}_Cod_Procedimento"))
        if codigo:
            itens.append((codigo, digitos(serie.get(f"Sec{i}_Cbo")), digitos(serie.get(f"Sec{i}_Quantidade"))))
    return itens


def _cabecalho(apac: str, pagina: int) -> List[str]:
    estrelas = " " + "*" * 78
    return [
        estrelas,
        " MS/SAS/DATASUS      SISTEMA DE INFORMACOES AMBULATORIAIS            DATA COMP.",
        "               DEMONSTRATIVO DE APAC MAGNETICO (PENNA)               ",
        estrelas,
        f" NUMERO DO APAC: {com_dv(apac, 12)}                                       PAG.: {pagina:>4}",
        "",
    ]


def _unidade(serie: Row, est: Dict[str, str], proc_principal: str) -> List[str]:
    cnes = digitos(serie.get("Cnes_Executante"), est.get("cnes", "") or "0").zfill(7)[:7]
    return [
        " IDENTIFICACAO DA UPS/APAC",
        " -------------------------",
        "",
        f" CODIGO DA UNIDADE:             {com_dv(cnes, 6)}",
        f" NOME/RAZAO SOCIAL UPS:         {est['nome']}",
        f" INICIO DA VALIDADE DA APAC:    {formatting.data(serie.get('Inicio_Validade'))}",
        f" FIM DA VALIDADE DO APAC:       {formatting.data(serie.get('Fim_Validade'))}",
        f" PROCEDIMENTO PRINCIPAL:        {com_dv(proc_principal, 9)}",
        f" CNS DO PROFISSIONAL EXECUTANTE :{digitos(serie.get('Cns_Executante'))}     EQUIPE INE: {text(serie.get('INE'))}",
        "",
    ]


def _paciente(serie: Row) -> List[str]:
    sexo = formatting.SEXO.get(text(serie.get("Sexo")).strip().upper()[:1], "")
    raca_cod = digitos(serie.get("Raca")).zfill(2)[:2]
    telefone = digitos(serie.get("Telefone"))
    logradouro = digitos(serie.get("Codigo_Logradouro")) or digitos(serie.get("Logradouro"))
    return [
        " IDENTIFICACAO DO PACIENTE",
        " -------------------------",
        "",
        f" CPF: {formatting.cpf(digitos(serie.get('Cpf_Paciente')))}   PRONTUARIO: {text(serie.get('No_Prontuario'))}",
        f" NOME:               {text(serie.get('Nome_Paciente')).upper()[:30]:<30} ",
        f" LOGRADOURO:         {logradouro:>3}-{text(serie.get('Rua')).upper():<10}",
        f" ENDERECO:           {text(serie.get('Rua')).upper()[:30]:<30}",
        f" NUMERO:             {text(serie.get('Numero_Endereco')):<5}             COMPLEMENTO: {text(serie.get('Complemento'))[:10]}",
        f" CEP:                {formatting.cep(digitos(serie.get('Cep')))}                  BAIRRO: {text(serie.get('Bairro')).upper()[:30]}",
        f" MUNICIPIO:          {digitos(serie.get('Codigo_Municipio')):<6} TEL.: ({telefone[:2]:>2}){telefone[2:]}",
        f" DATA DE NASCIMENTO: {formatting.data(serie.get('Data_Nascimento'))}                   SEXO: {sexo}",
        f" UF DE NASCIMENTO OU NACIONALIDADE: {text(serie.get('Uf_Nascimento')):<3}       RACA: {raca_cod} {formatting.RACA.get(raca_cod, '')}",
        f" NOME DA MAE: {text(serie.get('Nome_Da_Mae')).upper()[:30]}",
        f" NOME DO RES: {text(serie.get('Nome_Do_Responsavel') or serie.get('Nome_Paciente')).upper()[:30]}",
        f" SITUACAO DE RUA: {(text(serie.get('Situacao_De_Rua')).upper()[:1] or 'N')}",
        f" E-MAIL: {text(serie.get('Email'))}",
        " ------------------------------------------------------------------",
        f" C.I.D. PRINCIPAL         {text(serie.get('Cid_Princ')).upper()[:4]} ",
        f"        SECUNDARIO            {text(serie.get('Cid_Secun')).upper()[:4]} ",
        " ------------------------------------------------------------------",
        " MEDICO SOLICITANTE:",
        f" CPF: {formatting.cpf(digitos(serie.get('Medico_Cpf')))}            NOME:   {text(serie.get('Nome_Profissional')).upper()[:30]}",
        f" CNS: {digitos(serie.get('Medico_Cns'))}",
        "",
    ]


def _procedimentos_realizados(procedimentos: List[Procedimento], descricoes: Dict[str, str]) -> List[str]:
    linhas = [
        " PROCEDIMENTOS REALIZADOS:",
        " -------------------------",
        " CODIGO            PROCEDIMENTO        CBO.    QTD.",
    ]
    for codigo, cbo, qtd in procedimentos:
        descricao = descricoes.get(digitos(codigo)[:9], "")[:24]
        linhas.append(f" {com_dv(codigo, 9):<12}{descricao:<24}{cbo:<8}{qtd.zfill(7) if qtd else '0000000'}")
    return linhas


def _desfecho(serie: Row, proc_principal: str) -> List[str]:
    linhas = []
    for regra in establishment.regras_do_procedimento(digitos(proc_principal)[:9]):
        descricao = formatting.DESCRICOES_REGRAS.get(regra, "")
        linhas.append(f" ATENCAO : REGRA CONDICIONADA {regra}{': ' + descricao if descricao else ''}")
    motivo = digitos(serie.get("Motivo_Saida"), "11").zfill(2)[:2]
    return [
        *linhas,
        f" MOTIVO DE SAIDA   : {motivo} / {formatting.MOTIVO_SAIDA.get(motivo, ''):<20}",
        "",
        f" DATA DA OCORRENCIA: {formatting.data(serie.get('Data_Alta_Obito'))}",
        "",
        f" AUTORIZADOR: {formatting.cpf(digitos(serie.get('Autorizador_Cpf')))}       {text(serie.get('Autorizador_Nome')).upper()[:30]}",
        f" CNS: {digitos(serie.get('Autorizador_Cns'))}  COD.ORGAO EMISS.: {text(serie.get('Cod_Orgao_Emiss'))}",
        "",
    ]


def secao_apac(serie: Row, pagina: int, est: Dict[str, str], descricoes: Dict[str, str]) -> str:
    """Uma página do demonstrativo: a APAC de uma linha da planilha."""
    apac = digitos(serie.get("Numero_Apac")).zfill(13)[:13]
    procedimentos = _procedimentos(serie)
    principal = procedimentos[0][0]
    partes = [
        *_cabecalho(apac, pagina),
        *_unidade(serie, est, principal),
        *_paciente(serie),
        *_procedimentos_realizados(procedimentos, descricoes),
        *_desfecho(serie, principal),
    ]
    return "\r\n".join(partes)


def gerar_demonstrativo(df: Any, destino: Optional[Path] = None, pasta_base: Optional[Path] = None) -> Path:
    """Grava o demonstrativo completo por APAC (CP1252) e devolve o caminho."""
    est = establishment.dados_estabelecimento()
    descricoes = establishment.descricoes_procedimentos()
    linhas_df = [dict(serie) for _, serie in df.iterrows()]
    secoes = [secao_apac(dados, pagina, est, descricoes) for pagina, dados in enumerate(linhas_df, start=1)]

    if destino is None:
        competencia = header_competence([linha for dados in linhas_df for linha in build_patient_lines(dados)])
        base = Path(pasta_base) if pasta_base else default_remittances_dir()
        pasta = base / (competencia or SEM_COMPETENCIA) / "demonstrativo"
        pasta.mkdir(parents=True, exist_ok=True)
        primeira = linhas_df[0] if linhas_df else {}
        destino = pasta / f"Demonstrativo_{digitos(primeira.get('Numero_Apac'), 'APAC')[:13]}.TXT"
    destino = Path(destino)
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_bytes(("\r\n".join(secoes) + "\r\n").encode("cp1252", errors="replace"))
    return destino
