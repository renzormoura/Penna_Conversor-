# Arquitetura

O código vive em `src/penna/`, em camadas com dependência em um único sentido (das altas
para as baixas). A regra é executável: `tests/test_arquitetura.py` falha se um pacote
importar de fora da lista permitida.

```
                         ui            interface tkinter (tela, widgets, tarefas)
                          |
                       services        casos de uso sem Tk: validar, exportar, mensagens
                          |
        +-----------+-----+-----+-----------+
     validation  remittance   cards          regra de negócio por tema
        |           |           |
        +-----+-----+           |
              |                 |
            layout           reference      TXT fiscal  |  tabelas SIA/SIGTAP
              |                 |
            config  ------------+
              |
            core    paths                   puros, sem I/O de domínio
```

| Pacote | Responsabilidade | Depende de |
|---|---|---|
| `paths` | Onde ficam recursos e dados, no código-fonte e no executável | (nada) |
| `core` | Texto, datas, identificadores, competência e acesso tolerante às colunas | (nada) |
| `config` | `penna_config.json`: valores de fábrica, carga mesclada, gate e gravação atômica | `core`, `paths` |
| `reference` | Leitura de DBF/ZBF, seleção por vigência e SIGTAP (FTP, cache, parser) | `paths` |
| `layout` | Layout fixo do TXT: `ApacBody`, blocos 06 e 13, cabeçalho, nome e gravação do arquivo | `core`, `config` |
| `validation` | Motor de regras de consistência (RCONSIST) | `core`, `config`, `layout`, `reference`, `remittance` |
| `remittance` | Registro da remessa, histórico de APACs, comprovante e demonstrativo | `core`, `config`, `layout`, `reference`, `paths` |
| `cards` | Fichas do paciente em PDF a partir do modelo `.xlsx` | `config`, `paths`, `reference` |
| `services` | Casos de uso: `validar_arquivo`, `exportar`, textos finais | camadas abaixo |
| `ui` | Janela, widgets e execução em segundo plano | `services` e camadas abaixo |

## Decisões

**O layout fixo é um tipo.** `layout.body.ApacBody` é uma dataclass cuja ordem de campos *é* o
layout posicional do bloco 14; `render()` concatena na ordem de declaração. Cada seção
(identificação, paciente, endereço, profissionais, autorização) extrai seus campos da linha.
O arquivo de referência anonimizado (`tests/fixtures/apac_referencia.txt`) trava o resultado
byte a byte.

**Validação é um motor de regras.** Cada regra é um objeto `Regra` (ou `RegraItem`, aplicada a cada
procedimento) com nome, códigos que pode emitir e a base de dados que exige. A lista de
"regras desativadas por base ausente" sai das próprias regras; não há tabela paralela. A ordem
das regras define a numeração `SEQ` do relatório e é preservada do programa original.
Códigos `(HIPOTESE)` só avisam até haver confirmação oficial (`validation/catalog.py`,
`SEVERIDADE_HIPOTESE`).

**Base ausente desativa a regra, nunca gera falso positivo.** `reference` devolve `None` e a
regra correspondente não dispara.

**Sem estado global na importação.** O config é lido no momento do uso; caminhos vêm de
`paths`; datas de geração são funções isoladas para os testes.

**Interface fina.** `services` não conhece Tk e é testado sem display. `ui.tasks.TaskRunner`
isola a thread de fundo, o overlay e o retorno na thread principal. `ui.app.PennaApp` só monta
a tela, abre diálogos e chama os serviços.

**Falhas vistas, nunca engolidas.** Exceções são específicas; nas fronteiras (thread de fundo,
callbacks, remessa) o erro é registrado com `log.exception` em
`%LOCALAPPDATA%\PennaConversor\penna.log`. O `ruff` proíbe `except Exception` solto.

## Fluxo

```
planilha .xlsx
  -> services.validation.validar_arquivo   (layout.carregar_planilha + validation.validar_planilha)
  -> ui: destinos (TXT, pasta das fichas)
  -> services.export.exportar              (layout.exportar_txt -> remittance -> cards)
  -> services.messages                     (status e diálogo final)
```

## Como estender

- **Nova regra de consistência:** crie a `Regra` em `validation/rules/<tema>.py`, registre o código
  em `validation/catalog.py` e inclua a regra em `rules/__init__.py` na posição desejada.
  `tests/test_motor_regras.py` confere que todo código do catálogo tem quem o emita.
- **Novo campo no bloco 14:** adicione o campo em `ApacBody` na posição do layout e a extração na
  seção correspondente; atualize o golden file de forma consciente
  (`PENNA_REGENERAR_GOLDEN=1`).
- **Nova base de referência:** exponha-a em `reference` (ou derive-a em `validation/lookups.py`).
