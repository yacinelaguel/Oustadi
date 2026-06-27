@echo off
setlocal EnableDelayedExpansion

title OSTADI - Server Launcher

echo.
echo ================================================================
echo                  OSTADI — ÃÓÊÇÐí
echo          Algerian AI Exam Generator
echo          Architect: Yacine Laguel
echo ================================================================
echo.

:: -------------------------------------------------------
:: STEP 1 - Find Python 3.10+
:: -------------------------------------------------------

echo [1/9] Checking Python...

set PYTHON=

for %%P in (python python3 py) do (
    %%P --version >nul 2>&1
    if not errorlevel 1 (
        set PYTHON=%%P
        goto :python_found
    )
)

echo.
echo ERROR:
echo Python was not found.
echo Install Python 3.10 or newer.
pause
exit /b 1

:python_found

%PYTHON% --version

:: -------------------------------------------------------
:: STEP 2 - Project root
:: -------------------------------------------------------

cd /d "%~dp0"

echo.
echo Project:
echo %cd%

:: -------------------------------------------------------
:: STEP 3 - Virtual Environment
:: -------------------------------------------------------

if not exist ".venv" (

    echo.
    echo Creating virtual environment...

    %PYTHON% -m venv .venv

)

call .venv\Scripts\activate.bat

:: -------------------------------------------------------
:: STEP 4 - Upgrade pip
:: -------------------------------------------------------

echo.
echo Updating pip...

python -m pip install --upgrade pip

:: -------------------------------------------------------
:: STEP 5 - Install requirements
:: -------------------------------------------------------

if not exist requirements.txt (

    echo.
    echo requirements.txt not found.
    pause
    exit /b 1

)

echo.
echo Installing packages...

pip install -r requirements.txt

:: -------------------------------------------------------
:: STEP 6 - Fonts
:: -------------------------------------------------------

if not exist backend\fonts mkdir backend\fonts

set FONT_OK=1

if not exist backend\fonts\Amiri-Regular.ttf (
    echo.
    echo Missing:
    echo backend\fonts\Amiri-Regular.ttf
    set FONT_OK=0
)

if not exist backend\fonts\Amiri-Bold.ttf (
    echo.
    echo Missing:
    echo backend\fonts\Amiri-Bold.ttf
    set FONT_OK=0
)

if "%FONT_OK%"=="0" (

    echo.
    echo ===========================================
    echo Download Amiri Font Family
    echo.
    echo Copy:
    echo     Amiri-Regular.ttf
    echo     Amiri-Bold.ttf
    echo.
    echo Into:
    echo backend\fonts\
    echo ===========================================

    pause
    exit /b 1

)

:: -------------------------------------------------------
:: STEP 7 - Exports folder
:: -------------------------------------------------------

if not exist backend\exports mkdir backend\exports

:: -------------------------------------------------------
:: STEP 8 - Frontend
:: -------------------------------------------------------

if not exist frontend\index.html (

    echo.
    echo WARNING:
    echo frontend\index.html not found.

)

:: -------------------------------------------------------
:: STEP 9 - Launch
:: -------------------------------------------------------

echo.
echo ================================================================
echo Server Ready
echo.
echo http://127.0.0.1:8000
echo.
echo API Docs:
echo http://127.0.0.1:8000/api/docs
echo ================================================================
echo.

cd backend

python -m uvicorn main:app ^
    --host 0.0.0.0 ^
    --port 8000 ^
    --reload ^
    --reload-dir "%cd%" ^
    --log-level info ^
    --access-log

pause