@echo off
cd /d "%~dp0"
echo ============================================
echo  CNBC Turk - Windows Service Kaldirma
echo ============================================
echo.

net session >nul 2>&1
if %errorLevel% neq 0 (
    echo HATA: Bu dosyayi yonetici olarak calistirmaniz gerekiyor.
    echo Cozum: Sag tik ^> Yonetici olarak calistir
    pause
    exit /b 1
)

echo Servis durduruluyor...
venv\Scripts\python.exe service\windows_service.py stop 2>nul

echo Servis kaldiriliyor...
venv\Scripts\python.exe service\windows_service.py remove

echo.
echo Servis kaldirildi.
pause
