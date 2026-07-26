@echo off
setlocal EnableDelayedExpansion

echo ============================================================
echo  SincroSIG - Build Script
echo ============================================================

:: Detectar PyInstaller (primero en PATH, luego en Python 3.12)
set PYI=pyinstaller
where pyinstaller >nul 2>&1
if errorlevel 1 (
    set PYI=C:\Users\gfrov\AppData\Local\Programs\Python\Python312\Scripts\pyinstaller.exe
    if not exist !PYI! (
        echo [ERROR] PyInstaller no encontrado. Instalar con:
        echo         C:\Users\gfrov\AppData\Local\Programs\Python\Python312\python.exe -m pip install pyinstaller
        pause & exit /b 1
    )
)

:: Verificar Inno Setup (rutas habituales + instalación winget en %LOCALAPPDATA%)
set ISC="C:\Program Files (x86)\Inno Setup 6\ISCC.exe"
if not exist %ISC% set ISC="C:\Program Files\Inno Setup 6\ISCC.exe"
if not exist %ISC% set ISC="%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe"
if not exist %ISC% (
    echo [WARN] Inno Setup no encontrado. Instalar con: winget install JRSoftware.InnoSetup
    echo        O ajustar la variable ISC en este script.
    set SKIP_ISS=1
)

echo.
echo [1/2] Empaquetando con PyInstaller...
%PYI% sincrosig.spec --clean --noconfirm
if errorlevel 1 (
    echo [ERROR] PyInstaller falló.
    pause & exit /b 1
)
echo [OK] PyInstaller completado. Salida en: dist\SincroSIG\

if defined SKIP_ISS goto :skip_installer

echo.
echo [2/2] Creando instalador con Inno Setup...
%ISC% installer\sincrosig.iss
if errorlevel 1 (
    echo [ERROR] Inno Setup falló.
    pause & exit /b 1
)
echo [OK] Instalador creado en: installer\

echo.
echo ============================================================
echo  Build completo.
echo  Subir a GitHub Releases: installer\SincroSIG_Setup_*.exe
echo ============================================================
goto :end

:skip_installer
echo.
echo [SKIP] Inno Setup no disponible. Solo se generó el directorio dist\.
echo        Para crear el instalador, instalar Inno Setup 6 y re-ejecutar.

:end
pause
