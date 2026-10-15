# apac_mag — utilitários compartilhados

Pacote enxuto usado pelo conversor (`apac_mag_gerador.py`, `apac_mag_validador.py`,
`apac_mag_remessa.py`, `apac_mag_fichas.py` e `ui/`). O caminho real de geração do TXT é o
**gerador legado** `apac_mag_gerador.py`; havia um serializador orientado a objetos paralelo
(`models`, `serializers`, `validation`, `workbook`, `template`, `numbers`, `columns`) que nunca
foi integrado e divergia do gerador (UF, datas); foi removido para existir uma única fonte da
verdade. Está no histórico do Git se for preciso consultar.

| Módulo | Responsabilidade |
|---|---|
| `config.py` | Carrega `penna_config.json` e mescla chave a chave com os valores de fábrica. Identidade do estabelecimento sem valor de fábrica válido: `verificar_configuracao()` / `ConfigInvalidaError` bloqueiam a exportação. Gravação atômica. |
| `normalization.py` | Fonte única dos helpers: `text`, `digits`, `text_upper`, `pad_left`, `pad_right`, `resolve_row_value`, `normalize_date`, `date_to_txt`, `nascimento_to_aaaammdd`, `normalize_cpf`, `normalize_cns`, competência. Nenhum módulo redefine essas funções. |

Modelo de configuração versionado: `../penna_config.example.json`.
