@echo off
setlocal EnableExtensions EnableDelayedExpansion

REM Shared launcher: sets up Python/Conda env, installs deps, health check, starts app.
REM Usage: bootstrap.bat app.py

if "%~1"=="" (
    echo [ERROR] bootstrap.bat requires an entry script ^(app.py^).
    goto fail_pause
)

set "APP_ENTRY=%~1"
cd /d "%~dp0\.."

if not exist "downloads" mkdir "downloads"

set "APP_TITLE=YouTube ^& Instagram Downloader"

title "!APP_TITLE!"
echo.
echo  !APP_TITLE!
echo  ------------------------------
echo.
echo  This window stays open so you can read setup messages and errors.
echo  While the app runs, leave this window open. Close it to stop the app.
echo.

REM --- Detect Python launcher / python.exe ---
set "HAS_PY_LAUNCHER=0"
set "HAS_PYTHON=0"
set "HAS_CONDA=0"
set "RUNTIME_METHOD="

py -3 --version >nul 2>&1 && set "HAS_PY_LAUNCHER=1"
where python >nul 2>&1 && set "HAS_PYTHON=1"

call :init_conda
where conda >nul 2>&1 && set "HAS_CONDA=1"

echo [DETECT] Python launcher: !HAS_PY_LAUNCHER!  ^|  python.exe: !HAS_PYTHON!  ^|  conda: !HAS_CONDA!
echo.

if "!HAS_PY_LAUNCHER!"=="1" goto choose_runtime
if "!HAS_PYTHON!"=="1" goto choose_runtime
if "!HAS_CONDA!"=="1" goto choose_runtime
goto no_runtime

:choose_runtime
if "!HAS_CONDA!"=="1" if "!HAS_PY_LAUNCHER!"=="1" goto prompt_runtime
if "!HAS_CONDA!"=="1" if "!HAS_PYTHON!"=="1" goto prompt_runtime
if "!HAS_PY_LAUNCHER!"=="1" goto use_venv
if "!HAS_PYTHON!"=="1" goto use_venv
goto use_conda

:prompt_runtime
echo Both Python and Conda were found.
echo   1 ^) Python virtual environment ^(.venv^)  [Recommended — no Conda TOS issues]
echo   2 ^) Conda environment ^(youtube-downloader^)
echo.
set "RUNTIME_CHOICE="
set /p "RUNTIME_CHOICE=Choose 1 or 2 [default 1]: "
if "!RUNTIME_CHOICE!"=="" set "RUNTIME_CHOICE=1"
if "!RUNTIME_CHOICE!"=="2" goto use_conda
goto use_venv

:use_venv
set "RUNTIME_METHOD=venv"
set "YTD_RUNTIME=venv"
call :pick_python_launcher
echo [RUNTIME] Using Python virtual environment ^(.venv^) with !PY_LAUNCHER!

if exist ".venv\Scripts\python.exe" (
    call :check_venv_python_version
    if errorlevel 1 goto recreate_venv
)

if not exist ".venv\Scripts\python.exe" goto create_venv
goto activate_venv

:recreate_venv
echo.
echo [WARN] Existing .venv uses Python 3.10 or older. Streamlit recommends 3.11+.
set "RECREATE="
set /p "RECREATE=Recreate .venv with !PY_LAUNCHER!? [Y/n]: "
if /i "!RECREATE!"=="n" goto activate_venv
echo [SETUP] Removing old .venv ...
rmdir /s /q ".venv" 2>nul

:create_venv
echo [SETUP] Creating .venv ...
!PY_LAUNCHER! -m venv .venv
if errorlevel 1 (
    echo [ERROR] Could not create .venv
    call :show_python_guide
    goto fail_pause
)

:activate_venv
call ".venv\Scripts\activate.bat"
if errorlevel 1 (
    echo [ERROR] Could not activate .venv
    goto fail_pause
)
goto setup_deps

:pick_python_launcher
set "PY_LAUNCHER="
py -3.12 --version >nul 2>&1 && set "PY_LAUNCHER=py -3.12"
if not defined PY_LAUNCHER py -3.11 --version >nul 2>&1 && set "PY_LAUNCHER=py -3.11"
if not defined PY_LAUNCHER py -3 --version >nul 2>&1 && set "PY_LAUNCHER=py -3"
if not defined PY_LAUNCHER set "PY_LAUNCHER=python"
exit /b 0

:check_venv_python_version
".venv\Scripts\python.exe" -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 11) else 1)" >nul 2>&1
exit /b %ERRORLEVEL%

:use_conda
set "RUNTIME_METHOD=conda"
set "YTD_RUNTIME=conda"
echo [RUNTIME] Using Conda environment ^(youtube-downloader^)

call :init_conda
where conda >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Conda not available.
    call :show_python_guide
    goto fail_pause
)

conda info --envs 2>nul | findstr /i /c:"youtube-downloader" >nul 2>&1
if errorlevel 1 (
    call :create_conda_env
    if errorlevel 1 goto conda_failed
) else (
    echo [OK] Conda environment "youtube-downloader" already exists.
)
call :activate_conda_env
if errorlevel 1 goto conda_failed
call :check_conda_python_version
if errorlevel 1 call :offer_conda_python_upgrade
goto setup_deps

:create_conda_env
echo.
echo [SETUP] Preparing Conda environment ^(first time only^) ...
echo.

REM Try conda-forge first — avoids Anaconda default-channel TOS on many installs
echo [SETUP] Creating env from conda-forge ^(recommended^) ...
call conda create -n youtube-downloader -c conda-forge --override-channels python=3.12 -y
if not errorlevel 1 (
    echo.
    echo [OK] Conda environment "youtube-downloader" created successfully.
    echo      ^(Ignore any conda-pypi INFO/WARNING above — that is normal.^)
    echo.
    echo [SETUP] Continuing with Python package install...
    exit /b 0
)

echo.
echo [WARN] conda-forge create failed. Trying Anaconda channels with Terms of Service ...
call :accept_conda_tos
if errorlevel 1 (
    echo [ERROR] Could not accept Conda Terms of Service automatically.
    call :show_conda_tos_guide
    exit /b 1
)

echo [SETUP] Creating env youtube-downloader ...
call conda create -n youtube-downloader python=3.12 -y
if not errorlevel 1 (
    echo.
    echo [OK] Conda environment "youtube-downloader" created successfully.
    echo      ^(Ignore any conda-pypi INFO/WARNING above — that is normal.^)
    echo.
    echo [SETUP] Continuing with Python package install...
    exit /b 0
)
exit /b 1

:accept_conda_tos
echo.
echo [SETUP] Accepting Conda Terms of Service ^(one-time, may take a moment^) ...
set "TOS_OK=1"

call conda tos accept --override-channels --channel https://repo.anaconda.com/pkgs/main
if errorlevel 1 set "TOS_OK=0"

call conda tos accept --override-channels --channel https://repo.anaconda.com/pkgs/r
if errorlevel 1 set "TOS_OK=0"

call conda tos accept --override-channels --channel https://repo.anaconda.com/pkgs/msys2
if errorlevel 1 set "TOS_OK=0"

if "!TOS_OK!"=="0" exit /b 1
echo [OK] Conda Terms of Service accepted.
exit /b 0

:conda_failed
echo.
echo [ERROR] Conda setup failed.
echo.
if "!HAS_PY_LAUNCHER!"=="1" set "HAS_PYTHON=1"
if "!HAS_PYTHON!"=="1" (
    echo You also have Python installed. The .venv route avoids Conda entirely.
    set "SWITCH="
    set /p "SWITCH=Switch to Python .venv now? [Y/n]: "
    if /i not "!SWITCH!"=="n" (
        set "RUNTIME_METHOD=venv"
        set "YTD_RUNTIME=venv"
        goto use_venv
    )
)
call :show_conda_tos_guide
call :show_python_guide
goto fail_pause

:setup_deps
set "YTD_RUNTIME=!RUNTIME_METHOD!"
echo.
call :upgrade_packages
echo [SETUP] Installing / verifying Python packages ...
echo        ^(This may take a few minutes on first run — please wait.^)
echo.
if "!RUNTIME_METHOD!"=="conda" (
    python scripts\healthcheck.py --ensure-deps
    if errorlevel 1 goto deps_failed
    python scripts\healthcheck.py --check
    if errorlevel 1 goto health_failed
) else (
    python scripts\healthcheck.py --ensure-deps
    if errorlevel 1 goto deps_failed
    python scripts\healthcheck.py --check
    if errorlevel 1 goto health_failed
)

call :offer_ffmpeg_install
if errorlevel 1 goto fail_pause
goto start_app

:upgrade_packages
echo.
echo [UPDATE] Updating pip and all project packages ^(yt-dlp, streamlit, curl_cffi + dependencies^) ...
python -m pip install --upgrade pip --quiet
python -m pip install --upgrade --upgrade-strategy eager -r requirements.txt --quiet
if errorlevel 1 (
    echo [WARN] Package update failed ^(offline?^). Continuing with the installed versions.
) else (
    echo [OK] Packages are up to date.
)
exit /b 0

:deps_failed
echo.
echo [ERROR] Dependency installation failed.
echo Run manually: pip install -r requirements.txt
goto fail_pause

:health_failed
echo.
echo [ERROR] Health check failed. Fix the issues above, then run this .bat again.
call :offer_ffmpeg_install
goto fail_pause

:start_app
echo.
echo ============================================================
echo [START] Opening http://localhost:8501
echo         Entry: !APP_ENTRY!
echo.
echo  DO NOT CLOSE this window while the app is running.
echo  Closing it will stop the server.
echo ============================================================
echo.

if "!RUNTIME_METHOD!"=="conda" (
    python !APP_ENTRY!
) else (
    python !APP_ENTRY!
)
set "APP_EXIT=!ERRORLEVEL!"

echo.
echo ============================================================
if "!APP_EXIT!"=="0" (
    echo [INFO] The app stopped.
) else (
    echo [ERROR] The app exited with code !APP_EXIT!.
)
echo ============================================================
echo.
echo Press any key to close this window...
pause >nul
exit /b !APP_EXIT!

:no_runtime
echo [ERROR] No Python or Conda installation was detected.
call :show_python_guide
goto fail_pause

:show_python_guide
echo.
echo === Installation guide ===
echo.
echo Option A — Python ^(recommended^)
echo   1. Download Python 3.11+ : https://www.python.org/downloads/
echo   2. Run installer — CHECK "Add python.exe to PATH"
echo   3. Open a new Command Prompt and run this .bat again
echo.
echo Option B — Miniconda
echo   1. Download : https://docs.anaconda.io/miniconda/
echo   2. Install, open "Anaconda Prompt", cd to this folder
echo   3. Run this .bat again — prefer option 1 ^(.venv^) if Python is on PATH
echo.
echo Option C — Manual run
echo   pip install -r requirements.txt
echo   python scripts\healthcheck.py --check
echo   python !APP_ENTRY!
echo.
exit /b 0

:show_conda_tos_guide
echo.
echo === Fix Conda Terms of Service manually ===
echo.
echo Open "Anaconda Prompt" or a terminal where conda works, then run:
echo.
echo   conda tos accept --override-channels --channel https://repo.anaconda.com/pkgs/main
echo   conda tos accept --override-channels --channel https://repo.anaconda.com/pkgs/r
echo   conda tos accept --override-channels --channel https://repo.anaconda.com/pkgs/msys2
echo.
echo Or avoid Conda: install Python from python.org and run this .bat again,
echo choose option 1 ^(.venv^).
echo.
echo Or create the env with conda-forge only:
echo   conda create -n youtube-downloader -c conda-forge --override-channels python=3.12 -y
echo.
exit /b 0

:offer_ffmpeg_install
where ffmpeg >nul 2>&1
if not errorlevel 1 exit /b 0

echo.
echo [WARN] FFmpeg was not found. Video merge and MP3 conversion need it.
where winget >nul 2>&1
if errorlevel 1 (
    echo Install FFmpeg manually: https://ffmpeg.org/download.html
    echo Or: winget install Gyan.FFmpeg
    echo.
    set "CONTINUE="
    set /p "CONTINUE=Continue without FFmpeg? [Y/n]: "
    if /i "!CONTINUE!"=="n" exit /b 1
    exit /b 0
)

set "INSTALL_FF="
set /p "INSTALL_FF=Try to install FFmpeg with winget now? [Y/n]: "
if /i "!INSTALL_FF!"=="n" exit /b 0

echo [SETUP] Installing FFmpeg via winget ...
if "!RUNTIME_METHOD!"=="conda" (
    python scripts\healthcheck.py --install-ffmpeg
) else (
    python scripts\healthcheck.py --install-ffmpeg
)
echo.
echo If FFmpeg was just installed, restart this .bat if the app still warns about FFmpeg.
exit /b 0

:init_conda
if defined CONDA_ACTIVATE goto :eof
set "CONDA_ACTIVATE="
if exist "%USERPROFILE%\miniconda3\Scripts\activate.bat" set "CONDA_ACTIVATE=%USERPROFILE%\miniconda3\Scripts\activate.bat"
if exist "%USERPROFILE%\anaconda3\Scripts\activate.bat" set "CONDA_ACTIVATE=%USERPROFILE%\anaconda3\Scripts\activate.bat"
if exist "%LocalAppData%\miniconda3\Scripts\activate.bat" set "CONDA_ACTIVATE=%LocalAppData%\miniconda3\Scripts\activate.bat"
if exist "%ProgramData%\miniconda3\Scripts\activate.bat" set "CONDA_ACTIVATE=%ProgramData%\miniconda3\Scripts\activate.bat"
if defined CONDA_ACTIVATE call "%CONDA_ACTIVATE%" >nul 2>&1
goto :eof

:activate_conda_env
call :init_conda
if not defined CONDA_ACTIVATE (
    echo [ERROR] Could not find conda activate script.
    exit /b 1
)
call "%CONDA_ACTIVATE%"
call conda activate youtube-downloader
if errorlevel 1 (
    echo [ERROR] Could not activate conda env "youtube-downloader".
    echo Try manually: conda activate youtube-downloader
    exit /b 1
)
echo [OK] Activated conda env: youtube-downloader
where python >nul 2>&1
if errorlevel 1 (
    echo [ERROR] python not found after conda activate.
    exit /b 1
)
exit /b 0

:check_conda_python_version
python -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 11) else 1)" >nul 2>&1
exit /b %ERRORLEVEL%

:offer_conda_python_upgrade
echo.
echo [WARN] Conda env uses Python 3.10. Streamlit recommends 3.11+ ^(deprecation warnings^).
echo   A^) Upgrade in place: conda install -n youtube-downloader python=3.12 -y
echo   B^) Recreate env ^(removes env, reinstalls packages^)
echo   C^) Continue with 3.10 anyway
echo.
set "UPGRADE="
set /p "UPGRADE=Choose A/B/C [default A]: "
if "!UPGRADE!"=="" set "UPGRADE=A"
if /i "!UPGRADE!"=="C" exit /b 0
if /i "!UPGRADE!"=="B" (
    echo [SETUP] Removing old conda env ...
    call conda env remove -n youtube-downloader -y
    call :create_conda_env
    if errorlevel 1 exit /b 1
    call :activate_conda_env
    exit /b 0
)
echo [SETUP] Upgrading Python in conda env to 3.12 ...
call conda install -n youtube-downloader python=3.12 -y
if errorlevel 1 (
    echo [WARN] In-place upgrade failed. Try option B on next run.
    exit /b 0
)
echo [OK] Python upgraded. Reinstalling pip packages ...
python -m pip install -r requirements.txt --upgrade
exit /b 0

:fail_pause
echo.
echo ============================================================
echo  Setup did not finish. Read the messages above.
echo ============================================================
echo.
echo Press any key to close this window...
pause >nul
exit /b 1
