@echo off
cd /d "%~dp0"

if not exist ".env" (
    echo [ERREUR] Fichier .env manquant. Copie .env.example en .env et remplis les variables.
    pause
    exit /b 1
)

where python >nul 2>&1
if errorlevel 1 (
    echo [ERREUR] Python introuvable dans le PATH.
    pause
    exit /b 1
)

where ffmpeg >nul 2>&1
if errorlevel 1 (
    echo [ERREUR] FFmpeg introuvable dans le PATH.
    echo Installe-le depuis https://ffmpeg.org/download.html
    pause
    exit /b 1
)

echo [OK] Lancement de Discoss...
python bot.py
pause
