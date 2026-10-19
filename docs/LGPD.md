# Dados pessoais e retenção (LGPD)

O Penna Conversor trata dados pessoais e de saúde de pacientes (dados sensíveis).
Este documento descreve **onde** eles ficam no disco e a **política de retenção
proposta**. A retenção é uma decisão do controlador (o estabelecimento): ajuste
os prazos abaixo à política dele e ao seu encarregado (DPO) antes de adotar.

## Onde ficam os dados

| Local | Conteúdo | Dado pessoal |
|---|---|---|
| `%USERPROFILE%\Penna\remessas\<AAAAMM>\<data_hora>\` (EXE) ou `dados\remessas\` (código-fonte) | cópia do TXT fiscal, `apacs.txt` (nº das APACs), `remessa.json`, comprovante (RELEXP) e demonstrativo (R0201) | **Sim, em texto puro**: o TXT e o demonstrativo trazem nome, CPF, CNS, data de nascimento e endereço |
| Pasta escolhida na exportação | TXT fiscal e fichas em PDF | Sim |
| `%LOCALAPPDATA%\PennaConversor\penna.log` | tracebacks de falhas inesperadas | Não deve conter dados de paciente; não anexe a terceiros sem conferir |
| `%LOCALAPPDATA%\PennaConversor\penna_config.json` | CNES, CGC e dados do estabelecimento | Não (dado do prestador) |

O Penna **não** grava mais o CSV `Formatado\numeracao_apac_usada.csv` (continha
nome e CPF); foi removido.

## Retenção proposta

- **Histórico de APACs (`apacs.txt`)**: manter. Alimenta o aviso 010084 (reenvio)
  e só contém números de APAC.
- **Cópia do TXT, demonstrativo e comprovante**: manter pelo prazo de auditoria
  do faturamento definido pelo estabelecimento (proposta inicial: **5 anos**) e
  depois eliminar a pasta `<AAAAMM>` correspondente.
- **Fichas em PDF e TXT exportados fora da pasta de remessas**: são cópias de
  trabalho; apagar após o envio ao DATASUS e a conferência.

A eliminação é manual (apagar a pasta da competência). Não há rotina automática.

## Medidas recomendadas

- Manter `%USERPROFILE%` em disco criptografado (BitLocker) e com acesso restrito
  ao(s) operador(es) do faturamento.
- Não versionar nem enviar por e-mail/mensageria a pasta `Penna\remessas`; o
  `.gitignore` já exclui `dados/remessas/`, `Formatado/` e `Temp/`.
- Backups da pasta de remessas seguem o mesmo prazo e as mesmas proteções.
