@echo off
setlocal
cd /d "%~dp0"

echo ================================================
echo  PENNA CONVERSOR - Gerar instalador (build completo)
echo ================================================
echo.

REM ---- 1) Ambiente virtual (usa o existente ou cria um novo) ----
if not exist ".venv\Scripts\python.exe" (
    echo Criando ambiente virtual...
    python -m venv .venv
    if errorlevel 1 goto erro
)

set "PY=%~dp0.venv\Scripts\python.exe"

REM ---- 2) Dependencias ----
echo Instalando dependencias ^(pandas, openpyxl, tkinterdnd2, pillow, pyinstaller^)...
"%PY%" -m pip --version >nul 2>&1
if errorlevel 1 (
    echo pip ausente neste .venv ^(criado por uv?^) - tentando ensurepip...
    "%PY%" -m ensurepip --default-pip >nul 2>&1
)
"%PY%" -m pip --version >nul 2>&1
if errorlevel 1 (
    where uv >nul 2>&1
    if errorlevel 1 (
        echo ERRO: pip e uv ausentes - nao ha como instalar as dependencias.
        goto erro
    )
    echo pip indisponivel - instalando com uv...
    uv pip install --python "%~dp0.venv" -r requirements.txt
    if errorlevel 1 goto erro
    goto deps_ok
)
"%PY%" -m pip install --quiet --disable-pip-version-check -r requirements.txt
if errorlevel 1 goto erro
:deps_ok

REM ---- 3) Testes rapidos do nucleo (gate de qualidade antes do build) ----
echo Rodando testes do nucleo de conversao...
"%PY%" -m unittest discover -s tests -q
if errorlevel 1 goto erro

REM ---- 4) Executavel standalone com PyInstaller ----
echo Gerando executavel PennaConversor.exe com PyInstaller...
if exist "build" rmdir /s /q "build"
if exist "dist" rmdir /s /q "dist"
"%PY%" -m PyInstaller Conversor.spec --noconfirm
if errorlevel 1 goto erro
if not exist "dist\PennaConversor.exe" goto erro

REM ---- 5) Instalador com Inno Setup 6 ----
set "ISCC=%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe"
if not exist "%ISCC%" set "ISCC=%LocalAppData%\Programs\Inno Setup 6\ISCC.exe"
if not exist "%ISCC%" (
    echo.
    echo ERRO: Inno Setup 6 nao foi encontrado.
    echo Instale gratuitamente em: https://jrsoftware.org/isdl.php
    echo e rode este script novamente.
    pause
    exit /b 1
)

echo Compilando instalador com Inno Setup...
"%ISCC%" installer.iss
if errorlevel 1 goto erro

echo.
echo ================================================
echo  SUCESSO!
echo  Instalador gerado em:
echo  %~dp0installer_output\PennaConversor_Installer.exe
echo ================================================
start "" explorer "%~dp0installer_output"
pause
exit /b 0

:erro
echo.
echo ERRO no build. Verifique as mensagens acima.
pause
exit /b 1
