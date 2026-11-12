@echo off
REM ===== Sawtak engine for Windows: double-click to run =====
cd /d %~dp0
where python >nul 2>nul || (echo [!] Install Python 3.12 from https://www.python.org/downloads/ and tick "Add python.exe to PATH" & pause & exit /b 1)
if not exist .venv (
  echo First run: installing (10-20 minutes, one time only^)...
  python -m venv .venv || (pause & exit /b 1)
  call .venv\Scripts\activate
  python -m pip install --upgrade pip
  where nvidia-smi >nul 2>nul && (
    pip install torch torchaudio torchvision --index-url https://download.pytorch.org/whl/cu124
  ) || (
    pip install torch torchaudio torchvision --index-url https://download.pytorch.org/whl/cpu
  )
  pip install -r engine\requirements.txt || (pause & exit /b 1)
) else (
  call .venv\Scripts\activate
)
python -m engine.run %*
pause
