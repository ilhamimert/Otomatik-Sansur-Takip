@echo off
echo ============================================
echo  AI Vision Guard - Kurulum Scripti
echo ============================================
echo.

:: Python kontrol
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [HATA] Python bulunamadi. https://python.org adresinden Python 3.11+ kurun.
    pause
    exit /b 1
)

echo [1/4] Sanal ortam olusturuluyor...
python -m venv venv
if %errorlevel% neq 0 (
    echo [HATA] Sanal ortam olusturulamadi.
    pause
    exit /b 1
)

echo [2/4] Sanal ortam aktive ediliyor...
call venv\Scripts\activate.bat

echo [3/4] Bagimliliklar yukleniyor...
pip install --upgrade pip
pip install -r requirements.txt

echo [4/4] Model klasoru olusturuluyor...
if not exist models mkdir models
if not exist data mkdir data

echo.
echo ============================================
echo  Kurulum tamamlandi!
echo  Uygulamayi baslatmak icin: run.bat
echo ============================================
pause
