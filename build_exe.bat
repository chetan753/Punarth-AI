@echo off
REM Builds a Windows desktop app in dist\PunarthAI\PunarthAI.exe
cd /d "%~dp0"
call .venv\Scripts\activate
pip install pyinstaller
pyinstaller --noconfirm --windowed --name PunarthAI ^
  --hidden-import payment_server.server ^
  --collect-submodules onnxruntime ^
  main.py
if exist models xcopy /E /I /Y models dist\PunarthAI\models
if exist .env copy /Y .env dist\PunarthAI\.env
echo.
echo Done. Run dist\PunarthAI\PunarthAI.exe
