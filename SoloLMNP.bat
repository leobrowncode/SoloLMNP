@echo off
setlocal
cd /d "%~dp0"
chcp 65001 >nul
set "PYTHONUNBUFFERED=1"
set "PYTHONUTF8=1"

set "PYCMD="

where py >nul 2>nul
if not errorlevel 1 (
  py -3.12 -c "import sys" >nul 2>nul
  if not errorlevel 1 set "PYCMD=py -3.12"
)

if not defined PYCMD (
  echo.
  echo SoloLMNP: Python 3.12 ou plus recent est requis.
  echo.
  echo Installez-le avec :
  echo   winget install -e --id Python.Python.3.12
  echo Puis fermez cette fenetre et double-cliquez a nouveau sur SoloLMNP.bat.
  echo.
  pause
  exit /b 1
)

echo Lancement de SoloLMNP avec Python 3.12...
%PYCMD% scripts\start_local.py
set EXITCODE=%ERRORLEVEL%
if not "%EXITCODE%"=="0" (
  echo.
  echo SoloLMNP s'est arrete avec une erreur.
  pause
)
exit /b %EXITCODE%
