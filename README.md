# PENNA CONVERSOR

> Conversor de planilhas Excel em **arquivo TXT fiscal APAC-MAG do DATASUS (SIA)**,
> com validação de consistência, geração de fichas do paciente em PDF e ciclo
> completo de remessa — interface gráfica moderna para Windows, no lugar do
> programa antigo APAC-MAG.

[![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB?logo=python&logoColor=white)](https://www.python.org/downloads/)
[![Testes](https://img.shields.io/badge/testes-168%20OK-2ea44f)](#-testes)
[![Plataforma](https://img.shields.io/badge/windows-10%2F11-0078D6?logo=windows&logoColor=white)]()
[![Licença](https://img.shields.io/badge/licença-PENNA%20(custom)-8A2BE2)](LICENSE.txt)

---

##  Objetivo

O programa antigo APAC-MAG recebia planilhas de apacs oftalmológicas e gerava
o arquivo TXT enviado ao DATASUS, mas era uma ferramenta envelhecida, sem
interface gráfica e com validação manual. O **PENNA CONVERSOR** mantém o
**mesmo layout fiscal comprovado** (idêntico ao TXT real `APCEO26P.JUN`) e
devolve isso em uma interface gráfica arrastar-e-soltar, com:

- **validação automática** antes de exportar (as mesmas checagens do programa
  antigo + regras SIGTAP por competência);
- **fichas do paciente em PDF**, uma por linha, no layout oficial da
  planilha-modelo;
- **registro de remessa** com comprovante, demonstrativo e histórico de
  reenvio.

Em resumo: **menos erro humano, menos retrabalho e o mesmo arquivo fiscal que
o DATASUS espera.**

---

##  O que ele faz

| Recurso | Descrição |
|---|---|
| 📂 **Carga da planilha** | Arraste o `.xlsx`/`.xlsm`/`.xls` para a janela (ou clique em *Selecionar*); o cabeçalho mostra a competência detectada. |
| 🛡️ **Gate de consistência (RCONSIST)** | No carregar e de novo no EXECUTAR: erros **ERR** bloqueiam a exportação, avisos **AVS** apenas aparecem — idêntico ao programa antigo. |
| 🏷️ **Regras SIGTAP por competência** | Idade, sexo, quantidade, par principal/secundário, habilitação no CNES, CID válido — com download automático da base do mês via FTP do DATASUS (seletor em *Automático*). |
| 🧾 **TXT fiscal APAC-MAG** | Header `01#APAC` com checksum oficial, blocos **14/06/13**, CRLF e encoding CP1252 — layout confirmado contra o arquivo real do programa antigo. |
| 📅 **Competência e extensão automáticas** | O mês da planilha vai para o cabeçalho e para a extensão do arquivo (ex.: `.JUN`); a versão do cabeçalho (`Versao XX.XX`) é resolvida por competência no histórico do config. |
| 📄 **Fichas em PDF** | Uma ficha por linha, **em uma única página A4**, com todas as colunas da linha; listas de procedimentos e CIDs reduzidas ao que o paciente **realmente** fez/recebeu. |
| 📮 **Ciclo de remessa** | Cópia do TXT + comprovante estilo RELEXP + demonstrativo estilo R0201 + histórico de APACs que avisa sobre reenvio (código oficial **010084**) sem bloquear. |
| 🧩 **Opções de exportação** | Escolha entre *só TXT*, *só fichas*, *ambas* ou *nenhuma* — saem exatamente as opções marcadas. |
| ⚡ **Interface responsiva** | Validação e geração rodam em segundo plano com tela de carregamento — a janela nunca congela. |

---

##  Pré-requisitos e instalação

**Para usar (cliente final):**

- Windows 10/11 — não precisa de Python.

| Caminho | O que fazer |
|---|---|
| **Instalação completa** | Execute `PennaConversor_Installer.exe` |
| **Portátil** | Execute o `PennaConversor.exe` (standalone, arquivo único) |

Na primeira execução, configure o estabelecimento no `penna_config.json`
(ver a seção **Configuração do estabelecimento** abaixo) e pronto.

**Para desenvolver/compilar a partir do código:**

1. [Python 3.10+](https://www.python.org/downloads/) (marque *Add to PATH*);
2. [Inno Setup 6](https://jrsoftware.org/isdl.php) (apenas para o instalador);
3. `pip install -r requirements.txt`;
4. Rode os testes: `python -m unittest discover -s tests`;
5. Gere os artefatos (detalhes em [GUIA_DE_COMPILACAO.md](GUIA_DE_COMPILACAO.md)):

```bash
build_installer.bat   # testes + EXE + instalador
build_exe.bat         # apenas dist\PennaConversor.exe
```

| Artefato | Caminho |
|---|---|
| EXE standalone | `dist\PennaConversor.exe` |
| Instalador | `installer_output\PennaConversor_Installer.exe` |

---

##  Passo a passo — como usar

1. **Abra o programa** e arraste a planilha Excel para a janela
   (ou clique em *Selecionar* e procure o arquivo);
2. **Confira o cabeçalho** — a competência do mês é detectada
   automaticamente e o seletor de bases SIGTAP foca esse mês; se a base ainda
   não estiver em cache, o **download começa sozinho** (uma vez por mês);
3. **Clique em EXECUTAR** — o sistema valida a planilha inteira; se houver
   erro bloqueante, o relatório **RCONSIST** lista o que corrigir (corrija a
   planilha e repita); avisos não impedem;
4. **Escolha o que exportar** em **OPÇÕES DE EXPORTAÇÃO**:
   - ☑️ **TXT** — salve com o nome que quiser (a extensão do mês, ex. `.JUN`,
     é adicionada automaticamente);
   - ☑️ **Fichas (PDF)** — escolha a pasta de destino: sai um PDF por linha;
5. **Confira a saída** — o TXT fiscal, e junto ao histórico de remessas
   (`Penna\remessas` no seu perfil) a cópia, o comprovante, o demonstrativo e
   o aviso de reenvio, quando houver.

---

##  Como funciona por dentro

Fluxo completo, do Excel ao arquivo fiscal:

```
planilha .xlsx
     │
     ▼
[1] Leitura e normalização ────── apac_mag_gerador + apac_mag/normalization
     │   colunas canônicas, datas, CPF/CNS, degradação graciosa
     ▼
[2] Detecção de competência ──── mês da planilha → cabeçalho + extensão
     │   + seletor SIGTAP foca o mês (download automático se preciso)
     ▼
[3] Gate de consistência ─────── apac_mag_validador (RCONSIST)
     │   checagens clássicas (APAC, CEP, nascimento, raça, datas…)
     │   + regras SIGTAP da competência (idade, sexo, habilitação, CID…)
     │   ERR → bloqueia · AVS → lista e segue
     ▼
[4] Serialização fiscal ──────── apac_mag_gerador
     │   header 01#APAC (checksum) + blocos 14 / 06 / 13
     │   CP1252, CRLF, layout fixo idêntico ao arquivo real
     ▼
[5] Exportação ───────────────── exatamente o que está marcado
     │   ├── TXT fiscal (extensão do mês)
     │   └── Fichas PDF (1 por linha, 1 página A4)
     ▼
[6] Remessa ──────────────────── apac_mag_remessa
         cópia + comprovante RELEXP + demonstrativo R0201
         + histórico → aviso de reenvio 010084 (não bloqueia)
```

Decisões de arquitetura que valem conhecer:

- **O núcleo não conhece a interface** — `apac_mag/` (domínio),
  `apac_mag_*.py` (orquestração) e `ui/` (GUI) separam camadas; a dependência
  sempre desce, nunca sobe (ver [apac_mag/README.md](apac_mag/README.md));
- **Bases ausentes desativam a regra, nunca geram falso positivo** — se a
  tabela SIGTAP não existir, a checagem correspondente é pulada;
- **Processamento em segundo plano** — validação e geração rodam em thread
  própria com overlay de progresso (a UI não trava);
- **Layout fiscal espelhado no original** — os blocos foram conferidos
  byte a byte contra o TXT real gerado pelo programa antigo.

---

##  Configuração do estabelecimento

O arquivo `penna_config.json` define o **header fiscal** e os valores padrão
da planilha. Ele **não é versionado no Git** (é dado privado do
estabelecimento) — ver também a seção [Privacidade](#-privacidade).

Parta do modelo versionado `penna_config.example.json` (valores fictícios):
copie para `penna_config.json` e preencha. Chaves ausentes herdam o valor de
fábrica, mas a identidade (CNES, CGC, órgão, destino, município) não tem valor
de fábrica válido: com o arquivo ausente, corrompido ou ainda com
`NAO CONFIGURADO`/zeros, **a exportação é bloqueada** com um aviso na tela.

Local conforme o modo de execução:

| Modo | Caminho |
|---|---|
| Instalado via setup | `%LOCALAPPDATA%\PennaConversor\penna_config.json` |
| EXE solto (portátil) | mesma pasta do `PennaConversor.exe` |
| Desenvolvimento (fonte) | raiz do projeto |

Campos principais:

| Campo | Significado |
|---|---|
| `header.orgao_responsavel` | Nome do órgão responsável pela informação |
| `header.cgc` | CGC/CNPJ (14 dígitos) |
| `header.destino` | Secretaria de saúde destino das APACs |
| `header.destino_indicador` | `M` municipal ou `E` estadual |
| `header.versao` | Versão padrão do cabeçalho (`Versao XX.XX`) quando o mês não tem valor definido |
| `header.versao_por_mes` | Histórico por competência (ex.: `"202603": "Versao 03.21"`) conferido nos TXTs do programa antigo |
| `header.versao_escolhas` | Escolhas do usuário na interface, que sobrepõem o histórico daquele mês |
| `defaults.Cnes_Executante` | CNES do estabelecimento executante |
| `defaults.Codigo_Municipio` | Código IBGE do município (7 dígitos com DV) |
| `defaults.Cod_Orgao_Emiss` | Código do órgão emissor |

Edite com o Bloco de Notas e reabra o programa. **Sem o arquivo**, o sistema
usa os valores de fábrica e emite um aviso.

---

##  Colunas esperadas na planilha

O conversor lê as colunas canônicas do APAC-MAG (**nomes exatos**, em
português) — contrato do gerador (`COLUNAS_PLANILHA` em
`apac_mag_gerador.py`) mais as demais colunas canônicas declaradas em
`apac_mag/columns.py`:

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
Sec1_Cod_Procedimento, Sec1_Cbo, Sec1_Quantidade … até Sec8_*,
Motivo_Saida, Data_Alta_Obito, Carater_Atend,
Medico_Cns, Medico_Cpf, Medico_Nome,
Data_Solicitacao, Autorizador_Cns, Autorizador_Cpf, Autorizador_Nome,
Data_Autorizacao, Cod_Orgao_Emiss
```

Colunas ausentes são tratadas como vazias (degradação graciosa) — mas o
controle de consistência **exige** os campos obrigatórios (número da APAC,
data de nascimento, raça, logradouro, CEP etc.).

---

##  Regras de consistência e bases SIGTAP

O validador **bloqueia** (ERR) enquanto houver: APAC inválida/duplicada no
histórico, data de nascimento inválida, CEP inexistente, raça ou logradouro
inválidos, datas incoerentes, quantidade zero no procedimento principal da
APAC MÃE, e as regras SIGTAP por competência (idade mín/máx, sexo,
quantidade máxima, secundário obrigatório, par principal/secundário,
habilitação no CNES, CID válido e restrição de sexo). Avisos (AVS) são
listados e não bloqueiam.

As tabelas SIGTAP ficam em `dados/bases_sia/` (S_PA, S_PAPA, S_PAHA,
S_PAREGR, S_CID, S_DEPARA, XUPSHA), são **versionadas no repositório** e
**embutidas no EXE**.

- **Bases da instalação do programa antigo**: defina `PENNA_APAC_DIR`
  apontando para a pasta (ex.: `C:\APAC`) — tem prioridade sobre as embutidas;
- **S_CEP não é distribuída**: sem ela, a regra de CEP fica desativada;
- **Download automático**: com o seletor em *Automático*, o mês detectado na
  planilha é focado e, se o ZIP existir no FTP do DATASUS e não estiver em
  cache (`dados/sigtap_cache`), o download começa sozinho, com barra de
  progresso, e a validação é refeita ao concluir. Escolher um mês à mão
  mantém a seleção; meses que o FTP não oferece mais seguem com as bases
  locais, avisando no status.

---

##  Estrutura do projeto

```
PENNA_CONVERSOR/
├── apac_mag_gui.py         Entry point da interface (thin wrapper)
├── apac_mag_gerador.py     Motor fiscal: Excel → TXT APAC-MAG
├── apac_mag_validador.py   Gate de consistência (RCONSIST + SIGTAP)
├── apac_mag_remessa.py     Ciclo de remessa (RELEXP + R0201 + histórico)
├── apac_mag_fichas.py      Fichas do paciente em PDF (1 por linha, 1 página)
├── apac_mag_bases.py       Leitor DBF/ZBF das bases SIA (com cache)
├── apac_mag_sigtap_download.py   Download das bases SIGTAP (FTP DATASUS)
├── apac_mag/               Núcleo de domínio (config, normalization,
│                           utilitários compartilhados)
├── ui/                     Interface (theme, components, app)
├── dados/
│   ├── bases_sia/          Bases SIGTAP versionadas
│   └── modelo_ficha_…xlsx  Template da ficha PDF
├── tests/                  13 arquivos de teste (unittest)
├── Excel_Base.xlsx         Planilha-base (cabeçalho + tabelas de referência)
├── Conversor.spec          Build PyInstaller (onefile)
├── build_exe.bat           Gera dist/PennaConversor.exe
├── build_installer.bat     Gera EXE + instalador
├── installer.iss           Script Inno Setup 6
├── requirements.txt        Dependências fixadas
└── GUIA_DE_COMPILACAO.md   Guia de compilação detalhado
```

---

##  Testes

```bash
python -m unittest discover -s tests
```

**168 testes**, cobrindo o núcleo de conversão, validador SIGTAP, remessa,
fichas, interface e o fluxo completo Excel → TXT/PDF. Os testes usam apenas
**dados fictícios** — o repositório não contém dados de paciente.

---

##  Privacidade

Este repositório é **puro**: não há dados reais de pacientes, CPFs, nomes ou
configuração do estabelecimento. O que é privado fica fora do Git (ver
[`.gitignore`](.gitignore)):

- `penna_config.json` — CGC/CNES e dados do estabelecimento;
- `dados/remessas/`, `Formatado/`, `Temp/` — histórico e saídas com dados de
  paciente gerados em runtime;
- `dados/sigtap_cache/`, `build/`, `dist/`, `installer_output/` — caches e
  artefatos de build.

---

##  Solução de problemas

| Sintoma | O que fazer |
|---|---|
| Planilha não carrega | Confirme que é `.xlsx`, `.xlsm` ou `.xls` |
| "Consistência reprovada" | Corrija os itens **ERR** listados na tela e execute de novo |
| Header com dados errados | Revise o `penna_config.json` e reabra o programa |
| Regra SIGTAP "desligada" | A base da competência não está disponível — deixe o seletor em *Automático* com internet, ou aponte `PENNA_APAC_DIR` |
| Onde achar o comprovante | Pasta `Penna\remessas` no perfil do Windows |

---

## 📄 Licença

Uso interno — ver [LICENSE.txt](LICENSE.txt). É proibida a reprodução,
distribuição ou revenda sem autorização escrita.
