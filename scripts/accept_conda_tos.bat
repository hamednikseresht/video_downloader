@echo off
setlocal EnableExtensions
title Accept Conda Terms of Service

echo.
echo  Conda Terms of Service — one-time accept
echo  ----------------------------------------
echo.

if exist "%USERPROFILE%\miniconda3\Scripts\activate.bat" call "%USERPROFILE%\miniconda3\Scripts\activate.bat"
if exist "%USERPROFILE%\anaconda3\Scripts\activate.bat" call "%USERPROFILE%\anaconda3\Scripts\activate.bat"
if exist "%LocalAppData%\miniconda3\Scripts\activate.bat" call "%LocalAppData%\miniconda3\Scripts\activate.bat"

where conda >nul 2>&1
if errorlevel 1 (
    echo [ERROR] conda not found. Install Miniconda first:
    echo   https://docs.anaconda.io/miniconda/
    goto end_pause
)

echo Running conda tos accept for default channels...
echo.

call conda tos accept --override-channels --channel https://repo.anaconda.com/pkgs/main
call conda tos accept --override-channels --channel https://repo.anaconda.com/pkgs/r
call conda tos accept --override-channels --channel https://repo.anaconda.com/pkgs/msys2

echo.
echo [OK] If no errors appeared above, TOS should be accepted.
echo.
echo Tip: the launcher uses conda-forge first to avoid most TOS issues:
echo   conda create -n youtube-downloader -c conda-forge --override-channels python=3.12 -y
echo.

:end_pause
echo Press any key to close...
pause >nul
