@echo off
cd /d "%~dp0"
if not exist venv\Scripts\activate.bat (
    python -m venv venv
    call venv\Scripts\activate.bat
    python -m pip install --upgrade pip
) else (
    call venv\Scripts\activate.bat
)
python -c "import PySide6, numpy, mss, winrt.windows.media.ocr, anthropic" 2>NUL || pip install -r requirements.txt
python main.py
if errorlevel 1 pause
