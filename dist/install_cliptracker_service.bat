@echo off
setlocal enabledelayedexpansion

set SERVICE_NAME=ClipTracker
set NSSM_PATH=%~dp0nssm.exe
set INSTALL_DIR=C:\Program Files\ClipTracker
set EXE_NAME=cliptracker.exe
set RTF_CONF=rtfactor.conf
set OUT_FOLDER_CONF=out_folder.ini

REM Vérifier les droits administrateur
net session >nul 2>&1
if %errorlevel% neq 0 (
    echo Erreur: Exécutez ce script en tant qu'Administrateur!
    pause
    exit /b 1
)

REM Vérifier la présence de nssm.exe
if not exist "%NSSM_PATH%" (
    echo Erreur: nssm.exe introuvable dans ce dossier!
    echo Placez nssm.exe ici: %~dp0
    pause
    exit /b 1
)

REM Créer le dossier d'installation s'il n'existe pas
if not exist "%INSTALL_DIR%" (
    echo 📁 Création du dossier d'installation...
    mkdir "%INSTALL_DIR%"
)

REM Copier le programme compilé
echo 📂 Copie de %EXE_NAME% dans %INSTALL_DIR%...
copy /Y "%~dp0%EXE_NAME%" "%INSTALL_DIR%\"

REM Copier ou créer rtfactor.conf si absent
if not exist "%INSTALL_DIR%\%RTF_CONF%" (
    echo 📝 Création de %RTF_CONF% avec valeur par défaut...
    echo 10.0 > "%INSTALL_DIR%\%RTF_CONF%"
) else (
    echo ✅ %RTF_CONF% déjà présent.
)

REM Copier ou créer out_folder.ini si absent
if not exist "%INSTALL_DIR%\%OUT_FOLDER_CONF%" (
    echo 📝 Création de %OUT_FOLDER_CONF% avec valeur par défaut...
    echo %INSTALL_DIR% > "%INSTALL_DIR%\%OUT_FOLDER_CONF%"
) else (
    echo ✅ %OUT_FOLDER_CONF% déjà présent.
)

REM Vérifier l'existence du service et le supprimer s'il existe déjà
echo Vérification du service %SERVICE_NAME%...
"%NSSM_PATH%" status %SERVICE_NAME% >nul 2>&1
if %errorlevel% equ 0 (
    echo 🔄 Le service %SERVICE_NAME% existe déjà. Suppression de l'ancien service...
    
    REM Arrêt et suppression du service existant
    "%NSSM_PATH%" stop %SERVICE_NAME% confirm
    "%NSSM_PATH%" remove %SERVICE_NAME% confirm
    timeout /t 2 >nul
)

REM Installation du service avec NSSM
echo 🚀 Installation du service %SERVICE_NAME%...
"%NSSM_PATH%" install %SERVICE_NAME% "%INSTALL_DIR%\%EXE_NAME%"

REM Configuration du service
echo 🔧 Configuration du service...
"%NSSM_PATH%" set %SERVICE_NAME% DisplayName "ClipTracker"
"%NSSM_PATH%" set %SERVICE_NAME% Start SERVICE_AUTO_START
"%NSSM_PATH%" set %SERVICE_NAME% AppDirectory "%INSTALL_DIR%"
"%NSSM_PATH%" set %SERVICE_NAME% AppStdout "%INSTALL_DIR%\cliptracker.log"
"%NSSM_PATH%" set %SERVICE_NAME% AppStderr "%INSTALL_DIR%\cliptracker_error.log"
"%NSSM_PATH%" set %SERVICE_NAME% AppStopMethodSkip 0

REM Démarrer le service
echo ▶️ Démarrage du service...
"%NSSM_PATH%" start %SERVICE_NAME%

REM Vérification du statut du service
echo 🔍 Vérification du statut du service...
"%NSSM_PATH%" status %SERVICE_NAME%
if %errorlevel% neq 0 (
    echo ❌ Erreur: Le service n'a pas pu être démarré!
    pause
    exit /b 1
)

echo 🎉 Service ClipTracker installé et démarré avec succès!
pause
exit /b 0
