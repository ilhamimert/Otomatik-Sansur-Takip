@echo off
cd /d "%~dp0"
echo ============================================
echo  CNBC Turk - Windows Service Kurulum
echo ============================================
echo.

net session >nul 2>&1
if %errorLevel% neq 0 (
    echo HATA: Bu dosyayi yonetici olarak calistirmaniz gerekiyor.
    echo.
    echo Cozum: Sag tik ^> Yonetici olarak calistir
    pause
    exit /b 1
)

echo [1] pywin32 kuruluyor...
venv\Scripts\pip.exe install pywin32 --quiet
venv\Scripts\python.exe venv\Scripts\pywin32_postinstall.py -install >nul 2>&1

echo [2] Servis kaydediliyor...
venv\Scripts\python.exe service\windows_service.py install
if %errorLevel% neq 0 (
    echo Kurulum basarisiz.
    pause
    exit /b 1
)

echo [3] Servis baslatiliyor...
venv\Scripts\python.exe service\windows_service.py start
if %errorLevel% neq 0 (
    echo Servis baslatma basarisiz.
    pause
    exit /b 1
)

echo.
echo ============================================
echo  Servis basariyla kuruldu ve basladi!
echo  Bilgisayar her acildiginda otomatik calisir.
echo.
echo  Durdurmak : sc stop CnbcContentScanner
echo  Kaldirmak : service_remove.bat (yonetici ile)
echo  Loglar    : %~dp0logs\
echo ============================================
pause
