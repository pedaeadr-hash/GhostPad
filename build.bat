@echo off
setlocal
cd /d "%~dp0"

echo [1/3] Preparando ambiente virtual...
if not exist .venv (
    py -m venv .venv
    if errorlevel 1 goto erro
)
call .venv\Scripts\activate.bat

echo.
echo [2/3] Instalando dependencias...
python -m pip install --upgrade pip
python -m pip install -r requirements.txt pyinstaller
if errorlevel 1 goto erro

echo.
echo [3/3] Gerando GhostPad.exe...
flet pack ghostpad.py --name GhostPad --icon assets\icon.ico ^
  --product-name GhostPad --file-description "GhostPad - ponte de controle celular para PC" ^
  --product-version 1.0.0 -y -- --collect-all vgamepad
if errorlevel 1 goto erro

echo.
echo Pronto: dist\GhostPad.exe
pause
exit /b 0

:erro
echo.
echo Falhou. Veja a mensagem acima.
echo Dica: se der erro no Python 3.14, instale o 3.12 ou 3.13 e troque "py -m venv" por "py -3.12 -m venv".
pause
exit /b 1
