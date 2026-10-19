# PENNA CONVERSOR

Conversor de planilhas Excel em arquivo TXT fiscal APAC-MAG do DATASUS (SIA), com validação de consistência, geração de fichas do paciente em PDF e registro de remessa. Aplicação desktop para Windows, em substituição ao programa APAC-MAG original.

[![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB?logo=python&logoColor=white)](https://www.python.org/downloads/)
[![Plataforma](https://img.shields.io/badge/Windows-10%2F11-0078D6?logo=windows&logoColor=white)]()
[![Licença](https://img.shields.io/badge/licença-PENNA%20(custom)-8A2BE2)](LICENSE.txt)

## Sumário

1. [Objetivo](#objetivo)
2. [Funcionalidades](#funcionalidades)
3. [Instalação](#instalação)
4. [Uso](#uso)
5. [Arquitetura](#arquitetura)
6. [Configuração do estabelecimento](#configuração-do-estabelecimento)
7. [Colunas da planilha](#colunas-da-planilha)
8. [Regras de consistência e bases SIGTAP](#regras-de-consistência-e-bases-sigtap)
9. [Estrutura do projeto](#estrutura-do-projeto)
10. [Testes e qualidade](#testes-e-qualidade)
11. [Privacidade e LGPD](#privacidade-e-lgpd)
12. [Solução de problemas](#solução-de-problemas)
13. [Licença](#licença)

## Objetivo

O programa APAC-MAG original recebia planilhas de APACs oftalmológicas e gerava o arquivo TXT enviado ao DATASUS, mas não possuía interface gráfica moderna e dependia de conferência manual. O PENNA CONVERSOR preserva o layout fiscal do arquivo gerado pelo programa original e acrescenta:

- validação automática antes da exportação (checagens do programa original e regras SIGTAP por competência);
- fichas do paciente em PDF, uma por linha da planilha;
- registro de remessa, com comprovante, demonstrativo e histórico de reenvio.

## Funcionalidades

| Recurso | Descrição |
|---|---|
| Carga da planilha | Arraste o arquivo `.xlsx`, `.xlsm` ou `.xls` para a janela ou use o botão Selecionar. A competência detectada é exibida no cabeçalho. |
| Gate de consistência (RCONSIST) | Executado ao carregar e ao exportar. Ocorrências ERR bloqueiam a exportação; ocorrências AVS são apenas listadas. |
| Regras SIGTAP por competência | Idade, sexo, quantidade, par principal/secundário, habilitação no CNES e CID, com download automático da base do mês via FTP do DATASUS. |
| TXT fiscal APAC-MAG | Cabeçalho `01#APAC` com checksum, blocos 14, 06 e 13, quebra de linha CRLF e codificação CP1252. |
| Competência e extensão automáticas | O mês da planilha define o cabeçalho e a extensão do arquivo (por exemplo, `.JUN`). A versão do cabeçalho é resolvida por competência. |
| Fichas em PDF | Uma ficha por linha, em uma página A4, com as listas de procedimentos e CIDs reduzidas ao que o paciente efetivamente recebeu. |
| Ciclo de remessa | Cópia do TXT, comprovante (modelo RELEXP), demonstrativo (modelo R0201) e histórico de APACs com aviso de reenvio (código 010084). |
| Opções de exportação | Somente TXT, somente fichas ou ambos. |
| Interface responsiva | Validação e geração executam em segundo plano, com indicador de progresso. |

## Instalação

### Usuário final

Requer Windows 10 ou 11. Não é necessário instalar Python.

| Modalidade | Procedimento |
|---|---|
| Instalação completa | Execute `PennaConversor_Installer.exe`. |
| Portátil | Execute `PennaConversor.exe` (arquivo único). |

Na primeira execução, configure o estabelecimento conforme a seção [Configuração do estabelecimento](#configuração-do-estabelecimento). Sem essa configuração a exportação é bloqueada.

### Desenvolvimento

1. Instale o [Python 3.10 ou superior](https://www.python.org/downloads/) com a opção Add to PATH.
2. Instale o [Inno Setup 6](https://jrsoftware.org/isdl.php) (somente para gerar o instalador).
3. Instale as dependências: `pip install -r requirements.txt`.
4. Copie `penna_config.example.json` para `penna_config.json` e preencha os dados do estabelecimento.
5. Execute os testes: `python -m unittest discover -s tests`.
6. Gere os artefatos, conforme o [guia de compilação](GUIA_DE_COMPILACAO.md):

```bash
build_installer.bat   # testes, executável e instalador
build_exe.bat         # somente dist\PennaConversor.exe
```

| Artefato | Caminho |
|---|---|
| Executável standalone | `dist\PennaConversor.exe` |
| Instalador | `installer_output\PennaConversor_Installer.exe` |

## Uso

1. Abra o programa e arraste a planilha para a janela, ou use o botão Selecionar.
2. Confira a competência no cabeçalho. O seletor de bases SIGTAP é posicionado nesse mês e, se a base ainda não estiver em cache, o download é iniciado automaticamente.
3. Clique em Executar. A planilha inteira é validada. Havendo erros bloqueantes, o relatório RCONSIST lista as correções necessárias; avisos não impedem a exportação.
4. Em Opções de exportação, escolha o que gerar:
   - TXT: informe o nome do arquivo; a extensão do mês é adicionada automaticamente.
   - Fichas (PDF): informe a pasta de destino; é gerado um PDF por linha.
5. Confira a saída: o TXT fiscal e, no histórico de remessas (`Penna\remessas` no perfil do usuário), a cópia, o comprovante, o demonstrativo e o aviso de reenvio, quando houver.

## Arquitetura

```
planilha .xlsx
     |
     v
[1] Leitura e normalização      apac_mag_gerador, apac_mag/normalization
     |   colunas canônicas, datas, CPF/CNS
     v
[2] Detecção de competência     mês da planilha -> cabeçalho e extensão
     |   seletor SIGTAP posicionado no mês
     v
[3] Gate de consistência        apac_mag_validador
     |   checagens clássicas (APAC, CEP, nascimento, raça, datas)
     |   regras SIGTAP da competência
     |   ERR bloqueia; AVS lista e prossegue
     v
[4] Serialização fiscal         apac_mag_gerador
     |   cabeçalho 01#APAC (checksum) e blocos 14, 06 e 13
     |   CP1252, CRLF, layout de largura fixa
     v
[5] Exportação                  conforme as opções marcadas
     |   TXT fiscal e/ou fichas em PDF
     v
[6] Remessa                     apac_mag_remessa
         cópia, comprovante, demonstrativo e histórico
```

Decisões de projeto:

- O núcleo não conhece a interface. `apac_mag/` (utilitários compartilhados), `apac_mag_*.py` (domínio e orquestração) e `ui/` (interface) são camadas separadas, com dependência em sentido único. O caminho de geração do TXT é exclusivamente `apac_mag_gerador.py`.
- Base ausente desativa a regra correspondente, nunca gera falso positivo. A interface informa quantas regras foram desativadas na validação.
- Configuração é lida no momento do uso, sem estado global na importação dos módulos.
- Validação e geração executam em thread própria, com indicador de progresso.

## Configuração do estabelecimento

O arquivo `penna_config.json` define o cabeçalho fiscal e os valores padrão da planilha. Contém dados do estabelecimento e por isso não é versionado.

Parta do modelo versionado `penna_config.example.json` (valores fictícios): copie para `penna_config.json` e preencha. Chaves ausentes herdam o valor de fábrica, mas a identidade do estabelecimento (CNES, CGC, órgão, destino e município) não possui valor de fábrica válido. Com o arquivo ausente, corrompido ou ainda com `NAO CONFIGURADO` ou zeros, a exportação é bloqueada com um aviso na tela.

| Modo de execução | Local do arquivo |
|---|---|
| Instalado via setup | `%LOCALAPPDATA%\PennaConversor\penna_config.json` |
| Executável portátil | Mesma pasta de `PennaConversor.exe` |
| Desenvolvimento | Raiz do projeto |

| Campo | Significado |
|---|---|
| `header.orgao_responsavel` | Nome do órgão responsável pela informação |
| `header.cgc` | CGC/CNPJ (14 dígitos) |
| `header.destino` | Secretaria de saúde destinatária das APACs |
| `header.destino_indicador` | `M` (municipal) ou `E` (estadual) |
| `header.versao` | Versão padrão do cabeçalho (`Versao XX.XX`) quando o mês não possui valor definido |
| `header.versao_por_mes` | Histórico por competência (por exemplo, `"202603": "Versao 03.21"`) |
| `header.versao_escolhas` | Escolhas feitas na interface, que prevalecem sobre o histórico do mês |
| `defaults.Cnes_Executante` | CNES do estabelecimento executante |
| `defaults.Codigo_Municipio` | Código IBGE do município |
| `defaults.Cod_Orgao_Emiss` | Código do órgão emissor |

Edite o arquivo em um editor de texto e reabra o programa. A gravação feita pela interface (escolha de versão) é atômica.

## Colunas da planilha

O conversor lê as colunas canônicas do APAC-MAG, com os nomes exatos abaixo (contrato `COLUNAS_PLANILHA`, em `apac_mag_gerador.py`):

```
Numero_Apac, Numero_Apac_Anterior, Competencia, Tipo_Atendimento,
Cnes_Solicitante, Cnes_Executante, Inicio_Validade, Fim_Validade,
Tipo_Apac, Nacionalidade, No_Prontuario,
Cpf_Paciente, Cns_Paciente, Situacao_De_Rua, Nome_Paciente, Nome_Da_Mae,
Nome_Do_Responsavel, Nome_Profissional, Cep, Logradouro, Rua,
Numero_Endereco, Codigo_Logradouro, Complemento, Bairro, Telefone, Email,
Codigo_Municipio, IBGE, Nome_Municipio, Raca, Data_Nascimento, Sexo, Etnia,
Cod_Procedimento, Cbo, Quantidade, Cns_Executante, Equipe, Equipe_Area,
Cnes_Terceiro, Servico, Classif, Cid_Princ, Cid_Secun, Cid_Causas_Assoc,
Cnpj_Fornecedor, Num_Nota_Fiscal, Data_Identificacao,
Sec1_Cod_Procedimento, Sec1_Cbo, Sec1_Quantidade, ... Sec8_*,
Motivo_Saida, Data_Alta_Obito, Carater_Atend,
Medico_Cns, Medico_Cpf, Medico_Nome,
Data_Solicitacao, Autorizador_Cns, Autorizador_Cpf, Autorizador_Nome,
Data_Autorizacao, Cod_Orgao_Emiss
```

Colunas ausentes são tratadas como vazias, porém o controle de consistência exige os campos obrigatórios (número da APAC, data de nascimento, raça, logradouro, CEP, entre outros).

Datas são aceitas em AAAAMMDD, DDMMAAAA, DD/MM/AAAA e ISO (com ou sem hora), e normalizadas para AAAAMMDD no TXT. Textos devem usar caracteres compatíveis com CP1252 e respeitar a largura do layout.

## Regras de consistência e bases SIGTAP

O validador bloqueia a exportação (ERR) quando há:

- competência inválida ou mista entre as linhas;
- data de nascimento inválida;
- qualquer data do TXT preenchida e inválida (validade, solicitação, autorização, alta ou óbito, emissão);
- caractere não suportado no TXT (fora do CP1252 ou de controle);
- CEP inexistente, raça ou logradouro inválidos, datas incoerentes;
- idade máxima do procedimento excedida;
- quantidade zero no procedimento principal da APAC mãe.

Geram apenas aviso (AVS): texto acima da largura do layout (será truncado), reenvio de APAC presente no histórico (010084) e as regras SIGTAP ainda sem confirmação do comportamento oficial (códigos 000006 a 000009, 010040 e 010041: secundário obrigatório, sexo, quantidade máxima, par principal/secundário e CID). A constante `SEVERIDADE_HIPOTESE`, em `apac_mag_validador.py`, promove essas regras a ERR quando forem confirmadas.

Quando uma base (S_CEP, S_PA, S_PAPA, S_PAHA, S_CID, S_PAREGR) não está disponível, a interface informa quantas regras foram desativadas na validação e quais. O catálogo S_PA utiliza a versão vigente na competência da planilha.

As tabelas SIGTAP ficam em `dados/bases_sia/` (S_PA, S_PAPA, S_PAHA, S_PAREGR, S_CID, S_DEPARA e XUPSHA), são versionadas no repositório e embutidas no executável.

- Bases da instalação do programa original: defina `PENNA_APAC_DIR` apontando para a pasta (por exemplo, `C:\APAC`). Ela tem prioridade sobre as embutidas.
- A base S_CEP não é distribuída. Sem ela, a regra de CEP é desativada.
- Download automático: com o seletor em Automático, o mês detectado na planilha é selecionado e, se o ZIP existir no FTP do DATASUS e não estiver em cache (`dados/sigtap_cache`), o download é iniciado com barra de progresso e a validação é refeita ao concluir. A escolha manual de um mês é preservada. Meses indisponíveis no FTP utilizam as bases locais, com aviso no status.

## Estrutura do projeto

```
PENNA_CONVERSOR/
|-- apac_mag_gui.py               Ponto de entrada da interface
|-- apac_mag_gerador.py           Motor fiscal: Excel -> TXT APAC-MAG
|-- apac_mag_validador.py         Gate de consistência (RCONSIST e SIGTAP)
|-- apac_mag_remessa.py           Ciclo de remessa (RELEXP, R0201 e histórico)
|-- apac_mag_fichas.py            Fichas do paciente em PDF
|-- apac_mag_bases.py             Leitor DBF/ZBF das bases SIA (com cache)
|-- apac_mag_sigtap_download.py   Download das bases SIGTAP (FTP DATASUS)
|-- apac_mag/                     Configuração e normalização compartilhadas
|-- ui/                           Interface (theme, components, app)
|-- dados/
|   |-- bases_sia/                Bases SIGTAP versionadas
|   `-- modelo_ficha_*.xlsx       Modelo da ficha em PDF
|-- docs/LGPD.md                  Dados pessoais, local e retenção
|-- tests/                        Testes (unittest) e fixtures
|-- penna_config.example.json     Modelo de configuração
|-- pyproject.toml                Configuração do ruff
|-- .github/workflows/ci.yml      Integração contínua
|-- Excel_Base.xlsx               Planilha-base
|-- Conversor.spec                Build PyInstaller (arquivo único)
|-- build_exe.bat                 Gera dist/PennaConversor.exe
|-- build_installer.bat           Gera executável e instalador
|-- installer.iss                 Script do Inno Setup 6
|-- requirements.txt              Dependências fixadas
`-- GUIA_DE_COMPILACAO.md         Guia de compilação
```

## Testes e qualidade

```bash
python -m unittest discover -s tests
ruff check .
```

A suíte cobre o núcleo de conversão, validador, parser SIGTAP, remessa, fichas, configuração, interface e o fluxo Excel para TXT/PDF. Inclui um arquivo de referência anonimizado (`tests/fixtures/apac_referencia.txt`) que valida byte a byte o cabeçalho e os blocos 14, 06 e 13. Os testes de interface são ignorados quando o `tkinter` não está disponível.

Os testes usam apenas dados fictícios. Em um clone limpo, copie `penna_config.example.json` para `penna_config.json` antes de executá-los. O workflow de CI executa `unittest` e `ruff` a cada push.

## Privacidade e LGPD

O repositório não contém dados reais de pacientes nem a configuração do estabelecimento. Permanecem fora do Git (ver [`.gitignore`](.gitignore)):

- `penna_config.json`: CGC, CNES e dados do estabelecimento;
- `dados/remessas/`, `Formatado/` e `Temp/`: histórico e saídas com dados de pacientes, gerados em execução;
- `dados/sigtap_cache/`, `build/`, `dist/` e `installer_output/`: caches e artefatos de build.

O histórico de remessas (`%USERPROFILE%\Penna\remessas`) armazena o TXT e o demonstrativo com nome, CPF, CNS e endereço em texto puro. O local, o prazo de retenção proposto e as medidas de proteção estão descritos em [docs/LGPD.md](docs/LGPD.md). Falhas inesperadas são registradas em `%LOCALAPPDATA%\PennaConversor\penna.log`.

## Solução de problemas

| Sintoma | Ação |
|---|---|
| A planilha não carrega | Confirme que o arquivo é `.xlsx`, `.xlsm` ou `.xls`. |
| Consistência reprovada | Corrija as ocorrências ERR listadas na tela e execute novamente. |
| Configuração inválida ao exportar | Preencha o `penna_config.json` a partir de `penna_config.example.json` e reabra o programa. |
| Cabeçalho com dados incorretos | Revise o `penna_config.json` e reabra o programa. |
| Regras SIGTAP desativadas | A base da competência não está disponível. Mantenha o seletor em Automático com acesso à internet ou defina `PENNA_APAC_DIR`. |
| Localizar o comprovante | Pasta `Penna\remessas` no perfil do usuário. |

## Licença

Uso interno. Consulte [LICENSE.txt](LICENSE.txt). É proibida a reprodução, distribuição ou revenda sem autorização escrita.
