# Guia de compilação — PENNA CONVERSOR

Como regenerar o EXE e o instalador deste produto a partir do código-fonte.

## Pré-requisitos (uma vez)

- Windows 10/11
- [Python 3.10+](https://www.python.org/downloads/) (marque "Add to PATH")
- [Inno Setup 6](https://jrsoftware.org/isdl.php) (apenas para o instalador)

## Gerar tudo (EXE + instalador)

```
build_installer.bat
```

O script: cria o `.venv`, instala as dependências fixadas do
`requirements.txt`, roda os testes do núcleo, compila o EXE com PyInstaller
(`Conversor.spec`) e empacota o instalador com Inno Setup.

Resultados:

| Artefato | Caminho |
|---|---|
| EXE standalone | `dist\PennaConversor.exe` |
| Instalador do cliente | `installer_output\PennaConversor_Installer.exe` |

## Gerar apenas o EXE

```
build_exe.bat
```

## Atualizar a versão

1. Edite `#define MyAppVersion` em `installer.iss`;
2. Rode `build_installer.bat`.

## Observações técnicas

- O spec usa modo **onefile** (EXE único), igual ao build de produção do
  projeto original (`APAC_MAG_GERADOR.spec`).
- As bases SIGTAP de `dados/bases_sia` são embutidas no EXE e extraídas em
  tempo de execução — não é necessário instalá-las à parte.
- `penna_config.json` também é embutido (fallback de fábrica). Em máquinas do
  cliente, o arquivo editável fica em
  `%LOCALAPPDATA%\PennaConversor\penna_config.json` (instalação via setup) ou
  ao lado do EXE (modo standalone).
- O código fica em `src/penna`; o spec usa `pathex=['src']` e a entrada `src/penna/__main__.py`.
- Testes: `pip install -e .` e `python -m unittest discover -s tests`
  (em clone limpo, copie antes `penna_config.example.json` para `penna_config.json`).
