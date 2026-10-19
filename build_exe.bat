@echo off
setlocal
cd /d "%~dp0"

echo ================================================
echo  PENNA CONVERSOR - Gerar executavel standalone
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
echo Instalando dependencias (pandas, openpyxl, tkinterdnd2, pillow, pyinstaller)...
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

REM ---- 3) Executavel standalone com PyInstaller ----
echo Gerando executavel PennaConversor.exe com PyInstaller...
if exist "build" rmdir /s /q "build"
if exist "dist" rmdir /s /q "dist"
"%PY%" -m PyInstaller Conversor.spec --noconfirm
if errorlevel 1 goto erro
if not exist "dist\PennaConversor.exe" goto erro

echo.
echo ================================================
echo  SUCESSO!
echo  Executavel gerado em:
echo  %~dp0dist\PennaConversor.exe
echo ================================================
echo.
echo Para gerar o instalador completo (setup para o cliente),
echo rode build_installer.bat
pause
exit /b 0

:erro
echo.
echo ERRO no build. Verifique as mensagens acima.
pause
exit /b 1
