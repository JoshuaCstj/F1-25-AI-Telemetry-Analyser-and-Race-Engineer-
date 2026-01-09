@echo off
chcp 65001 >nul
title F1 25 Race Engineer - Installation
color 0A

echo.
echo ========================================================================
echo.
echo            🏎️  F1 25 RACE ENGINEER - INSTALLATION  🏎️
echo.
echo ========================================================================
echo.
echo.
echo   Bienvenue dans l'installateur automatique!
echo.
echo   Ce script va:
echo   ✅ Vérifier Python
echo   ✅ Installer toutes les dépendances
echo   ✅ Créer les raccourcis de lancement
echo   ✅ Configurer l'application
echo.
echo   Temps estimé: 2-5 minutes
echo.
echo ========================================================================
echo.
pause

python setup.py

echo.
echo ========================================================================
echo   Installation terminée!
echo ========================================================================
echo.
pause