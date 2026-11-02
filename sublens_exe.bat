@echo off
setlocal
cd /d "%~dp0"

echo ============================================================
echo  SubLens  -  Tek dosya EXE derleme
echo ============================================================
echo.

REM venv yoksa kur
if not exist venv\Scripts\activate.bat (
    echo [1/4] venv olusturuluyor...
    python -m venv venv || goto :err
    call venv\Scripts\activate.bat
    python -m pip install --upgrade pip
) else (
    call venv\Scripts\activate.bat
)

echo.
echo [2/4] Bagimliliklar kontrol ediliyor...
pip install -q -r requirements.txt pyinstaller || goto :err

echo.
echo [3/4] Eski build temizleniyor...
taskkill /im SubLens.exe /f >NUL 2>&1
if exist build       rmdir /s /q build
if exist dist        rmdir /s /q dist
if exist SubLens.spec del /q SubLens.spec
if exist dist (
    echo UYARI: dist\ klasoru silinemedi. SubLens.exe hala calisiyor olabilir,
    echo tray ikonundan tamamen kapatip tekrar deneyin.
    goto :err
)

echo.
echo [4/4] PyInstaller derleme basliyor (1-3 dakika)...
echo.
python _build.py || goto :err

echo.
echo ============================================================
echo  TAMAM:  %CD%\dist\SubLens.exe
for %%I in ("%CD%\dist\SubLens.exe") do echo  Boyut :  %%~zI bayt
echo ============================================================
pause
exit /b 0

:err
echo.
echo HATA: Derleme basarisiz. Yukaridaki ciktiya bakin.
pause
exit /b 1
