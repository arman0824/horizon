@echo off
rem Open Horizon's launcher on Windows: pick your Minecraft files, press Play.
rem Double-click "Start Horizon.bat" in the archive; this file may sit beside it or in tools\.
setlocal
set "HERE=%~dp0"
set "ROOT=%HERE%"
if not exist "%ROOT%tools\launcher.py" set "ROOT=%HERE%.."

rem The python.org installer includes Tk; the Microsoft Store build does not.
py -3 -c "import tkinter" >nul 2>nul
if not errorlevel 1 (
    py -3 "%ROOT%\tools\launcher.py" %*
    exit /b %errorlevel%
)
python -c "import tkinter" >nul 2>nul
if not errorlevel 1 (
    python "%ROOT%\tools\launcher.py" %*
    exit /b %errorlevel%
)
python3 -c "import tkinter" >nul 2>nul
if not errorlevel 1 (
    python3 "%ROOT%\tools\launcher.py" %*
    exit /b %errorlevel%
)

echo launcher: no Python on this machine has tkinter, so the window cannot open.
echo   Install Python 3 from https://www.python.org/downloads/ and tick
echo   "tcl/tk and IDLE" in the installer, then run this file again.
pause
exit /b 1
