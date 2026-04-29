@echo off
cd /d "%~dp0"
echo ============================================
echo  CNBC Turk - Gorev Zamanlayici Kurulum
echo ============================================
echo.

net session >nul 2>&1
if %errorLevel% neq 0 (
    echo HATA: Yonetici olarak calistirin.
    echo Sag tik ^> Yonetici olarak calistir
    pause
    exit /b 1
)

set TASK_NAME=CnbcContentScanner
set PYTHON=%~dp0venv\Scripts\python.exe
set SCRIPT=%~dp0service\windows_service.py

echo Eski gorev siliniyor (varsa)...
schtasks /delete /tn "%TASK_NAME%" /f >nul 2>&1

echo Gorev olusturuluyor...
schtasks /create /tn "%TASK_NAME%" /tr "\"%PYTHON%\" \"%SCRIPT%\" run" /sc onstart /ru SYSTEM /rl HIGHEST /f

if %errorLevel% neq 0 (
    echo Gorev olusturma basarisiz.
    pause
    exit /b 1
)

echo Gorev hemen baslatiliyor...
schtasks /run /tn "%TASK_NAME%"

echo.
echo ============================================
echo  Basariyla kuruldu!
echo  Bilgisayar her acildiginda otomatik calisir.
echo.
echo  Durdurmak : schtasks /end /tn "%TASK_NAME%"
echo  Kaldirmak : schtasks /delete /tn "%TASK_NAME%" /f
echo  Loglar    : %~dp0logs\
echo ============================================
pause
