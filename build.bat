@echo off
setlocal EnableDelayedExpansion

echo ============================================================
echo  SincroSIG - Build Script
echo ============================================================

:: Verificar PyInstaller
where pyinstaller >nul 2>&1
if errorlevel 1 (
    echo [ERROR] PyInstaller no encontrado. Instalar con: pip install pyinstaller
    pause & exit /b 1
)

:: Verificar Inno Setup
set ISC="C:\Program Files (x86)\Inno Setup 6\ISCC.exe"
if not exist %ISC% set ISC="C:\Program Files\Inno Setup 6\ISCC.exe"
if not exist %ISC% (
    echo [WARN] Inno Setup no encontrado en rutas por defecto.
    echo        Instalar desde: https://jrsoftware.org/isdl.php
    echo        O ajustar la variable ISC en este script.
    set SKIP_ISS=1
)

echo.
echo [1/2] Empaquetando con PyInstaller...
pyinstaller sincrosig.spec --clean --noconfirm
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
