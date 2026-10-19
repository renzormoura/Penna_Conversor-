# apac_mag — Núcleo de Domínio SIA/APAC

Este pacote é o **primeiro módulo completo** da plataforma PENNA e serve como **referência de arquitetura** para todos os sistemas do CMD que serão implementados a seguir (BPA, AIH, SINASC, SIM, SINAN e outros).

A regra central do pacote: **nenhum módulo aqui conhece UI, I/O de disco ou detalhes de framework**. O fluxo é sempre descendente — a raiz do projeto depende deste pacote, nunca o contrário.

---

## Módulos

| Módulo | Responsabilidade |
|---|---|
| `config.py` | Carrega `penna_config.json` via `get_header()` e `get_defaults()`. Singleton com cache, fallback automático, sem exceção por arquivo ausente. |
| `normalization.py` | **Fonte única de verdade** para todos os helpers de string: `text`, `digits`, `text_upper`, `pad_left`, `pad_right`, `resolve_row_value`, `date_to_ddmmaa`, `nascimento_to_aaaammdd`, `normalize_cpf`, `normalize_cns`. Nenhum módulo do projeto redefine essas funções. |
| `models.py` | Dataclasses de domínio imutáveis e tipadas: `ApacRecord`, `PatientRecord`, `ProcedureRecord`. São os objetos canônicos que transitam entre camadas — nunca dicts soltos. |
| `validation.py` | Validação estrutural leve de `ApacRecord` → `ValidationResult`. Verifica integridade antes da serialização, independente das regras SIGTAP. |
| `serializers.py` | **Serialização OO canônica** de `ApacRecord` para blocos de layout fixo (tipo 14, 06, 13) via `serialize_apac()`. Fonte única de verdade para a montagem dos campos posicionais. |
| `workbook.py` | Leitura/mesclagem da planilha Excel para objetos de domínio. Isola o pandas do restante do código. |
| `columns.py` | Constantes de nomes de colunas por categoria (`PATIENT_COLUMNS`, `APAC_COLUMNS`, `PROCEDURE_COLUMNS`). Vocabulário canônico da planilha. |
| `numbers.py` | Geração de numeração APAC no formato oficial: UF + AAMM + sequencial + DV (mod 11). Validado em 25 números reais do `S_APAC.DBF`. |
| `template.py` | Criação do template Excel estruturado com abas, estilos, validações de lista e tabelas. |

---

## Status de produção

| Módulo | Em produção | Observação |
|---|---|---|
| `config.py` | ✅ | Usado por gerador, validador e remessa |
| `normalization.py` | ✅ | Importado por todos os módulos da raiz |
| `models.py` | ✅ | Usado por workbook.py e serializers.py |
| `validation.py` | ✅ | Validação estrutural pré-serialização |
| `serializers.py` | ✅ | Serialização OO canônica — substitui versão por dict do gerador |
| `columns.py` | ✅ | Usado por workbook.py e template.py |
| `workbook.py` | 🔶 | Integração com gerador pendente (migração de dict para ApacRecord) |
| `numbers.py` | 🔶 | A ser conectado ao fluxo de exportação |
| `template.py` | 🔶 | Funcional; integração com a GUI pendente |

---

## Arquitetura e regra de dependência

```
penna_config.json           ← configuração do estabelecimento (editável, fora do código)
│
apac_mag/                   ← núcleo de domínio (zero dependências externas ao pacote)
│   config.py               ← lê penna_config.json
│   normalization.py        ← helpers puros (fonte única de verdade)
│   models.py               ← dataclasses de domínio
│   validation.py           ← validação estrutural
│   serializers.py          ← serialização OO para layout fixo
│   workbook.py             ← leitura do Excel orientada a objeto
│   columns.py, numbers.py, template.py
│
apac_mag_gerador.py         ← orquestração: lê Excel → gera TXT
apac_mag_validador.py       ← gate de consistência (RCONSIST + SIGTAP)
apac_mag_remessa.py         ← ciclo de remessa (RELEXP + R0201 + histórico)
apac_mag_bases.py           ← acesso às bases SIA em DBF/ZBF com cache
│
ui/
│   theme.py                ← paleta de cores e constantes visuais
│   components.py           ← HeaderCanvas, DropZone, PainelErros
│   app.py                  ← PennaApp (orquestração da GUI)
│
apac_mag_gui.py             ← thin wrapper de retrocompatibilidade (re-exporta ui/)
```

**Fluxo de dependência — sempre desce, nunca sobe:**

```
ui/ → apac_mag_gerador, apac_mag_validador, apac_mag_remessa
apac_mag_gerador    → apac_mag.normalization, apac_mag.config
apac_mag_validador  → apac_mag.normalization, apac_mag.config, apac_mag_bases, apac_mag_remessa
apac_mag_remessa    → apac_mag.normalization, apac_mag.config, apac_mag_gerador (serialização)
apac_mag/           → zero dependências de módulos da raiz
```

---

## Este pacote como template para novos sistemas do CMD

Ao implementar um novo sistema (BPA, AIH, SINASC, etc.), a estrutura a seguir é esta:

```
<sistema>/               ex.: bpa/, aih/, sinasc/
    models.py            dataclasses do domínio (herdando ou reutilizando PatientRecord)
    validation.py        regras específicas do sistema → ValidationResult
    serializers.py       serialize_<sistema>() → list[str] (blocos de layout fixo)
    columns.py           colunas canônicas da planilha do sistema
    template.py          template Excel do sistema
```

Os módulos `config.py` e `normalization.py` do `apac_mag/` são transversais — todos os sistemas os importam. Não há razão para redefinir `text()`, `digits()`, `pad_left()` ou `resolve_row_value()` em nenhum outro lugar do projeto.

---

## Próximos passos

1. Concluir a migração `workbook.py` → gerador (substituir leitura por dict por `ApacRecord`)
2. Conectar `numbers.py` ao fluxo de exportação (numeração automática quando a planilha não preenche)
3. Adicionar testes em `apac_mag/tests/` cobrindo serializers e regras do validador
4. Integrar `template.py` à GUI (botão "Criar nova planilha")
5. Criar `bpa/models.py` + `bpa/serializers.py` como primeiro módulo da expansão BPA-I
